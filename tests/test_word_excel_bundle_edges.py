"""PR 1356 (Word and Excel bundle) mutation hunt: the edges its own tests left open.

  * excel_import._six_digit_fraction (row 1061 follow-up for Python 3.9, which reads a fraction of exactly 3 or 6 digits): its output is
    pinned directly, because Python 3.11 and later read any fraction and so hide a wrong pad or cut when only _moved is looked at.
  * glance.client_pill: a status that is empty, or not text, says nothing of its own.

Run: python3 dev/run_tests.py test_word_excel_bundle_edges     Fictional data only.
"""
import unittest
from datetime import datetime

from _paths import SRC  # noqa: F401

from clark import excel_import as xi, glance

TODAY = "2026-10-28"


class SixDigitFraction(unittest.TestCase):
    def test_a_fraction_is_padded_or_cut_to_six_digits(self):
        for text, want in (("2026-10-05 10:00:00.5", "2026-10-05 10:00:00.500000"),
                           ("2026-10-05 10:00:00.12", "2026-10-05 10:00:00.120000"),
                           ("2026-10-05 10:00:00.123", "2026-10-05 10:00:00.123000"),
                           ("2026-10-05 10:00:00.1234567", "2026-10-05 10:00:00.123456"),
                           ("2026-10-05 10:00:00.123456789012", "2026-10-05 10:00:00.123456"),
                           ("2026-10-05 10:00:00", "2026-10-05 10:00:00")):
            self.assertEqual(xi._six_digit_fraction(text), want, text)

    def test_only_the_first_fraction_after_a_time_is_changed(self):
        self.assertEqual(xi._six_digit_fraction("10:00:00.5 and 11:00:00.5"), "10:00:00.500000 and 11:00:00.5")

    def test_a_cell_and_a_stored_time_with_odd_length_fractions_are_compared_to_the_microsecond(self):
        self.assertFalse(xi._moved("2026-10-05 10:00:00.5", "2026-10-05 10:00:00.50"))
        self.assertFalse(xi._moved("2026-10-05 10:00:00.5001", "2026-10-05 10:00:00.5"))
        self.assertTrue(xi._moved("2026-10-05 10:00:00.5", "2026-10-05 10:00:00.5040"))
        self.assertTrue(xi._moved("2026-10-05 10:00:00.5", "2026-10-05T10:00:00.51"))
        self.assertTrue(xi._moved(datetime(2026, 10, 5, 10, 0, 0, 500000), "2026-10-05 10:00:00.51"))


class ClientPillOwnStatus(unittest.TestCase):
    def pill(self, **row):
        return glance.client_pill(dict({"kind": "action", "priority": "Medium", "due_date": "2026-12-31"}, **row), TODAY)

    def test_an_empty_or_missing_status_says_nothing_of_its_own(self):
        for status in ("", None):
            for kind in ("action", "risk", "issue"):
                got = self.pill(kind=kind, status=status)
                self.assertNotEqual(got["text"], "", (kind, status))
        self.assertEqual(self.pill(status="")["text"], "On track")

    def test_a_status_that_is_not_text_says_nothing_of_its_own(self):
        for status in (5, 2.5, ["Blocked"], {"a": 1}, True):
            got = self.pill(status=status)
            self.assertEqual(got, {"text": "On track", "class": "g"}, status)


if __name__ == "__main__":
    unittest.main()
