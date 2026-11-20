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
RULES = (ROOT / "src" / "clark" / "themes" / NAME / "rules.css").read_text(encoding="utf-8")


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


for _n in [n for n in dir(GP.Page) if n.startswith("test_")]:
    setattr(Toolbar, _n, None)
if __name__ == "__main__":
    unittest.main()
