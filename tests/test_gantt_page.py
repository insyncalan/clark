"""#926, #928: the Gantt page (src/clark/page/src/gantt/components/GanttPage.jsx) with the chart and the table in it, at 1400 and 900 px.
It mounts the page on a bare page (tests/fixtures/gantt_page_demo.jsx) on the in-memory host (gantt/logic/ganttHost.js) with fictional lines in
the stored shape, so every change comes back as a host call that the test reads. The chart and the table have their own tests
(test_gantt_chart.py, test_gantt_table.py); this file is about what the page adds: the banner and its own editable title, the View|Edit pill and
the E and V keys, the toolbar, one list of lines for both views, the mode kept when the view changes, the saved plan height, and the two slots.

Run: python3 dev/run_tests.py test_gantt_page
The Static tests never start Chrome; the rest need it and fail, never skip, without it.
"""
import contextlib
import json
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

from test_server import Running, chrome, wait  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
GANTT_SRC = PAGE_SRC / "gantt"
DEMO = ROOT / "tests" / "fixtures" / "gantt_page_demo.jsx"
GUARDED = ["store.py", "changes.py", "publish.py", "server.py", "excel_route.py", "history.py"]
_PAGE = {}


def bundle(entry, out):
    return esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}", *build_page.preact_flags(),
                        f"--alias:@src={PAGE_SRC}", str(entry), f"--outfile={out}"], cwd=str(out.parent), capture_output=True, text=True)


def page_html():
    if "html" not in _PAGE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "t.js"
            done = bundle(DEMO, out)
            assert done.returncode == 0, done.stderr
            script = out.read_text(encoding="utf-8").replace("</script", "<\\/script")
        css = (build_page.TOKENS.read_text(encoding="utf-8") + (build_page.PAGE / "shell.css").read_text(encoding="utf-8")
               + build_page.EDIT_CSS.read_text(encoding="utf-8")).replace("</style", "<\\/style")      # the served page's styles, Edit parts included
        _PAGE["html"] = ('<!doctype html>\n<html lang="en-GB" data-theme="auto"><head><meta charset="utf-8">'
                         '<meta name="viewport" content="width=device-width, initial-scale=1"><title>t</title>'
                         f'<style>\n{css}</style></head>\n<body><div id="root"></div>\n<script>{script}</script>\n</body></html>\n')
    return _PAGE["html"]


def lit(x):
    return json.dumps(x)


class Static(unittest.TestCase):
    """No Chrome: the page compiles into a bundle, uses tokens only, keeps the wire format in one place."""

    def test_the_page_and_its_demo_compile_into_one_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            done = bundle(DEMO, Path(tmp) / "t.js")
            self.assertEqual(done.returncode, 0, done.stderr)

    def test_the_page_files_have_no_hex_colour_and_the_new_css_has_tokens_and_the_two_widths_only(self):
        for f in [GANTT_SRC / "components" / "GanttPage.jsx", GANTT_SRC / "logic" / "ganttPage.js", GANTT_SRC / "logic" / "ganttHost.js",
                  GANTT_SRC / "logic" / "ganttStoreHost.js", PAGE_SRC / "edit" / "GanttTitle.jsx"]:
            self.assertNotRegex(f.read_text(encoding="utf-8"), r"#[0-9a-fA-F]{6}\b", f"{f.name}: a colour is a token")
        css = (build_page.PAGE / "shell.css").read_text(encoding="utf-8")
        block = css[css.index("The Gantt page (rows 926 and 928)"):]
        self.assertNotRegex(block, r"#[0-9a-fA-F]{6}\b")
        self.assertNotRegex(block, r"\brgba?\(")
        self.assertLessEqual(set(re.findall(r"@media \(max-width: (\d+)px\)", block)), {"900"})

    def test_the_wire_format_is_in_the_store_host_only(self):
        page = (GANTT_SRC / "components" / "GanttPage.jsx").read_text(encoding="utf-8")
        for word in ("/api/", "fetch(", "gantt_lines", "kind:"):
            self.assertNotIn(word, page, f"the page never builds a request ({word})")
        host = (GANTT_SRC / "logic" / "ganttStoreHost.js").read_text(encoding="utf-8")
        self.assertIn('"gantt_lines"', host)

    def test_the_page_reuses_the_dashboards_banner_pill_and_keys(self):
        page = (GANTT_SRC / "components" / "GanttPage.jsx").read_text(encoding="utf-8")
        self.assertIn("<Cover ", page)
        self.assertIn("Toggle pill", page)
        self.assertIn('"gantt"', (PAGE_SRC / "edit" / "keys.js").read_text(encoding="utf-8"), "V and E work on the Gantt page")
        self.assertNotRegex(page, r"addEventListener\(\s*[\"']keydown[\"'],\s*\(?e?\)?\s*=>\s*\{?\s*if \(e\.key === [\"'][eEvV]", "no second V and E handler")

    def test_a_new_line_is_sent_after_the_line_above_it_and_the_height_is_saved_under_the_data_layers_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "probe.cjs"
            banner = "globalThis.addEventListener=()=>{};globalThis.location={hash:'',search:''};globalThis.window=globalThis;"
            done = esbuild.run(["--bundle", "--format=cjs", "--platform=node", "--target=es2020", "--tsconfig-raw={}", f"--banner:js={banner}", *build_page.preact_flags(),
                                f"--alias:@src={PAGE_SRC}", str(ROOT / "tests" / "fixtures" / "gantt_store_host_probe.js"), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            ran = subprocess.run(["node", str(out)], capture_output=True, text=True)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        sent = json.loads(ran.stdout.strip().splitlines()[-1])
        self.assertEqual([(r["op"], r["after"]) for r in sent], [("new", "PRJ-GNT-002")], "the new line goes after the line above it")
        for path in sorted((PAGE_SRC / "gantt").rglob("*.js*")):
            self.assertNotIn("gantt_plan_rows", path.read_text(encoding="utf-8"), f"{path.name}: the data layer's name is gantt_default_rows")

    def test_the_page_does_not_touch_the_guarded_files(self):
        # Only the page's own folder is compared: this branch carries the data layer, whose edits to the server files are not the page's.
        for path in sorted((PAGE_SRC / "gantt").rglob("*")) + [DEMO]:
            if path.suffix not in (".js", ".jsx"):
                continue
            text = path.read_text(encoding="utf-8")
            for name in GUARDED:
                self.assertNotRegex(text, r"import[^\n]*" + re.escape(name[:-3]) + r"\.py", f"{path.name} imports {name}")
        changed = subprocess.run(["git", "diff", "--name-only", "origin/main...HEAD", "--", "src/clark/page"], cwd=ROOT, capture_output=True, text=True).stdout.split()
        for name in GUARDED:
            self.assertFalse([c for c in changed if c.endswith("/" + name)], name)


class Page(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, cls.sid)
        cls.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{cls.server.port}/"}, cls.sid)
        assert wait(lambda: cls.cdp.js("!!(window.P && window.P.mount)", cls.sid)), "the test bundle ran"

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    # ── helpers ──────────────────────────────────────────────────────────────

    def js(self, expr):
        return self.cdp.js(expr, self.sid)

    def val(self, expr):
        got = self.js(f"(function(){{ try {{ return JSON.stringify({expr}); }} catch (e) {{ return 'ERROR ' + e.message; }} }})()")
        self.assertIsNotNone(got, expr)
        self.assertFalse(got.startswith("ERROR"), f"{expr}: {got}")
        return json.loads(got)

    def until(self, expr, what):
        self.assertTrue(wait(lambda: self.js(f"!!({expr})"), 8), what)

    def look(self, width, scheme="light"):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        self.js(f"document.documentElement.dataset.theme = {lit(scheme)}; document.body.style.margin = '0'; document.body.style.padding = '0 20px'")

    def mount(self, **opts):
        opts.setdefault("width", int(self.js("innerWidth")) - 40)
        self.js(f"P.mount({lit(opts)})")
        self.until("document.querySelector('#gantt-page')", "the page is drawn")

    def count(self, sel):
        return self.val(f"document.querySelectorAll({lit(sel)}).length")

    def text(self, sel):
        return self.js(f"(function(){{ var e = document.querySelector({lit(sel)}); return e ? e.textContent.replace(/\\s+/g, ' ').trim() : null; }})()")

    def click(self, sel):
        self.js(f"document.querySelector({lit(sel)}).click()")

    def settle(self):
        time.sleep(0.3)

    def key(self, key, target="document", **kw):
        self.js(f"{target}.dispatchEvent(new KeyboardEvent('keydown', Object.assign({{key: {lit(key)}, bubbles: true, cancelable: true}}, {lit(kw)})))")

    def mode(self):
        return self.js("document.querySelector('#gantt-page').dataset.mode")

    def calls(self):
        return self.val("P.host.calls")

    def type_title(self, text, how="blur"):
        self.js("(function(){ var t = document.querySelector('[data-g-title]'); t.focus(); t.textContent = " + lit(text) + "; })()")
        if how == "blur":
            self.js("document.querySelector('[data-g-title]').blur()")
        else:
            self.key(how, "document.querySelector('[data-g-title]')")

    # ── View ─────────────────────────────────────────────────────────────────

    def test_view_draws_the_banner_the_toolbar_the_chart_and_both_slots_at_both_widths(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                self.look(width)
                self.mount()
                self.assertEqual(self.mode(), "view")
                self.assertEqual(self.text("#cover h1"), "Demo project", "the title defaults to the project name")
                self.assertIn("Week ending 06-11-2026", self.text("#cover .cover-line"))
                self.assertIn("for Example client", self.text("#cover .cover-line"))
                self.assertEqual(self.count("#cover [contenteditable], #cover input"), 0, "View has no title box")
                self.assertEqual(self.count("[data-gantt]"), 1)
                self.assertEqual(self.count("[data-slot=above] #slot-above-box"), 1)
                self.assertEqual(self.count("[data-slot=below] #slot-below-box"), 1)
                self.assertLess(self.val("document.querySelector('[data-slot=above]').getBoundingClientRect().bottom"),
                                self.val("document.querySelector('[data-gp-plan]').getBoundingClientRect().top") + 1, "above sits over the plan")
                self.assertLess(self.val("document.querySelector('[data-gp-plan]').getBoundingClientRect().bottom"),
                                self.val("document.querySelector('[data-slot=below]').getBoundingClientRect().top") + 1, "below sits under the plan")
                self.assertLessEqual(self.val("document.documentElement.scrollWidth"), width, "no sideways scroll")

    def test_a_slot_with_nothing_in_it_is_not_drawn(self):
        self.look(1400)
        self.mount(slots=False)
        self.assertEqual(self.count("[data-slot]"), 0)

    def test_the_banner_is_the_dashboards_component_not_a_copy(self):
        self.mount()
        self.assertEqual(self.val("document.querySelector('#cover').tagName"), "HEADER")
        self.assertEqual(self.text("#cover .cover-kind"), "Weekly report")

    def test_view_shows_only_the_lines_the_client_sees_and_is_read_only(self):
        self.mount()
        self.assertEqual(self.count("[data-g-bar]"), 3, "the three lines with the eye on")
        self.assertEqual(self.count("[data-g-eye], [data-g-edit]"), 0)

    def test_a_published_file_has_no_pill_no_edit_button_and_no_title_box(self):
        self.mount(fromFile=True, mode="edit")
        self.assertEqual(self.mode(), "view")
        self.assertEqual(self.count(".modes, [data-gp-mode], [data-g-title]"), 0)
        self.assertEqual(self.count("[data-gp-export], [data-gp-import]"), 0, "a published file has no server to export from")

    # ── the pill, the Edit/View button and the keys ──────────────────────────

    def test_the_edit_button_names_the_mode_you_switch_to_and_follows_the_pill(self):
        self.look(1400)
        self.mount()
        b = "[data-gp-mode]"
        self.assertEqual(self.text(b), "Edit")
        self.assertEqual(self.js(f"document.querySelector({lit(b)}).title"), "Edit the plan")
        self.click(b)
        self.until("document.querySelector('#gantt-page').dataset.mode === 'edit'", "Edit")
        self.assertEqual(self.text(b), "View")
        self.assertEqual(self.js(f"document.querySelector({lit(b)}).title"), "Back to the view (what the client sees)")
        self.assertEqual(self.js("document.querySelector('.modes [data-mode=edit]').getAttribute('aria-pressed')"), "true", "the pill follows")
        self.click(".modes [data-mode=view]")
        self.until("document.querySelector('#gantt-page').dataset.mode === 'view'", "the pill's View")
        self.assertEqual(self.text(b), "Edit")

    def test_e_and_v_switch_the_mode_with_the_dashboards_own_keys_and_leave_a_field_alone(self):
        self.mount()
        self.key("e", "document.body")
        self.until("document.querySelector('#gantt-page').dataset.mode === 'edit'", "E")
        self.js("(function(){ var t = document.querySelector('[data-g-title]'); t.focus(); })()")
        self.key("v", "document.querySelector('[data-g-title]')")
        self.assertEqual(self.mode(), "edit", "a key typed in the title is the title's")
        self.js("document.activeElement.blur()")
        self.key("v", "document.body")
        self.until("document.querySelector('#gantt-page').dataset.mode === 'view'", "V")

    # ── the title ────────────────────────────────────────────────────────────

    def test_the_title_is_editable_in_edit_and_saves_on_click_away_enter_and_not_on_esc(self):
        self.look(1400)
        self.mount(mode="edit")
        self.assertEqual(self.count("#cover h1 [data-g-title]"), 1)
        self.assertEqual(self.text("[data-g-title]"), "Demo project")
        self.type_title("Records move, plan")
        self.until("P.settings().gantt_title === 'Records move, plan'", "click away saves")
        self.assertEqual(self.text("#cover h1"), "Records move, plan")
        self.type_title("Second title", "Enter")
        self.until("P.settings().gantt_title === 'Second title'", "Enter saves")
        n = len(self.calls())
        self.js("(function(){ var t = document.querySelector('[data-g-title]'); t.focus(); t.textContent = 'Not kept'; })()")
        self.key("Escape", "document.querySelector('[data-g-title]')")
        self.assertEqual(self.text("[data-g-title]"), "Second title", "Esc puts the old title back")
        self.assertEqual(len(self.calls()), n, "Esc saves nothing")

    def test_the_title_change_has_an_undo_toast_and_undo_puts_the_old_one_back(self):
        self.mount(mode="edit")
        self.type_title("Changed")
        self.until("document.querySelector('[data-gp-toast]')", "the toast")
        self.assertIn("Title changed.", self.text("[data-gp-toast]"))
        self.click("[data-gp-undo]")
        self.until("P.settings().gantt_title === ''", "undo")
        self.assertEqual(self.text("#cover h1"), "Demo project", "an empty title is the project name")

    def test_the_title_does_not_rename_the_project(self):
        self.mount(mode="edit")
        self.type_title("Another heading")
        self.until("P.settings().gantt_title === 'Another heading'", "saved")
        self.assertEqual(self.val("P.host.read().project.name"), "Demo project")

    def test_the_banner_looks_the_same_in_edit_and_in_view(self):
        self.look(1400)
        self.mount()
        want = self.val("(function(){ var s = getComputedStyle(document.querySelector('#cover h1')); return [s.fontSize, s.fontWeight, s.color, getComputedStyle(document.querySelector('#cover')).backgroundColor]; })()")
        self.mount(mode="edit")
        got = self.val("(function(){ var s = getComputedStyle(document.querySelector('#cover h1')); return [s.fontSize, s.fontWeight, s.color, getComputedStyle(document.querySelector('#cover')).backgroundColor]; })()")
        self.assertEqual(got, want)

    # ── the toolbar and the two views ────────────────────────────────────────

    def test_the_table_toggle_keeps_the_mode_and_the_lines(self):
        self.look(1400)
        self.mount(mode="edit")
        self.assertEqual(self.text("[data-gp-layout]"), "Table")
        self.click("[data-gp-layout]")
        self.until("document.querySelector('.gt-scroll')", "the table")
        self.assertEqual(self.mode(), "edit", "the mode is kept")
        self.assertEqual(self.text("[data-gp-layout]"), "Chart")
        self.assertEqual(self.count(".gt-scroll tbody tr"), 6, "Edit shows every line in the table")
        self.click("[data-gp-layout]")
        self.until("document.querySelector('[data-g-bar]')", "the chart")
        self.assertEqual(self.mode(), "edit")
        self.assertEqual(self.count("[data-g-row]"), 6)

    def test_the_table_reads_in_full_in_the_published_file_and_in_edit_at_both_widths(self):
        # the real ID carries the project code; the ID cell and the Days, Done % and Depends on headers are not cut
        lines = [{**l, "id": "PUB-" + l["id"], "parent": ("PUB-" + l["parent"]) if l["parent"] else "", "depends": ["PUB-" + d for d in l["depends"]]}
                 for l in self.val("P.LINES")]
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                for published in (True, False):
                    with self.subTest(width=width, scheme=scheme, published=published):
                        self.look(width, scheme)
                        self.mount(lines=lines, fromFile=published, mode="edit")
                        self.click("[data-gp-layout]")
                        self.until("document.querySelector('.gt-scroll td[data-k=id]')", "the table")
                        cut = self.val("[...document.querySelectorAll(\"td[data-k=id], th[data-k=id], th[data-k=dur], th[data-k=pct], th[data-k=dep]\")]"
                                       ".filter((e) => { var l = e.querySelector('.gt-hl') || e; return l.scrollWidth > l.clientWidth || l.getBoundingClientRect().right > e.getBoundingClientRect().right; })"
                                       ".map((e) => e.tagName + ':' + e.dataset.k + ':' + e.textContent + ':' + e.scrollWidth + '>' + e.clientWidth)")
                        self.assertEqual(cut, [])
                        self.assertTrue(self.val("document.querySelector('td[data-k=id]').textContent.startsWith('PUB-GNT-')"))
                        self.assertLessEqual(self.val("document.documentElement.scrollWidth"), width, "the page does not scroll sideways")

    def test_view_in_the_table_shows_the_same_three_lines(self):
        self.mount()
        self.click("[data-gp-layout]")
        self.until("document.querySelector('.gt-scroll')", "the table")
        self.assertEqual(self.count(".gt-scroll tbody tr"), 3)

    def test_export_and_import_run_the_editors_own_excel_flows(self):
        self.mount(mode="edit")
        self.assertEqual(self.js("document.querySelector('[data-gp-export]').disabled"), False, "Export to Excel is on (row 926)")
        self.assertEqual(self.js("document.querySelector('[data-gp-export]').title"), "Export to Excel")
        self.click("[data-gp-export]")
        self.assertEqual(self.js("window.__exports"), 1, "one press runs the editor's own workbook export once")
        self.assertEqual(self.count("[data-gp-import]"), 0, "Import is for Edit in the table")
        self.click("[data-gp-layout]")
        self.until("document.querySelector('[data-gp-import]')", "Import in the table")
        self.assertEqual(self.js("document.querySelector('[data-gp-import]').disabled"), False, "Import from Excel is on")
        self.assertEqual(self.js("document.querySelector('[data-gp-import]').title"), "Import from Excel")
        self.click("[data-gp-import]")
        self.assertEqual(self.js("window.__imports"), 1, "one press opens the editor's own import box once")

    def test_the_show_menu_filters_the_table_and_ticked_lines_is_for_edit_only(self):
        self.mount(mode="edit")
        self.click("[data-gp-layout]")
        self.click("[data-gp-show]")
        self.assertEqual(self.count("[data-gp-filter]"), 4)
        self.click("[data-gp-filter=phases]")
        self.until("document.querySelectorAll('.gt-scroll tbody tr').length === 2", "phases only")
        self.click("[data-gp-mode]")
        self.until("document.querySelector('#gantt-page').dataset.mode === 'view'", "View")
        self.click("[data-gp-show]")
        self.assertEqual(self.count("[data-gp-filter]"), 3)

    def test_the_show_menu_hands_focus_back_to_its_button_on_a_pick_and_on_esc(self):
        self.mount(mode="edit")
        self.click("[data-gp-layout]")
        self.js("document.querySelector('[data-gp-show]').focus()")
        self.click("[data-gp-show]")
        self.js("document.querySelector('[data-gp-filter=phases]').focus(); document.querySelector('[data-gp-filter=phases]').click()")
        self.until("document.querySelectorAll('.gt-scroll tbody tr').length === 2", "phases only")
        self.assertTrue(self.val("document.activeElement === document.querySelector('[data-gp-show]')"), "a pick returns to the Show button")
        self.click("[data-gp-show]")
        self.assertEqual(self.count("[data-gp-showmenu]"), 1)
        self.key("Escape", target="document.querySelector('[data-gp-show]')")
        self.until("!document.querySelector('[data-gp-showmenu]') || document.querySelector('[data-gp-show]').getAttribute('aria-expanded') === 'false'", "Esc closes the menu")
        self.assertTrue(self.val("document.activeElement === document.querySelector('[data-gp-show]')"), "Esc returns to the Show button")

    def test_deleting_a_row_in_the_table_keeps_focus_in_the_table(self):
        self.mount(mode="edit")
        self.click("[data-gp-layout]")
        self.until("document.querySelector('[data-del]')", "the table")
        n = self.count(".gt-scroll tbody tr")
        self.js("document.querySelector('[data-del=\"0\"]').focus(); document.querySelector('[data-del=\"0\"]').click()")
        self.until(f"document.querySelectorAll('.gt-scroll tbody tr').length === {n - 1}", "the row is gone")
        self.assertTrue(self.val("document.activeElement === document.querySelector('.gt-scroll')"), "focus stays on the table, not the page top")

    # ── changes go to the host ───────────────────────────────────────────────

    def test_the_eye_in_the_chart_is_sent_as_one_update_with_its_words(self):
        self.mount(mode="edit")
        self.click("[data-g-eye='GNT-002']")
        self.until("P.lines().find(function(l){ return l.id === 'GNT-002'; }).show === 1", "the eye is on")
        kind, ops, words = self.calls()[-1]
        self.assertEqual(ops, [{"op": "update", "id": "GNT-002", "changes": {"show": 1}}])
        self.assertEqual(words, "Shown on the dashboard: Scan paper files.")

    def test_adding_a_line_below_sends_a_new_line_with_the_next_free_id(self):
        self.mount(mode="edit")
        self.click("[data-g-add='GNT-002']")
        self.click("[data-g-addtype=task]")
        self.until("P.lines().length === 7", "a line was added")
        added = [o for o in self.calls()[-1][1] if o["op"] == "new"]
        self.assertEqual([o["id"] for o in added], ["GNT-007"])
        self.assertEqual(self.calls()[-1][2], "A line was added with the next free ID.")

    def test_deleting_a_phase_keeps_its_tasks_at_the_top_level(self):
        self.mount(mode="edit")
        got = self.val("P.page.without(P.lines(), ['GNT-004']).map(function(l){ return [l.id, l.parent, l.sort_order]; })")
        self.assertEqual([g for g in got if g[0] in ("GNT-005", "GNT-006")], [["GNT-005", "", 4], ["GNT-006", "", 5]])

    def test_the_chart_and_the_table_work_on_the_same_stored_lines(self):
        self.mount(mode="edit")
        self.assertEqual(self.val("P.page.fromTable(P.page.toTable(P.lines()))"), self.val("P.lines()"), "a round trip changes nothing")

    def test_a_cell_changed_in_the_table_is_sent_as_one_update_of_that_field(self):
        self.mount(mode="edit")
        before = len(self.calls())
        self.val("(function(){ var rows = P.page.toTable(P.lines()); rows[1].o = 'Ada Example'; return 1; })()")
        ops = self.val("P.page.diff(P.lines(), P.page.fromTable(P.page.toTable(P.lines()).map(function(r){ return r.id === 'GNT-002' ? Object.assign({}, r, {o: 'Ada Example'}) : r; })))")
        self.assertEqual(ops, [{"op": "update", "id": "GNT-002", "changes": {"owner": "Ada Example"}}])
        self.assertEqual(len(self.calls()), before)

    def test_a_column_eye_saves_only_hideable_columns_and_the_chart_keeps_its_dates(self):
        self.mount(mode="edit")
        self.assertEqual(self.count("[data-g-coleye]"), 0, "no eye on Start, End or Done")
        self.click("[data-gp-layout=table]")
        self.until("document.querySelector('[data-hc=o]')", "the table's column eyes")
        for k in ("t", "s", "e", "pct"):
            self.assertEqual(self.count(f"[data-hc={k}]"), 0, k + " has no eye")
        self.click("[data-hc=o]")
        self.until("P.settings().gantt_hidden_columns.indexOf('owner') >= 0", "hidden")
        never = self.val("P.settings().gantt_hidden_columns.filter(k => ['type', 'start', 'end', 'pct'].indexOf(k) >= 0)")
        self.assertEqual(never, [], "type, start, end and pct are never in what is saved")
        self.assertEqual(self.calls()[-1][2], "Hidden columns changed.")
        self.click("[data-gp-layout=chart]")
        self.click("[data-gp-mode]")
        self.until("document.querySelector('#gantt-page').dataset.mode === 'view'", "View")
        self.assertEqual(self.count("[data-g-rz=end]"), 1, "the dates stay in the client view")

    def test_the_plan_height_grip_saves_the_default_in_edit_and_not_in_view(self):
        self.look(1400)
        self.mount(mode="edit")
        self.js("(function(){ var g = document.querySelector('[data-g-grip]'); g.focus(); })()")
        self.key("ArrowUp", "document.querySelector('[data-g-grip]')")
        self.until("P.settings().gantt_default_rows !== null", "the height is saved")
        self.assertRegex(self.calls()[-1][2], r"^Plan height saved: \d+ of 6 rows\. Viewers can still change their own\.$")
        self.click("[data-gp-mode]")
        self.until("document.querySelector('#gantt-page').dataset.mode === 'view'", "View")
        n = len(self.calls())
        self.js("(function(){ var g = document.querySelector('[data-g-grip]'); g.focus(); })()")
        self.key("ArrowDown", "document.querySelector('[data-g-grip]')")
        self.assertEqual(len(self.calls()), n, "a viewer's own height is not saved")

    def test_clicking_outside_the_chart_lets_go_of_the_selected_line(self):
        self.mount()
        self.click("[data-g-bar='GNT-001']")
        self.until("document.querySelector('[data-g-bar].sel')", "selected")
        self.settle()      # the page hooks its click-away listener a moment after it draws the selection
        self.js("document.querySelector('#cover').dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}))")
        self.until("!document.querySelector('[data-g-bar].sel')", "let go")

    def test_cmd_z_undoes_the_last_change_in_edit(self):
        self.mount(mode="edit")
        self.click("[data-g-eye='GNT-002']")
        self.until("P.lines().find(function(l){ return l.id === 'GNT-002'; }).show === 1", "on")
        self.key("z", "document.body", metaKey=True)
        self.until("P.lines().find(function(l){ return l.id === 'GNT-002'; }).show === 0", "undone")

    def test_edit_at_both_widths_and_in_both_schemes_has_no_sideways_scroll(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme):
                    self.look(width, scheme)
                    self.mount(mode="edit")
                    self.assertLessEqual(self.val("document.documentElement.scrollWidth"), width)


if __name__ == "__main__":
    unittest.main()
