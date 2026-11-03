"""#45: a use case's status word changed through POST /api/change and undone through /api/undo (src/clark/changes.py; guarded).

Run: python3 dev/run_tests.py test_changes_use_case_status
Each test makes a real store in a temporary folder (fictional data) and calls the same functions the server calls.
"""
import sqlite3
import unittest

from _demo import USER, DemoStore
from clark import changes, store as store_module


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.uc = self.demo.use_case
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "DEF", "name": "Other Programme", "health": "On track"})
            self.other = st.create("use_cases", {"project": "DEF", "title": "Elsewhere", "status": "On track", "source": "demo"})

    def req(self, ref=None, project="ABC", **changes_):
        return {"project": project, "kind": "use_cases", "op": "update", "id": self.uc if ref is None else ref, "changes": changes_}

    def snapshot(self):
        con = sqlite3.connect(str(self.s.path))
        try:
            return (con.execute("SELECT count(*) FROM applies").fetchone()[0], con.execute("SELECT count(*) FROM change_log").fetchone()[0],
                    con.execute("SELECT group_concat(id || status || title) FROM use_cases").fetchone()[0])
        finally:
            con.close()

    def refused(self, request, words):
        before = self.snapshot()
        got = self.change(request)
        self.assertEqual((got[0], got[1]["ok"], got[1]["message"]), (400, False, words), request)
        self.assertEqual(self.snapshot(), before, "nothing was written")


class Status(Base):
    def test_the_kind_takes_the_status_and_every_field_is_a_column(self):
        # #164's kind is the one use_cases kind; the status menu uses only its `status` field
        self.assertIn("status", changes.CHANGE_KINDS["use_cases"]["update"])
        self.assertTrue(set(changes.CHANGE_KINDS["use_cases"]["update"]) <= set(store_module.columns(self.s.con, "use_cases")))
        self.assertIn("status", changes.UNDOABLE["use_cases"])
        self.assertIn("archived", changes.UNDOABLE["use_cases"])

    def test_each_status_is_one_step_with_one_undo(self):
        for to in ("Flag", "High risk", "Done"):
            before = self.s.read("use_cases", ref=self.uc)["status"]
            status, body = self.change(self.req(status=to))
            self.assertEqual((status, body["ok"]), (200, True), body)
            self.assertEqual(body["use_case"]["status"], to)
            self.assertEqual(self.s.read("use_cases", ref=self.uc)["status"], to)
            self.assertTrue(body["undoable"])
            code, back = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
            self.assertEqual(code, 200, back)
            self.assertEqual(back["words"], f"Put back: the status of “Invoice matching” is back to {before}.")
            self.assertEqual(self.s.read("use_cases", ref=self.uc)["status"], before)
            self.assertEqual(self.undo({"project": "ABC", "apply_id": body["apply_id"]})[0], 409, "twice is refused")

    def test_the_same_status_makes_no_step(self):
        before = self.snapshot()
        status, body = self.change(self.req(status="On track"))
        self.assertEqual(status, 200)
        self.assertIsNone(body["apply_id"])
        self.assertFalse(body["undoable"])
        self.assertEqual(self.snapshot(), before)

    def test_a_status_the_store_does_not_have_is_refused_in_plain_words(self):
        for bad in ("done", "Closed", "on track", "", None, 3, ["Flag"], "Flag\n", "Done "):
            self.refused(self.req(status=bad), changes.UC_STATUS_WORDS)       # main's #164 kind has one set of words for every bad status

    def test_done_is_a_status_and_the_refusal_names_all_four(self):
        """#412: Done is the fourth status; the refusal names every status the store allows, in its order."""
        self.assertEqual(store_module.ALLOWED[("use_cases", "status")], ("On track", "Flag", "High risk", "Done"))
        self.assertEqual(changes.UC_STATUS_WORDS, "A use case's status can be On track, Flag, High risk or Done.")
        status, body = self.change(self.req(status="Done"))
        self.assertEqual((status, body["ok"], body["use_case"]["status"]), (200, True, "Done"), body)
        self.assertEqual(self.s.read("use_cases", ref=self.uc)["status"], "Done")

    def test_a_field_that_is_not_the_kinds_is_refused(self):
        for field in ("project", "sort_order", "id", "type"):
            before = self.snapshot()
            got = self.change(self.req(**{field: "x"}))
            self.assertEqual((got[0], got[1]["ok"]), (400, False), field)
            self.assertEqual(self.snapshot(), before, field)
        self.refused(self.req(archived=1), "The field 'archived' can't be set here.")

    def test_another_projects_use_case_and_a_missing_one_get_the_same_words(self):
        self.refused(self.req(self.other, status="Flag"), changes.UC_NOT_MINE)
        self.refused(self.req("ABC-U-777", status="Flag"), changes.UC_NOT_MINE)
        self.refused(self.req(self.uc, project="DEF", status="Flag"), changes.UC_NOT_MINE)
        self.refused(self.req(["x"], status="Flag"), changes.UC_NOT_MINE)

    def test_an_archived_use_case_is_not_changed(self):
        with self.s.step("dashboard", USER) as st:
            st.archive("use_cases", self.uc)
        self.refused(self.req(status="Flag"), changes.ARCHIVED_USE_CASE)

    def test_no_new_move_or_delete_for_use_cases(self):
        for op in ("new", "move", "delete"):
            self.refused({"project": "ABC", "kind": "use_cases", "op": op, "id": self.uc}, changes.BAD_OP)

    def test_undo_is_refused_when_the_status_was_changed_since(self):
        _, body = self.change(self.req(status="Flag"))
        self.change(self.req(status="High risk"))
        code, back = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual(self.s.read("use_cases", ref=self.uc)["status"], "High risk", back)
        self.assertIn("was changed later", back.get("words", "") + str(back.get("message", "")))

    def test_a_step_that_changed_another_field_is_not_undone_from_here(self):
        with self.s.step("dashboard", USER) as st:
            st.update("use_cases", self.uc, {"sort_order": 5000})
        apply_id = self.demo.last_step()
        code, body = self.undo({"project": "ABC", "apply_id": apply_id})
        self.assertEqual(code, 400, body)
        self.assertEqual(self.s.read("use_cases", ref=self.uc)["sort_order"], 5000)

    def test_archive_and_restore_still_work_and_are_named_by_id(self):
        _, body = self.change({"project": "ABC", "kind": "use_cases", "op": "archive", "id": self.uc})
        self.assertEqual(self.s.read("use_cases", ref=self.uc)["archived"], 1)
        code, back = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual((code, self.s.read("use_cases", ref=self.uc)["archived"]), (200, 0))


if __name__ == "__main__":
    unittest.main()
