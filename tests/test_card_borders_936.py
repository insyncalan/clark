"""Row 936 (card borders): the decorative one-side stripes that edit.css quiets, and the proof that the published page keeps its own.

Run: python3 dev/run_tests.py test_card_borders_936
Headless Chrome through the shared harness. Covers (1) the Help note has a hairline all round (no blue stripe), light and dark,
(2) edit.css carries the two overrides and the use-cases row hover has no inset stripe, (3) page-view.html has neither override and
shell.css still holds the original rules (the published page is unchanged).
"""
import unittest

from _paths import ROOT
from test_help_nav_page import WhatNextPage, set_theme
from test_server import chrome

PAGE = ROOT / "src" / "clark" / "page"


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class HelpNote(WhatNextPage):
    def test_the_help_note_has_no_one_side_stripe(self):
        with chrome() as cdp:
            p = self.open_at(cdp, "guide-fixture-guide")
            for theme in ("light", "dark"):
                set_theme(cdp, p, theme)
                got = p.js("""(() => { const s = getComputedStyle(document.querySelector('#hp-guide-fixture-guide .hp-note'));
                    return [s.borderTopWidth, s.borderRightWidth, s.borderBottomWidth, s.borderLeftWidth, s.borderTopColor === s.borderLeftColor]; })()""")
                self.assertEqual(got, ["1px", "1px", "1px", "1px", True], f"{theme}: a hairline all round")


class Source(unittest.TestCase):
    def test_edit_css_carries_the_overrides_and_the_row_hover_has_no_stripe(self):
        css = read(PAGE / "src" / "edit" / "edit.css")
        self.assertIn(".hp-note { border: 1px solid var(--grey-200); border-radius: var(--radius); }", css)
        line = next(l for l in css.splitlines() if l.startswith(".ucl-list .ucl-row:hover"))
        self.assertNotIn("inset", line)
        self.assertNotIn("box-shadow", line)

    def test_the_published_page_has_no_edit_override_and_shell_css_has_the_quiet_note(self):
        view = read(PAGE / "page-view.html")
        self.assertNotIn(".hp-note { border: 1px solid", view)
        self.assertNotIn(".ucl-list .ucl-row:hover", view)
        note = next(l for l in read(PAGE / "shell.css").splitlines() if l.startswith(".hp-note {"))
        self.assertIn("border: 1px solid var(--grey-200)", note)
        self.assertNotIn("border-left", note)


if __name__ == "__main__":
    unittest.main()
