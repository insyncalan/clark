"""Row 1470: the Dashboard peek draws the editable Latest update whatever the Dashboard mode, with the stamp "Last updated <date> <time> by <name> · Source: <source>"
(name and Source only when known), and an item nobody has updated shows its Created entry. Server side: GET /api/activity carries the Source alone
(`source_words`) and the Created row with who and when. Page side: the gate is the file, not the mode (read from the source; no browser here).
Run: python3 dev/run_tests.py test_peek_latest_stamp_1470"""
import unittest

from _paths import SRC as _SRC
from _demo import USER, DemoStore
from clark import activity_read


SRC = _SRC / "clark" / "page" / "src" if not (_SRC / "components").is_dir() else _SRC


class Server(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        s = self.demo.store
        self.read = activity_read.make_read(s.path, s.data_for)

    def test_the_source_alone_and_the_created_entry_with_who_and_when(self):
        a = self.demo.action(source="Excel import, 2026-10-01, plan.xlsx")
        got = self.read("ABC", a)
        self.assertEqual(got["source_words"], "Excel import, 01-10-2026, plan.xlsx")
        self.assertEqual(got["source"], got["source_words"] + " by " + USER)
        made = [r for r in got["rows"] if r["kind"] == "Created"]
        self.assertTrue(made)
        self.assertEqual(made[-1]["who"], USER)
        self.assertRegex(made[-1]["when_text"], r"^\d{2}-\d{2}-\d{4} \d{2}:\d{2}")

    def test_no_source_words_is_an_empty_string(self):
        a = self.demo.action(source="demo")
        self.demo.store.con.execute("UPDATE actions SET source = '' WHERE id = ?", (a,))
        self.demo.store.con.commit()
        self.assertEqual(self.read("ABC", a)["source_words"], "")


class Page(unittest.TestCase):
    def test_the_latest_update_gate_is_the_file_not_the_mode(self):
        peek = (SRC / "components" / "Peek.jsx").read_text(encoding="utf-8")
        self.assertIn("const latestOn = !!tools && !fromFile.value;", peek)
        self.assertIn("Latest = latestOn && forItem && tools.PeekLatest", peek)
        self.assertIn("MsLatest = latestOn && tools.PeekMsLatest", peek)
        self.assertNotIn("Latest = editing &&", peek)

    def test_the_stamp_wording(self):
        box = (SRC / "edit" / "PeekLatest.jsx").read_text(encoding="utf-8")
        self.assertIn("`Last updated ${when}${upd && upd.who ? ` by ${upd.who}` : \"\"}${sourceBit(source)}`", box)
        self.assertIn("` · Source: ${s}`", box)
        self.assertIn("`${made.who ? ` by ${made.who}` : \"\"}, ${at(made)}${sourceBit(source)}`", box)
        self.assertIn("<b data-pk-created-k>Created</b>{st.created}", box)      # "Created" bold, then "by <name>, <date time> · Source: <source>"


if __name__ == "__main__":
    unittest.main()
