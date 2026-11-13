"""excel.from_cell reads a DATES text cell written 13/11/2026 or 13.11.2026 as well as 13-11-2026, like excel_import.

Run: python3 dev/run_tests.py test_excel_from_cell_dates
"""
import unittest

from _paths import ROOT, SRC, TOOLS  # noqa: F401

from clark import excel  # noqa: E402


class FromCellDates(unittest.TestCase):
    def test_slash_and_dot_dates_are_read(self):
        field = sorted(excel.DATES)[0]
        for text in ("13-11-2026", "13/11/2026", "13.11.2026", " 13/11/2026 ", "3.1.2026"):
            want = "2026-01-03" if text == "3.1.2026" else "2026-11-13"
            self.assertEqual(excel.from_cell(field, text), want, text)

    def test_a_bad_date_is_left_as_typed(self):
        field = sorted(excel.DATES)[0]
        for text in ("31/02/2026", "13/11/26", "soon"):
            self.assertEqual(excel.from_cell(field, text), text)


if __name__ == "__main__":
    unittest.main()
