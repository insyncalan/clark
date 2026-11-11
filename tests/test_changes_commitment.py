"""#709: a use case's commitment flag through the one writer (changes.py): set, clear, a bad word, Undo, History, a new use case.

Run: python3 dev/run_tests.py test_changes_commitment
"""
import sqlite3
import unittest

from _demo import USER, DemoStore
from clark import changes, history
from clark.store import COMMITMENTS


class Flag(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.uc = self.demo.use_case
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)

    def edit(self, changes_):
        return self.change({"project": "ABC", "kind": "use_cases", "op": "update", "id": self.uc, "changes": changes_})

    def ok(self, changes_):
        status, body = self.edit(changes_)
        self.assertEqual((status, body.get("message")), (200, None), body)
        return body

    def row(self):
        return self.s.read("use_cases", ref=self.uc)

    def counts(self):
        con = sqlite3.connect(str(self.s.path))
        try:
            return con.execute("SELECT (SELECT count(*) FROM applies), (SELECT count(*) FROM change_log)").fetchone()
        finally:
            con.close()

    def test_the_three_words_are_the_owners_and_the_message_names_them(self):
        self.assertEqual(changes.UC_COMMITMENTS, ("Planned 2026", "Committed", "Planned 2027"))
        self.assertEqual(changes.UC_COMMITMENT_WORDS, "A use case's commitment can be Planned 2026, Committed or Planned 2027, or none.")

    def test_a_use_case_starts_with_no_flag(self):
        self.assertIsNone(self.row()["commitment"])

    def test_each_word_is_set_in_one_step_with_one_undo(self):
        for word in COMMITMENTS:
            with self.subTest(word=word):
                body = self.ok({"commitment": word})
                self.assertEqual((self.row()["commitment"], body["use_case"]["commitment"], body["undoable"]), (word, word, True))
                status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
                self.assertEqual((status, undone["ok"]), (200, True), undone)
                self.assertIsNone(self.row()["commitment"])
                self.assertEqual(undone["words"], "Put back: the commitment of “Invoice matching” is cleared again.")

    def test_clearing_is_one_change_with_one_undo_that_says_what_it_was(self):
        self.ok({"commitment": "Committed"})
        for none in (None, ""):
            self.ok({"commitment": "Committed"}) if self.row()["commitment"] is None else None
            body = self.ok({"commitment": none})
            self.assertIsNone(self.row()["commitment"])
            self.assertTrue(body["undoable"])
            status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
            self.assertEqual(status, 200, undone)
            self.assertEqual(self.row()["commitment"], "Committed")
            self.assertEqual(undone["words"], "Put back: the commitment of “Invoice matching” is back to Committed.")

    def test_setting_the_same_flag_again_makes_no_step(self):
        self.ok({"commitment": "Planned 2026"})
        body = self.ok({"commitment": "Planned 2026"})
        self.assertEqual((body["apply_id"], body["undoable"]), (None, False))
        body = self.ok({"commitment": None}) and self.ok({"commitment": None})
        self.assertEqual(body["apply_id"], None)

    def test_a_different_spelling_or_kind_of_value_is_refused_in_plain_words_and_writes_nothing(self):
        for bad in ("committed", "COMMITTED", "Planned 2028", "Planned  2027", "Planned2027", " Committed", "Done", 1, True, ["Committed"], 0):
            with self.subTest(bad=bad):
                before = self.counts()
                status, body = self.edit({"commitment": bad})
                self.assertEqual((status, body["ok"], body["message"]), (400, False, changes.UC_COMMITMENT_WORDS), bad)
                self.assertEqual(self.counts(), before)
                self.assertIsNone(self.row()["commitment"])

    def test_history_labels_the_field_and_shows_from_and_to(self):
        self.ok({"commitment": "Planned 2027"})
        body = self.ok({"commitment": None})
        events = history.history(self.s.con, self.uc)
        made = [e for e in events if e["field"] == "commitment"]
        self.assertEqual([(e["before"], e["after"]) for e in made][:2], [("Planned 2027", None), (None, "Planned 2027")])
        self.assertEqual(history.field_name("use_cases", "commitment"), "Commitment")
        self.assertTrue(body["undoable"])

    def test_several_fields_with_the_flag_are_one_step(self):
        body = self.ok({"status": "Flag", "commitment": "Committed"})
        self.assertEqual(len({r["via"] for r in self.s.step_rows(body["apply_id"])}), 1)
        status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual(status, 200)
        self.assertEqual((self.row()["status"], self.row()["commitment"]), ("On track", None))

    def test_a_new_use_case_has_no_flag_and_may_carry_one(self):
        status, body = self.change({"project": "ABC", "kind": "use_cases", "op": "new", "values": {"ref": "7.1", "title": "Plain one"}})
        self.assertEqual(status, 200, body)
        self.assertIsNone(self.s.read("use_cases", ref=body["ref"])["commitment"])
        self.assertIsNone(body["use_case"]["commitment"])
        status, body = self.change({"project": "ABC", "kind": "use_cases", "op": "new",
                                    "values": {"ref": "7.2", "title": "Flagged one", "commitment": "Planned 2026"}})
        self.assertEqual(status, 200, body)
        self.assertEqual(self.s.read("use_cases", ref=body["ref"])["commitment"], "Planned 2026")
        before = self.counts()
        status, body = self.change({"project": "ABC", "kind": "use_cases", "op": "new",
                                    "values": {"ref": "7.3", "title": "Bad one", "commitment": "Soon"}})
        self.assertEqual((status, body["message"]), (400, changes.UC_COMMITMENT_WORDS))
        self.assertEqual(self.counts(), before)

    def test_the_store_refuses_a_wrong_word_whichever_route_writes_it(self):
        from clark.store import Invalid
        with self.assertRaises(Invalid):
            with self.s.step("excel", USER) as st:
                st.update("use_cases", self.uc, {"commitment": "committed"})


if __name__ == "__main__":
    unittest.main()
