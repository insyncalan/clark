"""Row 1026 (motion): four more menus fade out as they close, like the others of row 962: the Gantt Show menu (.gt-pop, the page's table layout), the Gantt table's
right-click menu (.gt-menu), the slash Insert list of the text editor (.rt-slash). The Work items filter box (.fbox) is the published file's own and that file carries
no fade code, so it is not in this row. Run: python3 dev/run_tests.py test_motion_menu_exit_four

Each is drawn again as a copy when its owner stops drawing it (class leaving, inert, aria-hidden, role=presentation) which runs m-out over 0.12 s, opacity only, and
is removed when the animation ends; under reduced motion no copy is ever drawn. The bare pages have the shell's CSS only, so the Edit part's rules are added as
the real page has them. Widths 1400 and 900.
"""
import json
import unittest

import _rich_page as rp
from test_gantt_page import Page as GanttPage
from test_gantt_table import Table as GanttTable
from _paths import ROOT
from test_motion_menu_exit_edit import Drive
from test_server import chrome, wait

EDIT_CSS = (ROOT / "src/clark/page/src/edit/edit.css").read_text(encoding="utf-8")
ADD = "(() => { const sh = new CSSStyleSheet(); sh.replaceSync(%s); document.adoptedStyleSheets = [...document.adoptedStyleSheets, sh]; return true; })()" % json.dumps(EDIT_CSS)
MOTIONS = ("no-preference", "reduce")


def emulate(cdp, sid, motion):
    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": motion}]}, sid)


class Show(GanttPage):
    def test_row_1026_1_the_gantt_show_menu_fades_out(self):
        for width in (1400, 900):
            for motion in MOTIONS:
                with self.subTest(width=width, motion=motion):
                    self.look(width)
                    self.mount(mode="edit")
                    self.js(ADD)
                    emulate(self.cdp, self.sid, motion)
                    self.click("[data-gp-layout]")
                    self.until("document.querySelector('[data-gp-show]')", "the Show button")
                    self.click("[data-gp-show]")
                    self.until("document.querySelector('[data-gp-showmenu]')", "the menu")
                    Drive(self, self.js, self.until).fades(motion, lambda: self.click("[data-gp-show]"), ".gt-pop.leaving")
                    self.until("!document.querySelector('[data-gp-showmenu]')", "closed")


class Context(GanttTable):
    def test_row_1026_2_the_gantt_table_right_click_menu_fades_out(self):
        for width in (1400, 900):
            for motion in MOTIONS:
                with self.subTest(width=width, motion=motion):
                    self.load(width)
                    self.js(ADD)
                    emulate(self.cdp, self.sid, motion)
                    self.go("T.mouse(T.cell(3, 1), 'contextmenu', {button: 2})")
                    d = Drive(self, self.js, lambda e, what: self.assertTrue(wait(lambda: self.js(f"!!({e})"), 8), what))
                    d.until("document.querySelector('.gt-menu:not(.leaving)')", "the menu")
                    d.fades(motion, lambda: self.js("document.querySelector('.gt-menu').dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true}))"), ".gt-menu.leaving")
                    d.until("!document.querySelector('.gt-menu')", "closed")


class Slash(unittest.TestCase):
    def test_row_1026_3_the_slash_insert_list_fades_out(self):
        for motion in MOTIONS:
            with self.subTest(motion=motion), rp.Harness(chrome) as h:
                h.ev(ADD)
                emulate(h.cdp, h.sid, motion)
                h.mount("")
                h.type("/")
                self.assertTrue(h.until("!!document.querySelector('.rt-slash:not(.leaving)')"), "the list")
                Drive(self, h.ev, lambda e, what: self.assertTrue(h.until(e, 8), what)).fades(motion, lambda: h.key("Escape", 0, "Escape", 27), ".rt-slash.leaving")
                self.assertTrue(h.until("!document.querySelector('.rt-slash')"))
                self.assertEqual(h.ev("window.ended"), 0, "Esc closed the list, not the field")


class Pins(unittest.TestCase):
    def test_row_1026_each_menu_is_wired_to_the_fade_and_the_css_names_it(self):
        src = ROOT / "src/clark/page/src"
        for path, mark in (("gantt/components/GanttPage.jsx", '<Fade class="gt-pop"'), ("gantt/components/GanttTable.jsx", '<Fade class="gt-menu"'), ("edit/RichText.jsx", '<Fade class="rt-slash"')):
            self.assertIn(mark, (src / path).read_text(encoding="utf-8"), path)
        css = (src / "edit/edit.css").read_text(encoding="utf-8")
        self.assertIn(".gt-menu, .gt-pop, .rt-slash,", css)
        self.assertNotIn(".rt-slash.leaving", (ROOT / "src/clark/page/shell.css").read_text(encoding="utf-8"), "the published page carries none of it")


for _cls in (Show, Context):
    for _n in [n for n in dir(_cls) if n.startswith("test_") and "row_1026" not in n]:
        setattr(_cls, _n, None)
del GanttPage, GanttTable

if __name__ == "__main__":
    unittest.main()
