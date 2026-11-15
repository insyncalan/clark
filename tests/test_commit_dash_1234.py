"""Row 1234: a use case with no commitment shows a dash in View (and the published file); Edit keeps "Set commitment".

Run: python3 dev/run_tests.py test_commit_dash_1234
Widths 1400 and 900 px. Fictional data; the committed page over a real server.
"""
import unittest

from test_commitment_page import Flags, OVERLAP, CHIPS, tearDownModule  # noqa: F401
from test_server import chrome

ROW2 = ".ucrow:nth-child(2)"


class Dash(Flags):
    def test_view_draws_a_dash_for_no_commitment_and_the_chip_for_a_flag_at_1400_and_900(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                self.assertEqual(p.js(CHIPS % ".uc"), ["Committed"])
                self.assertEqual(p.js(f"[...document.querySelectorAll('{ROW2} [data-commit-none]')].map(e => e.textContent)"), ["—"])
                self.assertEqual(p.js("document.querySelectorAll('.ucrow:nth-child(1) [data-commit-none]').length"), 0, "a flagged row has no dash")
                self.assertEqual(p.js(f"document.querySelectorAll('{ROW2} .cchip').length"), 0, "the dash is not a chip")
                body = p.js("document.querySelector('.uc').innerText")
                for word in ("Set commitment", "No flag", "None"):
                    self.assertNotIn(word, body)
                self.assertEqual(p.js("document.querySelectorAll('.uc [data-uc-commit], .uc .ucw-btn').length"), 0)
                self.assertEqual(p.js(f"{OVERLAP}('.ucbar', '.ucstc')"), [])

    def test_edit_keeps_set_commitment_and_no_dash(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.edit()
                p.until("document.querySelectorAll('[data-uc-commit]').length === 2", "Edit drew the menus")
                self.assertEqual(p.js("document.querySelector('[data-uc-commit=\"%s\"] button').textContent.trim()" % self.uc2), "Set commitment")
                self.assertEqual(p.js("document.querySelectorAll('.uc [data-commit-none]').length"), 0)


if __name__ == "__main__":
    unittest.main()
