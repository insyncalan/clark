"""#136 G2: GET /api/movement (src/clark/server.py; guarded): the owner-only Movement page's one read."""
import http.client
import json
import threading
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from _paths import SRC
from clark import movement_read
from clark import movement_view as mv
from clark import server as sv

INTERNAL = "PLANTED-INTERNAL-NOTE-4417 supplier wants more money"
REBASE = {"agreed_with": "Pat Placeholder", "reason": "Build ran long", "source": "Steering, 01-10-2026"}


class Rig:
    def __init__(self, case, movement=True):
        self.demo = DemoStore()
        case.addCleanup(self.demo.close)
        store = self.demo.store
        self.today = "2026-10-28"
        read = movement_read.make_read(store.milestone_moves, store.data_for, today=lambda: self.today)
        self.httpd = sv.LocalServer((sv.HOST, 0), data_for=store.data_for, projects=lambda: [], movement=read if movement else None)
        self.httpd.handle_error = lambda *a: None
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        case.addCleanup(self.close)

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def get(self, path, token=True, host=None, origin=None, body=None):
        conn = http.client.HTTPConnection(sv.HOST, self.httpd.server_port, timeout=20)
        try:
            headers = {"Host": host or f"127.0.0.1:{self.httpd.server_port}"}
            if token:
                headers[sv.TOKEN_HEADER] = sv.TOKEN
            if origin:
                headers["Origin"] = origin
            data = None
            if body is not None:
                data = body.encode()
                headers["Content-Length"] = str(len(data))
            conn.request("GET", path, data, headers)
            r = conn.getresponse()
            raw = r.read()
            return r.status, json.loads(raw)
        finally:
            conn.close()


def keys_of(value):
    if isinstance(value, dict):
        out = set(value)
        for v in value.values():
            out |= keys_of(v)
        return out
    if isinstance(value, list):
        out = set()
        for v in value:
            out |= keys_of(v)
        return out
    return set()


class TheRoute(unittest.TestCase):
    def setUp(self):
        self.rig = Rig(self)
        d = self.rig.demo
        d.update("milestones", d.milestone, {"internal_note": INTERNAL})
        d.update("milestones", d.milestone, {"baseline_date": "2030-04-01"}, rebaseline=REBASE)

    def test_a_good_request_answers_with_the_view_and_nothing_else(self):
        status, got = self.rig.get("/api/movement?project=ABC")
        self.assertEqual((status, got["ok"], got["project"]), (200, True, "ABC"))
        self.assertEqual(set(got), {"ok", "project", "movement"})
        self.assertEqual(set(got["movement"]), set(mv.SUMMARY_KEYS))
        (row,) = got["movement"]["rows"]
        self.assertEqual(set(row), set(mv.ROW_KEYS))
        self.assertTrue(row["moved"])
        self.assertTrue(all(set(e) <= set(mv.ENTRY_KEYS) | {"tag"} for e in row["entries"]))

    def test_no_internal_note_no_raw_event_and_no_body_or_description_key(self):
        status, got = self.rig.get("/api/movement?project=ABC")
        text = json.dumps(got)
        self.assertNotIn(INTERNAL, text)
        self.assertNotIn("internal_note", text)
        banned = {"internal_note", "before", "after", "by_user", "old_value", "new_value", "body", "description", "src_ref"}
        self.assertEqual(keys_of(got) & banned, set())

    def test_the_token_the_host_and_the_origin_are_checked_as_for_the_data(self):
        for kw in ({"token": False}, {"host": "evil.example"}, {"origin": "https://evil.example"}):
            status, got = self.rig.get("/api/movement?project=ABC", **kw)
            self.assertEqual((status, got["ok"]), (403, False), kw)
            self.assertNotIn("movement", got)
        status, other = self.rig.get("/api/data?project=ABC", token=False)
        self.assertEqual(status, 403)

    def test_plain_refusals(self):
        for path, want, code in (("/api/movement", 400, "bad_project_code"), ("/api/movement?project=abc", 400, "bad_project_code"),
                                 ("/api/movement?project=ABC&project=XYZ", 400, "bad_project_code"),
                                 ("/api/movement?project=ABC&x=1", 400, "bad_project_code"),
                                 ("/api/movement?project=ZZZ", 404, "project_not_found")):
            status, got = self.rig.get(path)
            self.assertEqual((status, got["ok"], got["code"]), (want, False, code), path)
            self.assertNotIn("Traceback", got["message"])

    def test_a_request_with_a_body_is_refused(self):
        status, got = self.rig.get("/api/movement?project=ABC", body='{"project": "ABC"}')
        self.assertEqual((status, got["code"]), (400, "bad_request"))

    def test_a_fault_in_the_read_is_the_plain_500(self):
        def broken(code):
            raise RuntimeError("PLANTED-FAULT")
        self.rig.httpd.movement = broken
        status, got = self.rig.get("/api/movement?project=ABC")
        self.assertEqual((status, got["code"]), (500, "server_error"))
        self.assertNotIn("PLANTED-FAULT", json.dumps(got))

    def test_the_slip_is_counted_from_todays_date(self):
        self.rig.today = "2031-01-01"
        status, got = self.rig.get("/api/movement?project=ABC")
        (row,) = got["movement"]["rows"]
        self.assertGreater(row["slip"], 0)
        self.assertTrue(row["can_move"])


class WithoutTheRead(unittest.TestCase):
    def test_no_seam_means_no_route(self):
        rig = Rig(self, movement=False)
        status, got = rig.get("/api/movement?project=ABC")
        self.assertEqual((status, got["code"]), (404, "not_found"))


class TheSource(unittest.TestCase):
    def read(self, name):
        return (Path(SRC) / "clark" / name).read_text(encoding="utf-8")

    def test_only_the_route_table_and_the_launcher_know_the_route(self):
        for name in sorted(p.name for p in (Path(SRC) / "clark").glob("*.py")):
            text = self.read(name)
            if name in ("server.py", "__main__.py", "store.py", "movement_read.py"):
                continue
            self.assertNotIn("/api/movement", text, name)
            self.assertNotIn("milestone_moves", text, name)

    def test_ask_clarks_reach_does_not_include_it(self):
        for name in ("reach.py", "platform.py"):
            self.assertNotIn("movement", self.read(name).lower())

    def test_the_launcher_hands_the_server_the_read(self):
        self.assertIn("movement_read.make_read(store.milestone_moves, store.data_for)", self.read("__main__.py"))
        self.assertIn('"/api/movement": movement_route', self.read("server.py"))


if __name__ == "__main__":
    unittest.main()
