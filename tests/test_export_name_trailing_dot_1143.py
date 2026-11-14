"""Row 1143: when the cut of a long project name lands on a dot or a space, the download name must not carry a stray dot or space
in front of the "(" of the code or in front of the date (excel.download_name). Pure Python, no browser.

Run: python3 dev/run_tests.py test_export_name_trailing_dot_1143
"""
import datetime
import unittest

from _paths import SRC  # noqa: F401
from clark import excel

WHEN = datetime.datetime(2026, 11, 13, 18, 52, 7)
TAIL = " 2026.11.13 18.52.07.xlsx"


class TrailingDot(unittest.TestCase):
    def test_a_cut_that_ends_on_a_dot_leaves_no_dot_before_the_code(self):
        name = "a" * (excel.DOWNLOAD_NAME_CUT - 1) + ". Phase two"
        self.assertEqual(excel.download_name(name, "NWD", WHEN), "a" * (excel.DOWNLOAD_NAME_CUT - 1) + "(NWD)" + TAIL)

    def test_a_cut_that_ends_on_a_dot_and_spaces_leaves_none_before_the_code(self):
        name = "a" * (excel.DOWNLOAD_NAME_CUT - 3) + " . " + "tail"
        self.assertEqual(excel.download_name(name, "NWD", WHEN), "a" * (excel.DOWNLOAD_NAME_CUT - 3) + "(NWD)" + TAIL)

    def test_a_cut_that_ends_on_a_dot_leaves_no_dot_before_the_date_when_there_is_no_code(self):
        name = "a" * (excel.DOWNLOAD_NAME_CUT - 1) + ". Phase two"
        self.assertEqual(excel.download_name(name, "", WHEN), "a" * (excel.DOWNLOAD_NAME_CUT - 1) + TAIL)

    def test_a_name_that_is_only_dots_and_spaces_falls_back_to_the_code(self):
        self.assertEqual(excel.download_name(" ... ", "NWD", WHEN), "NWD" + TAIL)

    def test_no_name_part_ends_in_a_dot_or_space_before_the_bracket(self):
        for n in range(1, excel.DOWNLOAD_NAME_CUT + 3):
            name = ("ab. " * 30)[:n]
            out = excel.download_name(name, "NWD", WHEN)
            self.assertNotRegex(out, r"[. ]\(NWD\)", name)
            self.assertTrue(out.endswith("(NWD)" + TAIL), name)


if __name__ == "__main__":
    unittest.main()
