"""Row 1260 gap G4: Classic hides the sentence under the Milestones title (Plan view); Cards keeps it.

Run: python3 dev/run_tests.py test_theme_milestones_hint_1260
"""
import unittest

from _paths import ROOT  # noqa: F401

from clark import page

RULE = '.wbar:has([data-mspv="plan"][aria-pressed="true"]) [data-mspage-hint] { display: none; }'


class MilestonesHint(unittest.TestCase):
    def test_classic_carries_the_hiding_rule_once(self):
        html = page.page_html(branding=page.NO_BRAND, theme="prototype-2.0")
        self.assertEqual(html.count(RULE), 1)

    def test_cards_page_has_no_such_rule(self):
        html = page.page_html(branding=page.NO_BRAND)
        self.assertNotIn("data-mspage-hint] { display: none", html)

    def test_the_hiding_rule_names_only_the_plan_view(self):
        self.assertIn('[data-mspv="plan"][aria-pressed="true"]', RULE)


if __name__ == "__main__":
    unittest.main()
