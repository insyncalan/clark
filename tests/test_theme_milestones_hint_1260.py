"""Row 1260 gap G4, as row 1329 left it: the Plan | Movement switch and its hint are gone, so Classic carries no rule for the hint (Cards never had one).

Run: python3 dev/run_tests.py test_theme_milestones_hint_1260
"""
import unittest

from _paths import ROOT  # noqa: F401

from clark import page


class MilestonesHint(unittest.TestCase):
    def test_classic_carries_no_hint_rule(self):
        html = page.page_html(branding=page.NO_BRAND, theme="prototype-2.0")
        self.assertNotIn("data-mspage-hint", html.split('<script', 1)[0])
        self.assertNotIn("data-mspv", html.split('<script', 1)[0])

    def test_cards_page_has_no_such_rule(self):
        html = page.page_html(branding=page.NO_BRAND)
        self.assertNotIn("data-mspage-hint] { display: none", html)


if __name__ == "__main__":
    unittest.main()
