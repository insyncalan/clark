"""Row 1061 follow-up: a change-log line written before the word Candidate became Planned 2026 still says Candidate.

An Undo that would put that old word back must not write it: the store keeps only the three words, so the step is skipped in plain
words and the use case keeps the word it has. (History lines keep the word they were written with; see migrate_commitment_planned_2026.)

Run: python3 dev/run_tests.py test_changes_commitment_old_word
"""
import sqlite3
import unittest

from _demo import USER, DemoStore
from clark import changes


class OldWord(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)

    def test_an_undo_that_would_put_back_candidate_leaves_the_word_as_it_is_and_says_so(self):
        uc = self.demo.use_case
        status, body = self.change({"project": "ABC", "kind": "use_cases", "op": "update", "id": uc, "changes": {"commitment": "Committed"}})
        self.assertEqual(status, 200, body)
        con = sqlite3.connect(str(self.s.path))
        try:
            con.execute("UPDATE change_log SET old_value = 'Candidate' WHERE field = 'commitment'")
            con.commit()
        finally:
            con.close()
        status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual(status, 200, undone)
        self.assertEqual(undone["reversed"], [])
        self.assertEqual([s["field"] for s in undone["skipped"]], ["commitment"])
        self.assertIn("couldn't be put back", undone["words"])
        self.assertEqual(self.s.read("use_cases", ref=uc)["commitment"], "Committed")
        self.assertNotIn("cleared again", undone["words"])


if __name__ == "__main__":
    unittest.main()
