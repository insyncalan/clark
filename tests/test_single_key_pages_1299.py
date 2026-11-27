"""Row 1299 AP29, in the page: the single-key switch is named "Single-key slash commands" on Profile and Appearance.
Run: python3 dev/run_tests.py test_single_key_pages_1299"""
import unittest

import test_projects_overview_ui_1299 as ui
from test_server import chrome

NEW = "Single-key slash commands"


class SingleKeyNamePages(ui.Overview):
    """AP29, in the page: every Settings page that carries the switch names it "Single-key slash commands" (aria name and row name), at 1400 and 900, light and dark."""
    PAGES = ("profile", "appearance")      # Essentials (Profile) and the Personal card (Appearance)

    test_O_the_page_draws_the_ruled_words_and_one_row_for_each_project = None
    test_O_needs_attention_keeps_only_the_projects_with_something_to_look_at = None
    test_O_a_click_on_a_value_opens_that_setting_for_that_project = None

    def test_every_page_with_the_switch_names_it_slash_commands(self):
        for w in (1400, 900):
            for mode in ("light", "dark"):
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    for slug in self.PAGES:
                        self.open_settings(p, w, mode, slug=slug)
                        p.until(f"document.querySelector('.set-cards').getAttribute('data-page') === {slug!r}", slug + " drew")
                        names = p.js("[...document.querySelectorAll('.set-cards [role=switch][aria-label]')].map(e => e.getAttribute('aria-label')).filter(n => /single-key/i.test(n))")
                        self.assertTrue(names, slug + ": the page carries the single-key switch")
                        self.assertEqual(set(names), {NEW}, slug + ": every single-key switch is named so")
                        self.assertNotIn("Single-key shortcuts", p.js("document.querySelector('.set-cards').textContent"), slug + ": the old name is not on the page")


if __name__ == "__main__":
    unittest.main()
