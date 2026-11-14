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

    def test_a_code_that_ends_on_a_dot_has_none_before_the_date_when_it_stands_in_for_the_name(self):
        self.assertEqual(excel.download_name("", "NWD.", WHEN), "NWD" + TAIL)
        self.assertEqual(excel.download_name(" ... ", "N W.", WHEN), "N W" + TAIL)

    def test_no_name_part_ends_in_a_dot_or_space_before_the_bracket(self):
        for n in range(1, excel.DOWNLOAD_NAME_CUT + 3):
            name = ("ab. " * 30)[:n]
            out = excel.download_name(name, "NWD", WHEN)
            self.assertNotRegex(out, r"[. ]\(NWD\)", name)
            self.assertTrue(out.endswith("(NWD)" + TAIL), name)

    def test_a_multibyte_name_is_cut_by_the_byte_limit_on_a_character_boundary(self):
        out = excel.download_name("\u20ac" * 50, "NWD", WHEN)      # 150 bytes, 50 characters: 40 euro signs fit in 120 bytes
        self.assertEqual(out, "\u20ac" * 40 + "(NWD)" + TAIL)

    def test_a_byte_cut_inside_a_character_that_leaves_a_dot_last_drops_the_dot(self):
        name = "\u20ac" * 39 + ".\u20ac tail"      # 118 bytes, the dot is byte 118 and the next sign would end at 121
        self.assertEqual(excel.download_name(name, "NWD", WHEN), "\u20ac" * 39 + "(NWD)" + TAIL)

    def test_no_name_with_a_code_uses_the_code_alone(self):
        self.assertEqual(excel.download_name(None, "NWD", WHEN), "NWD" + TAIL)

    def test_no_name_and_no_code_gives_work_items(self):
        self.assertEqual(excel.download_name("", "", WHEN), "work items" + TAIL)
        self.assertEqual(excel.download_name(None, None, WHEN), "work items" + TAIL)

    def test_a_name_ending_in_a_non_breaking_space_then_a_dot_leaves_neither_before_the_code(self):
        self.assertEqual(excel.download_name("Plan\u00a0.", "NWD", WHEN), "Plan(NWD)" + TAIL)
        self.assertEqual(excel.download_name("Plan.\u00a0.\u00a0", "NWD", WHEN), "Plan(NWD)" + TAIL)
        self.assertEqual(excel.download_name("Plan\u00a0.", "", WHEN), "Plan" + TAIL)

    def test_a_code_ending_in_a_non_breaking_space_then_a_dot_has_neither_before_the_date(self):
        self.assertEqual(excel.download_name("", "NWD\u00a0.", WHEN), "NWD" + TAIL)


if __name__ == "__main__":
    unittest.main()
