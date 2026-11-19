"""#1366 slice (b): the list of files left out (spec row 6) and the answer note (spec row 7). Made-up files only."""
import unittest

from _paths import SRC  # noqa: F401

from test_ask_index_1366 import Base, FAKE_KEY, ix


class LeftOut(Base):
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
