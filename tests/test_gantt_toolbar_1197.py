"""Row 1197: the Gantt toolbar as the approved mock-up draws it, in the Classic theme (computed style at 1400 and 900, light and dark).

Run: python3 dev/run_tests.py test_gantt_toolbar_1197
Measured in the approved mock-up (gt-bar, gt-ib, gt-zf, gt-sep): gap 6px, margin 4px 0 10px, icon buttons 34x34 (the two-button groups 36 wide),
divider 1x22 with 6px each side, one divider between the zoom-in and the filter. Classic only; shell.css and edit.css are untouched.
"""
import re
import unittest
from unittest import mock

from _paths import ROOT

import test_gantt_page as GP  # noqa: E402
from clark import theme  # noqa: E402
from test_server import chrome  # noqa: E402,F401  (the runner tells a browser file by this import)

NAME = "prototype-2.0"
RULES = ((ROOT / "src" / "clark" / "themes" / NAME / "rules.css").read_text(encoding="utf-8") + (ROOT / "src" / "clark" / "themes" / NAME / "rules-2.css").read_text(encoding="utf-8"))


PLAIN = GP.page_html


def setUpModule():
    css = theme.css(NAME)
    orig = GP.page_html
    p = mock.patch.object(GP, "page_html", lambda: (lambda h: h.replace("</head>", f'<style id="theme">{css}</style></head>', 1))(orig()))
    p.start()
    unittest.addModuleCleanup(p.stop)


class Static(unittest.TestCase):
    def test_the_rules_are_in_rules_css_before_row_1314_and_nowhere_else(self):
        self.assertLess(RULES.index("Row 1197"), RULES.index("Row 1314"))
        for f in (GP.PAGE_SRC.parent / "shell.css", GP.PAGE_SRC / "edit" / "edit.css"):
            self.assertNotIn("Row 1197: the Gantt toolbar", f.read_text(encoding="utf-8"))


class Toolbar(GP.Page):
    def test_the_bar_spacing_buttons_and_divider_are_the_approved_ones(self):
        for scheme in ("light", "dark"):
            for width in (1400, 900):
                with self.subTest(scheme=scheme, width=width):
                    self.look(width, scheme)
                    self.mount(mode="edit")
                    m = self.val("""(() => { const q = s => document.querySelector(s), cs = e => getComputedStyle(e), b = q('[data-gantt] .gt-bar');
                      const zin = q('[data-g-zin]'), r = e => e.getBoundingClientRect(), sep = zin.nextElementSibling;
                      return {gap: cs(b).columnGap, mt: cs(b).marginTop, mb: cs(b).marginBottom, zin: [r(zin).width, r(zin).height], zout: [r(q('[data-g-zout]')).width, r(q('[data-g-zout]')).height],
                        fit: r(q('[data-g-fit]')).height, grp: [r(q('[data-g-scale]')).width, r(q('[data-g-scale]')).height],
                        sep: sep.classList.contains('gt-sep') ? [r(sep).width, r(sep).height, cs(sep).marginLeft, cs(sep).marginRight] : null,
                        before: q('[data-g-show]').closest('.gt-showwrap').previousElementSibling === sep}; })()""")
                    self.assertEqual((m["gap"], m["mt"], m["mb"]), ("6px", "4px", "10px"))
                    self.assertEqual((m["zin"], m["zout"], m["fit"], m["grp"]), ([34, 34], [34, 34], 34, [36, 34]))
                    self.assertEqual(m["sep"], [1, 22, "6px", "6px"], "a divider sits between the zoom-in and the filter")
                    self.assertTrue(m["before"])

    def test_the_zoom_percentage_and_the_show_menu_are_the_measured_ones(self):
        for scheme in ("light", "dark"):
            for width in (1400, 900):
                with self.subTest(scheme=scheme, width=width):
                    self.look(width, scheme)
                    self.mount(mode="edit")
                    self.js("document.querySelector('[data-g-show]').click()")
                    self.until("document.querySelector('[data-g-showmenu]')", "the menu")
                    m = self.val("""(() => { const q = s => document.querySelector(s), cs = e => getComputedStyle(e), menu = q('[data-g-showmenu]'), fit = q('[data-g-fit]'), row = menu.querySelector('button');
                      return {fitMin: cs(fit).minWidth, fitFont: cs(fit).fontSize, w: menu.getBoundingClientRect().width, pad: cs(menu).padding, radius: cs(menu).borderRadius,
                        rowPad: cs(row).padding, rowFont: cs(row).fontSize, rowGap: cs(row).columnGap, tick: cs(menu.querySelector('.gt-ck')).width}; })()""")
                    self.assertEqual((m["fitMin"], m["fitFont"]), ("56px", "14px"))
                    self.assertEqual((m["w"], m["pad"], m["radius"]), (240, "6px", "12px"))
                    self.assertEqual((m["rowPad"], m["rowFont"]), ("8px 10px", "14px"))
                    self.assertEqual((m["rowGap"], m["tick"]), ("10px", "14px"), "rows gap 10, tick slot 14")

    def test_the_one_view_edit_control_is_the_pill_and_the_cover_band_is_not_drawn(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                self.look(width)
                self.mount(mode="edit")
                self.assertEqual(self.count("[data-gp-mode]"), 0, "no text View/Edit button in the toolbar")
                self.assertEqual(self.count(".modes [data-mode=view], .modes [data-mode=edit]"), 2, "the pill's two buttons")
                self.assertEqual(self.count("#cover, .cover"), 0, "the approved Gantt page has no Cover band")
                self.assertEqual(self.val("getComputedStyle(document.querySelector('[data-gp-plan]')).marginTop"), "0px", "no gap above the toolbar")
                self.click(".modes [data-mode=view]")
                self.until("document.querySelector('#gantt-page').dataset.mode === 'view'", "View")
                self.click(".modes [data-mode=edit]")
                self.until("document.querySelector('#gantt-page').dataset.mode === 'edit'", "Edit")

    def test_view_has_no_cover_and_edit_has_the_title_box_on_one_flat_line(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                self.look(width)
                self.mount()
                self.assertEqual(self.count(".cover, #cover, [data-gp-flat], [data-g-title]"), 0, "View: no Cover, no title box")
                self.mount(mode="edit")
                m = self.val("""(() => { const q = s => document.querySelector(s), cs = e => getComputedStyle(e), r = e => e.getBoundingClientRect(), f = q('[data-gp-flat]');
                  return {covers: document.querySelectorAll('.cover, #cover').length, box: !!(f && f.querySelector('[data-g-title]')), label: f ? f.querySelector('.gp-flat-l').textContent : null,
                    bg: f ? cs(f).backgroundColor : null, text: f ? f.textContent : '', left: f ? r(f).left : -1, bar: r(q('[data-gantt] .gt-bar, .gt-bar')).left}; })()""")
                self.assertEqual(m["covers"], 0)
                self.assertTrue(m["box"], "Edit has the title box")
                self.assertEqual(m["label"], "Title")
                self.assertEqual(m["bg"], "rgba(0, 0, 0, 0)", "no band fill")
                self.assertNotIn("Weekly report", m["text"])
                self.assertAlmostEqual(m["left"], m["bar"], delta=1, msg="same left edge as the toolbar")


class CardsPlain(GP.Page):
    """The Cards look (no theme) is untouched by row 1197: the text View/Edit button stays, with the pill above it."""

    @classmethod
    def setUpClass(cls):
        p = mock.patch.object(GP, "page_html", PLAIN)      # this class serves the page with no theme
        p.start()
        cls.addClassCleanup(p.stop)
        super().setUpClass()

    def test_cards_keep_the_text_view_edit_button_and_the_pill(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                self.look(width)
                self.assertEqual(self.val("document.getElementById('theme')"), None, "no theme: Cards")
                self.mount()
                self.assertEqual(self.count(".gt-bar [data-gp-mode=edit]"), 1, "Cards: the toolbar keeps its text button")
                self.assertEqual(self.text("[data-gp-mode]"), "Edit", "its main label in View")
                self.assertEqual(self.count(".modes [data-mode=view], .modes [data-mode=edit]"), 2, "the pill stays")
                self.click("[data-gp-mode]")
                self.until("document.querySelector('#gantt-page').dataset.mode === 'edit'", "Edit")
                self.assertEqual(self.text("[data-gp-mode]"), "View", "its main label in Edit")
                self.assertEqual(self.count(".modes [data-mode=view], .modes [data-mode=edit]"), 2)


for _n in [n for n in dir(GP.Page) if n.startswith("test_")]:
    setattr(Toolbar, _n, None)
    setattr(CardsPlain, _n, None) if _n != "test_cards_keep_the_text_view_edit_button_and_the_pill" else None
if __name__ == "__main__":
    unittest.main()

