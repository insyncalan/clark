"""Row 1107, the mutation hunt on PR 1382: the Linked milestones cell read and written without a workbook (excel_import.py and excel.py: guarded).
Run: python3 dev/run_tests.py test_uc_milestones_cells_1382
"""
import unittest

import _paths  # noqa: F401
from clark import excel, excel_import as xi


class Cell(unittest.TestCase):
    def test_one_id_and_name_per_line_or_ids_split_by_commas_read_as_the_sorted_distinct_ids(self):
        for text, want in (("ABC-M-001: Kick off\nABC-M-002: Go live", ["ABC-M-001", "ABC-M-002"]),
                           ("ABC-M-002: Go live\nABC-M-001: Kick off", ["ABC-M-001", "ABC-M-002"]),
                           ("ABC-M-002, ABC-M-001", ["ABC-M-001", "ABC-M-002"]),
                           ("ABC-M-001", ["ABC-M-001"]),
                           ("ABC-M-001\r\nABC-M-001\rABC-M-003", ["ABC-M-001", "ABC-M-003"]),
                           ("ABC-M-001: a\n\n  \n ABC-M-003", ["ABC-M-001", "ABC-M-003"]),
                           ("ABC-M-001,", ["ABC-M-001"]),
                           ("ABC-M-001: Kick, off", ["ABC-M-001"]),          # a comma inside a name does not split a line that has ': '
                           ("", []), ("  \n ", [])):
            self.assertEqual(xi.milestone_ids(text), (want, ""), repr(text))

    def test_the_first_piece_that_is_not_a_milestone_id_is_named(self):
        for text, bad in (("ABC-A-001", "ABC-A-001"), ("ABC-M-001, junk", "junk"), ("junk\nABC-A-002", "junk"), ("abc-m-001", "abc-m-001"),
                          ("ABC-M-001 Kick off", "ABC-M-001 Kick off"), ("ABC-U-001", "ABC-U-001"), ("ABC-M-001, one, two", "one")):
            got, said = xi.milestone_ids(text)
            self.assertEqual(said, bad, repr(text))
        self.assertEqual(xi.milestone_ids("ABC-M-001, junk")[0], ["ABC-M-001"], "the good ones are still read")

    def test_the_cell_is_a_virtual_column_of_use_cases_only(self):
        self.assertEqual(xi.virtual_columns("use_cases"), [xi.UC_MILESTONES])
        self.assertEqual(xi.UC_MILESTONES, "milestones")
        self.assertEqual(xi.virtual_columns("milestones"), [])
        self.assertEqual(xi.virtual_columns("projects"), [])
        self.assertEqual(xi.virtual_columns("actions"), [xi.LABELS])

    def test_the_export_value_reads_back_as_ids(self):
        self.assertEqual(excel.writer_ids("ABC-M-001, ABC-M-002"), ["ABC-M-001", "ABC-M-002"])
        self.assertEqual(excel.writer_ids(""), [])
        self.assertEqual(excel.writer_ids(None), [])
        self.assertEqual(excel.writer_ids("ABC-M-001, , ABC-M-002"), ["ABC-M-001", "ABC-M-002"])


if __name__ == "__main__":
    unittest.main()
