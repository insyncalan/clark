"""Row 1366 slice (b): the list of files left out (spec row 6) and the answer note (spec row 7). Made-up files only."""
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401

from test_ask_index_1366 import Base, FAKE_KEY, ix

from clark import ask_picture


class LeftOut(Base):
    def setUp(self):
        super().setUp()
        p = mock.patch.object(ask_picture, "_READER", None)        # on a Mac ask_index registers the real reader at import: these tests start with none
        p.start()
        self.addCleanup(p.stop)

    def test_list_names_each_file_with_a_plain_reason_and_never_the_matched_text(self):
        self.put("a.txt", "zqone")
        self.put("c.bin", b"\x89BIN", binary=True)
        self.put("keys.txt", "zqnote\n" + FAKE_KEY)
        self.build()
        out = ix.mod().files_left_out(self.data, "P1", 200)
        self.assertEqual(out["more"], 0)
        names = dict(out["files"])
        self.assertEqual(set(names), {"saved/c.bin", "saved/keys.txt"})
        self.assertEqual(names["saved/c.bin"], "of a type clark can't read yet")
        self.assertEqual(names["saved/keys.txt"], "looks like a password or a key")
        self.assertNotIn("hunter2", repr(out))
        self.assertNotIn("zqnote", repr(out))

    def test_list_is_cut_at_the_limit_and_says_how_many_more(self):
        for i in range(7):
            self.put(f"f{i}.bin", b"\x89BIN", binary=True)
        self.build()
        out = ix.mod().files_left_out(self.data, "P1", 5)
        self.assertEqual((len(out["files"]), out["more"]), (5, 2))
        self.assertEqual(ix.mod().more_line(2), "and 2 more")

    def test_two_folders_with_the_same_name_each_list_only_their_own_files(self):
        one, two = self.d / "a" / "docs", self.d / "b" / "docs"
        self.put("one.png", b"\x89PNG", binary=True, folder=one)
        self.put("two.png", b"\x89PNG", binary=True, folder=two)
        ix.build(self.data, "P1", [one, two])
        got = ix.mod()._left_by_folder(self.data, "P1", [str(one), str(two)])
        self.assertEqual([f[0] for f in got[str(one)]["files"]], ["one.png"])
        self.assertEqual([f[0] for f in got[str(two)]["files"]], ["two.png"])

    def test_a_folder_whose_name_only_starts_the_same_gets_nothing_of_the_other(self):
        one, two = self.d / "docs", self.d / "docs2"
        self.put("one.png", b"\x89PNG", binary=True, folder=one)
        self.put("two.png", b"\x89PNG", binary=True, folder=two)
        ix.build(self.data, "P1", [one, two])
        got = ix.mod()._left_by_folder(self.data, "P1", [str(one), str(two)])
        self.assertEqual([f[0] for f in got[str(one)]["files"]], ["one.png"])
        self.assertEqual([f[0] for f in got[str(two)]["files"]], ["two.png"])

    def test_list_follows_a_refresh(self):
        p = self.put("c.bin", b"\x89BIN", binary=True)
        self.build()
        p.unlink()
        ix.refresh(self.data, "P1", [self.box])
        self.assertEqual(ix.mod().files_left_out(self.data, "P1", 200), {"files": [], "more": 0})

    def test_no_index_gives_an_empty_list(self):
        self.assertEqual(ix.mod().files_left_out(self.data, "NONE", 200), {"files": [], "more": 0})

    def test_the_list_holds_names_not_text(self):
        self.put("c.bin", b"\x89BIN zqpixel", binary=True)
        self.build()
        self.assertNotIn(b"zqpixel", ix.path_for(self.data, "P1").read_bytes())


class AnswerNote(unittest.TestCase):
    def test_words(self):
        m = __import__("clark.ask_index", fromlist=["x"])
        self.assertEqual(m.answer_note({"not_yet": 120}), "Still reading 120 files, so this answer may miss some.")
        self.assertEqual(m.answer_note({"not_yet": 1}), "Still reading 1 file, so this answer may miss some.")
        self.assertEqual(m.answer_note({"not_yet": 0}), "")
        self.assertEqual(m.answer_note({}), "")
        self.assertEqual(m.LEFT_OUT_BUTTON, "Show the files left out")

    def test_reason_words(self):
        m = __import__("clark.ask_index", fromlist=["x"])
        self.assertEqual(m.left_out_line("safety", 4), "4 look like a password or a key and were left out.")
        self.assertEqual(m.left_out_line("safety", 1), "1 looks like a password or a key and was left out.")


if __name__ == "__main__":
    unittest.main()
