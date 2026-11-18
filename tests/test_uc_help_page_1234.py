"""Row 1234: two Help sentences about the use case summary are checked against the real page.

Run: python3 dev/run_tests.py test_uc_help_page_1234
Help says the count and the meter cover every use case on the dashboard (a use case that is not on the dashboard is not counted, and the
page says how many more there are), and that the commitment shows a dash in View when none, a Set commitment button in Edit.
Widths 1400 and 900 px. Fictional data; the committed page over a real server.
"""
import json
import unittest

from _paths import SRC
from test_commitment_page import Flags, tearDownModule  # noqa: F401
from test_server import chrome
from test_use_cases_list import Setup

HELP = SRC / "clark" / "page" / "src" / "help" / "helpContent.json"
COUNT = "The count and the meter cover every use case on the dashboard."
COMMIT = "the commitment (in View, a dash when none; in Edit, a Set commitment button)"


def keep_text():
    def find(node):
        if isinstance(node, dict):
            if node.get("id") == "keep-the-use-cases":
                return node
            for v in node.values():
                r = find(v)
                if r:
                    return r
        elif isinstance(node, list):
            for v in node:
                r = find(v)
                if r:
                    return r
        return None
    return " ".join(find(json.loads(HELP.read_text(encoding="utf-8")))["s"])


class HelpSaysWhatTheStripDoes(Setup):
    def test_the_count_and_the_meter_cover_only_the_use_cases_on_the_dashboard(self):
        text = keep_text()
        self.assertIn(COUNT, text)
        self.assertNotIn("always cover every use case", text)
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width, hash_="#dashboard&p=ABC")
                p.until("!!document.querySelector('.uc')", "the summary drew")
                self.assertEqual(p.js("document.querySelector('.uctotal').textContent"), "2 use cases", "4 exist, 2 are on the dashboard")
                self.assertEqual(p.js("document.querySelectorAll('.uc .meter i').length"), 2, "the meter has one mark per counted use case")
                self.assertEqual(p.js("document.querySelector('[data-uc-more]').textContent"), "2 more on the Use cases page")


class HelpSaysWhatTheCommitmentDraws(Flags):
    def test_view_draws_a_dash_and_edit_a_set_commitment_button_for_none(self):
        text = keep_text()
        self.assertIn(COMMIT, text)
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                self.assertEqual(p.js("[...document.querySelectorAll('.ucrow:nth-child(2) [data-commit-none]')].map(e => e.textContent)"), ["—"])
                p.edit()
                p.until("document.querySelectorAll('[data-uc-commit]').length === 2", "Edit drew the menus")
                self.assertEqual(p.js("document.querySelector('[data-uc-commit=\"%s\"] button').textContent.trim()" % self.uc2), "Set commitment")


if __name__ == "__main__":
    unittest.main()
