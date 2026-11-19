"""Row 1369: what ask clark reads from a saved folder, and how the files it did not read are counted (ruling 19-11).

Run: python3 dev/run_tests.py test_ask_1369
Pure logic, made-up files. Asserted with numbers: 180 files are all opened (no cut at 10); the first-ten cap does not exist; the
read caps (files, bytes) count a readable file as `limit`, never as `other` (type); the counts by reason add up to the files; the
note says "because of its type" only for an unreadable type; the 40,000 character budget cuts exactly above the limit.
"""
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401

import test_ask_passages as tp
from clark import ask, ask_data, ask_passages, ask_service


class Counts(tp.Folders):
    def make(self, n, prefix="f", size=100):
        for i in range(n):
            self.put(self.box, f"{prefix}{i:03d}.md", f"ZQ{i:03d} " + "x" * size)

    def test_180_files_are_all_opened_not_ten(self):
        self.make(180)
        got = self.run_it("ZQ179", budget=10**9, max_passages=10**9)
        self.assertEqual(len({p.file for p in got.passages}), 180)
        self.assertEqual((got.other, got.limit), (0, 0))

    def test_the_last_sorting_file_is_found_by_its_word_when_the_budget_is_small(self):
        self.make(180)
        got = self.run_it("ZQ179", budget=3 * 110)
        self.assertIn("saved/f179.md", [p.file for p in got.passages])

    def test_file_cap_counts_readable_files_as_limit_not_type(self):
        self.make(20)
        with mock.patch.object(ask_passages, "MAX_FILES_READ", 12):
            got = self.run_it(budget=10**9, max_passages=10**9)
        self.assertEqual(len({p.file for p in got.passages}), 12)
        self.assertEqual((got.other, got.limit), (0, 8))

    def test_byte_cap_twenty_files_of_five_mb_style(self):
        self.make(20, size=1000)
        with mock.patch.object(ask_passages, "MAX_BYTES_READ", 12 * 1005):   # 12 files fill the byte cap (scaled from 12 x 5 MB of 60 MB)
            got = self.run_it(budget=10**9, max_passages=10**9)
        self.assertEqual(len({p.file for p in got.passages}), 12)
        self.assertEqual((got.other, got.limit), (0, 8))

    def test_counts_by_reason_add_up_to_the_files(self):
        self.make(10)
        for i in range(3):
            self.put(self.box, f"pic{i}.png", b"\x89PNG", binary=True)
        with mock.patch.object(ask_passages, "MAX_FILES_READ", 6):
            got = self.run_it(budget=10**9, max_passages=10**9)
        read = len({p.file for p in got.passages})
        self.assertEqual((read, got.other, got.limit, got.safety, got.pdf), (6, 3, 4, 0, 0))
        self.assertEqual(read + got.other + got.limit, 13)

    def test_note_names_each_reason_once_and_type_only_for_the_type(self):
        lim = ask_service.folder_notes(ask_passages.FolderData(limit=8))
        self.assertEqual(len(lim), 1)
        self.assertNotIn("type", lim[0])
        self.assertIn("8 files were not opened", lim[0])
        typ = ask_service.folder_notes(ask_passages.FolderData(other=3))
        self.assertEqual(typ, ["3 files were not read because of its type."])
        both = ask_service.folder_notes(ask_passages.FolderData(other=1, limit=1))
        self.assertEqual(len(both), 2)
        self.assertEqual(ask_service.folder_notes(ask_passages.FolderData(limit=1))[0].split()[:3], ["1", "file", "was"])


class Budget(unittest.TestCase):
    def passages(self, sizes):
        return [ask.Passage(f"p{i}", "x" * n) for i, n in enumerate(sizes)]

    def test_exactly_at_below_and_above_the_limit(self):
        self.assertEqual(ask.BUDGET, 40000)
        for total, kept in ((39999, 2), (40000, 2), (40001, 1)):
            ps = self.passages([20000, total - 20000])
            got, left = ask_data.choose(ps, "", ask.BUDGET)
            self.assertEqual((len(got), left), (kept, 2 - kept), total)


if __name__ == "__main__":
    unittest.main()
