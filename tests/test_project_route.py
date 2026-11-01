"""#444 (guarded): POST /api/project, a new project and a project's edit (src/clark/project_route.py), on a real store, and the route
through the real server. Fictional data only. Run: python3 dev/run_tests.py test_project_route

What is asserted: a new project is made in ONE step with its starting words, its report sections and the workstreams named (Delivery
when none is); a taken code, a bad code, a bad name, hidden characters and too many workstreams are refused in plain words and write
nothing; an edit changes the name and client, adds the workstreams it names and closes the ones it leaves out, and an empty list
leaves them; an archived or missing project is refused; a request with a field that is not allowed is refused; the route sits behind
the same token, Host and Origin checks as every route, with its own small limit.
"""
import json
import re
import unittest

from _demo import DemoStore
from clark import project_route
from test_word_route import Up

USER = "Dana Ellis"
JARGON = r"(?i)\bsql\b|\bjson\b|traceback|exception|errno|\bschema\b|\bapply_id\b"


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        self.seam = project_route.make_project(self.store.path, [], USER)

    def post(self, **req):
        return self.seam(req)

    def counts(self):
        con = self.store.con
        return {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("projects", "workstreams", "applies", "change_log", "report_sections")}

    def streams(self, code="ABC"):
        return {w["name"]: w["status"] for w in self.store.read("workstreams", project=code)}


class New(Base):
    def test_a_new_project_is_one_step_with_the_starting_words_sections_and_the_workstreams_named(self):
        before = self.counts()
        status, got = self.post(op="new", code="newco", name="  New   Company ", client="Example Client", workstreams=["Build", "Run", "build"])
        self.assertEqual((status, got["ok"], got["code"], got["name"]), (200, True, "NEWCO", "New Company"), got)
        row = self.store.read("projects", ref="NEWCO")
        self.assertEqual((row["name"], row["client_name"], row["health"], row["health_reason"], row["archived"]),
                         ("New Company", "Example Client", "On track", "Just started.", 0))
        self.assertEqual(self.streams("NEWCO"), {"Build": "Active", "Run": "Active"})
        after = self.counts()
        self.assertEqual(after["applies"], before["applies"] + 1)
        self.assertGreater(after["report_sections"], before["report_sections"])
        self.assertEqual(self.store.read("workstreams", project="NEWCO")[0]["source"], project_route.SOURCE)
        self.assertEqual({r["via"] for r in self.store.step_rows(got["apply_id"]) if r["table"] == "projects"}, {"dashboard"})

    def test_no_workstreams_named_gives_delivery_and_no_client_is_none(self):
        for ws in (None, [], ["", "  "]):
            code = "N" + str(len(self.store.read("projects")))
            status, got = self.post(op="new", code=code + "AA", name="Fresh", workstreams=ws)
            self.assertEqual(status, 200, got)
            self.assertEqual(self.streams(code + "AA"), {"Delivery": "Active"})
            self.assertIsNone(self.store.read("projects", ref=code + "AA")["client_name"])

    def test_a_taken_code_archived_or_not_is_refused_and_writes_nothing(self):
        self.post(op="new", code="GONE", name="Gone")
        self.store.con.execute("UPDATE projects SET active = 0, archived = 1 WHERE code = 'GONE'")
        self.store.con.commit()
        before = self.counts()
        for code in ("ABC", "abc", "GONE"):
            status, got = self.post(op="new", code=code, name="Again")
            self.assertEqual((status, got["code"], got["message"]), (409, "code_taken", project_route.TAKEN), code)
        self.assertEqual(self.counts(), before)

    def test_a_bad_code_name_or_workstream_is_refused_in_words_and_writes_nothing(self):
        before = self.counts()
        cases = [({"code": "AB", "name": "X"}, project_route.BAD_CODE), ({"code": "ABCDEFGH", "name": "X"}, project_route.BAD_CODE),
                 ({"code": "1ABC", "name": "X"}, project_route.BAD_CODE), ({"code": "AB-C", "name": "X"}, project_route.BAD_CODE),
                 ({"code": 5, "name": "X"}, project_route.BAD_CODE), ({"code": "NEWC", "name": ""}, project_route.NO_NAME),
                 ({"code": "NEWC", "name": "   "}, project_route.NO_NAME), ({"code": "NEWC", "name": "x" * 121}, project_route.LONG_NAME),
                 ({"code": "NEWC", "name": "a‮b"}, project_route.BAD_TEXT), ({"code": "NEWC", "name": 7}, project_route.BAD_TEXT),
                 ({"code": "NEWC", "name": "X", "client": "y" * 121}, project_route.LONG_CLIENT),
                 ({"code": "NEWC", "name": "X", "workstreams": "Build"}, project_route.BAD_WORKSTREAMS),
                 ({"code": "NEWC", "name": "X", "workstreams": [1]}, project_route.BAD_WORKSTREAMS),
                 ({"code": "NEWC", "name": "X", "workstreams": ["w" * 61]}, project_route.LONG_WORKSTREAM),
                 ({"code": "NEWC", "name": "X", "workstreams": [f"w{i}" for i in range(13)]}, project_route.TOO_MANY)]
        for req, words in cases:
            status, got = self.post(op="new", **req)
            self.assertEqual((status, got["ok"], got["message"]), (400, False, words), req)
            self.assertIsNone(re.search(JARGON, got["message"]), got["message"])
        self.assertEqual(self.counts(), before)

    def test_a_request_with_something_that_is_not_allowed_or_not_an_object_is_refused(self):
        before = self.counts()
        for req in ({"op": "new", "code": "NEWC", "name": "X", "health": "At risk"}, {"op": "delete", "code": "NEWC", "name": "X"}, {"code": "NEWC", "name": "X"},
                    [], "x", None):
            status, got = self.seam(req)
            self.assertEqual((status, got["ok"]), (400, False), req)
        self.assertEqual(self.counts(), before)


class Edit(Base):
    def test_an_edit_changes_the_name_and_client_adds_new_workstreams_and_closes_the_ones_left_out(self):
        status, got = self.post(op="edit", code="ABC", name="Renamed", client="Client Co", workstreams=["Run", "Test"])
        self.assertEqual((status, got["ok"], got["name"]), (200, True, "Renamed"), got)
        row = self.store.read("projects", ref="ABC")
        self.assertEqual((row["name"], row["client_name"], row["code"]), ("Renamed", "Client Co", "ABC"))
        self.assertEqual(self.streams(), {"Build": "Closed", "Run": "Active", "Test": "Active"})
        self.assertEqual(len(self.store.step_rows(got["apply_id"])) > 0, True)

    def test_keeping_a_workstream_in_any_case_keeps_it_and_an_empty_list_leaves_them_all(self):
        status, got = self.post(op="edit", code="ABC", name="Example Programme", client="", workstreams=["BUILD"])
        self.assertEqual((status, got["apply_id"]), (200, None), got)          # nothing changed: no step, so no row to undo
        self.assertEqual(self.streams(), {"Build": "Active"})
        self.post(op="edit", code="ABC", name="Example Programme", client="", workstreams=[])
        self.assertEqual(self.streams(), {"Build": "Active"})

    def test_the_code_in_the_request_is_the_project_and_is_never_changed(self):
        self.post(op="new", code="OTHER", name="Other One")
        self.post(op="edit", code="other", name="Other Two")
        self.assertEqual([p["name"] for p in self.store.read("projects") if p["code"] in ("ABC", "OTHER")], ["Example Programme", "Other Two"])

    def test_a_missing_or_archived_project_is_refused_and_writes_nothing(self):
        status, got = self.post(op="edit", code="NOPE", name="X")
        self.assertEqual((status, got["code"], got["message"]), (404, "project_not_found", project_route.NOT_FOUND))
        self.store.con.execute("UPDATE projects SET active = 0, archived = 1 WHERE code = 'ABC'")
        self.store.con.commit()
        before = self.counts()
        status, got = self.post(op="edit", code="ABC", name="X")
        self.assertEqual((status, got["code"], got["message"]), (409, "archived", project_route.ARCHIVED))
        self.assertEqual(self.counts(), before)

    def test_a_workstream_that_is_closed_and_named_again_is_refused_in_the_stores_words(self):
        self.post(op="edit", code="ABC", name="Example Programme", workstreams=["Run"])         # Build is closed now
        before = self.counts()
        status, got = self.post(op="edit", code="ABC", name="Example Programme", workstreams=["Build"])
        self.assertEqual((status, got["ok"]), (400, False), got)
        self.assertIn("Build", got["message"])
        self.assertEqual(self.counts(), before)


class ThroughTheServer(unittest.TestCase):
    ROUTE = "/api/project"

    def setUp(self):
        self.calls = []
        self.up = Up()
        self.up.httpd.project_save = lambda r: (self.calls.append(r) or (200, {"ok": True}))
        self.addCleanup(self.up.close)

    def test_without_the_right_token_host_and_origin_the_seam_is_never_called(self):
        for token in (None, "", "wrong"):
            self.assertEqual(self.up.ask(self.ROUTE, b"{}", token=token)[0], 403, token)
        self.assertEqual(self.up.ask(self.ROUTE, b"{}", host="evil.example")[0], 403)
        for extra in ({"Origin": "https://evil.example"}, {"Origin": "null"}, {"Sec-Fetch-Site": "cross-site"}):
            self.assertEqual(self.up.ask(self.ROUTE, b"{}", headers=extra)[0], 403, extra)
        self.assertEqual(self.up.ask(self.ROUTE, b"{}", method="GET")[0], 404)
        self.assertEqual(self.calls, [])

    def test_json_only_a_small_body_and_no_seam_is_503(self):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.up.port, timeout=10)
        conn.request("POST", self.ROUTE, b"{}", {self.up.sv.TOKEN_HEADER: self.up.sv.TOKEN, "Content-Type": "text/plain"})
        self.assertEqual(conn.getresponse().status, 415)
        conn.close()
        self.assertEqual(self.up.ask(self.ROUTE, b"{nope")[0], 400)
        big = json.dumps({"name": "x" * 5000}).encode()
        self.assertEqual(self.up.ask(self.ROUTE, big)[1]["code"], "too_large")
        self.assertEqual(self.calls, [])
        self.assertEqual(self.up.ask(self.ROUTE, b"{}")[0], 200)
        bare = Up()
        self.addCleanup(bare.close)
        status, body = bare.ask(self.ROUTE, b"{}")
        self.assertEqual((status, body["code"]), (503, "saving_off"))


if __name__ == "__main__":
    unittest.main()
