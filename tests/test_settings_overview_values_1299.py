"""Row 1299 AP14 (the Projects overview values, Classic only), in a real browser at 1400 and 900 px.
Run: python3 dev/run_tests.py test_settings_overview_values_1299

Asserted: Asking shows the computer's On or Off on every row; the brand "generic" reads "clark default" and another brand shows as stored; no backup reads "No backup yet" in
amber and an old one "3 days ago" in amber; "Nothing needs attention." when no row needs a look; each value is a link titled "Open <what> for <code>". Chrome is required."""
import unittest

import test_projects_overview_ui_1299 as ui
from test_server import chrome

NOBACKUP = [ui.row("PUB", "Harbour Bridge Programme", last_backup_days=None, attention=["no_backup"]),
            ui.row("ABC", "Second Programme", asking=True, brand="acme", last_backup_days=3, attention=["backup_old"])]


class Values(ui.Overview):
    rows = NOBACKUP

    def test_asking_brand_backup_and_titles(self):
        for w in ui.WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, w)
                p.until("!!document.querySelector('#projects-overview .ov-table')", "the overview drew")
                cell = lambda code, key: p.js(f"document.querySelector('tr[data-ov-project={code}] [data-ov={key}]').textContent")
                self.assertEqual([cell("PUB", "asking"), cell("ABC", "asking")], ["Off", "On"])
                self.assertEqual([cell("PUB", "brand"), cell("ABC", "brand")], ["clark default", "acme"])
                self.assertEqual([cell("PUB", "backup"), cell("ABC", "backup")], ["No backup yet", "3 days ago"])
                for code in ("PUB", "ABC"):
                    self.assertTrue(p.js(f"document.querySelector('tr[data-ov-project={code}] [data-ov=backup]').classList.contains('ov-amber')"), code + " backup is amber")
                self.assertEqual(p.js("document.querySelector('tr[data-ov-project=ABC] [data-ov=backup]').title"), "Open Backups for ABC")
                self.assertEqual(p.js("document.querySelector('tr[data-ov-project=PUB] [data-ov=brand]').title"), "Open Brand for PUB")
                self.assertFalse(p.js("!!document.querySelector('#ov-none')"), "something needs a look: no clear line")

    test_O_the_page_draws_the_ruled_words_and_one_row_for_each_project = None
    test_O_needs_attention_keeps_only_the_projects_with_something_to_look_at = None
    test_O_a_click_on_a_value_opens_that_setting_for_that_project = None


class ValuesClean(ui.Overview):
    rows = [ui.row("PUB", "Harbour Bridge Programme")]

    def test_asking_brand_backup_and_titles(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 1400)
            p.until("!!document.querySelector('#projects-overview .ov-table')", "the overview drew")
            self.assertEqual(p.js("document.querySelector('#ov-none').textContent"), "Nothing needs attention.")

    test_O_the_page_draws_the_ruled_words_and_one_row_for_each_project = None
    test_O_needs_attention_keeps_only_the_projects_with_something_to_look_at = None
    test_O_a_click_on_a_value_opens_that_setting_for_that_project = None


if __name__ == "__main__":
    unittest.main()
