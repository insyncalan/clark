"""#926, the Gantt table on the page (src/clark/page/src/gantt/components/GanttTable.jsx): select, type, Enter, Tab, paste, fill, undo, the
plain words of a refusal, View against Edit, the right-click menu, width and zoom, at 1400 and 900 px, in light and dark. Fictional data.
The rules themselves are tested in test_gantt_grid.py.

Run: python3 dev/run_tests.py test_gantt_table
The table needs no store, so it is mounted on a bare page (tests/fixtures/gantt_table_demo.jsx) with the brand and shell styles, by the same
route as test_picker_minimap.py. The keys are sent as real key events to what has focus, and paste and copy as real clipboard events.
Chrome is required: these tests fail, never skip, without it.
"""
import contextlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from _gantt_lines import LINES
from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

from test_server import Running, chrome, wait  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
DEMO = ROOT / "tests" / "fixtures" / "gantt_table_demo.jsx"
_PAGE = {}
NAMES = [x["n"] for x in LINES]


def page_html():
    if "html" not in _PAGE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "t.js"
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(DEMO), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            script = out.read_text(encoding="utf-8").replace("</script", "<\\/script")
        css = (build_page.TOKENS.read_text(encoding="utf-8") + (build_page.PAGE / "shell.css").read_text(encoding="utf-8")).replace("</style", "<\\/style")
        _PAGE["html"] = ('<!doctype html>\n<html lang="en-GB" data-theme="auto"><head><meta charset="utf-8">'
                         '<meta name="viewport" content="width=device-width, initial-scale=1"><title>t</title>'
                         f'<style>\n{css}</style></head>\n<body><div id="root"></div>\n<script>{script}</script>\n</body></html>\n')
    return _PAGE["html"]


def lit(x):
    return json.dumps(x)


class Table(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, cls.sid)

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def load(self, width=1400, scheme="light", **props):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        self.cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, self.sid)
        self.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.server.port}/"}, self.sid)
        self.assertTrue(wait(lambda: self.cdp.js("!!(window.T && window.T.mount)", self.sid)), "the test bundle ran")
        self.go(f"T.mount({lit(LINES)}, {lit(props) if props else 'null'})")

    def js(self, expr):
        return self.cdp.js(expr, self.sid)

    def val(self, expr):
        got = self.js(f"(function(){{ try {{ return JSON.stringify({expr}); }} catch (e) {{ return 'ERROR ' + e.message; }} }})()")
        self.assertIsNotNone(got, expr)
        self.assertFalse(got.startswith("ERROR"), f"{expr}: {got}")
        return json.loads(got)

    def go(self, expr):
        """Do something in the page, then give it a moment to draw."""
        self.js(f"(function(){{ {expr}; }})()")
        self.cdp.call("Runtime.evaluate", {"expression": "new Promise(r => setTimeout(r, 120))", "awaitPromise": True}, self.sid)

    def press(self, key, **mods):
        self.go(f"T.press({lit(key)}, {lit(mods)})")

    def click(self, r, c, **mods):
        self.go(f"T.click({r}, {c}, {lit(mods)})")

    def state(self):
        return self.val("T.state()")

    def names(self):
        return self.val("T.lines.map((l) => l.n)")

    def type_in(self, text):
        self.go(f"T.typeIn({lit(text)})")

    # ── select, type, Enter, Tab ──

    def test_click_selects_a_cell_and_arrows_move_it(self):
        self.load()
        self.click(2, 3)
        self.assertEqual(self.state()["act"], [2, 3])
        self.press("ArrowRight")
        self.press("ArrowDown")
        self.assertEqual(self.state()["act"], [3, 4])
        self.press("ArrowDown", shift=True)
        self.press("ArrowRight", shift=True)
        s = self.state()
        self.assertEqual((s["act"], s["sel"]), ([4, 5], 4), "Shift extends a range from the cell")
        self.press("ArrowUp", meta=True)
        self.assertEqual(self.state()["act"][0], 0, "Cmd+arrow goes to the edge")
        self.press("End")
        self.assertEqual(self.state()["act"][1], 20)
        self.press("Home")
        self.assertEqual(self.state()["act"][1], 0)
        self.press("PageDown")
        self.assertEqual(self.state()["act"][0], 6, "Page Down stops at the last line")
        self.press("End", meta=True)
        self.assertEqual(self.state()["act"], [6, 20])
        self.press("Home", meta=True)
        self.assertEqual(self.state()["act"], [0, 0])

    def test_typing_replaces_and_enter_moves_down(self):
        self.load()
        self.click(1, 1)
        self.press("Q")
        self.assertTrue(self.state()["editing"])
        self.assertEqual(self.val("document.activeElement.value"), "Q", "the first key starts the replacement")
        self.type_in("Boxed up files")
        self.press("Enter")
        self.assertEqual(self.names()[1], "Boxed up files")
        s = self.state()
        self.assertEqual((s["act"], s["editing"]), ([2, 1], False))
        self.assertEqual(self.val("T.calls[0]"), ["change", "edit", ["GNT-002"]])
        self.assertEqual(self.state()["msg"][:12], "Line changed")

    def test_f2_and_double_click_edit_and_escape_cancels(self):
        self.load()
        self.click(0, 1)
        self.press("F2")
        self.assertEqual(self.val("document.activeElement.value"), "Discovery", "F2 edits what is there")
        self.type_in("Never kept")
        self.press("Escape")
        self.assertEqual(self.names()[0], "Discovery")
        self.assertEqual(self.val("document.activeElement.className"), "gt-scroll", "focus returns to the table")
        self.go("T.mouse(T.cell(3, 1), 'dblclick')")
        self.assertTrue(self.state()["editing"])
        self.press("Escape")
        self.assertFalse(self.state()["editing"])

    def test_tab_moves_right_and_at_the_last_cell_adds_a_line(self):
        self.load()
        self.click(0, 1)
        self.press("Tab")
        self.assertEqual(self.state()["act"], [0, 2])
        self.press("Tab", shift=True)
        self.assertEqual(self.state()["act"], [0, 1])
        self.press("End", meta=True)
        self.press("Tab")
        s = self.state()
        self.assertEqual(s["rows"], 8)
        self.assertEqual((s["act"], s["editing"]), ([7, 1], True), "the new line's name is ready to type")
        self.assertEqual(self.val("T.calls.map((c) => c[0])"), ["change", "add"])
        self.assertEqual(self.val("T.lines[7].id"), "GNT-008")
        self.assertEqual(self.state()["msg"][:30], "A line was added with the next")

    def test_tab_in_the_middle_of_an_edit_saves_it_and_moves_right(self):
        self.load()
        self.click(0, 1)
        self.press("F2")
        self.type_in("Discovery, phase one")
        self.press("Tab")
        self.assertEqual(self.names()[0], "Discovery, phase one")
        self.assertEqual(self.state()["act"], [0, 2])

    def test_delete_clears_the_cells(self):
        self.load()
        self.click(0, 11, )
        self.press("ArrowDown", shift=True)
        self.press("Delete")
        self.assertEqual(self.val("T.lines.slice(0, 2).map((l) => l.o)"), ["", ""])
        self.assertEqual(self.state()["msg"], "2 cells cleared.")

    # ── copy, paste, fill, undo ──

    def test_copy_gives_tab_separated_text_and_paste_past_the_end_adds_lines(self):
        self.load()
        self.click(0, 1)
        self.press("ArrowDown", shift=True)
        self.press("ArrowRight", shift=True)
        self.assertEqual(self.val("T.copy()"), "Discovery\tPhase\nScan paper files\tTask")
        self.click(6, 1)
        self.go(f"T.paste({lit('Alpha' + chr(9) + 'Task' + chr(10) + 'Beta' + chr(9) + 'Milestone' + chr(10))})")
        self.assertEqual(self.names()[6:], ["Alpha", "Beta"])
        self.assertEqual(self.val("T.lines.slice(6).map((l) => l.t)"), ["t", "m"])
        self.assertEqual(self.val("T.lines.slice(7).map((l) => l.id)"), ["GNT-008"])
        self.assertEqual(self.state()["msg"][:12], "Pasted 4 cel")
        self.assertEqual(self.state()["rows"], 8)

    def test_paste_from_excel_with_crlf_and_one_bad_cell(self):
        self.load()
        self.click(3, 4)
        self.go(f"T.paste({lit('02-11-2026' + chr(9) + 'nonsense' + chr(13) + chr(10))})")
        self.assertEqual(self.val("T.lines[3].s"), "2026-11-02")
        self.assertEqual(self.val("T.lines[3].e"), "2027-02-26", "the refused cell is left as it was")
        s = self.state()
        self.assertIn("1 refused (", s["msg"])
        self.assertEqual(s["bad"], "ok", "some cells landed, so it is a note, not a refusal")

    def test_cmd_d_fills_down_and_cmd_r_fills_right(self):
        self.load()
        self.click(3, 11)
        self.press("ArrowDown", shift=True)
        self.press("ArrowDown", shift=True)
        self.press("d", meta=True)
        self.assertEqual(self.val("T.lines.slice(3, 6).map((l) => l.o)"), ["Sam Example"] * 3)
        self.assertEqual(self.state()["msg"][:17], "Filled down 2 cel")
        self.click(0, 11)
        self.press("ArrowRight", shift=True)
        self.press("r", meta=True)
        self.assertEqual(self.val("T.lines[0].ws"), "Ada Example")
        self.assertEqual(self.state()["msg"][:18], "Filled right 1 cel")

    def test_the_fill_handle_drags_a_value_down(self):
        self.load()
        self.click(3, 11)
        self.go("T.mouse(document.querySelector('.gt-fh'), 'mousedown'); T.mouse(T.cell(5, 11), 'mouseover'); T.mouse(document, 'mouseup')")
        self.assertEqual(self.val("T.lines.slice(3, 6).map((l) => l.o)"), ["Sam Example"] * 3)
        s = self.state()
        self.assertEqual(s["sel"], 3, "the filled cells stay selected")

    def test_many_steps_of_undo_and_redo(self):
        self.load()
        for n, name in enumerate(["One", "Two", "Three"]):
            self.click(n, 1)
            self.press("F2")
            self.type_in(name)
            self.press("Enter")
        self.assertEqual(self.names()[:3], ["One", "Two", "Three"])
        self.press("z", meta=True)
        self.assertEqual(self.names()[:3], ["One", "Two", "Records audit complete"])
        self.press("z", meta=True)
        self.press("z", meta=True)
        self.assertEqual(self.names()[:3], NAMES[:3])
        self.press("z", meta=True)
        self.assertEqual(self.names()[:3], NAMES[:3], "nothing more to undo")
        self.press("z", meta=True, shift=True)
        self.press("y", meta=True)
        self.assertEqual(self.names()[:3], ["One", "Two", "Records audit complete"])
        self.assertEqual(self.val("T.calls.slice(-1)[0][1]"), "redo")

    def test_the_undo_button_in_the_note_undoes_the_step(self):
        self.load()
        self.click(0, 1)
        self.press("Delete")
        self.assertEqual(self.names()[0], "Discovery", "a name cannot be cleared")
        self.click(0, 11)
        self.press("Delete")
        self.assertEqual(self.val("T.lines[0].o"), "")
        self.go("document.querySelector('[data-gt-undo]').click()")
        self.assertEqual(self.val("T.lines[0].o"), "Ada Example")

    # ── refusals ──

    def test_a_bad_date_is_refused_in_plain_words_and_nothing_changes(self):
        self.load()
        self.click(0, 4)
        self.press("F2")
        self.type_in("banana")
        self.press("Enter")
        s = self.state()
        self.assertEqual(s["msg"], "Use DD-MM-YYYY, for example 06-11-2026.")
        self.assertEqual(s["bad"], "bad")
        self.assertEqual(self.val("T.lines[0].s"), "2026-09-01")
        self.assertEqual(self.val("T.calls.length"), 0)
        self.assertEqual(s["act"], [0, 4], "the selection stays on the cell")

    def test_other_refusals_reach_the_person(self):
        self.load()
        cases = [(0, 5, "01-01-2026", "The end cannot be before the start."), (3, 7, "250", "Done % is a number from 0 to 100."),
                 (4, 10, "GNT-404", 'There is no line "GNT-404" to depend on.'), (2, 5, "25-10-2026", "A milestone has one date: change Start.")]
        for r, c, text, said in cases:
            self.click(r, c)
            self.press("F2")
            self.type_in(text)
            self.press("Enter")
            self.assertEqual(self.state()["msg"], said, said)
        self.click(0, 8)
        self.press("F2")
        self.assertEqual(self.state()["msg"], "Status is worked out; it cannot be typed over.")
        self.assertFalse(self.state()["editing"])

    def test_effort_and_budget_past_the_data_layers_limits_are_refused_in_its_words(self):
        self.load()
        said = "Effort and budget are numbers, zero or more."
        for c, text in ((16, "1000001"), (17, "1000000000001"), (17, "1e999"), (16, "-1")):
            self.click(0, c)
            self.press("F2")
            self.type_in(text)
            self.press("Enter")
            self.assertEqual(self.state()["msg"], said, text)
        self.assertEqual(self.val("T.calls.length"), 0, "nothing was sent")
        for c, text in ((16, "1000000"), (17, "1000000000000")):
            self.click(0, c)
            self.press("F2")
            self.type_in(text)
            self.press("Enter")
        self.assertEqual(self.val("[T.lines[0].eff, T.lines[0].cost]"), [1000000, 10 ** 12], "the limits themselves are allowed")

    # ── View against Edit ──

    def real_key(self, key, code, vk, modifiers=0):
        for kind in ("keyDown", "keyUp"):
            self.cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": key, "code": code, "windowsVirtualKeyCode": vk, "modifiers": modifiers}, self.sid)
        self.go("0")

    def test_tab_leaves_a_read_only_table_with_a_real_key_at_both_widths(self):
        """In View the Tab walk has no purpose: Tab and Shift+Tab pass on to the page, with no Esc first."""
        for width in (1400, 900):
            self.load(width=width, edit=False)
            self.go("var b = document.createElement('button'); b.id = 'after'; b.textContent = 'After'; document.querySelector('.gt').after(b);")
            self.go("document.querySelector('.gt-scroll').focus()")
            self.real_key("Tab", "Tab", 9)
            self.assertEqual(self.val("document.activeElement.id"), "after", f"{width}: Tab leaves the table")
            self.go("document.querySelector('.gt-scroll').focus()")
            self.real_key("Tab", "Tab", 9, modifiers=8)
            self.assertNotEqual(self.val("document.activeElement.className"), "gt-scroll", f"{width}: Shift+Tab leaves the table")

    def test_view_is_read_only_with_no_row_numbers_and_no_hidden_columns(self):
        self.load(edit=False)
        s = self.state()
        self.assertEqual(s["rows"], 4, "only the lines on the dashboard")
        self.assertEqual(len(s["heads"]), 15)
        for gone in ("show", "note", "cost", "eff", "bs", "be"):
            self.assertNotIn(gone, s["heads"])
        self.assertEqual(s["rowNumbers"], [])
        self.assertFalse(self.val("!!document.querySelector('.gt-rh, .gt-rh0, .gt-eye, .gt-fh, .gt-rb')"))
        self.click(1, 1)
        self.press("X")
        self.assertEqual(self.state()["msg"], "Switch to Edit to change the plan.")
        self.assertFalse(self.state()["editing"])
        self.press("Delete")
        self.go(f"T.paste('x')")
        self.assertEqual((self.names(), self.val("T.calls.length")), (NAMES, 0))
        self.assertEqual(self.val("T.copy()"), "Records audit complete", "copy still works in View")

    def test_edit_shows_every_column_and_keeps_the_original_row_numbers(self):
        self.load()
        s = self.state()
        self.assertEqual((s["rows"], len(s["heads"])), (7, 21))
        self.assertEqual(s["rowNumbers"], [str(n) for n in range(1, 8)])
        self.go("T.setProps({filter: 'phases'})")
        s = self.state()
        self.assertEqual((s["rows"], s["rowNumbers"]), (3, ["1", "4", "7"]), "hiding lines keeps the numbers of the rest")
        self.go("T.setProps({filter: 'all', edit: false})")
        self.assertEqual(self.state()["rowNumbers"], [])
        self.go("T.setProps({edit: true})")
        self.assertEqual(self.state()["rows"], 7)

    def test_the_column_eye_hides_a_column_from_the_client(self):
        self.load()
        self.assertTrue(self.val("document.querySelector('th[data-k=note]').classList.contains('gt-hid')"))
        self.assertFalse(self.val("document.querySelector('th[data-k=s]').classList.contains('gt-hid')"))
        self.assertFalse(self.val("!!document.querySelector('th[data-k=id] .gt-eye, th[data-k=n] .gt-eye')"), "ID and Line are always shown")
        self.go("document.querySelector('[data-hc=o]').click()")
        self.assertEqual(self.val("T.calls.slice(-1)[0][0]"), "hidden")
        self.assertIn("o", self.val("T.calls.slice(-1)[0][1]"))
        self.assertTrue(self.val("document.querySelector('th[data-k=o]').classList.contains('gt-hid')"))
        self.assertEqual(self.state()["msg"], "Owner: hidden from the client.")
        self.go("T.setProps({edit: false})")
        self.assertNotIn("o", self.state()["heads"], "View does not draw it")

    def test_type_start_end_and_done_have_no_eye_and_are_always_drawn(self):
        self.load()
        for k in ("t", "s", "e", "pct"):
            self.assertFalse(self.val(f"!!document.querySelector('[data-hc={k}]')"), k + " has no eye (the data layer never hides it)")
        self.go("T.setProps({edit: false, hidden: ['t', 's', 'e', 'pct', 'o']})")
        heads = self.state()["heads"]
        for k in ("t", "s", "e", "pct"):
            self.assertIn(k, heads)
        self.assertNotIn("o", heads)

    def test_only_the_columns_the_author_types_into_have_an_eye(self):
        self.load()
        got = self.val("[...document.querySelectorAll('th[data-k]')].filter((e) => e.querySelector('.gt-eye')).map((e) => e.dataset.k)")
        self.assertEqual(got, ["par", "rag", "dep", "o", "ws", "pri", "bs", "be", "eff", "cost", "del", "show", "note"])
        for k in ("id", "n", "t", "s", "e", "pct", "dur", "st"):
            self.assertFalse(self.val(f"!!document.querySelector('th[data-k={k}] .gt-eye')"), k + " has no eye")
        self.go("T.setProps({edit: false, hidden: ['dur', 'st', 'o']})")
        heads = self.state()["heads"]
        self.assertIn("dur", heads)
        self.assertIn("st", heads)
        self.assertNotIn("o", heads)

    # ── menu, width, zoom ──

    def test_right_click_menu_adds_and_deletes_lines(self):
        self.load()
        self.go("T.mouse(T.cell(3, 1), 'contextmenu', {button: 2})")
        items = self.val("[...document.querySelectorAll('.gt-menu button')].map((b) => b.textContent)")
        self.assertEqual(items, ["Add a task below", "Add a phase below", "Add a milestone below", "Copy", "Clear cells", "Delete this line"])
        self.go("[...document.querySelectorAll('.gt-menu button')][2].click()")
        self.assertEqual(self.val("T.lines[4].t"), "m")
        self.assertEqual(self.val("T.lines[4].n"), "New milestone")
        self.assertEqual(self.state()["act"], [4, 1])
        self.press("Escape")
        self.go("T.mouse(T.cell(4, 1), 'contextmenu', {button: 2})")
        self.go("[...document.querySelectorAll('.gt-menu button')].pop().click()")
        self.assertEqual(self.names(), NAMES)
        self.assertEqual(self.val("T.calls.slice(-2).map((c) => c[0])"), ["change", "delete"])
        self.assertEqual(self.state()["msg"][:12], "Line GNT-008")

    def test_right_click_on_several_rows_offers_to_delete_them(self):
        self.load()
        self.go("T.mouse(document.querySelector('th[data-row=\"1\"]'), 'mousedown')")
        self.go("T.mouse(document.querySelector('th[data-row=\"2\"]'), 'mouseover')")
        self.go("T.mouse(document, 'mouseup')")
        self.assertEqual(self.state()["sel"], 42, "two whole rows")
        self.go("T.mouse(T.cell(2, 3), 'contextmenu', {button: 2})")
        self.assertEqual(self.val("[...document.querySelectorAll('.gt-menu button')].pop().textContent"), "Delete 2 lines")
        self.go("[...document.querySelectorAll('.gt-menu button')].pop().click()")
        self.assertEqual(len(self.names()), 5)
        self.assertEqual(self.val("T.lines.every((l) => l.dep.every((d) => T.lines.some((x) => x.id === d)))"), True, "nothing waits for a deleted line")

    def test_the_fading_copy_of_the_menu_keeps_the_delete_colour_and_the_rule(self):
        """The copy of a closed menu is drawn on the body, outside [data-gt]: it looks as the live menu did (red Delete, the hr's border and the button box)."""
        self.load()
        edit_css = (ROOT / "src/clark/page/src/edit/edit.css").read_text(encoding="utf-8")
        self.js("(() => { const sh = new CSSStyleSheet(); sh.replaceSync(%s); document.adoptedStyleSheets = [sh]; })()" % lit(edit_css))
        self.cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "no-preference"}]}, self.sid)
        look = ("(() => { const m = document.querySelector('.gt-menu%s'); if (!m) return null; const d = m.querySelector('button.gt-danger'), h = m.querySelector('hr'), b = m.querySelector('button');"
                " const c = (e, ks) => ks.map((k) => getComputedStyle(e)[k]); return JSON.stringify({danger: c(d, ['color']), hr: c(h, ['borderTopWidth', 'borderTopStyle', 'borderTopColor', 'marginTop']),"
                " btn: c(b, ['display', 'paddingTop', 'paddingLeft', 'color', 'textAlign']), box: c(m, ['borderTopWidth', 'paddingTop', 'minWidth'])}); })()")
        self.go("T.mouse(T.cell(3, 1), 'contextmenu', {button: 2})")
        live = json.loads(self.js(look % ":not(.leaving)"))
        self.assertNotEqual(live["danger"], live["btn"][3:4], "the live Delete is not drawn in the plain text colour")
        self.js("(() => { window.__seen = null; new MutationObserver(() => { if (!window.__seen && document.querySelector('.gt-menu.leaving')) window.__seen = %s; })"
                ".observe(document.body, {subtree: true, childList: true}); })()" % look.replace("%s", ".leaving"))
        self.press("Escape")
        self.assertTrue(wait(lambda: self.js("!!window.__seen")), "a copy of the closed menu was drawn")
        self.assertEqual(json.loads(self.js("window.__seen")), live)

    def test_escape_in_the_menu_closes_only_the_menu(self):
        """Esc inside the context menu is the menu's: it is stopped and prevented, so a peek listening on the page keeps its card."""
        self.load()
        self.go("T.mouse(T.cell(3, 1), 'contextmenu', {button: 2})")
        self.js("(() => { window.__peekSaw = false; document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !e.defaultPrevented) window.__peekSaw = true; }); })()")
        self.go("document.querySelector('.gt-menu button').dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true}))")
        self.assertFalse(self.js("window.__peekSaw"), "the peek never saw the Esc")
        self.assertFalse(self.val("!!document.querySelector('.gt-menu:not(.leaving)')"), "the menu closed")

    def test_view_menu_offers_only_copy(self):
        self.load(edit=False)
        self.go("T.mouse(T.cell(0, 1), 'contextmenu', {button: 2})")
        self.assertEqual(self.val("[...document.querySelectorAll('.gt-menu button')].map((b) => b.textContent)"), ["Copy"])

    def test_double_click_on_a_header_edge_fits_the_column(self):
        self.load()
        before = self.val("document.querySelector('th[data-k=n]').offsetWidth")
        self.go("T.mouse(document.querySelector('th[data-k=n] .gt-cr'), 'dblclick')")
        after = self.val("document.querySelector('th[data-k=n]').offsetWidth")
        self.assertLess(after, before, "Line is wider than its longest name")

    def test_zoom_runs_from_50_to_200_percent(self):
        self.load()
        label = "document.querySelector('[data-gt-zoom-fit]').textContent"
        self.assertEqual(self.val(label), "100%")
        h0 = self.val("T.cell(0, 1).offsetHeight")
        self.go("document.querySelector('[data-gt-zoom-in]').click()")
        self.assertEqual(self.val(label), "120%")
        self.assertGreater(self.val("T.cell(0, 1).offsetHeight"), h0)
        for _ in range(8):
            self.go("document.querySelector('[data-gt-zoom-in]').click()")
        self.assertEqual(self.val(label), "200%")
        for _ in range(12):
            self.go("document.querySelector('[data-gt-zoom-out]').click()")
        self.assertEqual(self.val(label), "50%")
        self.go("document.querySelector('[data-gt-zoom-fit]').click()")
        self.assertEqual(self.val(label), "100%")

    def test_frozen_columns_stay_while_the_table_scrolls_sideways(self):
        self.load(900)
        self.go("document.querySelector('.gt-scroll').scrollLeft = 600")
        box = self.val("document.querySelector('.gt-scroll').getBoundingClientRect().left")
        line = self.val("T.cell(0, 1).getBoundingClientRect().left")
        ident = self.val("T.cell(0, 0).getBoundingClientRect().left")
        self.assertAlmostEqual(ident, box + 44, delta=2)
        self.assertAlmostEqual(line, ident + 116, delta=2)
        self.assertGreater(self.val("document.querySelector('.gt-scroll').scrollLeft"), 0)

    # ── 1400 and 900, light and dark ──

    def contrast(self, selector):
        got = self.val("""(function () {
            const el = document.querySelector(%s);
            const parse = (s) => { const n = s.match(/[\\d.]+/g).map(Number); return s.startsWith('color(') ? n.slice(-3).map((x) => x * 255) : n.slice(0, 3); };
            const lum = (c) => { const f = c.map((x) => { x /= 255; return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); }); return 0.2126 * f[0] + 0.7152 * f[1] + 0.0722 * f[2]; };
            const cs = getComputedStyle(el);
            const a = lum(parse(cs.color)), b = lum(parse(cs.backgroundColor));
            return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
        })()""" % lit(selector))
        return got

    def test_it_fits_and_reads_at_both_widths_in_light_and_dark(self):
        seen = {}
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                self.load(width, scheme)
                self.click(1, 4)
                self.press("ArrowDown", shift=True)
                where = f"{width} {scheme}"
                self.assertLessEqual(self.val("document.documentElement.scrollWidth"), width, f"no sideways scroll of the page at {where}")
                self.assertLessEqual(self.val("document.querySelector('.gt-scroll').getBoundingClientRect().right"), width, where)
                self.assertGreater(self.val("document.querySelector('.gt-scroll').scrollWidth"), self.val("document.querySelector('.gt-scroll').clientWidth"),
                                   "21 columns scroll inside the table")
                for what in ("td[data-r='0'][data-c='1']", "td[data-r='0'][data-c='0']", "thead th[data-k=n]", "td.gt-act"):
                    self.assertGreaterEqual(self.contrast(what), 4.5, f"{what} at {where}")
                seen[where] = self.val("getComputedStyle(T.cell(0, 1)).backgroundColor")
        self.assertNotEqual(seen["1400 light"], seen["1400 dark"], "dark really is dark")
        self.assertEqual(seen["1400 light"], seen["900 light"])

    def test_the_id_and_the_short_headers_are_not_cut_at_both_widths(self):
        # the real ID carries the project code ("PUB-GNT-001"); Days, Done % and Depends on read in full
        lines = [{**l, "id": "PUB-" + l["id"], "dep": ["PUB-" + d for d in l["dep"]]} for l in LINES]
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                for edit in (True, False):
                    with self.subTest(width=width, scheme=scheme, edit=edit):
                        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                        self.cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, self.sid)
                        self.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.server.port}/"}, self.sid)
                        self.assertTrue(wait(lambda: self.cdp.js("!!(window.T && window.T.mount)", self.sid)), "the test bundle ran")
                        self.go(f"T.mount({lit(lines)}, {lit({'edit': edit})})")
                        cut = self.val("[...document.querySelectorAll(\"td[data-k=id], th[data-k=id], th[data-k=dur], th[data-k=pct], th[data-k=dep]\")]"
                                       ".filter((e) => { var l = e.querySelector('.gt-hl') || e; return l.scrollWidth > l.clientWidth || l.getBoundingClientRect().right > e.getBoundingClientRect().right; })"
                                       ".map((e) => e.tagName + ':' + e.dataset.k + ':' + e.textContent + ':' + e.scrollWidth + '>' + e.clientWidth)")
                        self.assertEqual(cut, [], f"nothing cut at {width} {scheme}")
                        self.assertEqual(self.val("document.querySelector('td[data-k=id]').textContent"), "PUB-GNT-001")
                        self.assertLessEqual(self.val("document.documentElement.scrollWidth"), width, "the page does not scroll sideways")


    def test_on_dashboard_and_days_headings_are_read_in_full_in_the_scrolled_edit_table(self):
        # #995 D3 and D4: the heading text must fit between the cell's padding and the eye (when it has one), the table scrolled to its far edge
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme):
                    self.load(width=width, scheme=scheme)
                    self.go("var s = document.querySelector('.gt-scroll'); s.scrollLeft = s.scrollWidth")
                    cut = self.val("[...document.querySelectorAll('th[data-k=show], th[data-k=dur]')].map((th) => {"
                                   " var l = th.querySelector('.gt-hl'), eye = th.querySelector('.gt-eye'), r = th.getBoundingClientRect();"
                                   " var b = document.createRange(); b.selectNodeContents(l); var t = b.getBoundingClientRect();"
                                   " var room = (eye ? eye.getBoundingClientRect().left : r.right) - 1;"
                                   " return {k: th.dataset.k, text: l.textContent, over: Math.round((t.right - room) * 10) / 10, w: Math.round(r.width)}; }).filter((x) => x.over > 0.5)")
                    self.assertEqual(cut, [], f"nothing cut at {width} {scheme}")


if __name__ == "__main__":
    unittest.main()
