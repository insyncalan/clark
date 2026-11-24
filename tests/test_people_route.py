"""#115: GET and POST /api/people and POST /api/people/undo: the server's usual checks plus the seams in changes.py.
Fictional names. Run: python3 dev/run_tests.py test_people_route"""
import http.client
import json
import threading
import unittest

import _paths  # noqa: F401
from _demo import USER, DemoStore
from clark import changes
from clark import server as sv


class Running:
    def __init__(self, **seams):
        self.httpd = sv.LocalServer((sv.HOST, 0), **seams)
        self.port = self.httpd.server_port
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def call(self, method, path, obj=None, token=None, ctype="application/json"):
        body = None if obj is None else (obj if isinstance(obj, bytes) else json.dumps(obj).encode())
        conn = http.client.HTTPConnection(sv.HOST, self.port, timeout=10)
        try:
            conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            conn.putheader("Host", f"127.0.0.1:{self.port}")
            conn.putheader(sv.TOKEN_HEADER, sv.TOKEN if token is None else token)
            if body is not None:
                conn.putheader("Content-Type", ctype)
                conn.putheader("Content-Length", str(len(body)))
            conn.endheaders(body)
            r = conn.getresponse()
            raw = r.read()
            try:
                return r.status, json.loads(raw)
            except ValueError:
                return r.status, raw
        finally:
            conn.close()


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.path = self.demo.store.path
        self.demo.store.close()
        self.addCleanup(self.demo.close)
        self.srv = Running(people=changes.make_people(self.path, [], USER), people_undo=changes.make_people_undo(self.path, [], USER),
                           people_list=changes.make_people_list(self.path, [], USER))
        self.addCleanup(self.srv.close)

    def post(self, obj, path="/api/people"):
        return self.srv.call("POST", path, obj)

    def add(self, name, **kw):
        status, body = self.post({"op": "add", "name": name, **kw})
        self.assertEqual(status, 200, body)
        return body


class Writers(Base):
    def test_add_returns_the_id_the_step_and_the_list(self):
        body = self.add("Sam Reed", email="Sam@X.example")
        self.assertEqual((body["id"], body["items"]), ("P-001", 0))
        self.assertIsInstance(body["apply_id"], int)
        self.assertEqual([(p["id"], p["email"]) for p in body["people"]], [("P-001", "sam@x.example")])
        self.assertEqual(self.srv.call("GET", "/api/people")[1]["people"], body["people"])

    def test_edit_rename_archive_restore(self):
        pid = self.add("Sam Reed")["id"]
        self.assertEqual(self.post({"op": "edit", "id": pid, "changes": {"role": "Lead"}})[0], 200)
        status, body = self.post({"op": "rename", "id": pid, "name": "Sam Reid"})
        self.assertEqual((status, body["people"][0]["name"], body["people"][0]["role"]), (200, "Sam Reid", "Lead"))
        self.assertEqual(self.post({"op": "archive", "id": pid})[1]["people"][0]["archived"], 1)
        self.assertEqual(self.post({"op": "restore", "id": pid})[1]["people"][0]["archived"], 0)

    def test_merge_carries_the_items_and_says_how_many(self):
        a, b = self.add("Sam Reed")["id"], self.add("Sam Reid")["id"]
        s = clark_open(self.path)
        with s.step("dashboard", USER) as st:
            ref = st.create("actions", {"project": "ABC", "description": "Do it", "raised": "2026-10-01", "source": "t", "owner": "Sam Reed"})
            st.update("actions", ref, {"owner_id": a})
        s.close()
        status, body = self.post({"op": "merge", "from": a, "into": b})
        self.assertEqual((status, body["items"], body["id"]), (200, 1, b))

    def test_a_refusal_is_plain_words_and_writes_nothing(self):
        self.add("Sam Reed", email="sam@x.example")
        for req in ({"op": "add", "name": ""}, {"op": "add", "name": "A", "email": "sam@x.example"}, {"op": "add", "name": "A", "kind": "robot"},
                    {"op": "rename", "id": "P-001", "name": "  "}, {"op": "archive", "id": "P-099"}):
            status, body = self.post(req)
            self.assertEqual((status, body["ok"]), (400, False), req)
            self.assertTrue(body["message"])
        self.assertEqual(len(self.srv.call("GET", "/api/people")[1]["people"]), 1)

    def test_the_request_shape_is_checked(self):
        for req in ({"op": "dance"}, {"op": "add", "name": "A", "colour": "red"}, {"op": "add", "name": 5}, {"op": "edit", "id": "x", "changes": {}},
                    {"op": "edit", "id": "P-001", "changes": {"id": "P-009"}}, {"op": "merge", "from": "P-001"}, ["op"], {"op": "add", "name": "A", "needs_details": "yes"}):
            status, body = self.post(req)
            self.assertEqual(status, 400, req)
            self.assertFalse(body["ok"])


class Undo(Base):
    def test_one_undo_takes_a_creation_away_and_a_second_is_refused(self):
        step = self.add("Sam Reed")["apply_id"]
        status, body = self.post({"apply_id": step}, "/api/people/undo")
        self.assertEqual((status, body["people"]), (200, []))
        self.assertEqual(self.post({"apply_id": step}, "/api/people/undo")[0] in (400, 409), True)

    def test_undo_of_a_rename_puts_the_name_back(self):
        pid = self.add("Sam Reed")["id"]
        step = self.post({"op": "rename", "id": pid, "name": "Sam Reid"})[1]["apply_id"]
        body = self.post({"apply_id": step}, "/api/people/undo")[1]
        self.assertEqual(body["people"][0]["name"], "Sam Reed")

    def test_an_undo_that_would_leave_something_behind_is_refused_and_changes_nothing(self):
        a = self.add("Sam Reed", email="sam@x.example")["id"]
        b = self.add("Sam Reid", email="reid@x.example")["id"]
        s = clark_open(self.path)
        with s.step("dashboard", USER) as st:
            ref = st.create("actions", {"project": "ABC", "description": "Do it", "raised": "2026-10-01", "source": "t", "owner": "Sam Reed"})
            st.update("actions", ref, {"owner_id": a})
        s.close()
        merged = self.post({"op": "merge", "from": a, "into": b})[1]
        self.add("Jo Park", email="sam@x.example")                     # the address the merge freed is now someone else's
        before = self.srv.call("GET", "/api/people")[1]["people"]
        s = clark_open(self.path)
        steps = s.con.execute("SELECT count(*) FROM applies").fetchone()[0]
        s.close()
        status, body = self.post({"apply_id": merged["apply_id"]}, "/api/people/undo")
        self.assertEqual((status, body["ok"]), (400, False), body)
        self.assertEqual(body["message"], "This can't be undone: an email address it would put back is now used by Jo Park. "
                         "Change or archive Jo Park first, then undo again. Nothing has been changed.")
        self.assertEqual(self.srv.call("GET", "/api/people")[1]["people"], before)
        s = clark_open(self.path)
        self.addCleanup(s.close)
        self.assertEqual(s.con.execute("SELECT owner, owner_id FROM actions").fetchone()[:], ("Sam Reid", b))
        self.assertEqual(s.con.execute("SELECT count(*) FROM applies").fetchone()[0], steps)       # no step was written by the refusal

    def test_a_good_undo_says_what_it_put_back(self):
        a = self.add("Sam Reed", email="sam@x.example")["id"]
        b = self.add("Sam Reid")["id"]
        s = clark_open(self.path)
        with s.step("dashboard", USER) as st:
            ref = st.create("actions", {"project": "ABC", "description": "Do it", "raised": "2026-10-01", "source": "t", "owner": "Sam Reed"})
            st.update("actions", ref, {"owner_id": a})
        s.close()
        merged = self.post({"op": "merge", "from": a, "into": b})[1]
        status, body = self.post({"apply_id": merged["apply_id"]}, "/api/people/undo")
        self.assertEqual(status, 200, body)
        self.assertEqual(body["restored"], {"people": 2, "emails": 1, "items": 1})
        self.assertEqual(body["message"], "Undone: put back 2 people, 1 email address and 1 item.")
        sam = [p for p in body["people"] if p["id"] == a][0]
        self.assertEqual((sam["archived"], sam["email"]), (0, "sam@x.example"))

    def test_a_people_step_made_through_another_route_is_refused_and_changes_nothing(self):
        """The undo is for the dashboard's own people steps: a step another route made (here a Word import's) is refused with a 400, and the list is as it was."""
        s = clark_open(self.path)
        with s.step("word", USER) as st:
            st.add_person(name="Sam Reed", source="test")
            step = st.peek_apply_id()
        before = s.people(archived=None)
        s.close()
        self.assertEqual([p["name"] for p in before], ["Sam Reed"])
        status, body = self.post({"apply_id": step}, "/api/people/undo")
        self.assertEqual((status, body["ok"]), (400, False))
        self.assertTrue(body["message"])
        after = clark_open(self.path)
        self.addCleanup(after.close)
        self.assertEqual(after.people(archived=None), before, "nothing was changed")
        self.assertEqual(after.con.execute("SELECT count(*) FROM applies WHERE undone_at IS NOT NULL").fetchone()[0], 0)

    def test_only_a_people_step_is_undone_here(self):
        s = clark_open(self.path)
        with s.step("dashboard", USER) as st:
            st.create("actions", {"project": "ABC", "description": "Do it", "raised": "2026-10-01", "source": "t"})
        s.close()
        for req in ({"apply_id": 1}, {"apply_id": 9999}, {"apply_id": "1"}, {"apply_id": True}, {"apply_id": 1, "x": 1}, {}):
            self.assertEqual(self.post(req, "/api/people/undo")[0], 400, req)


class RouteChecks(Base):
    def test_no_token_is_refused_and_no_seam_is_off(self):
        self.assertEqual(self.srv.call("POST", "/api/people", {"op": "add", "name": "A"}, token="wrong")[0], 403)
        bare = Running()
        self.addCleanup(bare.close)
        self.assertEqual(bare.call("POST", "/api/people", {"op": "add", "name": "A"})[0], 503)
        self.assertEqual(bare.call("GET", "/api/people")[0], 404)

    def test_a_body_over_the_limit_is_refused(self):
        status, _ = self.srv.call("POST", "/api/people", {"op": "add", "name": "x" * 5000})
        self.assertEqual(status, 400)


def clark_open(path):
    from clark.store import open_store
    return open_store(path, onedrive_roots=[])


if __name__ == "__main__":
    unittest.main()
