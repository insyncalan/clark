"""Row 962 (motion): the pickers and menus of Edit fade out as they close (rows 1 to 11 of the by-eye list; the Add a section dialog is not in this row).
Run: python3 dev/run_tests.py test_motion_menu_exit_edit

Each one is taken off the page the moment its owner stops drawing it, so a copy is drawn where it was (class leaving, no id, role=presentation, inert,
aria-hidden) which runs m-out over --dur-instant (0.12 s, opacity only) and is removed when the animation ends. The copy is never drawn under reduced
motion. The test sets the motion state itself (Emulation.setEmulatedMedia, "no-preference" and "reduce"), so a runner that reports reduced motion changes
nothing, and it waits for document.getAnimations().length === 0 before it ends. The pins on the CSS and the code are at the end.

  1 cell pickers (Pop)           live        2 filter suggestions        live        3 column filter box         live (Use cases Status; the Work items one is the published file's)
  4 row menu and its fly-out     live        5 Move to (Board)           live        6 tile outline colour menu  live (Glance)
  7 client menu                  live (Client)               8 section options (Gutter)  live        9 Gantt Add menu           live (chart)
 10 template settings            live        11 date and decision boxes on the Board, both live
"""
import json
import re
import unittest

from _paths import ROOT

import test_gantt_chart as gc  # noqa: E402
import test_glance_page as gl  # noqa: E402
import test_row_menu as rm  # noqa: E402
import test_tracker_page as tp  # noqa: E402
import test_bulk_bar as bb  # noqa: E402
import test_use_cases_list as ucl  # noqa: E402
from test_row_menu import key  # noqa: E402
from test_server import chrome, wait  # noqa: E402
from test_work_filters import arm, click  # noqa: E402

SRC = ROOT / "src/clark/page/src"
read = lambda p: (SRC / p).read_text(encoding="utf-8")   # noqa: E731
MENU_JSX, FADE_JS, POP_JSX, EDIT_CSS = read("components/Menu.jsx"), read("edit/fadeCopy.js"), read("edit/cells/Pop.jsx"), read("edit/edit.css")
SHELL_CSS = (ROOT / "src/clark/page/shell.css").read_text(encoding="utf-8")

WATCH = """(() => { window.__saw = null; new MutationObserver(() => { const m = document.querySelector('SEL'); if (!m || window.__saw) return;
  const s = getComputedStyle(m), r = m.getBoundingClientRect(), e = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
  window.__saw = JSON.stringify({name: s.animationName, dur: s.animationDuration, inert: m.inert, hidden: m.getAttribute('aria-hidden'), role: m.getAttribute('role'),
    id: m.id || '', ids: m.querySelectorAll('[id]').length, hit: !!(e && e.closest('.leaving')), kids: m.querySelectorAll('button, li, label, input, p').length}); })
  .observe(document.body, {subtree: true, childList: true, attributes: true}); return true; })()"""


class Drive:
    """The two things a rig gives: js(expr) and until(expr, what)."""

    def __init__(self, test, js, until):
        self.t, self.js, self.until = test, js, until

    def fades(self, motion, close, sel):
        """`close()` closes the open picker or menu; `sel` names its copy (e.g. ".ddmenu.leaving"), so no other leaving thing (the peek) is mistaken for it.
        Motion on: a copy leaves (checked as it appears); reduced: no copy is ever drawn."""
        self.until("document.getAnimations().length === 0", "the opening has settled")
        self.js(WATCH.replace("SEL", sel))
        close()
        if motion == "no-preference":
            try:
                self.until("!!window.__saw", "a copy of the closed box was drawn")
            except AssertionError as e:
                raise AssertionError("%s; page: %s" % (e, self.js("JSON.stringify({reduce: matchMedia('(prefers-reduced-motion: reduce)').matches, dm: document.documentElement.dataset.motion || '', still_open: [...document.querySelectorAll(%s)].length, leaving: [...document.querySelectorAll('.leaving')].map(e => e.className)})" % json.dumps(sel.replace(".leaving", ":not(.leaving)")))))
            got = json.loads(self.js("window.__saw"))
            self.t.assertEqual((got["name"], got["dur"], got["inert"], got["hidden"], got["role"], got["id"], got["ids"], got["hit"]),
                               ("m-out", "0.12s", True, "true", "presentation", "", 0, False), got)
            self.t.assertGreater(got["kids"], 0, "the copy shows what the box showed")
            self.until("!document.querySelector(%s)" % json.dumps(sel), "the copy is removed after the fade")
        else:
            self.until("document.getAnimations().length === 0", "nothing is animating")
            self.t.assertIsNone(self.js("window.__saw"), "reduced motion: no copy was ever drawn")
            self.t.assertFalse(self.js("!!document.querySelector(%s)" % json.dumps(sel)))
        self.until("document.getAnimations().length === 0", "no animation is left running")


ESC = "(sel => { const b = document.querySelector(sel); b.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true})); })(%s)"


def esc_on(js, sel):
    """Esc pressed inside the box (the box's own handler), so the test does not depend on where the focus has got to."""
    return lambda: js(ESC % json.dumps(sel))


def motion_of(cdp, sid, value, scheme="light"):
    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": value}, {"name": "prefers-color-scheme", "value": scheme}]}, sid)


class Live(rm.Menu):
    def drive(self, cdp, sid):
        return Drive(self, lambda e: cdp.js(e, sid), lambda e, what: self.until(cdp, sid, e, what))

    # ---- 1 the cell pickers (Pop), 900 and 1400, light and dark ----
    def test_row_962_1_a_cell_picker_fades_out(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                for motion in ("no-preference", "reduce"):
                    with self.subTest(width=width, scheme=scheme, motion=motion), chrome() as cdp:
                        sid = self.visit(cdp, width=width)
                        motion_of(cdp, sid, motion, scheme)
                        d = self.drive(cdp, sid)
                        for cell in ("status", "priority", "owner", "due"):
                            d.until(f"!!document.querySelector(\"tr[data-id='{self.id_of('Order the laptops')}'] [data-cell$=':{cell}']\")", "the cell")
                            click(cdp, sid, f"tr[data-id='{self.id_of('Order the laptops')}'] [data-cell$=':{cell}']")
                            d.until("!!document.querySelector('.cpop:not(.leaving)')", "the picker opened")
                            d.fades(motion, lambda: key(cdp, sid, "Escape"), ".cpop.leaving")
                            d.until("document.querySelector('.cpop:not(.leaving)') === null", "closed")

    # ---- 2 the filter suggestions ----
    def test_row_962_2_the_filter_suggestions_fade_out(self):
        for motion in ("no-preference", "reduce"):
            with self.subTest(motion=motion), chrome() as cdp:
                sid = self.visit(cdp)
                motion_of(cdp, sid, motion)
                d = self.drive(cdp, sid)
                click(cdp, sid, "#fline-input")
                cdp.js("document.querySelector('#fline-input').select()", sid)
                arm(cdp, sid)                                           # row 931: the list follows Space
                cdp.call("Input.insertText", {"text": "s"}, sid)
                d.until("!!document.querySelector('#fline-list')", "the list")
                d.fades(motion, lambda: key(cdp, sid, "Escape"), ".flist.leaving")
                d.until("!document.querySelector('#fline-list')", "closed")

    # ---- 4 the row menu and its fly-out ----
    def test_row_962_4_the_row_menu_and_its_fly_out_fade_out(self):
        for width in (1400, 900):
            for motion in ("no-preference", "reduce"):
                with self.subTest(width=width, motion=motion), chrome() as cdp:
                    sid = self.visit(cdp, width=width)
                    motion_of(cdp, sid, motion)
                    d = self.drive(cdp, sid)
                    self.open_menu(cdp, sid, self.TABLE % self.id_of("Order the laptops"))
                    key(cdp, sid, "ArrowDown")
                    key(cdp, sid, "ArrowDown")
                    key(cdp, sid, "ArrowRight")                                 # Change status: its list opens, focus in it
                    d.until("!!document.querySelector('.rowmenu .rm-fly')", "the fly-out")
                    d.fades(motion, lambda: key(cdp, sid, "Escape"), ".ddmenu.rm-fly.leaving")
                    d.until("!document.querySelector('.rm-fly:not(.leaving)') && !!document.querySelector('.rowmenu [role=menu]')", "only the fly-out closed")
                    d.fades(motion, lambda: key(cdp, sid, "Escape"), ".rowmenu .ddmenu.rm.leaving")
                    self.shut(cdp, sid)

    # ---- 5 Move to on the Board, 11 the date box ----
    def test_row_962_5_the_move_to_menu_fades_out(self):
        for motion in ("no-preference", "reduce"):
            with self.subTest(motion=motion), chrome() as cdp:
                sid = self.visit(cdp)
                self.board(cdp, sid)
                motion_of(cdp, sid, motion)
                d = self.drive(cdp, sid)
                d.until("!!document.querySelector('.bc-move')", "a card")
                cdp.js("document.querySelector('.bc-move').click()", sid)
                d.until("!!document.querySelector('.ddmenu')", "Move to")
                d.fades(motion, lambda: key(cdp, sid, "Escape"), ".ddmenu.leaving")
                d.until("!document.querySelector('.ddmenu:not(.leaving)')", "closed")

    def test_row_962_11_the_date_box_on_the_board_fades_out(self):
        for motion in ("no-preference", "reduce"):
            with self.subTest(motion=motion), chrome() as cdp:
                sid = self.visit(cdp)
                self.board(cdp, sid, "due")
                motion_of(cdp, sid, motion)
                d = self.drive(cdp, sid)
                self.drag(cdp, sid, self.id_of("Order the laptops"), self.cell("this_week"))
                d.until("!!document.querySelector('.dpick')", "the date box")
                d.fades(motion, esc_on(lambda e: cdp.js(e, sid), ".dpick"), ".dpick.leaving")
                d.until("!document.querySelector('.dpick:not(.leaving)')", "closed")


    def test_row_962_1_the_rating_picker_fades_out(self):
        for motion in ("no-preference", "reduce"):
            with self.subTest(motion=motion), chrome() as cdp:
                sid = self.visit(cdp)
                motion_of(cdp, sid, motion)
                d = self.drive(cdp, sid)
                click(cdp, sid, "[data-type=risk]")
                d.until("!!document.querySelector(\"#work-list tr[data-kind='risk'] [data-cell$=':priority']\")", "a risk row's priority cell")
                click(cdp, sid, "#work-list tr[data-kind='risk'] [data-cell$=':priority']")
                d.until("!!document.querySelector('.cpop.rpick')", "the rating picker opened")
                d.fades(motion, lambda: key(cdp, sid, "Escape"), ".cpop.rpick.leaving")

    def test_row_962_11_the_decision_box_on_the_board_fades_out(self):
        for motion in ("no-preference", "reduce"):
            with self.subTest(motion=motion), chrome() as cdp:
                sid = self.visit(cdp)
                self.board(cdp, sid, "status")
                motion_of(cdp, sid, motion)
                d = self.drive(cdp, sid)
                self.drag(cdp, sid, self.id_of("Use the new tool"), self.cell("Made"))
                d.until("!!document.querySelector('[data-yes]')", "the decision box")
                d.fades(motion, lambda: cdp.js("document.querySelector('.dpick [data-cancel]').click()", sid), ".dpick.leaving")
                d.until("!document.querySelector('.dpick:not(.leaving)')", "closed")

    # ---- 8 a section's options ----
    def test_row_962_8_a_sections_options_fade_out(self):
        for motion in ("no-preference", "reduce"):
            with self.subTest(motion=motion), chrome() as cdp:
                sid = self.visit(cdp)
                cdp.js("document.querySelector('[data-view=dashboard]').click()", sid)
                self.until(cdp, sid, "!!document.querySelector('.secs > .sec')", "the report drew")
                cdp.js("if (document.querySelector('[data-mode=edit]').getAttribute('aria-pressed') !== 'true') document.querySelector('[data-mode=edit]').click()", sid)
                self.until(cdp, sid, "!!document.querySelector('.secs > .sec [data-options]')", "the report")
                motion_of(cdp, sid, motion)
                d = self.drive(cdp, sid)
                cdp.js("document.querySelector('.secs > .sec [data-options]').click()", sid)
                d.until("!!document.querySelector('.secs .menu')", "options")
                d.fades(motion, lambda: cdp.js("document.querySelector('.secs > .sec [data-options]').click()", sid), ".menu.leaving")
                d.until("!document.querySelector('.secs .menu')", "closed")


class Tile(gl.Setup):
    def test_row_962_6_the_tile_colour_menu_fades_out(self):
        for motion in ("no-preference", "reduce"):
            with self.subTest(motion=motion), chrome() as cdp:
                p = self.show(cdp)
                p.edit()
                motion_of(cdp, p.sid, motion)
                d = Drive(self, p.js, lambda e, what: p.until(e, what))
                p.js("document.querySelector('[data-tile=overdue]').dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true}))")
                d.until("!!document.querySelector('.tilemenu')", "the colour menu")
                d.fades(motion, lambda: key(cdp, p.sid, "Escape"), ".ddmenu.tilemenu.leaving")
                d.until("!document.querySelector('.tilemenu:not(.leaving)')", "closed")


class Settings(tp.Page):
    def test_row_962_10_the_template_settings_fade_out(self):
        ref = self.make(tp.BODY)
        for motion in ("no-preference", "reduce"):
            with self.subTest(motion=motion), chrome() as cdp:
                p = self.visit(cdp)
                p.edit()
                motion_of(cdp, p.sid, motion)
                d = Drive(self, p.js, lambda e, what: p.until(e, what))
                self.click(p, ref, "[data-template-settings]")
                d.until("!!document.querySelector('[data-template-settings-box]')", "the popover")
                d.fades(motion, esc_on(p.js, "[data-template-settings-box]"), ".tset.leaving")
                d.until("!document.querySelector('[data-template-settings-box]')", "closed")


class AddMenu(gc.Chart):
    def close_with_escape(self):
        """The chart listens for Esc on the document and re-listens after each state change, so a key sent in that gap is lost: send it again until the menu is gone."""
        for _ in range(20):
            self.js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true}))")
            if wait(lambda: not self.js("!!document.querySelector('[data-g-addmenu]:not(.leaving)')"), 0.5):
                return

    def test_row_962_9_the_gantt_add_menu_fades_out(self):
        for motion in ("no-preference", "reduce"):
            with self.subTest(motion=motion):
                self.look(1400, "light")
                self.mount(edit=True)
                inj = self.js("(() => { try { const sh = new CSSStyleSheet(); sh.replaceSync(%s); document.adoptedStyleSheets = [...document.adoptedStyleSheets, sh]; return 'ok ' + sh.cssRules.length; } catch (e) { return 'ERROR ' + e.message; } })()" % json.dumps(EDIT_CSS))   # (the chart's bare page has the shell's CSS only; the Edit part's rules are added as the real page has them)
                self.motion(motion)
                self.until("matchMedia('(prefers-reduced-motion: reduce)').matches === %s" % ("true" if motion == "reduce" else "false"), "the page reports the motion state set")
                self.assertTrue(self.js("[...document.styleSheets, ...document.adoptedStyleSheets].some(s => [...s.cssRules].some(r => r.cssText.includes('.gt-menu') && r.cssText.includes('.leaving') && r.cssText.includes('m-out')))"), "the Edit part's rule is in the page: %s " % inj + self.js("JSON.stringify([...document.styleSheets].map(s => [s.ownerNode.id, s.ownerNode.tagName, s.ownerNode.parentNode.tagName, s.cssRules.length, [...s.cssRules].filter(r => r.cssText.includes('leaving')).map(r => r.cssText.slice(0, 150))]))"))
                d = Drive(self, self.js, self.until)
                self.js("document.querySelector('[data-g-add=GNT-004]').click()")
                d.until("document.querySelector('[data-g-addmenu]')", "the menu")
                d.fades(motion, lambda: self.close_with_escape(), ".gt-menu.leaving")
                d.until("!document.querySelector('[data-g-addmenu]')", "closed")


class Bulk(bb.Page):
    def test_row_962_1_the_bulk_menu_fades_out(self):
        for motion in ("no-preference", "reduce"):
            with self.subTest(motion=motion), chrome() as cdp:
                sid = self.load(cdp)
                motion_of(cdp, sid, motion)
                d = Drive(self, lambda e: cdp.js(e, sid), lambda e, what: self.until(cdp, sid, e, what))
                rows = [r for r in cdp.js(self.ROWS, sid) if self.field(r, "status") != "Closed"]
                self.pick(cdp, sid, rows[:2])
                self.right_click(cdp, sid, self.rsel(rows[1]))
                self.menu_items(cdp, sid)
                d.fades(motion, lambda: key(cdp, sid, "Escape"), ".cpop.bmenu.leaving")


    def test_row_962_a_key_pressed_while_a_picker_fades_still_opens_the_next(self):
        sid = None
        with chrome() as cdp:
            sid = self.load(cdp)
            motion_of(cdp, sid, "no-preference")
            rows = [r for r in cdp.js(self.ROWS, sid) if self.field(r, "status") != "Closed"]
            self.focus(cdp, sid, rows[0])
            bb.letter(cdp, sid, "s")
            self.until(cdp, sid, "!!document.querySelector('.cpop [data-value=Delayed]')", "S opens the status menu")
            cdp.js("window.__held = 0; new MutationObserver(() => { if (document.querySelector('.cpop.leaving')) window.__held++; }).observe(document.body, {subtree: true, childList: true})", sid)
            bb.press(cdp, sid, "Escape")
            self.focus(cdp, sid, rows[0])
            bb.letter(cdp, sid, "t")
            self.until(cdp, sid, "!!document.querySelector('.cpop.cdate:not(.leaving)')", "T opens the date picker although the status menu is still fading")
            self.assertGreater(cdp.js("window.__held", sid), 0, "the status menu was fading when T was pressed")


class UseCasesStatus(ucl.Setup):
    """Row 3, as row 1085 left it: the Status column filter box (.fbox) went with the Use cases page's switch (the Status choice is the filter line's
    status: field); the page's one menu, Group by, fades out as every menu does (.ddmenu.leaving). The .fbox rule stays pinned below for the published file's older bar."""

    def test_row_962_3_the_use_cases_group_by_menu_fades_out(self):
        for motion in ("no-preference", "reduce"):
            with self.subTest(motion=motion), chrome() as cdp:
                p = self.show(cdp, edit=True)
                motion_of(cdp, p.sid, motion)
                d = Drive(self, p.js, lambda e, what: p.until(e, what))
                self.assertEqual(p.js("document.querySelectorAll('#ucl-status, .ucl-pop').length"), 0, "no Status popup on the page any more")
                p.js("document.querySelector('#ucl-group').click()")
                d.until("!!document.querySelector('.ddmenu [role=menuitemradio]')", "the Group by menu")
                d.fades(motion, esc_on(p.js, ".ddmenu"), ".ddmenu.leaving")
                d.until("!document.querySelector('.ddmenu:not(.leaving)')", "closed")


class Pins(unittest.TestCase):
    def test_row_962_the_css_is_edit_only_in_a_no_preference_block_with_tokens_only(self):
        gate = r'@media \(prefers-reduced-motion: no-preference\) \{\s*:root:not\(\[data-motion="reduce"\]\) '
        rule = r"\{ pointer-events: none; animation: m-out var\(--dur-instant\) var\(--ease-exit\) forwards; \}"
        for sel in (r"\.cpop\.leaving", r"\.menu\.leaving", r":is\(\.flist, \.fbox, \.gt-menu, \.tset, \.dpick\)\.leaving"):
            self.assertRegex(EDIT_CSS, gate + sel + " " + rule)
        self.assertNotRegex(SHELL_CSS, r"\.(cpop|menu|flist|fbox|gt-menu|tset|dpick)\.leaving")     # the published page carries none of it

    def test_row_962_the_copy_is_inert_hidden_idless_timed_out_and_never_drawn_when_motion_is_off(self):
        self.assertRegex(FADE_JS, r"setTimeout\(\(\) => done\(\), 400\)")
        self.assertRegex(FADE_JS, r'copy\.setAttribute\("role", "presentation"\); copy\.setAttribute\("aria-hidden", "true"\); copy\.setAttribute\("inert", ""\)')
        self.assertRegex(FADE_JS, r'n\.removeAttribute\("id"\)')
        self.assertRegex(FADE_JS, r"stillMotion\(\)\) return;")
        self.assertRegex(FADE_JS, r'animationName === "none"\) \{ done\(\); return; \}')       # a page whose stylesheet has no fade (the published one) leaves nothing standing
        self.assertRegex(POP_JSX, r"setTimeout\(gone, 400\)")
        self.assertRegex(POP_JSX, r'setAttribute\("inert", ""\)')
        self.assertRegex(POP_JSX, r'setAttribute\("aria-hidden", "true"\)')
        self.assertRegex(POP_JSX, r'setAttribute\("role", "presentation"\)')
        self.assertRegex(POP_JSX, r"stillMotion\(\)")

    def test_row_962_the_published_page_carries_none_of_the_fade_copy_and_the_client_menu_is_not_faded(self):
        view = (ROOT / "src/clark/page/page-view.html").read_text(encoding="utf-8")
        for word in ("data-edit-only", "cloneNode", "fadeCopy"):
            self.assertNotIn(word, MENU_JSX, "the shared Menu.jsx holds no copy code: " + word)
        self.assertNotIn("data-edit-only", view, "the published page names no edit-only attribute")
        self.assertNotRegex(read("components/ClientMenu.jsx"), r"\bfade\b", "the client menu is the published file's own: it is not faded")
        self.assertIn("fx.copy = fadeCopy", FADE_JS)

    def test_row_962_the_open_layer_lists_skip_a_fading_copy(self):
        for path, names in (("components/pick.js", (".ddmenu", ".dpick", ".fbox", ".cpop")), ("edit/Bulk.jsx", (".cpop", ".ddmenu", ".dpick", ".fbox")),
                            ("edit/HandOver.jsx", (".cpop", ".ddmenu", ".dpick", ".fbox")), ("edit/Board.jsx", (".ddmenu", ".dpick", ".fbox"))):
            text = read(path)
            for n in names:
                self.assertIn(n + ":not(.leaving)", text, f"{path}: {n} in the list of open layers ignores a copy that is fading")

    def test_row_962_every_one_of_the_eleven_is_wired_to_the_fade(self):
        wired = {"components/FilterLine.jsx": r'<Fade tag="ul" class="flist"', "edit/UseCasesPage.jsx": r'<Fade boxRef=\{box\} class="fbox ucl-pop"', "edit/RowMenu.jsx": r'useFadeOut\(box, true, "rowmenu"\)',
                 "edit/Board.jsx": r"fade ", "edit/GlanceEdit.jsx": r'cls="left tilemenu" fade ',
                 "edit/Gutter.jsx": r'useFadeOut\(boxRef, true, ""\)', "gantt/components/GanttChart.jsx": r'<Fade class="gt-menu"',
                 "edit/TemplateSettings.jsx": r'<Fade class="tset"', "edit/cells/Pop.jsx": r"fadeOut\(box\.current\)"}
        for path, pattern in wired.items():
            self.assertRegex(read(path), pattern, path)
        self.assertEqual(len(re.findall(r"useFadeOut\(root, true", read("edit/Board.jsx"))), 2, "the date box and the decision box")
        self.assertIn("<Pop ", read("edit/Bulk.jsx"), "the bulk menu is a Pop")


del rm, gc, gl, ucl   # (the imported modules' own tests belong to their files)
for _cls in (Live, Tile, Settings, AddMenu, Bulk, UseCasesStatus):
    for _n in [n for n in dir(_cls) if n.startswith("test_") and "row_962" not in n]:
        setattr(_cls, _n, None)

if __name__ == "__main__":
    unittest.main()
