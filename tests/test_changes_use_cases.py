"""#164: editing an existing use case through the one writer (changes.py), with Undo and history. Every field, every refusal in
plain words, hostile text, the other project's use case, and that no route adds, moves or removes a use case.

Run: python3 dev/run_tests.py test_changes_use_cases
"""
import sqlite3
import unittest
from unittest import mock

from _demo import USER, DemoStore
from clark import changes, history, server as sv


class Edit(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.uc = self.demo.use_case
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)

    def edit(self, changes_, ref="-", project="ABC", **more):
        return self.change({"project": project, "kind": "use_cases", "op": "update", "id": self.uc if ref == "-" else ref,
                            "changes": changes_, **more})

    def ok(self, changes_, **more):
        status, body = self.edit(changes_, **more)
        self.assertEqual((status, body.get("message")), (200, None), body)
        return body

    def counts(self):
        con = sqlite3.connect(str(self.s.path))
        try:
            return con.execute("SELECT (SELECT count(*) FROM applies), (SELECT count(*) FROM change_log), "
                               "(SELECT count(*) FROM use_cases)").fetchone()
        finally:
            con.close()

    def refused(self, changes_, words, **more):
        before = self.counts()
        status, body = self.edit(changes_, **more)
        self.assertEqual((status, body["ok"], body["message"]), (400, False, words), changes_)
        self.assertEqual(self.counts(), before, "nothing was written")

    def row(self):
        return self.s.read("use_cases", ref=self.uc)

    def test_each_field_changes_in_one_step_with_undo(self):
        for field, value in (("title", "Invoice checks"), ("headline", "Two suppliers left"), ("status", "Flag"),
                             ("standing", "<p>All <strong>good</strong></p>"), ("client_visible", 0)):
            with self.subTest(field=field):
                was = self.row()[field]
                body = self.ok({field: value})
                self.assertEqual(self.row()[field], value)
                self.assertTrue(body["undoable"])
                self.assertEqual(body["use_case"][field], value)
                status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
                self.assertEqual((status, undone["ok"]), (200, True), undone)
                self.assertEqual(self.row()[field], was)
                self.assertTrue(undone["words"].startswith("Put back: "), undone["words"])
                self.assertNotIn(self.uc, undone["words"])

    def test_several_fields_are_one_step_and_one_undo(self):
        body = self.ok({"title": "Matching", "status": "High risk", "headline": "Late"})
        self.assertEqual(len({r["via"] for r in self.s.step_rows(body["apply_id"])}), 1)
        status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual(status, 200)
        row = self.row()
        self.assertEqual((row["title"], row["status"], row["headline"]), ("Invoice matching", "On track", ""))
        self.assertIn("name", undone["words"])
        status, again = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual(status, 409)

    def test_a_five_field_undo_names_the_use_case_and_never_says_work_items(self):
        body = self.ok({"title": "Matching", "headline": "Late", "status": "Flag", "standing": "<p>New</p>", "client_visible": 0})
        status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual(status, 200, undone)
        self.assertEqual(undone["words"], "Put back: 5 changes to the use case.")
        self.assertNotIn("work items", undone["words"])
        self.assertNotIn("a record", undone["words"])

    def test_an_undo_of_the_undo_works_and_a_later_change_is_left_alone(self):
        first = self.ok({"headline": "One"})
        second = self.ok({"headline": "Two"})
        status, body = self.undo({"project": "ABC", "apply_id": first["apply_id"]})
        self.assertEqual(status, 200)
        self.assertEqual(self.row()["headline"], "Two", "the later change stays")
        self.assertIn("changed later", body["words"])
        self.assertEqual(second["use_case"]["headline"], "Two")

    def test_a_change_that_changes_nothing_has_no_step(self):
        body = self.ok({"status": "On track"})
        self.assertEqual((body["apply_id"], body["undoable"]), (None, False))

    def test_history_says_who_how_when_and_from_to_and_the_undo_too(self):
        body = self.ok({"status": "Flag"}, place="cell")
        status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual(status, 200)
        events = history.history(self.s.con, self.uc)
        made = [e for e in events if e["field"] == "status" and not e["is_undo"]][0]
        self.assertEqual((made["by_user"], made["route"], made["place"], made["before"], made["after"]),
                         (USER, "dashboard", "cell", "On track", "Flag"))
        self.assertTrue(made["at"])
        back = [e for e in events if e["is_undo"]][0]
        self.assertEqual((back["before"], back["after"], back["undoes"]), ("Flag", "On track", made["event_id"]))
        self.assertTrue(undone["ok"])

    def test_the_standing_text_is_cleaned(self):
        body = self.ok({"standing": '<p onclick="x()">Hi</p><script>alert(1)</script><a href="javascript:x()">l</a>'})
        for bad in ("script", "onclick", "javascript", "alert"):
            self.assertNotIn(bad, self.row()["standing"])
            self.assertNotIn(bad, body["use_case"]["standing"])
        self.assertIn("Hi", self.row()["standing"])

    def test_hostile_text_is_refused_in_plain_words(self):
        for bad in ("", "   ", "a\nb", "a‮b", "a\x00b", "x" * 121, None, 5, ["a"], {"a": 1}, True):
            with self.subTest(name=bad):
                self.refused({"title": bad}, changes.UC_NAME_WORDS)
        for bad in ("a\nb", "a​b", "x" * 301, None, 5, ["a"]):
            with self.subTest(headline=bad):
                self.refused({"headline": bad}, changes.UC_HEADLINE_WORDS)
        self.refused({"standing": 5}, changes.UC_STANDING_WORDS)
        self.refused({"standing": "x" * 300000}, changes.UC_STANDING_WORDS)
        body = self.ok({"headline": ""})
        self.assertEqual(body["use_case"]["headline"], "")

    def test_status_must_be_one_of_the_four(self):
        for bad in ("done", "Red", "on track", "", None, 1, ["Flag"], "Closed"):
            with self.subTest(status=bad):
                self.refused({"status": bad}, changes.UC_STATUS_WORDS)

    def test_the_eye_is_0_or_1_only(self):
        for bad in (True, False, 2, -1, 1.0, "1", None):
            with self.subTest(eye=bad):
                self.refused({"client_visible": bad}, changes.FLAG_WORDS)
        self.ok({"client_visible": 0})
        self.assertEqual(self.row()["client_visible"], 0)

    def test_a_partial_change_writes_nothing(self):
        self.refused({"title": "Fine", "status": "Finished"}, changes.UC_STATUS_WORDS)
        self.assertEqual(self.row()["title"], "Invoice matching")

    def test_fields_that_cannot_be_set_are_refused(self):
        for field in ("id", "project", "ref", "sort_order", "source", "archived", "updated_at", "type", "nope"):
            with self.subTest(field=field):
                status, body = self.edit({field: "x" if field != "archived" else 1})
                self.assertEqual((status, body["ok"]), (400, False))
                self.assertNotIn(self.uc, body["message"])
        self.refused({}, "Say what to change.")
        for odd in ("x", [1], 5):
            status, body = self.edit(odd)
            self.assertEqual((status, body["ok"]), (400, False))
        status, body = self.change({"project": "ABC", "kind": "use_cases", "op": "update", "id": self.uc})
        self.assertEqual(status, 400)

    def test_another_projects_use_case_and_a_missing_one_get_the_same_words(self):
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "DEF", "name": "Other Programme", "health": "On track"})
            other = st.create("use_cases", {"project": "DEF", "title": "Theirs", "status": "Flag", "source": "demo"})
        words = {self.edit({"title": "Mine now"}, ref=r)[1]["message"]
                 for r in (other, "ABC-U-099", "nonsense", "'; --", 5, None, ["x"])}
        self.assertEqual(words, {changes.UC_NOT_MINE})
        self.assertEqual(self.s.read("use_cases", ref=other)["title"], "Theirs")
        self.assertEqual(self.edit({"title": "Mine now"}, project="DEF")[0], 400)
        self.assertEqual(self.edit({"title": "x"}, project="ZZZ")[0], 404)

    def test_an_archived_use_case_is_not_edited(self):
        with self.s.step("dashboard", USER) as st:
            st.archive("use_cases", self.uc)
        self.refused({"title": "Back"}, changes.ARCHIVED_USE_CASE)

    def test_use_case_updates_always_reach_the_use_case_writer(self):
        """If another change ever sends a use case down the work item path first, this fails: that path would store the standing
        text as plain text without the rich-text cleaner, refuse the eye as not text, and reply with `item`, not `use_case`."""
        with mock.patch.object(changes, "_do_use_case_change", wraps=changes._do_use_case_change) as writer, \
                mock.patch.object(changes, "_do_item_change", wraps=changes._do_item_change) as item_path:
            body = self.ok({"standing": '<p onclick="x()">ok</p><script>bad()</script>', "client_visible": 0, "status": "Flag"})
        self.assertEqual(writer.call_count, 1)
        self.assertEqual(item_path.call_count, 0)
        self.assertEqual(self.row()["standing"], "<p>ok</p>")
        self.assertEqual(self.row()["client_visible"], 0)
        self.assertIn("use_case", body)
        self.assertNotIn("item", body)
        self.assertEqual(body["use_case"]["standing"], "<p>ok</p>")
        self.refused({"client_visible": True}, changes.FLAG_WORDS)                     # a whole number only

    def test_a_step_that_only_made_a_use_case_is_not_undone_from_here(self):
        """Undoing a creation would delete the row, and use cases are archived, never deleted."""
        with self.s.step("dashboard", USER) as st:
            made = st.create("use_cases", {"project": "ABC", "title": "Made here", "status": "Flag", "source": "demo"})
            apply_id = st.peek_apply_id()
        before = self.counts()
        status, body = self.undo({"project": "ABC", "apply_id": apply_id})
        self.assertEqual((status, body["ok"], body["message"]), (400, False, changes.NO_UNDO))
        self.assertEqual(self.counts()[2], before[2])
        self.assertEqual(self.s.read("use_cases", ref=made)["title"], "Made here")

    def test_undo_after_the_use_case_was_archived_says_to_restore_it(self):
        body = self.ok({"title": "Renamed"})
        with self.s.step("dashboard", USER) as st:
            st.archive("use_cases", self.uc)
        status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual(status, 200)
        self.assertIn("restore it first", undone["words"])
        self.assertEqual(self.row()["title"], "Renamed")

    def test_undo_is_only_for_this_project_and_this_route(self):
        body = self.ok({"title": "Renamed"})
        status, _ = self.undo({"project": "ABC", "apply_id": body["apply_id"] + 100})
        self.assertEqual(status, 400)
        with self.s.step("assistant", USER) as st:
            st.update("use_cases", self.uc, {"title": "By the assistant"})
            other = st.peek_apply_id()
        self.assertEqual(self.undo({"project": "ABC", "apply_id": other})[0], 400)


class NoCreateNoDelete(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.uc = self.demo.use_case
        self.change = changes.make_change(self.s.path, [], USER)

    def test_new_move_and_delete_are_refused_for_use_cases_and_nothing_is_made(self):
        before = self.s.read("use_cases", "ABC")
        for op, more in (("new", {"values": {"title": "Extra", "status": "Flag"}}), ("move", {"id": self.uc, "before": None}),
                         ("delete", {"id": self.uc})):
            with self.subTest(op=op):
                status, body = self.change({"project": "ABC", "kind": "use_cases", "op": op, **more})
                self.assertEqual((status, body["ok"], body["message"]), (400, False, changes.BAD_OP))
        self.assertEqual(self.s.read("use_cases", "ABC"), before)

    def test_the_kind_has_only_update_here_and_no_route_has_a_use_case_add_or_remove(self):
        self.assertEqual(set(changes.CHANGE_KINDS["use_cases"]) - {"archive", "restore"}, {"update"})
        routes = list(sv.GET_ROUTES) + list(sv.POST_ROUTES)
        self.assertEqual([r for r in routes if "use" in r or "case" in r], ["/api/use-cases"])
        self.assertIn("/api/use-cases", sv.GET_ROUTES)
        self.assertNotIn("/api/use-cases", sv.POST_ROUTES)
        for r in routes:
            self.assertFalse(any(w in r for w in ("add", "create", "delete", "remove", "new")), r)


if __name__ == "__main__":
    unittest.main()
