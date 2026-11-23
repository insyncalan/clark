"""Row 1295: GET and POST /api/ask-commands (ask_commands_service.py) over the real server, and the lists that must agree. No browser.

Run: python3 dev/run_tests.py test_ask_commands_service
"""
import http.client
import json
import re
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from _paths import ROOT  # noqa: F401  (puts src/ on the path)
from clark import ask_commands_service as svc
from clark import server as sv

class Running:
    """A server on a free port in a thread (no browser, so this file stays out of the browser tier; the harness of the browser tests is not used)."""

    def __init__(self):
        self.httpd = sv.LocalServer((sv.HOST, 0))
        self.port = self.httpd.server_port
        threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def api(self, method, path, body=None, token=None):
        """(status, headers, body bytes) with the token and a Host, as the page sends them; `body` is JSON bytes."""
        conn = http.client.HTTPConnection(sv.HOST, self.port, timeout=10)
        try:
            conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            conn.putheader("Host", f"127.0.0.1:{self.port}")
            conn.putheader(sv.TOKEN_HEADER, sv.TOKEN if token is None else token)
            if body is not None:
                conn.putheader("Content-Type", "application/json")
                conn.putheader("Content-Length", str(len(body)))
            conn.endheaders(body)
            r = conn.getresponse()
            return r.status, r.msg, r.read()
        finally:
            conn.close()


GOOD = {"name": "monday", "menu": "Monday summary", "text": "Group {today} overdue items by owner.", "scope": "anywhere", "result": "answer"}


class Service(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.s = Running()
        self.addCleanup(self.s.close)
        self.s.httpd.ask_commands = svc.AskCommandsService(self.root)

    def get(self, project=""):
        st, _, body = self.s.api("GET", "/api/ask-commands?project=" + project)
        return st, json.loads(body)

    def post(self, body):
        raw = json.dumps(body).encode()
        st, _, out = self.s.api("POST", "/api/ask-commands", raw)
        return st, json.loads(out)

    def test_without_the_service_the_route_does_not_exist(self):
        self.s.httpd.ask_commands = None
        self.assertEqual(self.s.api("GET", "/api/ask-commands")[0], 404)

    def test_a_new_install_has_none_of_yours_and_names_the_built_ins(self):
        st, b = self.get()
        self.assertEqual(st, 200)
        self.assertEqual((b["all"], b["project"], b["max"]), ([], [], 20))
        self.assertEqual(b["builtins"], list(svc.BUILTIN_NAMES))

    def test_save_then_read_for_all_projects_and_for_a_project(self):
        self.assertEqual(self.post({"scope": "all", "action": "save", "record": GOOD})[0], 200)
        st, b = self.post({"scope": "project", "project": "ABC", "action": "save", "record": {**GOOD, "name": "abc-only"}})
        self.assertEqual((st, b["message"]), (200, "Saved."))
        self.assertTrue((self.root / "ask-commands" / "monday.json").is_file())
        self.assertTrue((self.root / "ask-commands" / "ABC" / "abc-only.json").is_file())
        _, b = self.get("ABC")
        self.assertEqual([m["name"] for m in b["all"]], ["monday"])
        self.assertEqual([m["name"] for m in b["project"]], ["abc-only"])
        _, other = self.get("XYZ")
        self.assertEqual(other["project"], [])

    def test_a_refused_save_says_why_and_writes_nothing(self):
        for rec, word in (({**GOOD, "name": "Monday"}, "lower case"), ({**GOOD, "name": "who is"}, "spaces"), ({**GOOD, "name": "check"}, "built-in"),
                          ({**GOOD, "scope": "everywhere"}, "where it appears"), ({**GOOD, "text": ""}, "plain words")):
            st, b = self.post({"scope": "all", "action": "save", "record": rec})
            self.assertEqual((st, b["ok"], b["code"]), (400, False, "refused"))
            self.assertIn(word, b["message"])
        self.assertEqual(list(self.root.rglob("*.json")), [])

    def test_history_and_new_cannot_be_saved_as_your_version(self):
        for name in ("history", "new"):
            st, b = self.post({"scope": "all", "action": "save", "record": {**GOOD, "name": name, "replaces": name}})
            self.assertEqual(st, 400)
            self.assertIn("action, not a question", b["message"])
        self.assertEqual(list(self.root.rglob("*.json")), [])

    def test_a_text_that_looks_like_a_key_is_refused_and_not_kept(self):
        for field in ("text", "menu"):
            st, b = self.post({"scope": "all", "action": "save", "record": {**GOOD, field: "pass" + "word = Hunter2-Zebra-9"}})
            self.assertEqual((st, b["code"]), (400, "secret"))
        self.assertEqual(list(self.root.rglob("*.json")), [])

    def test_your_version_of_a_built_in_is_kept_and_reset_brings_the_original_back(self):
        mine = {"name": "check", "replaces": "check", "menu": "My check", "text": "Check it my way", "scope": "anywhere", "result": "answer"}
        self.assertEqual(self.post({"scope": "all", "action": "save", "record": mine})[0], 200)
        _, b = self.get()
        self.assertEqual([m["replaces"] for m in b["all"]], ["check"])
        st, b = self.post({"scope": "all", "action": "reset", "name": "check"})
        self.assertEqual((st, b["all"], b["message"]), (200, [], "Back to the built-in."))

    def test_remove_is_yours_only(self):
        self.post({"scope": "all", "action": "save", "record": GOOD})
        st, b = self.post({"scope": "all", "action": "remove", "name": "check"})
        self.assertEqual((st, b["code"]), (400, "refused"))
        st, b = self.post({"scope": "all", "action": "remove", "name": "monday"})
        self.assertEqual((st, b["all"], b["message"]), (200, [], "Removed."))

    def test_a_rename_removes_the_old_file(self):
        self.post({"scope": "all", "action": "save", "record": GOOD})
        self.assertEqual(self.post({"scope": "all", "action": "save", "was": "monday", "record": {**GOOD, "name": "weekly"}})[0], 200)
        self.assertEqual(sorted(p.name for p in self.root.rglob("*.json")), ["weekly.json"])

    def test_the_twenty_first_is_refused(self):
        for i in range(20):
            self.assertEqual(self.post({"scope": "all", "action": "save", "record": {**GOOD, "name": "cmd-%02d" % i}})[0], 200)
        st, b = self.post({"scope": "all", "action": "save", "record": GOOD})
        self.assertEqual(st, 400)
        self.assertIn("20 slash commands", b["message"])

    def test_bad_requests_change_nothing(self):
        for body in ({}, {"scope": "all"}, {"scope": "all", "action": "burn"}, {"scope": "project", "action": "save", "record": GOOD},
                     {"scope": "all", "project": "ABC", "action": "save", "record": GOOD}, {"scope": "project", "project": "../x", "action": "save", "record": GOOD},
                     {"scope": "all", "action": "save", "record": "x"}, {"scope": "all", "action": "save", "record": {**GOOD, "menu": 5}},
                     {"scope": "all", "action": "remove"}, {"scope": "all", "action": "save", "record": GOOD, "extra": 1}):
            st, b = self.post(body)
            self.assertEqual((st, b["ok"]), (400, False), body)
        self.assertEqual(list(self.root.rglob("*")), [])
        self.assertEqual(self.get("bad!")[0], 400)

    def test_each_bad_field_is_a_bad_request_with_its_own_code_and_writes_nothing(self):
        """Row 1295 mutation sweep: the checks of change() and read() each answer bad_request / bad_project_code, not a later refusal or a save."""
        cases = (({"scope": "everywhere", "action": "save", "record": GOOD}, "bad_request"),
                 ({"scope": "all", "action": "save", "record": GOOD, "was": 5}, "bad_request"),
                 ({"scope": "all", "action": "save", "record": {**GOOD, "name": 5}}, "bad_request"),
                 ({"scope": "all", "action": "save", "record": {**GOOD, "text": ["x"]}}, "bad_request"),
                 ({"scope": "project", "project": "ABC!", "action": "save", "record": GOOD}, "bad_project_code"),
                 ({"scope": "project", "project": "ABCDEFGH", "action": "save", "record": GOOD}, "bad_project_code"),
                 ({"scope": "project", "project": "ABC\n", "action": "save", "record": GOOD}, "bad_project_code"),
                 ({"scope": "project", "project": 5, "action": "save", "record": GOOD}, "bad_project_code"))
        for body, code in cases:
            st, b = self.post(body)
            self.assertEqual((st, b["code"]), (400, code), body)
        self.assertEqual(list(self.root.rglob("*")), [])
        for project in ("ABC!", "ABCDEFGH", "abc", "AB", "ABC%0A"):
            st, b = self.get(project)
            self.assertEqual((st, b["code"]), (400, "bad_project_code"), project)

    def test_a_read_has_no_message_and_the_route_is_a_save_path_with_room_for_a_full_command(self):
        st, b = self.get()
        self.assertNotIn("message", b)
        self.assertIn("/api/ask-commands", sv.SAVE_PATHS)
        full = {**GOOD, "text": "x" * 1000, "menu": "m" * 70}
        self.assertEqual(self.post({"scope": "all", "action": "save", "record": full})[0], 200)
        st, b = self.post({"scope": "all", "action": "save", "record": GOOD, "pad": "x" * 9000})
        self.assertEqual((st, b["code"]), (400, "too_large"))

    def test_a_disk_that_cannot_be_written_is_a_409_with_its_own_code(self):
        with mock.patch.object(svc.ac.AskCommands, "write", side_effect=OSError("disk")):
            st, b = self.post({"scope": "all", "action": "save", "record": GOOD})
        self.assertEqual((st, b["code"], b["ok"]), (409, "cant_save", False))

    def test_a_damaged_file_is_listed_and_the_rest_still_read(self):
        self.post({"scope": "all", "action": "save", "record": GOOD})
        (self.root / "ask-commands" / "broken.json").write_text("{not json", encoding="utf-8")
        _, b = self.get()
        self.assertEqual(([m["name"] for m in b["all"]], b["damaged"]["all"]), (["monday"], ["broken.json"]))

    def test_the_token_is_needed(self):
        self.assertEqual(self.s.api("GET", "/api/ask-commands", token="wrong")[0], 403)
        self.assertEqual(self.s.api("POST", "/api/ask-commands", b"{}", token="wrong")[0], 403)


class Lists(unittest.TestCase):
    def test_the_built_in_names_are_those_of_the_slash_menu_and_of_the_rules(self):
        menu = (ROOT / "src/clark/page/src/edit/askSlash.js").read_text(encoding="utf-8")
        names = re.findall(r'\{ name: "([a-z]+)", hint:', menu)
        self.assertEqual(tuple(names), svc.BUILTIN_NAMES)


if __name__ == "__main__":
    unittest.main()
