"""#126: archive and restore through the routes (changes.py and server.py): every kind and op, every refusal in plain words,
Undo of an archive from the route, and the Undo check that looks at the FIELD, not just the table.

Run: python3 dev/run_tests.py test_changes_archive
"""
import json
import sqlite3
import threading
import unittest
import urllib.error
import urllib.request

from _demo import USER, DemoStore
from clark import changes, server as sv
from clark.store import connect


class Routes(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)
        self.action = self.demo.action()
        with self.s.step("dashboard", USER) as st:
            self.raid = st.create("raid", {"project": "ABC", "type": "Risk", "description": "d", "raised": "2026-10-01", "source": "demo"})
            self.dec = st.create("decisions", {"project": "ABC", "decision": "Go", "date": "2026-10-01", "source": "demo"})
        self.s.con.execute("INSERT INTO documents (project, id, title, url, sort_order) VALUES ('ABC', 'd1', 'Plan', 'https://example.org/p', 1)")
        self.refs = {"milestones": self.demo.milestone, "actions": self.action, "raid": self.raid, "decisions": self.dec,
                     "use_cases": self.demo.use_case, "documents": "ABC|d1"}

    def send(self, kind, op, ref, **more):
        return self.change({"project": "ABC", "kind": kind, "op": op, "id": ref, **more})

    def flag(self, kind, ref):
        return self.s.read(kind, ref=ref)["archived"]

    def counts(self):
        con = sqlite3.connect(str(self.s.path))
        try:
            return con.execute("SELECT (SELECT count(*) FROM applies), (SELECT count(*) FROM change_log)").fetchone()
        finally:
            con.close()

    def refused(self, request, words=None):
        before = self.counts()
        status, body = self.change(request)
        self.assertEqual((status, body["ok"]), (400, False), request)
        if words:
            self.assertEqual(body["message"], words, request)
        self.assertEqual(self.counts(), before, "nothing was written")
        return body

    def test_every_kind_archives_and_restores(self):
        for kind, ref in self.refs.items():
            with self.subTest(kind=kind):
                status, body = self.send(kind, "archive", ref, place="menu")
                self.assertEqual((status, body["ok"], body["ref"], body["archived"]), (200, True, ref, 1), body)
                self.assertEqual(self.flag(kind, ref), 1)
                status, body = self.send(kind, "restore", ref)
                self.assertEqual((status, body["archived"]), (200, 0), body)
                self.assertEqual(self.flag(kind, ref), 0)

    def test_a_project_archive_says_how_many_went_with_it_and_holds_no_text(self):
        status, body = self.send("projects", "archive", "ABC")
        self.assertEqual(status, 200, body)
        self.assertEqual(body["counts"]["actions"], 1)
        self.assertEqual(body["counts"]["documents"], 1)
        self.assertNotIn("Draft the cut-over plan", json.dumps(body))
        self.assertEqual(set(body), {"ok", "apply_id", "ref", "archived", "counts"})
        status, body = self.send("projects", "restore", "ABC")
        self.assertEqual((status, body["archived"], body["counts"]["actions"]), (200, 0, 1))

    def test_the_refusals_are_the_same_plain_words(self):
        mine = self.refs["actions"]
        for bad_kind in ("workstreams", "links", "labels", "report_hidden", "Actions", "actions "):
            self.refused({"project": "ABC", "kind": bad_kind, "op": "archive", "id": mine}, changes.BAD_KIND)
        self.refused({"project": "ABC", "kind": "glance_tiles", "op": "archive", "id": "ABC|risks"}, changes.BAD_OP)   # a tile has no archive
        self.refused({"project": "ABC", "kind": "actions", "op": "delete", "id": mine}, changes.BAD_OP)
        self.refused({"project": "ABC", "kind": "actions", "op": "cancel", "id": mine}, changes.BAD_OP)
        self.refused({"project": "ABC", "kind": "actions", "op": "archive", "id": mine, "colour": "red"}, "clark doesn't know 'colour' in that request.")
        self.refused({"project": "ABC", "kind": "actions", "op": "archive", "id": mine, "changes": {"archived": 1}},
                     "That change doesn't take 'changes'.")
        self.refused({"project": "ABC", "kind": "actions", "op": "archive", "id": mine, "values": {"archived": 1}},
                     "That change doesn't take 'values'.")
        self.refused({"project": "ABC", "kind": "actions", "op": "archive", "id": mine, "archived": 1},
                     "clark doesn't know 'archived' in that request.")
        for ref in (None, 5, ["ABC-A-001"], {"id": mine}, "", "ABC-A-999", "XYZ-A-001"):
            self.refused({"project": "ABC", "kind": "actions", "op": "archive", "id": ref}, changes.NOT_MINE_RECORD)
        self.refused({"project": "abc", "kind": "actions", "op": "archive", "id": mine}, changes.BAD_PROJECT)

    def test_another_projects_record_and_a_missing_one_get_the_same_words(self):
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "ABCD", "name": "Other Programme"})
        other = self.demo.action(project="ABCD")
        self.assertTrue(other.startswith("ABCD-A-"))
        self.assertFalse(changes._belongs("actions", other, "ABC"))          # the dash is part of the test: ABC never matches ABCD-
        a = self.refused({"project": "ABC", "kind": "actions", "op": "archive", "id": other}, changes.NOT_MINE_RECORD)
        b = self.refused({"project": "ABC", "kind": "actions", "op": "archive", "id": "ABC-A-777"}, changes.NOT_MINE_RECORD)
        self.assertEqual(a["message"], b["message"])
        self.assertEqual(self.flag("actions", other), 0)

    def test_a_lone_surrogate_id_is_not_mine_and_is_not_a_server_fault(self):
        for kind in ("actions", "projects", "documents"):
            for op in ("archive", "restore"):
                self.refused({"project": "ABC", "kind": kind, "op": op, "id": "\ud800"}, changes.NOT_MINE_RECORD)
                self.refused({"project": "ABC", "kind": kind, "op": op, "id": "ABC-A-001\ud800"}, changes.NOT_MINE_RECORD)
        self.assertFalse(changes._belongs("documents", "ABC|\udfff", "ABC"))

    def test_an_item_is_not_put_on_an_archived_milestone_or_use_case_and_the_words_say_why(self):
        status, body = self.send("milestones", "archive", self.demo.milestone)
        self.assertEqual(status, 200, body)
        self.refused({"project": "ABC", "kind": "actions", "op": "update", "id": self.action, "place": "cell",
                      "changes": {"milestone": self.demo.milestone}}, changes.ARCHIVED_MILESTONE)
        # the route sets no use case on a work item yet; the store's sentence is still put into plain words, not the catch-all
        from clark.store import Invalid
        self.assertEqual(changes._store_words(Invalid("Use case ABC-U-001 is archived. Restore it first.")), changes.ARCHIVED_USE_CASE)
        self.assertEqual(changes.ARCHIVED_MILESTONE, "That milestone is archived. Restore it first.")
        self.assertNotEqual(changes.ARCHIVED_MILESTONE, changes.ITEM_VALUE_WORDS)

    def test_a_projects_id_must_be_the_requests_project(self):
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "ABCD", "name": "Other Programme"})
        self.refused({"project": "ABC", "kind": "projects", "op": "archive", "id": "ABCD"}, changes.NOT_MINE_RECORD)
        self.refused({"project": "ABC", "kind": "projects", "op": "archive", "id": "XYZ"}, changes.NOT_MINE_RECORD)
        self.assertEqual(self.flag("projects", "ABCD"), 0)

    def test_a_document_of_another_project_is_refused(self):
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "ABCD", "name": "Other Programme"})
        self.s.con.execute("INSERT INTO documents (project, id, title, url, sort_order) VALUES ('ABCD', 'd9', 'X', 'https://example.org/x', 1)")
        self.refused({"project": "ABC", "kind": "documents", "op": "archive", "id": "ABCD|d9"}, changes.NOT_MINE_RECORD)

    def test_archive_twice_and_restore_of_a_live_row_are_plain_refusals(self):
        self.assertEqual(self.send("actions", "archive", self.action)[0], 200)
        status, body = self.send("actions", "archive", self.action)
        self.assertEqual((status, body["ok"]), (400, False))
        status, body = self.send("actions", "restore", self.refs["raid"])
        self.assertEqual((status, body["ok"]), (400, False))

    def test_a_request_cannot_name_a_table_or_a_column(self):
        for more in ({"table": "actions"}, {"column": "archived"}, {"sql": "x"}, {"field": "archived"}):
            self.refused({"project": "ABC", "kind": "actions", "op": "archive", "id": self.action, **more})

    def test_undo_of_an_archive_and_of_a_project_archive_through_the_route(self):
        step = self.send("actions", "archive", self.action)[1]["apply_id"]
        status, body = self.undo({"project": "ABC", "apply_id": step})
        self.assertEqual(status, 200, body)
        self.assertEqual(body["words"], f"Undone: {self.action} restored.")
        self.assertEqual(self.flag("actions", self.action), 0)
        step = self.send("projects", "archive", "ABC")[1]["apply_id"]
        status, body = self.undo({"project": "ABC", "apply_id": step})
        self.assertEqual(status, 200, body)
        self.assertEqual(self.flag("projects", "ABC"), 0)
        self.assertEqual(self.s.read("projects", ref="ABC")["active"], 1)
        self.assertEqual(self.flag("actions", self.action), 0)
        self.assertNotIn(self.action, json.dumps(body["words"]))
        step = self.send("projects", "archive", "ABC")[1]["apply_id"]
        self.assertEqual(self.send("projects", "restore", "ABC")[0], 200)
        restore_step = self.demo.last_step()
        status, body = self.undo({"project": "ABC", "apply_id": restore_step})        # Undo of a project restore
        self.assertEqual(status, 200, body)
        self.assertEqual(self.flag("projects", "ABC"), 1)

    def test_undo_still_refuses_a_step_that_edited_a_title_in_these_tables(self):
        edit = self.demo.update("actions", self.action, {"description": "Changed"})
        status, body = self.undo({"project": "ABC", "apply_id": edit})
        self.assertEqual((status, body["message"]), (400, changes.NO_UNDO))
        ms = self.demo.update("milestones", self.demo.milestone, {"name": "Renamed"})
        self.assertEqual(self.undo({"project": "ABC", "apply_id": ms})[1]["message"], changes.NO_UNDO)
        proj = self.demo.update("projects", "ABC", {"name": "Renamed Programme"})
        self.assertEqual(self.undo({"project": "ABC", "apply_id": proj})[1]["message"], changes.NO_UNDO)
        self.assertEqual(self.s.read("actions", ref=self.action)["description"], "Changed")

    def test_eligibility_checks_the_field_and_the_dash(self):
        row = lambda table, key, field, via="dashboard": {"table": table, "key": key, "field": field, "via": via}   # noqa: E731
        ok = changes._eligible
        self.assertTrue(ok([row("actions", "ABC-A-001", "archived")], "ABC"))
        self.assertFalse(ok([row("actions", "ABC-A-001", "description")], "ABC"))
        self.assertTrue(ok([row("actions", "ABC-A-001", "archived"), row("actions", "ABC-A-001", "updated_at")], "ABC"))
        self.assertFalse(ok([row("actions", "ABC-A-001", "updated_at")], "ABC"))                 # a stamp alone is some other edit
        self.assertFalse(ok([row("actions", "ABC-A-001", "description"), row("actions", "ABC-A-001", "updated_at")], "ABC"))
        self.assertFalse(ok([row("actions", "ABC-A-001", "archived"), row("actions", "ABC-A-002", "updated_at")], "ABC"))
        self.assertFalse(ok([row("actions", "ABCD-A-001", "archived")], "ABC"))
        self.assertFalse(ok([row("documents", "ABCD|d1", "archived")], "ABC"))
        self.assertTrue(ok([row("documents", "ABC|d1", "archived")], "ABC"))
        self.assertTrue(ok([row("report_sections", "ABC-S-001", "title")], "ABC"))
        self.assertFalse(ok([row("report_sections", "ABCD-S-001", "title")], "ABC"))
        self.assertFalse(ok([row("actions", "ABC-A-001", "archived", "import")], "ABC"))
        self.assertFalse(ok([row("actions", "ABC-A-001", "archived", "revert:dashboard")], "ABC"))
        self.assertFalse(ok([], "ABC"))
        # the project's own row: the bare code, and `active` only inside its own archive or restore step
        self.assertTrue(ok([row("actions", "ABC-A-001", "archived"), row("projects", "ABC", "archived"), row("projects", "ABC", "active")], "ABC"))
        self.assertFalse(ok([row("projects", "ABC", "active")], "ABC"))
        self.assertFalse(ok([row("projects", "ABC", "name")], "ABC"))
        self.assertFalse(ok([row("projects", "ABCD", "archived")], "ABC"))
        self.assertFalse(ok([row("projects", "ABC", "archived"), row("actions", "ABCD-A-001", "archived")], "ABC"))
        self.assertFalse(ok([row("workstreams", "ABC-W-001", "archived")], "ABC"))          # only inside a project step
        self.assertTrue(ok([row("projects", "ABC", "archived"), row("workstreams", "ABC-W-001", "archived")], "ABC"))
        self.assertFalse(ok([row("links", "ABC-A-001", "archived")], "ABC"))
        # #126 LOWs: the project's stamp only beside its own flag, active or health change; a step is one family
        self.assertFalse(ok([row("projects", "ABC", "updated_at")], "ABC"))
        self.assertFalse(ok([row("actions", "ABC-A-001", "archived"), row("projects", "ABC", "updated_at")], "ABC"))
        self.assertTrue(ok([row("projects", "ABC", "archived"), row("projects", "ABC", "updated_at")], "ABC"))
        self.assertTrue(ok([row("projects", "ABC", "health"), row("projects", "ABC", "updated_at")], "ABC"))
        self.assertFalse(ok([row("actions", "ABC-A-001", "archived"), row("report_sections", "ABC-S-001", "title")], "ABC"))
        self.assertFalse(ok([row("actions", "ABC-A-001", "archived"), row("projects", "ABC", "health")], "ABC"))
        self.assertFalse(ok([row("actions", "ABC-A-001", "archived"), row("glance_tiles", "ABC|risks", "hidden")], "ABC"))
        self.assertFalse(ok([row("actions", "ABC-A-001", "status"), row("actions", "ABC-A-001", "archived")], "ABC"))


class Gets(unittest.TestCase):
    """GET /api/data?archived= and GET /api/projects?archived=1 are checked against a fixed list, never passed on."""

    def setUp(self):
        self.calls = []
        self.httpd = sv.LocalServer(
            (sv.HOST, 0),
            data_for=lambda code, archived="hide": self.calls.append(("data", code, archived)) or {"project": {"code": code}},
            page_html=lambda: "<html></html>",
            projects=lambda archived=False: self.calls.append(("projects", archived)) or [{"code": "ABC", "name": "Example Programme"}])
        self.port = self.httpd.server_address[1]
        t = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        t.start()
        self.addCleanup(lambda: (self.httpd.shutdown(), self.httpd.server_close()))

    def get(self, path):
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", headers={sv.TOKEN_HEADER: sv.TOKEN})
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_data_takes_hide_show_only(self):
        for mode in ("hide", "show", "only"):
            self.assertEqual(self.get(f"/api/data?project=ABC&archived={mode}")[0], 200)
        self.assertEqual(self.calls, [("data", "ABC", "hide"), ("data", "ABC", "show"), ("data", "ABC", "only")])
        self.assertEqual(self.get("/api/data?project=ABC")[0], 200)
        self.assertEqual(self.calls[-1], ("data", "ABC", "hide"))

    def test_data_refuses_an_unknown_value_without_calling_the_store(self):
        self.calls.clear()
        for mode in ("all", "1", "", "HIDE", "show;x"):
            status, body = self.get(f"/api/data?project=ABC&archived={mode}")
            self.assertEqual((status, body["code"], body["message"]), (400, "bad_archived", sv.MESSAGES["bad_archived"]), mode)
        self.assertEqual(self.calls, [])

    def test_projects_takes_only_one(self):
        self.assertEqual(self.get("/api/projects")[0], 200)
        self.assertEqual(self.get("/api/projects?archived=1")[0], 200)
        self.assertEqual(self.calls, [("projects", False), ("projects", True)])
        self.calls.clear()
        for value in ("0", "yes", "", "true"):
            self.assertEqual(self.get(f"/api/projects?archived={value}")[1]["code"], "bad_archived", value)
        self.assertEqual(self.calls, [])

    def test_more_than_one_archived_value_is_refused(self):
        self.calls.clear()
        for path in ("/api/data?project=ABC&archived=hide&archived=only", "/api/data?project=ABC&archived=show&archived=show",
                     "/api/projects?archived=1&archived=0", "/api/projects?archived=1&archived=1"):
            status, body = self.get(path)
            self.assertEqual((status, body["code"]), (400, "bad_archived"), path)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
