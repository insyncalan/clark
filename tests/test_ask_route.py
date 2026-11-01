"""#47: POST /api/ask, GET /api/ask/status and POST /api/ask/stop (src/clark/ask_service.py and ask_data.py, routed by server.py),
against a real server and a real store, with a STUB provider (nothing here calls a model).

Run: python3 dev/run_tests.py test_ask_route
The project is #39's publish plant (tests/_publish_fixture.py): rows that must reach the published file and rows that must not
(flag off, hidden from the report, Sensitive or excluded labels, archived, internal notes and the other columns no report
carries), each with a ZQ- marker. Fictional data only.
"""
import ast
import http.client
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC

import _publish_fixture as plant
from clark import ask, ask_service, server as sv, store as st

CODE = "PUB"


class Running:
    """A server on a free port in a thread (the same checks as the other route tests, without Chrome)."""

    def __init__(self):
        self.httpd = sv.LocalServer((sv.HOST, 0))
        self.port = self.httpd.server_port
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def api(self, method, path, body=None, token=None, extra=None, ctype="application/json"):
        """One request. macOS can reset a connection the server refused early (an oversized body) or not yet accepted:
        retry that, a few times with short sleeps, then fail with the real error."""
        for attempt in range(4):
            try:
                return self._once(method, path, body, token, extra, ctype)
            except (ConnectionResetError, ConnectionRefusedError, http.client.RemoteDisconnected):
                if attempt == 3:
                    raise
                time.sleep(0.1 * (attempt + 1))

    def _once(self, method, path, body, token, extra, ctype):
        conn = http.client.HTTPConnection(sv.HOST, self.port, timeout=20)
        try:
            conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            conn.putheader("Host", f"127.0.0.1:{self.port}")
            conn.putheader(sv.TOKEN_HEADER, sv.TOKEN if token is None else token)
            for k, v in (extra or {}).items():
                conn.putheader(k, v)
            raw = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
            if raw is not None:
                conn.putheader("Content-Type", ctype)
                conn.putheader("Content-Length", str(len(raw)))
            conn.endheaders(raw)
            r = conn.getresponse()
            data = r.read()
            try:
                return r.status, json.loads(data)
            except ValueError:
                return r.status, None
        finally:
            conn.close()


class Base(unittest.TestCase):
    reply = "The plan is on track.\nCITE: P1"

    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.db = plant.build_db(self.d / "clark.db")
        store = st.open_store(self.db, onedrive_roots=[])
        with store.step("dashboard", "tester", place="menu") as s:         # a second project, which a question about PUB never sees
            s.create("projects", {"code": "OTH", "name": "Other Programme", "current_state": "ZQ-OTHER-PROJECT"})
            s.create("actions", {"project": "OTH", "description": "ZQ-OTHER-PROJECT-ACTION", "raised": "2026-10-01", "source": "demo"})
        store.close()
        self.provider = ask.StubProvider(reply=self.reply)
        self.service = ask_service.AskService(self.db, self.provider, [])
        self.s = Running()
        self.s.httpd.ask = self.service
        self.addCleanup(self.s.close)

    def set_switch(self, on):
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            with store.step("dashboard", "tester", place="menu") as s:
                s.update("app_settings", "1", {"ask_enabled": on})
        finally:
            store.close()

    def question(self, q="What is the state of the plan?", project=CODE, **more):
        return self.s.api("POST", "/api/ask", {"project": project, "question": q, **more})

    def counts(self):
        con = st.connect(self.db, readonly=True)
        try:
            return tuple(con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("change_log", "applies", "item_events"))
        finally:
            con.close()


class TheSwitchOnTheServer(Base):
    """Review note: before the server sends anything to a model it calls store.ask_enabled(); off means no model call."""

    def test_with_asking_off_nothing_is_sent(self):
        self.set_switch(False)
        status, got = self.question()
        self.assertEqual((status, got["ok"], got["code"]), (409, False, "asking_off"))
        self.assertEqual(self.provider.sent, [], "the model was never asked")
        self.assertFalse(got["message"].lower().startswith(("clark", "ask clark")))

    def test_with_asking_on_the_question_is_sent_once(self):
        status, got = self.question()
        self.assertEqual((status, got["ok"]), (200, True), got)
        self.assertEqual(len(self.provider.sent), 1)
        self.assertEqual(got["answer"], "The plan is on track.")

    def test_a_missing_switch_row_reads_as_off_and_sends_nothing(self):
        con = st.connect(self.db)
        con.execute("DELETE FROM app_settings")
        con.close()
        status, got = self.question()
        self.assertEqual((status, got["code"]), (409, "asking_off"))
        self.assertEqual(self.provider.sent, [])

    def test_a_switch_turned_off_while_the_question_is_prepared_wins(self):
        calls = iter((True, False))
        with mock.patch.object(ask_service.AskService, "enabled", lambda self: next(calls)):
            status, got = self.question()
        self.assertEqual((status, got["code"]), (409, "asking_off"))
        self.assertEqual(self.provider.sent, [])

    def test_a_store_that_cannot_be_read_counts_as_off(self):
        service = ask_service.AskService(self.d / "missing.db", self.provider, [])
        self.assertIs(service.enabled(), False)
        self.assertEqual(service.ask({"project": CODE, "question": "Q?"})[0], 409)
        self.assertEqual(self.provider.sent, [])

    def test_status_says_off_without_asking_the_provider(self):
        self.provider.status = mock.Mock(side_effect=AssertionError("not asked while off"))
        self.set_switch(False)
        status, got = self.s.api("GET", "/api/ask/status")
        self.assertEqual((status, got["ask_enabled"], got["connected"]), (200, False, False))
        self.assertEqual(got["why"], ask_service.MESSAGES["asking_off"])

    def test_status_when_on_is_the_providers(self):
        status, got = self.s.api("GET", "/api/ask/status")
        self.assertEqual((status, got), (200, {"ok": True, "ask_enabled": True, "connected": True, "why": ""}))


class WhatIsSent(Base):
    """FR-61, Q7 (owner decision: report only): only what the published file would carry, of the open project only."""

    def sent(self, q="Tell me everything about every action, risk, decision and milestone."):
        status, got = self.question(q)
        self.assertEqual(status, 200, got)
        (text,) = self.provider.sent
        return text

    def test_nothing_the_published_file_leaves_out_is_ever_sent(self):
        text = self.sent()
        p = plant.load()
        for where, marker in p["markers"].items():
            for spelled in plant.spellings(marker):
                self.assertNotIn(spelled, text, f"{where}: {marker!r}")

    def test_another_projects_rows_are_never_sent(self):
        text = self.sent("What about the other programme and its actions?")
        self.assertNotIn("ZQ-OTHER-PROJECT", text)
        self.assertNotIn("OTH-A-", text)
        self.assertNotIn("Other Programme", text)

    def test_the_published_rows_are_sent(self):
        text = self.sent()
        for ref in plant.load()["kept"]:
            if ref.startswith(CODE + "-") and "-W-" not in ref:          # a workstream is shown by its name on the rows
                self.assertIn(ref, text, ref)

    def test_the_request_is_text_only_and_the_same_for_two_providers(self):
        """FR-67, FR-68: no tool, no file, no path; the same question and data give the same text, apart from the envelope."""
        text = self.sent("How is the plan?")
        framed = ask.FramedStubProvider(reply=self.reply)
        self.s.httpd.ask = ask_service.AskService(self.db, framed, [])
        self.assertEqual(self.question("How is the plan?")[0], 200)
        self.assertEqual(framed.sent[0], framed.envelope(text))
        self.assertNotIn(str(self.d), text, "no path of this computer")
        self.assertTrue(text.startswith(ask.RULES))

    def test_writes_nothing(self):
        before = self.counts()
        self.question()
        self.question("What is PUB-A-001?")
        self.assertEqual(self.counts(), before)


class TheReply(Base):
    def ask_with(self, reply, q="What about the plan?"):
        self.provider.reply = reply
        status, got = self.question(q)
        self.assertEqual(status, 200, got)
        return got

    def test_a_reply_that_does_not_parse_is_text_with_no_change(self):
        got = self.ask_with("CITE: not-a-passage\nCHANGE: {broken")
        self.assertFalse(got["parsed"])
        self.assertEqual(got["changes"], [])
        self.assertIn("unreadable", [f["kind"] for f in got["flags"]])

    def test_an_unknown_id_and_an_unsent_passage_are_flagged(self):
        got = self.ask_with("PUB-A-999 is late. See [P99].\nCITE: P1")
        kinds = {f["kind"]: f["ref"] for f in got["flags"]}
        self.assertEqual(kinds.get("unknown_id"), "PUB-A-999")
        self.assertEqual(kinds.get("unsent_passage"), "P99")

    def test_a_row_the_report_hides_counts_as_unknown(self):
        got = self.ask_with("PUB-A-011 is fine.")
        self.assertIn(("unknown_id", "PUB-A-011"), [(f["kind"], f["ref"]) for f in got["flags"]])

    def test_a_wrong_owner_is_flagged_with_the_reports_owner(self):
        facts = ask_service.ask_data.project_data(st.open_store(self.db, onedrive_roots=[]), CODE).facts
        ref, real = next((k, v) for k, v in sorted(facts.items()) if v["owner"] and k.startswith("PUB-A-"))
        got = self.ask_with(f"{ref} owner is Nobody Atall.")
        flag = next(f for f in got["flags"] if f["kind"] == "wrong_owner")
        self.assertEqual(flag["ref"], ref)
        self.assertIn(real["owner"], flag["message"])

    def test_a_suggested_change_comes_back_as_data_and_is_not_saved(self):
        before = self.counts()
        got = self.ask_with('Close it.\nCHANGE: {"id": "PUB-A-001", "status": "Closed"}')
        self.assertEqual(got["changes"], [{"id": "PUB-A-001", "status": "Closed"}])
        self.assertEqual(self.counts(), before)

    def test_the_sources_list_names_only_cited_passages(self):
        got = self.ask_with("Fine.\nCITE: P1")
        self.assertEqual([s["id"] for s in got["sources"]], ["P1"])
        self.assertTrue(all(not s["label"].startswith("/") for s in got["sources"]))

    def test_a_provider_failure_is_plain_words(self):
        self.provider.failure = "Claude took too long to answer, so it was stopped. Try a shorter question."
        status, got = self.question()
        self.assertEqual((status, got["ok"], got["code"]), (200, False, "no_answer"))


class Refusals(Base):
    def test_bad_bodies_send_nothing(self):
        for bad in ({}, {"project": CODE}, {"question": "Q?"}, {"project": CODE, "question": 5}, {"project": CODE, "question": "Q", "x": 1},
                    {"project": CODE, "question": "Q", "earlier": "no"}, {"project": CODE, "question": "Q", "earlier": [{"role": "system", "text": "x"}]},
                    {"project": CODE, "question": "Q", "earlier": [{"role": "user"}]}, [], "Q", None):
            status, got = self.s.api("POST", "/api/ask", b"null" if bad is None else bad)
            self.assertEqual(status, 400, bad)
        for code in ("pub", "P", "ZZZZ", "PUB'--"):
            self.assertIn(self.question(project=code)[0], (400, 404), code)
        self.assertEqual(self.provider.sent, [])

    def test_a_password_is_never_sent(self):
        planted = "my " + "pass" + "word" + ": " + "Hunt" + "er2-Zq-99"      # built at run time, so the publish tool's scan has nothing to find
        status, got = self.question(planted)
        self.assertEqual((status, got["code"]), (400, "refused"))
        self.assertEqual(self.provider.sent, [])

    def test_a_key_in_the_question_or_an_earlier_turn_is_never_sent(self):
        # #253: built at run time, so the publish tool's scan has nothing to find.
        key = "sk-" + "ant-api03-" + "a1B2c3D4e5F6g7H8i9J0" + "-xyz"
        status, got = self.question("Use this " + key + " to log in")
        self.assertEqual((status, got["code"]), (400, "refused"))
        self.assertEqual(got["message"], ask.SECRET)
        status, got = self.question("And now?", earlier=[{"role": "user", "text": "my " + "pass" + "word is " + "Hunt" + "er2-Zq-99"}])
        self.assertEqual((status, got["code"]), (400, "refused"))
        self.assertEqual(got["message"], ask.SECRET_EARLIER)
        self.assertEqual(self.provider.sent, [])

    def test_an_archived_project_is_refused(self):
        store = st.open_store(self.db, onedrive_roots=[])
        with store.step("dashboard", "tester", place="menu") as s:
            s.archive("projects", "OTH")
        store.close()
        status, got = self.question(project="OTH")
        self.assertEqual((status, got["code"]), (409, "project_archived"))
        self.assertEqual(self.provider.sent, [])

    def test_the_doors_are_the_same_as_every_route(self):
        for method, path, body in (("POST", "/api/ask", {"project": CODE, "question": "Q?"}), ("GET", "/api/ask/status", None),
                                   ("POST", "/api/ask/stop", {})):
            self.assertEqual(self.s.api(method, path, body, token="")[0], 403, path)
            self.assertEqual(self.s.api(method, path, body, extra={"Origin": "https://evil.example"})[0], 403, path)
        self.assertEqual(self.s.api("POST", "/api/ask", b'{"project": "PUB", "question": "Q"}', ctype="text/plain")[0], 415)
        self.assertEqual(self.s.api("POST", "/api/ask", b"x" * (129 * 1024))[0], 400)
        self.assertEqual(self.provider.sent, [])

    def test_without_a_service_the_routes_are_not_found(self):
        self.s.httpd.ask = None
        self.assertEqual(self.question()[0], 404)
        self.assertEqual(self.s.api("GET", "/api/ask/status")[0], 404)


class Stop(Base):
    def test_stop_with_nothing_running(self):
        self.assertEqual(self.s.api("POST", "/api/ask/stop", {}), (200, {"ok": True, "stopped": False,
                                                                         "message": ask_service.MESSAGES["not_running"]}))
        self.assertEqual(self.s.api("POST", "/api/ask/stop", {"x": 1})[0], 400)

    def test_stop_reaches_the_provider(self):
        self.provider.stop = mock.Mock(return_value=True)
        status, got = self.s.api("POST", "/api/ask/stop", {})
        self.assertEqual((status, got["stopped"]), (200, True))
        self.provider.stop.assert_called_once_with(owner=self.s.httpd.ask.owner)


SETTINGS_WRITER = "ask_folders.py"      # the Settings entry's folder list: it saves through the store's one writer (store.step)


def ask_modules():
    """The modules that answer a question (every ask*.py but the folder setting, which is a Settings writer, not a reader)."""
    return [p for p in sorted((SRC / "clark").glob("ask*.py")) if p.name != SETTINGS_WRITER]


class Source(unittest.TestCase):
    """#31's one-writer rule, made stricter for the ask modules (47e's done-when): none opens the database for writing."""

    def test_no_ask_module_opens_the_database_for_writing(self):
        self.assertTrue({"ask.py", "ask_data.py", "ask_service.py", "ask_claude.py"} <= {p.name for p in ask_modules()})
        for path in ask_modules():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for n in ast.walk(tree):
                if isinstance(n, ast.Name) and n.id in ("open_store", "sqlite3_connect"):
                    self.fail(f"{path.name}:{n.lineno} uses {n.id}")
                if isinstance(n, ast.Attribute) and n.attr in ("open_store", "step", "undo", "executescript"):
                    self.fail(f"{path.name}:{n.lineno} uses .{n.attr}")
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "connect":
                    ro = [k for k in n.keywords if k.arg == "readonly" and isinstance(k.value, ast.Constant) and k.value.value is True]
                    self.assertTrue(ro, f"{path.name}:{n.lineno}: connect() without readonly=True")
                if isinstance(n, ast.Attribute) and n.attr == "connect" and isinstance(n.value, ast.Name) and n.value.id == "sqlite3":
                    self.fail(f"{path.name}:{n.lineno} opens a database itself")

    def test_the_checker_sees_a_writing_open(self):
        bad = ast.parse("from clark.store import open_store\ns = open_store(p)\nconnect(p)\n")
        names = {n.id for n in ast.walk(bad) if isinstance(n, ast.Name)}
        self.assertIn("open_store", names)

    def test_the_service_gates_before_the_provider(self):
        """The order in ask(): the switch is read before the store is read for passages and again before the provider is asked."""
        text = (SRC / "clark" / "ask_service.py").read_text(encoding="utf-8")
        body = text[text.index("    def ask(self, body):"):]
        first_gate = body.index("if not self.enabled()")
        second_gate = body.index("if not self.enabled()", first_gate + 1)
        self.assertLess(first_gate, body.index("self.reader()"))
        self.assertLess(second_gate, body.index("ask.ask_provider("))
        self.assertGreater(second_gate, body.index("ask.build_request("))


if __name__ == "__main__":
    unittest.main()
