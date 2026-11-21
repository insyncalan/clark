"""Row 1369: what ask clark reads from a saved folder, and how the files it did not read are counted (ruling 19-11).

Run: python3 dev/run_tests.py test_ask_1369
Pure logic, made-up files. Asserted with numbers: 180 files are all opened (no cut at 10); the first-ten cap does not exist; the
read caps (files, bytes) count a readable file as `limit`, never as `other` (type); the counts by reason add up to the files; the
note says "because of its type" only for an unreadable type; the character budget (ask.BUDGET) cuts exactly above the limit.
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
        self.assertEqual(both, [typ[0].replace("3 files were", "1 file was"), "1 file was not opened because the limit for one question was reached."])
        self.assertEqual(lim, ["8 files were not opened because the limit for one question was reached."])
        self.assertEqual(ask_service.folder_notes(ask_passages.FolderData(limit=1))[0].split()[:3], ["1", "file", "was"])
        two = ask_service.folder_notes(ask_passages.FolderData(limit=2))
        self.assertEqual(two, ["2 files were not opened because the limit for one question was reached."])


    def test_only_unusable_folders_give_no_limit(self):
        got = ask_passages.folder_data([str(self.data)], self.data, "plan")
        self.assertEqual((got.passages, got.safety, got.limit, got.other), ((), 1, 0, 0))

    def test_byte_cap_stops_at_exactly_the_cap(self):
        self.make(20, size=1000)
        one = self.box.joinpath("f000.md").stat().st_size
        with mock.patch.object(ask_passages, "MAX_BYTES_READ", 12 * one):   # the 12th file brings the total to exactly the cap
            got = self.run_it(budget=10**9, max_passages=10**9)
        self.assertEqual(len({p.file for p in got.passages}), 12)
        self.assertEqual((got.other, got.limit), (0, 8))

    def test_character_cap_stops_at_exactly_the_cap(self):
        self.make(20, size=1000)
        one = self.run_it(folders=[self.box], budget=10**9, max_passages=10**9)
        per = sum(len(p.text) for p in one.passages) // 20
        with mock.patch.object(ask_passages, "MAX_CHARS", 12 * per):         # the 12th file brings the kept text to exactly the cap
            got = self.run_it(budget=10**9, max_passages=10**9)
        self.assertEqual(len({p.file for p in got.passages}), 12)
        self.assertEqual((got.other, got.limit), (0, 8))

    def test_a_found_without_a_limit_count_gets_no_limit_note(self):
        from types import SimpleNamespace
        found = SimpleNamespace(other=0, stopped=False, safety=0, pdf=0, pdf_reasons=(), secret_labels=())
        self.assertEqual([n for n in ask_service.folder_notes(found) if "limit" in n], [])

    def test_limit_note_comes_with_the_listing_cut_note(self):
        notes = ask_service.folder_notes(ask_passages.FolderData(limit=2, stopped=True))
        self.assertEqual(len(notes), 2)
        self.assertEqual(notes[1], "Not every file in your folders was looked at.")


class Budget(unittest.TestCase):
    def passages(self, sizes):
        return [ask.Passage(f"p{i}", "x" * n) for i, n in enumerate(sizes)]

    def test_exactly_at_below_and_above_the_limit(self):
        half = ask.BUDGET // 2
        for total, kept in ((ask.BUDGET - 1, 2), (ask.BUDGET, 2), (ask.BUDGET + 1, 1)):
            ps = self.passages([half, total - half])
            got, left = ask_data.choose(ps, "", ask.BUDGET)
            self.assertEqual((len(got), left), (kept, 2 - kept), total)


class SettingsSize(unittest.TestCase):
    """Test 4 of the row: the size the Settings page states is the size the code uses (the page reads the code's constant)."""

    def test_the_page_size_is_the_code_size_and_the_line_states_it(self):
        from clark import ai_connect
        self.assertIs(ai_connect.QUESTION_CHARS, ask.BUDGET)
        self.assertEqual(ask.BUDGET, 1_200_000)
        # what the page is actually given: AiConnect.view()["size"], not a line formatted again here
        import os, shutil, tempfile
        from pathlib import Path
        import test_ai_connect as T
        d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, d, True)
        connect, _chain = T.ac.chain(d, T.FakeClaude(), T.FakeChatGPT())
        line = connect.view()["size"]
        self.assertIn(f"{ask.BUDGET // 4:,} tokens", line)
        self.assertIn(f"{ask.BUDGET:,} characters", line)


if __name__ == "__main__":
    unittest.main()
