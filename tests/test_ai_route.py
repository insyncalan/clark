"""#72 slice 4: POST /api/ai/suggest, GET /api/ai/status and POST /api/ai/stop (src/clark/ai_service.py, routed by server.py), against a
real server and a real store, with a FAKE provider (nothing here calls a model, and no one signs in).

Run: python3 dev/run_tests.py test_ai_route
The doors are the ones every API route has (token, Host, Origin), checked before anything else. A refusal has its own plain line and
code. One run at a time is shared with ask clark's, because both go through the same provider. Fictional data only.
"""
import http.client
import json
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

from _paths import SRC

import _publish_fixture as plant
from clark import ai_menu, ai_service, ask, ask_service, server as sv, store as st
from test_ask_route import Running

TEXT = "We will finish the report by Friday and send it to the team for a read."
MARKER = "ZQ-SELECTED-WORDS-7731"
GOOD = "<<<SUGGESTION\nWe will finish the report by Friday and share it with the team to read.\nSUGGESTION>>>"
ROUTES = (("POST", "/api/ai/suggest", {"option": "rewrite", "place": "plain", "text": TEXT}), ("GET", "/api/ai/status", None),
          ("POST", "/api/ai/stop", {}))


class Fake(ask.Provider):
    """A provider that records what it is given. `hold` makes a run wait until released or stopped; `lock` is the one a real
    provider has, so a question's run and a suggestion's are one run at a time."""
    provider = "fake"

    def __init__(self, reply=GOOD, connected=True):
        self.reply, self.connected = reply, connected
        self.requests = []
        self.lock = threading.Lock()
        self.entered = threading.Event()
        self.release = threading.Event()
        self.hold = False
        self.stops = 0
        self.fault = None

    def status(self):
        return {"connected": self.connected, "why": "" if self.connected else "private fault text /Users/x/key"}

    def ask(self, request):
        self.requests.append(request)
        if self.fault:
            raise RuntimeError(self.fault)
        if self.hold:
            self.entered.set()
            self.release.wait(10)
            if self.stops:
                return ask.Failure(ask.STOPPED)
        return self.reply

    def stop(self):
        self.stops += 1
        self.release.set()
        return True


class Base(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.db = plant.build_db(self.d / "clark.db")
        self.provider = Fake()
        self.service = ask_service.AskService(self.db, self.provider, [])
        self.s = Running()
        self.s.httpd.ask = self.service
        self.s.httpd.ai = ai_service.AiService(self.service)
        self.addCleanup(self.s.close)
        self.addCleanup(self.provider.release.set)
        self.set_switch(True)

    def set_switch(self, on):
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            with store.step("dashboard", "tester", place="menu") as s:
                s.update("app_settings", "1", {"ask_enabled": on})
        finally:
            store.close()

    def suggest(self, **more):
        body = {"option": "rewrite", "place": "plain", "text": TEXT, **more}
        return self.s.api("POST", "/api/ai/suggest", {k: v for k, v in body.items() if v is not None})

    def counts(self):
        con = st.connect(self.db, readonly=True)
        try:
            return tuple(con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("change_log", "applies", "item_events"))
        finally:
            con.close()

    def start_held(self):
        """A suggestion that is running and waiting, in a thread; returns the thread and where its answer lands."""
        self.provider.hold = True
        out = []
        t = threading.Thread(target=lambda: out.append(self.suggest()), daemon=True)
        t.start()
        self.assertTrue(self.provider.entered.wait(10), "the run started")
        return t, out


class TheDoors(Base):
    def test_token_host_and_origin_are_checked_first(self):
        for method, path, body in ROUTES:
            self.assertEqual(self.s.api(method, path, body, token="")[0], 403, path)
            status, got = self.s.api(method, path, body, token="not-the-token")
            self.assertEqual((status, got.get("stale")), (403, True), path)
            self.assertEqual(self.s.api(method, path, body, extra={"Origin": "https://evil.example"})[0], 403, path)
            self.assertEqual(self.s.api(method, path, body, extra={"Origin": f"http://localhost:{self.s.port}"})[0], 403, path)

    def test_a_wrong_host_is_refused(self):
        for method, path, body in ROUTES:
            conn = http.client.HTTPConnection(sv.HOST, self.s.port, timeout=10)
            try:
                conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
                conn.putheader("Host", "evil.example")
                conn.putheader(sv.TOKEN_HEADER, sv.TOKEN)
                raw = json.dumps(body).encode() if body is not None else None
                if raw is not None:
                    conn.putheader("Content-Type", "application/json")
                    conn.putheader("Content-Length", str(len(raw)))
                conn.endheaders(raw)
                self.assertEqual(conn.getresponse().status, 403, path)
            finally:
                conn.close()

    def test_the_doors_come_before_every_refusal_and_nothing_is_sent(self):
        self.set_switch(False)                       # AI is off AND the token is wrong: the door answers, not the switch
        status, got = self.s.api("POST", "/api/ai/suggest", ROUTES[0][2], token="")
        self.assertEqual((status, got.get("code")), (403, "not_allowed"))
        self.assertEqual(self.provider.requests, [])

    def test_json_only_and_a_length(self):
        self.assertEqual(self.s.api("POST", "/api/ai/suggest", b'{"option": "rewrite"}', ctype="text/plain")[0], 415)

    def test_without_a_service_the_routes_are_not_found(self):
        self.s.httpd.ai = None
        for method, path, body in ROUTES:
            self.assertEqual(self.s.api(method, path, body)[0], 404, path)


class Refusals(Base):
    def line(self, got, key):
        self.assertEqual(got["message"], ai_service.MESSAGES[key])
        text = got["message"]
        for bad in ("Traceback", "Error", "/Users", "key", "Exception", "claude.ai", "sk-"):
            self.assertNotIn(bad.lower(), text.lower().replace("keys", ""), text)

    def test_off_has_its_own_line_and_the_provider_is_not_asked(self):
        self.set_switch(False)
        status, got = self.suggest()
        self.assertEqual((status, got["ok"], got["code"]), (409, False, "off"))
        self.assertEqual(got["message"], ai_menu.why_off("off"))
        self.assertEqual(self.provider.requests, [])

    def test_not_signed_in_has_its_own_line_and_never_the_providers_words(self):
        self.provider.connected = False
        status, got = self.suggest()
        self.assertEqual((status, got["code"]), (409, "not_signed_in"))
        self.assertEqual(got["message"], ai_menu.why_off("not_signed_in", "Claude"))
        self.assertNotIn("private fault", json.dumps(got))
        self.assertEqual(self.provider.requests, [])

    def test_a_run_already_going_is_refused_with_busy(self):
        t, out = self.start_held()
        status, got = self.suggest()
        self.assertEqual((status, got["code"]), (409, "busy"))
        self.assertEqual(got["message"], ai_menu.why_off("busy"))
        self.assertEqual(len(self.provider.requests), 1, "the second request never reached the provider")
        self.provider.release.set()
        t.join(10)
        self.assertEqual(out[0][0], 200)

    def test_a_question_running_is_one_run_with_a_suggestion(self):
        with self.provider.lock:                     # ask clark's run holds the provider's lock
            status, got = self.suggest()
            self.assertEqual((status, got["code"]), (409, "busy"))
            self.assertEqual(self.s.api("GET", "/api/ai/status")[1]["busy"], True)
        self.assertEqual(self.provider.requests, [])
        self.assertEqual(self.suggest()[0], 200)

    def test_the_order_is_off_then_not_signed_in_then_busy(self):
        self.provider.connected = False
        with self.provider.lock:
            self.assertEqual(self.suggest()[1]["code"], "not_signed_in")
            self.set_switch(False)
            self.assertEqual(self.suggest()[1]["code"], "off")

    def test_a_switch_turned_off_just_before_the_send_wins(self):
        calls = iter((True, False))
        self.service.enabled = lambda: next(calls)
        status, got = self.suggest()
        self.assertEqual((status, got["code"]), (409, "off"))
        self.assertEqual(self.provider.requests, [])

    def test_a_provider_fault_is_one_plain_line_without_its_text(self):
        self.provider.fault = f"/Users/me/.claude/key sk-abcdefghijklmnopqrstuvwxyz0123 {TEXT}"
        status, got = self.suggest()
        self.assertEqual((status, got["code"], got["message"]), (200, "failed", ai_service.MESSAGES["failed"]))
        self.assertNotIn("sk-", json.dumps(got))
        self.assertNotIn("/Users", json.dumps(got))

    def test_a_provider_failure_is_one_plain_line_too(self):
        self.provider.reply = ask.Failure("Claude isn't signed in. Open /Users/x and type claude.")
        status, got = self.suggest()
        self.assertEqual((status, got["code"], got["message"]), (200, "failed", ai_service.MESSAGES["failed"]))


class SecretsAreRefused(Base):
    """A key or password in the text or in Ask... is refused as given (before any squeezing), before the lock and the provider."""
    KEY = "sk-" + "ant-" + "api03-" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4"

    def refused(self, **kw):
        status, got = self.suggest(**kw)
        self.assertEqual((status, got["ok"], got["code"]), (400, False, "secret"), kw)
        self.assertEqual(got["message"], ai_service.MESSAGES["secret"])
        self.assertEqual(self.provider.requests, [], "nothing reached the provider")
        self.assertFalse(self.service.provider.lock.locked() or self.s.httpd.ai.run_lock.locked())
        self.assertEqual(self.suggest()[0], 200, "the busy lock was not taken: a normal request goes through")
        self.provider.requests.clear()
        return got

    def test_a_key_in_the_text(self):
        got = self.refused(text=f"Use {self.KEY} for the call.")
        self.assertNotIn("A1b2", json.dumps(got))

    def test_a_password_line_in_the_instruction(self):
        self.refused(option="custom", instruction="password: " + "hunter" + "2hunter2xx")

    def test_a_csv_column_with_a_password_on_the_next_line(self):
        self.refused(text="name,password\nann," + "Tr0ub4dor" + "&3xyz\n")

    def test_a_key_split_across_a_line_break(self):
        self.refused(text="the key is " + self.KEY[:12] + "\n" + self.KEY[12:] + " ok")

    def test_the_log_has_the_shape_never_the_words(self):
        with self.assertLogs("clark.ai", "INFO") as cm:
            self.refused(text=f"Use {self.KEY} now")
        logged = " ".join(cm.output)
        self.assertNotIn(self.KEY, logged)
        self.assertNotIn("Use ", logged)
        self.assertIn("option=rewrite", logged)


class OneRunAtATime(Base):
    def test_a_finished_run_frees_the_next(self):
        self.assertEqual(self.suggest()[0], 200)
        self.assertEqual(self.suggest()[0], 200)
        self.assertEqual(len(self.provider.requests), 2)

    def test_two_requests_that_both_passed_the_state_check_still_run_one_at_a_time(self):
        self.s.httpd.ai.state = lambda: "ready"      # both got past the early look: only the run's own lock is left
        t, out = self.start_held()
        status, got = self.suggest()
        self.assertEqual((status, got["code"]), (409, "busy"))
        self.assertEqual(len(self.provider.requests), 1)
        self.provider.release.set()
        t.join(10)

    def test_a_refused_request_does_not_hold_the_run(self):
        self.assertEqual(self.suggest(text="")[0], 400)
        self.assertFalse(self.s.httpd.ai.run_lock.locked())
        self.assertEqual(self.suggest()[0], 200)


class Stop(Base):
    def test_stop_ends_the_run_with_nothing_applied(self):
        before = self.counts()
        t, out = self.start_held()
        status, got = self.s.api("POST", "/api/ai/stop", {})
        self.assertEqual((status, got["stopped"]), (200, True))
        t.join(10)
        self.assertEqual(out[0][0], 200)
        self.assertEqual((out[0][1]["ok"], out[0][1]["code"], out[0][1]["message"]), (False, "stopped", ai_menu.FAULT_MESSAGES["stopped"]))
        self.assertNotIn("html", out[0][1])
        self.assertEqual(self.counts(), before, "no change, no step, no history")
        self.assertEqual(self.suggest(**{})[0], 200, "the next run is free")

    def test_stop_with_nothing_running(self):
        self.assertEqual(self.s.api("POST", "/api/ai/stop", {}), (200, {"ok": True, "stopped": False, "message": ai_service.MESSAGES["not_running"]}))
        self.assertEqual(self.provider.stops, 0)

    def test_stop_does_not_end_a_question(self):
        with self.provider.lock:
            self.assertEqual(self.s.api("POST", "/api/ai/stop", {})[1]["stopped"], False)
        self.assertEqual(self.provider.stops, 0)

    def test_stop_takes_no_body(self):
        self.assertEqual(self.s.api("POST", "/api/ai/stop", {"x": 1})[0], 400)


class BadRequests(Base):
    def test_a_body_that_is_too_large_is_400(self):
        status, got = self.s.api("POST", "/api/ai/suggest", b"x" * (81 * 1024))
        self.assertEqual(status, 400)
        self.assertEqual(self.provider.requests, [])

    def test_a_full_12000_character_selection_in_json_escapes_fits_the_body_limit(self):
        raw = json.dumps({"option": "rewrite", "place": "plain", "text": "\u00e9" * ai_menu.MAX_TEXT}).encode()     # 6 bytes a character
        self.assertGreater(len(raw), 32 * 1024)
        status, got = self.s.api("POST", "/api/ai/suggest", raw)
        self.assertEqual(status, 200, got)
        self.assertEqual(len(self.provider.requests), 1)

    def test_a_body_of_the_wrong_shape_is_400(self):
        for bad in ([], "text", None, {}, {"option": "rewrite", "place": "plain"}, {"option": "rewrite", "text": TEXT},
                    {"option": "rewrite", "place": "plain", "text": TEXT, "project": "PUB"},
                    {"option": "rewrite", "place": "plain", "text": TEXT, "tools": ["x"]},
                    {"option": 1, "place": "plain", "text": TEXT}, {"option": "rewrite", "place": "plain", "text": ["a"]},
                    {"option": "rewrite", "place": "plain", "text": TEXT, "instruction": 5},
                    {"option": "rewrite", "place": "nowhere", "text": TEXT}):
            raw = json.dumps(bad).encode()
            status, got = self.s.api("POST", "/api/ai/suggest", raw)
            self.assertEqual((status, got["code"]), (400, "bad_request"), bad)
        self.assertEqual(self.provider.requests, [])

    def test_a_request_the_menu_refuses_is_400_with_its_words(self):
        too_much = "word " * (ai_menu.MAX_TEXT // 5 + 10)
        for kw, words in ((dict(text=" "), "Select some text"), (dict(text=TEXT + "‮"), "can't be seen"),
                          (dict(text=too_much), "too much text"), (dict(option="shorter_not_here"), "isn't offered"),
                          (dict(option="custom"), "Say what you want"), (dict(option="custom", instruction="x" * 401), "under 400"),
                          (dict(option="custom", instruction="do it‮"), "can't be seen")):
            status, got = self.suggest(**kw)
            self.assertEqual((status, got["code"]), (400, "refused"), kw)
            self.assertIn(words, got["message"])
        self.assertEqual(self.provider.requests, [])


class WhatIsSent(Base):
    def test_the_provider_gets_the_prompt_and_nothing_else(self):
        status, got = self.suggest(text=TEXT + " " + MARKER)
        self.assertEqual(status, 200, got)
        (req,) = self.provider.requests
        self.assertIsInstance(req, ask.Request)
        self.assertEqual(req.text, ai_menu.build_prompt("rewrite", TEXT + " " + MARKER, "plain")["prompt"])
        self.assertEqual((req.question, req.passages, req.hidden, req.dropped_turns), ("", (), {}, 0))
        self.assertIn(MARKER, req.text)

    def test_no_project_name_id_or_tool_is_in_what_is_sent(self):
        self.suggest(option="custom", instruction="make it warmer")
        (req,) = self.provider.requests
        p = plant.load()
        for marker in list(p["markers"].values()) + list(p["kept_markers"].values() if isinstance(p["kept_markers"], dict) else p["kept_markers"]):
            self.assertNotIn(marker, req.text)
        for word in ("PUB", "PUB-A-", "ZQ-"):
            self.assertNotIn(word, req.text)
        self.assertIn("make it warmer", req.text)
        self.assertFalse(hasattr(req, "tools"))

    def test_the_instruction_is_sent_only_for_ask(self):
        self.suggest(instruction="ZQ-NOT-FOR-THIS-OPTION")
        self.assertNotIn("ZQ-NOT-FOR-THIS-OPTION", self.provider.requests[0].text)

    def test_the_route_asks_the_asking_providers_own_seam(self):
        self.assertIs(self.s.httpd.ai.provider, self.service.provider)


class TheReply(Base):
    def test_a_good_reply_is_cleaned_html_with_notes_and_changes(self):
        self.provider.reply = "<<<SUGGESTION\nWe will finish the **report** by Friday and share it with the team to read.\nSUGGESTION>>>"
        before = self.counts()
        status, got = self.suggest(place="notes", option="rewrite")
        self.assertEqual((status, got["ok"]), (200, True), got)
        self.assertIn("<strong>report</strong>", got["html"])
        self.assertEqual(set(got), {"ok", "html", "notes", "changes"})
        self.assertEqual({c["op"] for c in got["changes"]} - {"same", "del", "add"}, set())
        self.assertIn("add", {c["op"] for c in got["changes"]})
        self.assertEqual(self.counts(), before, "nothing is applied")

    def test_markup_in_a_reply_is_refused_before_it_reaches_the_page(self):
        for evil in ("<script>alert(1)</script>", '<img src=x onerror="alert(1)">', "[click](javascript:alert(1))", "<b>hi</b>"):
            self.provider.reply = f"<<<SUGGESTION\n{TEXT} {evil}\nSUGGESTION>>>"
            status, got = self.suggest()
            self.assertEqual((status, got["ok"], got["code"]), (200, False, "failed"), evil)
            self.assertNotIn("html", got)
            self.assertNotIn("script", json.dumps(got).lower().replace("hidden code", ""))

    def test_a_reply_that_changes_nothing_or_is_empty_is_a_plain_failure(self):
        for reply in ("", "<<<SUGGESTION\n" + TEXT + "\nSUGGESTION>>>"):
            self.provider.reply = reply
            status, got = self.suggest()
            self.assertEqual((status, got["ok"], got["code"]), (200, False, "failed"))
            self.assertTrue(got["message"].endswith((".", "!")))

    def test_the_html_has_only_the_allowed_tags(self):
        self.provider.reply = "<<<SUGGESTION\n# Plan\n- one new thing\n- two new things here\nSUGGESTION>>>"
        status, got = self.suggest(place="current", option="rewrite")
        self.assertEqual(status, 200, got)
        self.assertEqual(set(__import__("re").findall(r"<(/?\w+)", got["html"])) - {"h1", "/h1", "ul", "/ul", "li", "/li", "p", "/p", "strong", "/strong", "em", "/em"}, set())


class Logging(Base):
    def test_the_log_has_the_option_place_and_length_and_never_the_text(self):
        self.provider.reply = ask.Failure("x")
        with self.assertLogs("clark", level="DEBUG") as logs:
            self.suggest(text=TEXT + " " + MARKER)
            self.suggest(option="custom", instruction="ZQ-MY-INSTRUCTION-9921", text=TEXT + " " + MARKER)
        out = "\n".join(logs.output)
        self.assertIn("option=rewrite place=plain length=%d" % len(TEXT + " " + MARKER), out)
        self.assertIn("option=custom", out)
        for secret in (MARKER, "ZQ-MY-INSTRUCTION-9921", "finish the report"):
            self.assertNotIn(secret, out)


class Status(Base):
    def test_each_state(self):
        def get():
            status, got = self.s.api("GET", "/api/ai/status")
            self.assertEqual(status, 200)
            return got
        got = get()
        self.assertEqual((got["on"], got["signed_in"], got["busy"], got["provider"], got["line"]), (True, True, False, "Claude", ai_service.MESSAGES["ready"]))
        self.provider.connected = False
        got = get()
        self.assertEqual((got["on"], got["signed_in"], got["busy"], got["line"]), (True, False, False, ai_menu.why_off("not_signed_in", "Claude")))
        self.set_switch(False)
        got = get()
        self.assertEqual((got["on"], got["signed_in"], got["busy"], got["line"]), (False, False, False, ai_menu.why_off("off")))
        self.assertNotIn("private fault", json.dumps(got))

    def test_busy_while_a_run_goes(self):
        t, _out = self.start_held()
        got = self.s.api("GET", "/api/ai/status")[1]
        self.assertEqual((got["on"], got["signed_in"], got["busy"], got["state"]), (True, True, True, "busy"))
        self.assertEqual(got["line"], ai_menu.why_off("busy"))
        self.provider.release.set()
        t.join(10)

    def test_status_does_not_ask_the_provider_to_answer(self):
        self.s.api("GET", "/api/ai/status")
        self.assertEqual(self.provider.requests, [])

    def test_the_words_have_no_jargon_or_product_first_sentence(self):
        for key, line in ai_service.MESSAGES.items():
            self.assertFalse(line.startswith(("clark", "Clark")), key)
            for bad in ("error", "exception", "api", "token", "json", "http"):
                self.assertNotIn(bad, line.lower().split(), (key, bad))


class OneRunPath(unittest.TestCase):
    def test_this_module_starts_no_program_and_opens_no_store(self):
        text = (SRC / "clark" / "ai_service.py").read_text(encoding="utf-8")
        code = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
        for word in ("subprocess", "platform.", "run_stoppable", "connect(", "open_store", "sqlite3", "urllib", "socket"):
            self.assertNotIn(word, code.split('"""', 2)[2], word)


if __name__ == "__main__":
    unittest.main()
