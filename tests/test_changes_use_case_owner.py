"""Row 875: a use case's owner through the one writer (changes.py): text and link together, length, hidden characters, clear, one step,
one Undo, Redo, History's one Owner line, rename and merge of the person.

Run: python3 dev/run_tests.py test_changes_use_case_owner
"""
import sqlite3
import unittest

from _demo import USER, DemoStore
from clark import changes, history


class Owner(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.uc = self.demo.use_case
        self.anna = self.person("Anna Example")
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)

    def person(self, name):
        with self.s.step("dashboard", USER) as st:
            return st.add_person(name=name, source="People list")

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

    def test_a_use_case_starts_with_no_owner(self):
        self.assertEqual((self.row()["owner"], self.row()["owner_id"]), (None, None))

    def test_a_known_name_sets_the_text_and_the_link_in_one_step_with_one_undo(self):
        body = self.ok({"owner": "Anna Example"})
        self.assertEqual((self.row()["owner"], self.row()["owner_id"]), ("Anna Example", self.anna))
        self.assertEqual(body["use_case"]["owner"], "Anna Example")
        self.assertTrue(body["undoable"])
        status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual((status, undone["ok"]), (200, True), undone)
        self.assertEqual((self.row()["owner"], self.row()["owner_id"]), (None, None))

    def test_an_unknown_name_stays_text_only(self):
        self.ok({"owner": "Someone Else"})
        self.assertEqual((self.row()["owner"], self.row()["owner_id"]), ("Someone Else", None))

    def test_a_link_cannot_be_asked_for_directly(self):
        status, body = self.edit({"owner_id": self.anna})
        self.assertEqual(status, 400, body)
        self.assertIsNone(self.row()["owner_id"])

    def test_clearing_clears_both_and_says_what_it_was(self):
        self.ok({"owner": "Anna Example"})
        for none in ("", None, "   "):
            self.ok({"owner": "Anna Example"}) if self.row()["owner"] is None else None
            body = self.ok({"owner": none})
            self.assertEqual((self.row()["owner"], self.row()["owner_id"]), (None, None))
            status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
            self.assertEqual((status, undone["ok"]), (200, True), undone)
            self.assertEqual((self.row()["owner"], self.row()["owner_id"]), ("Anna Example", self.anna))
            self.ok({"owner": None})

    def test_200_characters_are_taken_and_201_refused_with_nothing_written(self):
        self.ok({"owner": "x" * 200})
        before = self.counts()
        status, body = self.edit({"owner": "y" * 201})
        self.assertEqual(status, 400, body)
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.row()["owner"], "x" * 200)

    def test_hidden_characters_and_non_text_are_refused_with_nothing_written(self):
        before = self.counts()
        for bad in ("Ann‮a", "Anna\x00", "A\nB", "A\tB", "A​B", "A\ud800", 5, ["Anna"], {"a": 1}, True):
            with self.subTest(bad=repr(bad)):
                status, body = self.edit({"owner": bad})
                self.assertEqual(status, 400, body)
                self.assertNotIn(repr(bad), body.get("message", ""))
        self.assertEqual(self.counts(), before)
        self.assertIsNone(self.row()["owner"])

    def test_the_same_owner_again_writes_nothing(self):
        self.ok({"owner": "Anna Example"})
        before = self.counts()
        body = self.ok({"owner": "Anna Example"})
        self.assertFalse(body["undoable"])
        self.assertEqual(self.counts(), before)

    def test_an_owner_and_another_field_are_one_step(self):
        before = self.counts()[0]
        self.ok({"owner": "Anna Example", "headline": "Going well"})
        self.assertEqual(self.counts()[0], before + 1)

    def test_a_new_use_case_takes_no_owner(self):
        status, body = self.change({"project": "ABC", "kind": "use_cases", "op": "new",
                                    "values": {"ref": "9.9", "title": "Fresh", "status": "On track", "headline": "", "owner": "Anna Example"}})
        self.assertEqual(status, 400, body)

    def test_the_owner_never_changes_through_the_other_project(self):
        status, body = self.change({"project": "DEF", "kind": "use_cases", "op": "update", "id": self.uc, "changes": {"owner": "Anna Example"}})
        self.assertNotEqual(status, 200)
        self.assertIsNone(self.row()["owner"])

    def test_history_has_one_owner_line_and_undo_words_name_the_use_case(self):
        body = self.ok({"owner": "Anna Example"})
        events = [e for e in history.history(self.s.con, self.uc) if e["step"] == body["apply_id"]]
        raw = [(e["field"], e["before"], e["after"]) for e in events if e["field"] in ("owner", "owner_id")]
        self.assertIn(("owner", None, "Anna Example"), raw)
        self.assertEqual(sorted(raw), [("owner", None, "Anna Example"), ("owner_id", None, self.anna)])
        shown = [r for r in history.rows_for_project(self.s.con, "ABC", "all") if (r.get("ref") == self.uc or r.get("item_id") == self.uc) and r["step"] == body["apply_id"]]
        self.assertEqual([(r["kind"], r["field"], r["from"], r["to"]) for r in shown], [("Changed", "Owner", "", "Anna Example")],
                         "one Owner line of any kind in this step, no second line for the link")
        status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual(undone["words"], "Put back: the owner of \u201cInvoice matching\u201d is cleared again.")
        body = self.ok({"owner": "Anna Example"})
        body = self.ok({"owner": "Ben Other"})
        status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual(undone["words"], "Put back: the owner of \u201cInvoice matching\u201d is back to Anna Example.")

    def test_renaming_the_person_carries_the_use_case_and_a_merge_moves_it(self):
        self.ok({"owner": "Anna Example"})
        with self.s.step("dashboard", USER) as st:
            st.rename_person(self.anna, "Anna Renamed")
        self.assertEqual((self.row()["owner"], self.row()["owner_id"]), ("Anna Renamed", self.anna))
        ben = self.person("Ben Example")
        with self.s.step("dashboard", USER) as st:
            st.merge_people(self.anna, ben)
        self.assertEqual((self.row()["owner"], self.row()["owner_id"]), ("Ben Example", ben))

    def test_the_200_limit_counts_the_stored_text_not_the_spaces_round_it(self):
        self.ok({"owner": " " + "x" * 200})
        self.assertEqual(self.row()["owner"], "x" * 200)
        self.ok({"owner": "y" * 200 + "   "})
        self.assertEqual(self.row()["owner"], "y" * 200)
        self.ok({"owner": "  " + "e\u0301" * 101})      # 202 characters typed, 101 stored
        self.assertEqual(self.row()["owner"], "\u00e9" * 101)
        for v in ("x" * 201, " " + "x" * 201 + " "):
            with self.subTest(n=len(v)):
                before = self.row()["owner"]
                status, body = self.edit({"owner": v})
                self.assertEqual(status, 400, body)
                self.assertEqual(self.row()["owner"], before)

    def test_an_archived_use_case_is_not_edited(self):
        con = sqlite3.connect(str(self.s.path))
        con.execute("UPDATE use_cases SET archived = 1 WHERE id = ?", (self.uc,))
        con.commit()
        con.close()
        before = self.counts()
        status, body = self.edit({"owner": "Anna Example"})
        self.assertNotEqual(status, 200)
        self.assertEqual(body.get("message"), changes.ARCHIVED_USE_CASE, "the fixed archived words, not a generic refusal from the store")
        self.assertIsNone(self.row()["owner"])
        self.assertEqual(self.counts(), before)

    def test_hostile_input_fuzz_is_either_clean_text_or_a_refusal_and_the_table_survives(self):
        import random
        rnd = random.Random(875)
        pool = ["\u202e", "\x00", "\n", "\t", "\u200b", "\ud800", "'; DROP TABLE use_cases;--", "<script>", "\u00e9", "e\u0301", "\U0001F600",
                "  ", "a" * 200, "a" * 201, "%s", "\\", "\u2028", "\ufeff"]
        for i in range(300):
            v = rnd.choice([None, 5, 1.5, True, [], {}, b"x"]) if i % 5 == 0 else "".join(rnd.choice(pool) for _ in range(rnd.randint(0, 5)))
            status, body = self.edit({"owner": v})
            self.assertIn(status, (200, 400), body)
            now = self.row()["owner"]
            self.assertTrue(now is None or (len(now) <= 200 and now.isprintable() and now == now.strip()), repr(now))
        self.assertEqual(self.s.con.execute("SELECT count(*) FROM use_cases").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
