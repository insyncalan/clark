"""#47: GET and POST /api/ask-enabled (src/clark/app_settings.py, routed by server.py). Every test talks to a
real server.

Run: python3 dev/run_tests.py test_app_settings_route
The data is a temporary clark database with fictional projects. The settings step is step 3 of MIGRATIONS, so a new file has it; a test that wants a file from before it strips it in setUp.
"""
import http.client
import json
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

import sqlite3

from clark import app_settings, changes, server as sv, store as st


def strip_settings(path):
    """The file as version 5 left it: the settings table gone, the version put back to 5."""
    con = sqlite3.connect(str(path), isolation_level=None)
    try:
        con.execute("DROP TABLE app_settings")
        con.execute("UPDATE meta SET v = '5' WHERE k = 'schema_version'")
    finally:
        con.close()


class Running:
    """A server on a free port in a thread (the same checks as the other route tests, without Chrome)."""

    def __init__(self):
        self.httpd = sv.LocalServer((sv.HOST, 0))
        self.port = self.httpd.server_port
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def ask(self, method, path, headers=None, body=None, host="default"):
        conn = http.client.HTTPConnection(sv.HOST, self.port, timeout=10)
        try:
            conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            if host == "default":
                host = f"127.0.0.1:{self.port}"
            if host is not None:
                conn.putheader("Host", host)
            for k, v in (headers or {}).items():
                conn.putheader(k, v)
            conn.endheaders(body)
            r = conn.getresponse()
            return r.status, r.msg, r.read()
        finally:
            conn.close()

    def api(self, method, path, body=None, ctype="application/json", token=None, extra=None, host="default"):
        h = {sv.TOKEN_HEADER: sv.TOKEN if token is None else token, **(extra or {})}
        if body is not None:
            h["Content-Type"] = ctype
            h["Content-Length"] = str(len(body))
        return self.ask(method, path, h, body, host=host)


class Base(unittest.TestCase):
    ready = True

    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.db = self.d / "clark.db"
        store = st.open_store(self.db, onedrive_roots=[])
        with store.step("dashboard", "tester", place="menu") as s:
            s.create("projects", {"code": "ABC", "name": "Example Programme"})
            s.create("projects", {"code": "DEF", "name": "Other Programme"})
            s.create("projects", {"code": "OLD", "name": "Old Programme"})
            s.archive("projects", "OLD")
        store.close()
        if not self.ready:
            strip_settings(self.db)          # a data file made before the settings step; this clark is held at version 5 while the test runs
            for patcher in (mock.patch.object(st, "SCHEMA_VERSION", 5), mock.patch.object(st, "MIGRATIONS", st.MIGRATIONS[:4])):
                patcher.start()
                self.addCleanup(patcher.stop)
        self.service = app_settings.AppSettings(self.db, [], by_user=lambda: "tester")
        self.s = Running()
        self.s.httpd.app_settings = self.service
        self.addCleanup(self.s.close)

    def call(self, method, path, body=None, **kw):
        raw = body if isinstance(body, bytes) else None if body is None else json.dumps(body).encode()
        status, _, data = self.s.api(method, path, raw, **kw)
        try:
            return status, json.loads(data)
        except ValueError:
            return status, None

    def snapshot(self):
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            return (store.con.execute("SELECT count(*) FROM change_log").fetchone()[0],
                    store.con.execute("SELECT count(*) FROM applies").fetchone()[0])
        finally:
            store.close()

    def stored_ask(self):
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            return store.ask_enabled()
        finally:
            store.close()

    def ask(self, enabled):
        return self.call("POST", "/api/ask-enabled", {"enabled": enabled})


class AskSwitch(Base):
    def test_on_to_start_with_then_off_then_on(self):
        self.assertEqual(self.call("GET", "/api/ask-enabled"), (200, {"ok": True, "ask_enabled": True, "saved": True}))
        status, got = self.ask(False)
        self.assertEqual((status, got["ok"], got["ask_enabled"]), (200, True, False))
        self.assertIsInstance(got["apply_id"], int)
        self.assertIn("Nothing is sent", got["message"])
        self.assertFalse(self.stored_ask())
        self.assertEqual(self.call("GET", "/api/ask-enabled")[1]["ask_enabled"], False)
        status, got = self.ask(True)
        self.assertEqual((status, got["ask_enabled"]), (200, True))
        self.assertTrue(self.stored_ask())

    def test_the_same_value_changes_nothing(self):
        before = self.snapshot()
        status, got = self.ask(True)
        self.assertEqual((status, got["ask_enabled"], got["message"]), (200, True, app_settings.MESSAGES["same"]))
        self.assertEqual(self.snapshot(), before)

    def test_undo_takes_the_change_back_once(self):
        step = self.ask(False)[1]["apply_id"]
        status, got = self.call("POST", "/api/ask-enabled", {"undo": step})
        self.assertEqual((status, got["ask_enabled"], got["message"]), (200, True, "Undone."))
        self.assertTrue(self.stored_ask())
        before = self.snapshot()
        status, got = self.call("POST", "/api/ask-enabled", {"undo": step})
        self.assertEqual((status, got["code"]), (409, "no_undo"))
        self.assertEqual(self.snapshot(), before)

    def test_an_undo_after_a_later_change_is_refused(self):
        """Pinned (a teammate's LOW): undo after the value changed again. The first step's undo is refused and nothing is written."""
        off = self.ask(False)[1]["apply_id"]
        self.ask(True)
        before = self.snapshot()
        status, got = self.call("POST", "/api/ask-enabled", {"undo": off})
        self.assertEqual((status, got["code"]), (409, "no_undo"))
        self.assertEqual(self.snapshot(), before)

    def test_an_undo_of_something_else_is_refused(self):
        """Pinned (a teammate's LOW): the undo of a different step (a project's change) or of a step that isn't there is refused on the ask
        route, and nothing is written."""
        store = st.open_store(self.db, onedrive_roots=[])
        with store.step("dashboard", "tester", place="menu") as s:
            s.update("projects", "ABC", {"name": "Example Programme Two"})
            other = s.peek_apply_id()
        store.close()
        before = self.snapshot()
        for step in (other, 1, 99999, 2 ** 40):
            status, got = self.call("POST", "/api/ask-enabled", {"undo": step})
            self.assertEqual((status, got["code"]), (409, "no_undo"), step)
        self.assertEqual(self.snapshot(), before)

    def test_an_undo_of_a_switch_step_written_another_way_is_refused(self):
        """Pinned (a teammate's mutant 3): a step on the switch itself but written by another route (via) is not this route's to undo."""
        store = st.open_store(self.db, onedrive_roots=[])
        with store.step("excel", "tester", place="excel") as s:
            s.update("app_settings", "1", {"ask_enabled": False})
            other = s.peek_apply_id()
        store.close()
        before = self.snapshot()
        status, got = self.call("POST", "/api/ask-enabled", {"undo": other})
        self.assertEqual((status, got["code"]), (409, "no_undo"))
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.stored_ask())

    def test_refused_requests_change_nothing_and_say_why(self):
        before = self.snapshot()
        for bad in ({"enabled": 0}, {"enabled": 1}, {"enabled": "false"}, {"enabled": "off"}, {"enabled": None}, {"enabled": []},
                    {"enabled": {"a": 1}}, {"enabled": 2.5}):
            status, got = self.call("POST", "/api/ask-enabled", bad)
            self.assertEqual((status, got["ok"], got["code"]), (400, False, "bad_value"), bad)
            self.assertTrue(got["message"].endswith("Nothing was changed."), bad)
        for bad in ({}, {"enabled": False, "extra": 1}, {"enabled": False, "undo": 1}, {"undo": 1, "x": 1}, {"project": "ABC", "enabled": True},
                    [], [True], "false", 5, None, True):
            status, got = self.call("POST", "/api/ask-enabled", b"null" if bad is None else bad)
            self.assertEqual((status, got["code"]), (400, "bad_request"), bad)
        for bad in ({"undo": True}, {"undo": "1"}, {"undo": -1}, {"undo": 0}, {"undo": 2 ** 63}, {"undo": 1.0}, {"undo": None}, {"undo": [1]}):
            status, got = self.call("POST", "/api/ask-enabled", bad)
            self.assertEqual((status, got["code"]), (400, "no_undo"), bad)
        self.assertEqual(self.snapshot(), before)
        self.assertTrue(self.stored_ask())


class NotReadyYet(Base):
    """A data file made before the settings step: the switch reads as OFF (never fails open), a change is refused in plain words and
    nothing is written."""
    ready = False

    def test_reads_work_and_changes_say_not_ready(self):
        self.assertEqual(self.call("GET", "/api/ask-enabled"), (200, {"ok": True, "ask_enabled": False, "saved": False}))
        before = self.snapshot()
        for path, body in (("/api/ask-enabled", {"enabled": False}), ("/api/ask-enabled", {"enabled": True}), ("/api/ask-enabled", {"undo": 1})):
            status, got = self.call("POST", path, body)
            self.assertEqual((status, got["code"], got["message"]), (409, "not_ready", app_settings.MESSAGES["not_ready"]), path)
        self.assertEqual(self.snapshot(), before)


class Attackers(Base):
    """The same doors as every other route: the token, the Host, the Origin, JSON, the length."""
    ROUTES = (("POST", "/api/ask-enabled", {"enabled": False}), ("GET", "/api/ask-enabled", None))

    def check_nothing_changed(self, before):
        self.assertEqual(self.snapshot(), before)
        self.assertTrue(self.stored_ask())

    def test_no_token_or_a_wrong_one(self):
        before = self.snapshot()
        for method, path, body in self.ROUTES:
            status, got = self.call(method, path, body, token="")
            self.assertEqual(status, 403, (method, path))
            status, got = self.call(method, path, body, token="not-the-token")
            self.assertEqual((status, got["code"]), (403, "stale"), (method, path))
        self.check_nothing_changed(before)

    def test_a_host_that_is_not_this_machine(self):
        before = self.snapshot()
        for method, path, body in self.ROUTES:
            for host in ("evil.example", f"evil.example:{self.s.port}", f"127.0.0.1.evil.example:{self.s.port}", "10.0.0.5", None):
                self.assertEqual(self.call(method, path, body, host=host)[0] if host is not None else 400, 403 if host is not None else 400)
        self.check_nothing_changed(before)

    def test_a_page_on_another_site(self):
        before = self.snapshot()
        for method, path, body in self.ROUTES:
            for origin in ("https://evil.example", "http://127.0.0.1.evil.example", "null", "http://localhost.evil.example:80"):
                status, _ = self.call(method, path, body, extra={"Origin": origin})
                self.assertEqual(status, 403, (method, path, origin))
        self.assertEqual(self.s.api("OPTIONS", "/api/ask-enabled")[0], 403)
        self.check_nothing_changed(before)

    def test_not_json_no_length_a_big_body_and_broken_json(self):
        before = self.snapshot()
        for path, good in (("/api/ask-enabled", b'{"enabled": false}'),):
            self.assertEqual(self.s.api("POST", path, good, ctype="text/plain")[0], 415)
            self.assertEqual(self.s.api("POST", path, good, ctype="application/x-www-form-urlencoded")[0], 415)
            status, _, _ = self.s.ask("POST", path, {sv.TOKEN_HEADER: sv.TOKEN, "Content-Type": "application/json",
                                                     "Transfer-Encoding": "chunked"}, None)
            self.assertIn(status, (411, 400), path)
            self.assertEqual(self.call("POST", path, b"x" * 2000)[0], 400, "over the 1 KB limit")
            self.assertEqual(self.call("POST", path, b'{"enabled": ')[0], 400)
            self.assertEqual(self.call("POST", path, b"[" * 5000 + b"]" * 5000)[0], 400)
            self.assertEqual(self.call("POST", path, b'{"enabled": NaN, "days": Infinity}')[0], 400)
            self.assertEqual(self.call("POST", path, b'\xff\xfe')[0], 400)
        self.check_nothing_changed(before)

    def test_the_wrong_method_and_other_paths(self):
        for method, path in (("PUT", "/api/ask-enabled"), ("DELETE", "/api/ask-enabled"), ("PATCH", "/api/ask-enabled")):
            self.assertNotEqual(self.s.api(method, path, b"{}")[0], 200)
        for path in ("/api/ask-enabled/", "/api/ask-enabled/x", "/api/ask-enable", "/api/settings"):
            self.assertEqual(self.call("GET", path)[0], 404, path)

    def test_without_a_service_the_routes_are_not_found(self):
        self.s.httpd.app_settings = None
        for method, path, body in self.ROUTES:
            self.assertEqual(self.call(method, path, body)[0], 404, path)


class TheOtherDoors(Base):
    """The page's general change and undo routes never reach the ask switch: its own route is the only way."""

    def test_the_general_change_route_refuses_both_settings(self):
        change = changes.make_change(self.db, [], "tester")
        before = self.snapshot()
        for req in ({"project": "ABC", "kind": "app_settings", "op": "update", "id": "1", "changes": {"ask_enabled": 0}},
                    {"project": "ABC", "kind": "app_settings", "op": "update", "id": "1", "fields": {"ask_enabled": 0}},
                    {"project": "ABC", "kind": "app_settings", "op": "new", "values": {"id": 2}},
                    {"project": "ABC", "kind": "actions", "op": "update", "id": "ABC-A-001", "fields": {"ask_enabled": 0}}):
            status, body = change(req)
            self.assertNotEqual(status, 200, req)
            self.assertFalse(body.get("ok"), req)
        self.assertEqual(self.snapshot(), before)
        self.assertTrue(self.stored_ask())

    def test_the_general_undo_route_will_not_undo_a_settings_step(self):
        undo = changes.make_undo(self.db, [], "tester")
        steps = [self.ask(False)[1]["apply_id"]]
        before = self.snapshot()
        for step in steps:
            status, body = undo({"project": "ABC", "apply_id": step})
            self.assertNotEqual(status, 200, step)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.stored_ask())


if __name__ == "__main__":
    unittest.main()
