"""Row 1492: Check again, the server side. Connected only after ONE real small request was answered; one fixed sentence for each failure; one deadline
(30 seconds) and a Cancel; one status check for each provider; nothing of the question or the answer kept. Fake providers, and the real Claude command
against a fake script (test_ask_claude.Fake). No sign-in, no model, no network.

Run: python3 dev/run_tests.py test_ai_connect_verify_1492
"""
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401
import test_ask_claude as tac
from test_ai_connect import FakeClaude, FakeChatGPT, FakeProvider
from clark import ai_codex, ai_connect as ac, ai_providers, ask, ask_claude, ask_words, platform, settings

QUESTIONS = []


class Probe(FakeProvider):
    """A provider that can fail in each way the command can: which check failed, what the one request gives, and how long it takes."""

    def __init__(self, name="claude", failed=None, why="", reply=None, hold=None, **kw):
        label, models = ("Claude", ask_claude.MODELS) if name == "claude" else ("ChatGPT", ai_codex.MODELS)
        super().__init__(name, label, models, signed_in=failed is None)
        self.failed, self.why, self.reply, self.hold = failed, why, reply, hold
        self.status_calls, self.requests, self.systems = 0, [], []

    def status(self):
        self.status_calls += 1
        return {"connected": self.signed_in, "why": "" if self.signed_in else self.why}

    def failed_check(self):
        return self.failed

    def ask(self, request, model=None, prefer=False):
        self.requests.append((request.text, model, prefer))
        self.systems.append(request.system)
        if self.hold is not None:
            self.hold.wait(20)
            if getattr(request, "cancel", None) is not None and request.cancel.is_set():
                return ask.Failure(ask.STOPPED)
        return self.reply if self.reply is not None else "ready"

    def stop(self, owner=None):
        self.stops.append(owner)
        if self.hold is not None:
            self.hold.set()
        return True


class Base(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)

    def svc(self, claude=None, chatgpt=None):
        self.claude = claude or Probe("claude")
        self.chatgpt = chatgpt or Probe("chatgpt")
        self.connect = ac.AiConnect(self.d, self.claude, self.chatgpt)
        return self.connect

    def verify(self, name, **kw):
        return self.connect.verify({"provider": name}, **kw)


class Answered(Base):
    def test_connected_only_after_one_answered_request(self):
        self.svc(chatgpt=Probe("chatgpt", reply=ask.Failure("ChatGPT couldn't answer just now.")))
        status, body = self.verify("chatgpt")
        self.assertEqual((status, body["code"]), (409, "no_answer"))
        self.assertFalse(settings.ai_read(self.d)["chatgpt_on"], "nothing is saved as on before an answer")
        self.assertFalse(self.connect.view()["chatgpt"]["checked"])
        self.chatgpt.reply = None                    # now it answers
        status, body = self.verify("chatgpt")
        self.assertEqual(status, 200)
        self.assertEqual(len(self.chatgpt.requests), 2, "one request for each check, no more")
        self.assertEqual(self.chatgpt.requests[-1], (ac.TEST_QUESTION, ac.RECOMMENDED["chatgpt"], True), "the one small question, with the model clark recommends")
        self.assertEqual(self.chatgpt.systems, [ask.RULES] * 2, "the check sends ask clark's own rules as its system prompt (ClaudeCommand refuses any other text, so the old one-word prompt could not be used)")
        self.assertTrue(settings.ai_read(self.d)["chatgpt_on"])
        tile = body["chatgpt"]
        self.assertTrue(tile["connected"] and tile["checked"])
        self.assertRegex(tile["checked_line"], r"^Connected\. ChatGPT answered in [0-9.]+ seconds\. Checked \d\d:\d\d\.$")

    def test_first_view_makes_no_request_and_says_not_checked_yet(self):
        self.svc()
        status, body = self.connect.get()
        self.assertEqual(status, 200)
        self.assertEqual(self.claude.requests, [], "viewing spends nothing")
        self.assertEqual(self.chatgpt.requests, [])
        self.assertTrue(body["claude"]["connected"] and body["claude"]["signed_in"], "asking keeps working from the sign-in")
        self.assertFalse(body["claude"]["checked"], "but the tile does not call it Connected: the page says Signed in, not checked yet")
        self.assertEqual(body["claude"]["checked_line"], "")
        self.assertEqual(ac.UNCHECKED, "Signed in, not checked yet")

    def test_a_disconnect_forgets_the_check(self):
        self.svc()
        self.verify("claude")
        self.assertTrue(self.connect.view()["claude"]["checked"])
        self.connect.disconnect({"provider": "claude"})
        self.connect.connect({"provider": "claude"})
        self.assertFalse(self.connect.view()["claude"]["checked"])


class Limits(Base):
    def test_verify_limit_30_seconds_and_cancel(self):
        self.assertEqual(ac.VERIFY_LIMIT, 30.0)
        self.assertLess(ac.VERIFY_LIMIT, ask_claude.TIME_LIMIT, "not the 120 seconds of a real question")
        hold = threading.Event()
        self.svc(claude=Probe("claude", hold=hold))
        started = time.monotonic()
        status, body = self.verify("claude", limit=0.3)
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual((status, body["code"], body["message"]), (409, "slow", "Claude did not answer within 30 seconds. Press Check again."))
        self.assertEqual(self.claude.stops, [None], "the request in it was stopped")
        self.assertFalse(self.connect.view()["claude"]["checked"])
        self.assertEqual(self.connect.running, {}, "nothing is left running")
        # Cancel ends the whole Connect
        hold = threading.Event()
        self.svc(claude=Probe("claude", hold=hold))
        got = []
        t = threading.Thread(target=lambda: got.append(self.verify("claude", limit=20)))
        t.start()
        for _ in range(200):
            if self.claude.requests:
                break
            time.sleep(0.02)
        self.assertEqual(self.connect.progress()[1]["steps"], {"claude": "ask"})
        self.assertEqual(self.connect.cancel({"provider": "claude"})[0], 200)
        t.join(10)
        self.assertFalse(t.is_alive())
        status, body = got[0]
        self.assertEqual((status, body["code"], body["message"]), (409, "cancelled", "Cancelled. Claude is not connected."))
        self.assertFalse(self.connect.view()["claude"]["checked"])
        self.assertEqual(self.connect.progress()[1]["steps"], {})
        self.assertEqual(self.connect.cancel({"provider": "gemini"})[0], 400)
        self.assertEqual(self.connect.cancel({"provider": "claude", "x": 1})[0], 400)

    def test_a_second_check_of_the_same_provider_says_busy(self):
        hold = threading.Event()
        self.svc(claude=Probe("claude", hold=hold))
        t = threading.Thread(target=lambda: self.verify("claude", limit=20))
        t.start()
        for _ in range(200):
            if self.claude.requests:
                break
            time.sleep(0.02)
        status, body = self.verify("claude")
        self.assertEqual((status, body["code"], body["message"]), (409, "busy", ask_claude.BUSY))
        self.connect.cancel({"provider": "claude"})
        t.join(10)


class Sentences(Base):
    ALL = {
        "claude": {"not_installed": "Claude is not installed on this computer. Install it, then press Check again.",
                   "not_signed_in": "Claude is not signed in. Open Terminal, type claude, sign in, then press Check again.",
                   "wrong_kind": "Claude is signed in in a way clark can't use. Sign in with your Claude subscription, then press Check again.",
                   "expired": "Your Claude sign-in has run out. Sign in again in Terminal, then press Check again.",
                   "no_network": "Claude could not be reached. Check your internet connection, then press Check again.",
                   "slow": "Claude did not answer within 30 seconds. Press Check again.",
                   "cancelled": "Cancelled. Claude is not connected.",
                   "limit": ask_claude.LIMIT_REACHED, "busy": ask_claude.BUSY},
        "chatgpt": {"not_installed": "ChatGPT is not installed on this computer. Install it, then press Check again.",
                    "not_signed_in": "ChatGPT is not signed in. Open Terminal, type codex login, sign in with ChatGPT, then press Check again.",
                    "wrong_kind": "ChatGPT is signed in in a way clark can't use. Sign in with your ChatGPT subscription, then press Check again.",
                    "expired": "Your ChatGPT sign-in has run out. Sign in again in Terminal, then press Check again.",
                    "no_network": "ChatGPT could not be reached. Check your internet connection, then press Check again.",
                    "slow": "ChatGPT did not answer within 30 seconds. Press Check again.",
                    "cancelled": "Cancelled. ChatGPT is not connected.",
                    "limit": ai_codex.LIMIT_REACHED, "busy": ask_claude.BUSY},
    }
    HOSTILE = "/Users/someone/.claude/secret.json: ENOTFOUND api.example.com; Bearer abcdef"

    def probe(self, name, kind):
        """A provider that fails the way `kind` says, with command text and a path in everything it says itself."""
        bad = f"{self.HOSTILE} (the command said this)"
        if kind == "not_installed":
            return Probe(name, failed="not_found", why=bad)
        if kind == "not_signed_in":
            return Probe(name, failed="no_login", why=bad)
        if kind == "wrong_kind":
            return Probe(name, failed="api_key", why=bad)
        reply = {"expired": ask_claude.Reasoned(bad, "expired"), "no_network": ask_claude.Reasoned(bad, "network"),
                 "slow": ask.Failure(ask_claude.TOO_SLOW if name == "claude" else ai_codex.TOO_SLOW),
                 "limit": ask_claude.limit_failure(None) if name == "claude" else ask.Failure(ai_codex.LIMIT_REACHED + " " + bad),
                 "busy": ask.Failure(ask_claude.BUSY)}.get(kind)
        return Probe(name, reply=reply)

    def test_each_failure_has_one_fixed_sentence(self):
        for name in ("claude", "chatgpt"):
            for kind, want in self.ALL[name].items():
                if kind == "cancelled":
                    continue                               # its own test: Cancel ends a running check
                with self.subTest(provider=name, kind=kind):
                    self.svc(**{name: self.probe(name, kind)})
                    status, body = self.verify(name)
                    self.assertEqual((status, body["ok"], body["code"]), (409, False, kind))
                    if kind == "limit" and name == "claude":
                        want = body["message"]               # the limit words of the Ask panel, with the models it offers
                        self.assertTrue(want.startswith(ask_claude.LIMIT_REACHED))
                    self.assertEqual(body["message"], want)
                    for leak in ("/Users", ".claude", "secret", "ENOTFOUND", "Bearer", "abcdef", "the command said"):
                        self.assertNotIn(leak, body["message"], "no path, command text or output in the sentence")
                    self.assertFalse(settings.ai_read(self.d)["chatgpt_on"], "a failure saves nothing as on")

    def test_cancelled_has_its_sentence_for_both(self):
        for name in ("claude", "chatgpt"):
            hold = threading.Event()
            self.svc(**{name: Probe(name, hold=hold)})
            got = []
            t = threading.Thread(target=lambda: got.append(self.verify(name, limit=20)))
            t.start()
            for _ in range(200):
                if getattr(self, name).requests:
                    break
                time.sleep(0.02)
            self.connect.cancel({"provider": name})
            t.join(10)
            self.assertEqual(got[0][1]["message"], self.ALL[name]["cancelled"])

    def test_chatgpt_failures_are_not_all_not_signed_in(self):
        cases = [("not_found", ai_codex.NOT_INSTALLED), ("untested", ai_codex.UNTESTED), ("odd_home", ai_codex.ODD_HOME),
                 ("version_flags", ai_codex.CANT_USE), ("login_unreadable", ai_codex.CANT_USE)]
        for code, own in cases:
            with self.subTest(check=code):
                self.svc(chatgpt=Probe("chatgpt", failed=code, why=own))
                status, body = self.connect.connect({"provider": "chatgpt"})
                self.assertEqual((status, body["code"]), (409, "not_signed_in"))
                if code != "not_found":
                    self.assertEqual(body["message"], own, "its own sentence, as the provider says it")
                    self.assertNotEqual(body["message"], ac.NOT_SIGNED_IN["chatgpt"])
                    self.assertEqual(self.verify("chatgpt")[1]["message"], own)
        self.svc(chatgpt=Probe("chatgpt", failed="not_found", why=ai_codex.NOT_INSTALLED))
        self.assertEqual(self.connect.connect({"provider": "chatgpt"})[1]["message"], ai_codex.NOT_INSTALLED)
        self.assertEqual(self.verify("chatgpt")[1]["message"], self.ALL["chatgpt"]["not_installed"])
        self.svc(chatgpt=Probe("chatgpt", failed="no_login", why=ai_codex.NOT_SIGNED_IN))
        self.assertEqual(self.connect.connect({"provider": "chatgpt"})[1]["message"], ac.NOT_SIGNED_IN["chatgpt"], "not signed in still says not signed in")
        five = {ai_codex.NOT_INSTALLED, ai_codex.UNTESTED, ai_codex.ODD_HOME, ai_codex.NOT_NATIVE, ac.NOT_SIGNED_IN["chatgpt"]}
        self.assertEqual(len(five), 5, "five different sentences, one per check")

    def test_the_real_codex_command_not_installed_keeps_its_own_sentence(self):
        other = ai_providers.ChatGPTSubscription(ai_codex.CodexCommand(places=("/nowhere/codex",), walled=False, roots=(str(self.d),)))
        self.svc(chatgpt=other)
        mac = mock.patch.object(platform, "system", return_value=platform.MAC)
        mac.start()
        self.addCleanup(mac.stop)
        status, body = self.connect.connect({"provider": "chatgpt"})
        self.assertEqual((status, body["code"]), (409, "not_signed_in"))
        self.assertIn("isn't on this computer", body["message"])
        self.assertEqual(self.verify("chatgpt")[1]["message"], self.ALL["chatgpt"]["not_installed"])


class RealClaude(tac.Fake):
    """The real command (ask_claude.ClaudeCommand) against a fake script, through verify."""

    def setUp(self):
        super().setUp()
        self.data = Path(tempfile.mkdtemp(prefix="clark-r1492-"))
        self.addCleanup(shutil.rmtree, self.data, True)
        self.svc = ac.AiConnect(self.data, ai_providers.ClaudeSubscription(self.provider), Probe("chatgpt"))

    def test_the_real_command_answers_and_is_then_connected(self):
        status, body = self.svc.verify({"provider": "claude"})
        self.assertEqual(status, 200)
        self.assertTrue(body["claude"]["checked"])
        asked = [c for c in self.calls() if "--print" in c["args"]]
        self.assertEqual(len(asked), 1, "one real request")
        self.assertEqual(self.seen()["stdin"].count(ac.TEST_QUESTION), 1)

    def test_timeout_says_took_too_long(self):
        real = ask_claude.run
        def slow_version(args, *a, **k):
            return ("slow", b"", None) if args[-1:] == ["--version"] else real(args, *a, **k)
        with mock.patch.object(ask_claude, "run", slow_version):
            status, body = self.svc.verify({"provider": "claude"})
            self.assertEqual(self.provider.failed, "slow")
        self.assertEqual((status, body["code"], body["message"]), (409, "slow", "The check took too long. Press Check again."))
        self.assertNotIn("Update", body["message"])
        self.assertNotEqual(body["message"], ask_claude.CANT_USE)
        # a check that ran out of time is not remembered as a verdict: the next one runs again and passes
        self.assertEqual(self.svc.verify({"provider": "claude"})[0], 200)
        # the sign-in check running out of time says the same
        def slow_auth(args, *a, **k):
            return ("slow", b"", None) if args[-2:] == ["auth", "status"] else real(args, *a, **k)
        with mock.patch.object(ask_claude, "run", slow_auth):
            self.assertEqual(self.svc.verify({"provider": "claude"})[1]["message"], "The check took too long. Press Check again.")

    def test_refused_sign_in_kind_and_child_env_unchanged(self):
        for method in ("oauth_token", "third_party", "something_new", None):
            self.put("auth", json.dumps({"loggedIn": True, "authMethod": method}))
            status, body = self.svc.verify({"provider": "claude"})
            self.assertEqual((status, body["code"]), (409, "wrong_kind"), method)
            self.assertEqual(body["message"], "Claude is signed in in a way clark can't use. Sign in with your Claude subscription, then press Check again.")
        self.assertIsNone(self.seen(), "no question was sent")
        self.assertEqual(ask_claude.child_env(home="/Users/sam", user="sam"),
                         {"PATH": ask_claude.SAFE_PATH, "LANG": "en_GB.UTF-8", "HOME": "/Users/sam", "USER": "sam", "LOGNAME": "sam", **ask_claude.PINNED_ENV})
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "x", "ANTHROPIC_AUTH_TOKEN": "y", "CLAUDE_CODE_OAUTH_TOKEN": "z"}):
            env = ask_claude.child_env(home="/Users/sam", user="sam")
        self.assertFalse(set(env) & {"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"}, "clark handles no token or key")
        self.assertEqual(set(env), {"PATH", "LANG", "HOME", "USER", "LOGNAME", *ask_claude.PINNED_ENV})

    def test_expired_ends_in_words(self):
        self.put("reply", json.dumps({"type": "result", "subtype": "success", "is_error": True, "result": "OAuth token has expired. Please run /login"}))
        status, body = self.svc.verify({"provider": "claude"})
        self.assertEqual((status, body["code"], body["message"]), (409, "expired", "Your Claude sign-in has run out. Sign in again in Terminal, then press Check again."))
        self.assertNotIn("OAuth", body["message"])
        self.put("reply", "")
        status, body = self.svc.verify({"provider": "claude"})
        self.assertEqual((status, body["code"], body["message"]), (409, "no_answer", ac.TEST_FAILED.format(label="Claude")))

    def test_no_network_ends_in_words(self):
        words = "Claude could not be reached. Check your internet connection, then press Check again."
        self.put("reply", json.dumps({"type": "result", "subtype": "success", "is_error": True, "result": "getaddrinfo ENOTFOUND api.anthropic.com"}))
        status, body = self.svc.verify({"provider": "claude"})
        self.assertEqual((status, body["code"], body["message"]), (409, "no_network", words))
        self.assertNotIn("ENOTFOUND", body["message"])

    def test_busy_is_not_failed(self):
        self.provider.lock.acquire()
        self.addCleanup(lambda: self.provider.lock.locked() and self.provider.lock.release())
        status, body = self.svc.verify({"provider": "claude"})
        self.assertEqual((status, body["code"], body["message"]), (409, "busy", ask_claude.BUSY))
        self.assertNotEqual(body["message"], ac.TEST_FAILED.format(label="Claude"), "not 'did not answer'")
        self.assertIsNone(self.seen())


class Counts(Base):
    def test_one_status_check_per_provider(self):
        self.svc()
        settings.ai_write(self.d, {"chatgpt_on": True})
        status, body = self.connect.test({})
        self.assertEqual(status, 200)
        self.assertEqual([r["provider"] for r in body["results"]], ["claude", "chatgpt"])
        self.assertEqual((self.claude.status_calls, self.chatgpt.status_calls), (1, 1), "not one for each view, not one more for each question")
        self.assertEqual((len(self.claude.requests), len(self.chatgpt.requests)), (1, 1))
        self.svc(claude=Probe("claude", reply=ask.Failure("no")))
        self.verify("claude")
        self.assertEqual(self.claude.status_calls, 1, "a check reads the status once for the checks and the request")

    def test_a_provider_that_is_off_or_signed_out_is_not_asked(self):
        self.svc(claude=Probe("claude", failed="no_login", why="x"))
        self.assertEqual(self.connect.test({})[0], 409)
        self.assertEqual((self.claude.requests, self.chatgpt.requests), ([], []))


class Calm(Base):
    def test_docker_has_no_check(self):
        self.svc()
        with mock.patch.object(platform, "container_mode", return_value=True):
            status, body = self.verify("claude")
            self.assertEqual((status, body["code"], body["message"]), (409, "docker", ask_words.DOCKER))
            self.assertTrue(self.connect.view()["docker"])
        self.assertEqual(self.claude.requests, [])

    def test_text_never_picks_a_provider(self):
        self.svc()
        for body in (None, [], {}, {"provider": "claude", "x": 1}, {"provider": 1}):
            self.assertEqual(self.connect.verify(body)[0], 400, body)
        self.assertEqual(self.connect.verify({"provider": "gemini"})[1]["code"], "no_provider")


class Command(Probe):
    """A provider whose command check can be held, to cancel or run out of time while it is on that step."""

    def __init__(self, name="claude", stop_at=None, **kw):
        super().__init__(name, **kw)
        self.inside, self.release, self.stop_at, self.found = threading.Event(), threading.Event(), stop_at, (Path("/x/claude"), None)
        self.command = type("C", (), {"lock": threading.Lock(), "command": staticmethod(self.look)})()

    def look(self):
        if self.stop_at == "command":
            self.inside.set()
            self.release.wait(10)
        return self.found

    def status(self):
        if self.stop_at == "signin":
            self.inside.set()
            self.release.wait(10)
        return super().status()


class Steps(Base):
    def seen_steps(self, provider):
        self.svc(claude=provider)
        steps = []
        real = self.connect.step
        with mock.patch.object(self.connect, "step", side_effect=lambda n, s: (steps.append(s), real(n, s))[1]):
            return self.verify("claude"), steps

    def test_a_check_goes_through_the_command_the_sign_in_and_the_one_request(self):
        (status, _body), steps = self.seen_steps(Command())
        self.assertEqual((status, steps), (200, ["command", "signin", "ask"]))

    def test_a_command_that_is_not_there_ends_at_the_first_step(self):
        provider = Command(failed="not_found", why="x")
        provider.found = (None, "x")
        (status, body), steps = self.seen_steps(provider)
        self.assertEqual((status, body["code"], steps), (409, "not_installed", ["command"]))
        self.assertEqual(provider.requests, [])

    def hold(self, stop_at, how):
        provider = Command(stop_at=stop_at)
        self.svc(claude=provider)
        got = []
        t = threading.Thread(target=lambda: got.append(self.verify("claude", limit=0.4 if how == "limit" else 20)))
        t.start()
        self.assertTrue(provider.inside.wait(10))
        if how == "cancel":
            self.connect.cancel({"provider": "claude"})
        else:
            t.join(10)                                   # the deadline passes while the step is held
        provider.release.set()
        t.join(10)
        time.sleep(0.3)                                  # the check, set free, must stop and not go on to ask
        return provider, got[0]

    def test_a_cancel_or_a_deadline_during_a_step_stops_the_check_before_the_next_one(self):
        for stop_at in ("command", "signin"):
            for how, code in (("cancel", "cancelled"), ("limit", "slow")):
                with self.subTest(step=stop_at, how=how):
                    provider, (status, body) = self.hold(stop_at, how)
                    self.assertEqual((status, body["code"]), (409, code))
                    self.assertEqual(provider.requests, [], "no request is sent after the check was ended")
                    if stop_at == "command":
                        self.assertEqual(provider.status_calls, 0, "and no sign-in check either")


class Late(Base):
    def test_a_cancel_that_comes_after_the_answer_does_not_undo_it(self):
        self.svc()
        real = self.claude.ask

        def answer_then_cancel(request, model=None, prefer=False):
            got = real(request, model, prefer)
            self.connect.running["claude"].set()            # the Cancel arrives just after the answer
            return got
        self.claude.ask = answer_then_cancel
        status, body = self.verify("claude")
        self.assertEqual(status, 200)
        self.assertTrue(body["claude"]["checked"])


class Answers(Base):
    def test_progress_and_cancel_answer_in_plain_ok(self):
        self.svc()
        self.assertEqual(self.connect.progress(), (200, {"ok": True, "steps": {}}))
        self.assertEqual(self.connect.cancel({"provider": "claude"}), (200, {"ok": True}), "also when nothing is running")

    def test_bad_cancel_and_verify_bodies_are_400(self):
        self.svc()
        for call in (self.connect.cancel, self.connect.verify):
            self.assertEqual(call({"provider": 1})[0], 400)
            self.assertEqual(call({"provider": "claude", "x": 1})[1]["code"], "bad_request")
            self.assertEqual(call({"provider": "gemini"}), (400, {"ok": False, "code": "no_provider", "message": ac.NO_PROVIDER}))

    def test_a_check_that_ran_out_of_time_on_the_command_says_the_check_took_too_long(self):
        self.svc(claude=Probe("claude", failed="slow", why="x"))
        status, body = self.verify("claude")
        self.assertEqual((status, body["code"], body["message"]), (409, "slow", "The check took too long. Press Check again."))
        self.assertEqual(self.claude.requests, [])

    def test_a_check_that_found_no_command_says_not_installed(self):
        self.svc(claude=Probe("claude", failed="not_found", why="x"))
        status, body = self.verify("claude")
        self.assertEqual((status, body["code"]), (409, "not_installed"))


class Timing(Base):
    def test_the_answer_time_is_shown_to_a_tenth_of_a_second(self):
        self.svc()
        clock = iter([100.0, 101.26])
        fake = mock.Mock(monotonic=lambda: next(clock), strftime=time.strftime)
        with mock.patch.object(ac, "time", fake):
            status, body = self.verify("claude")
        self.assertEqual(status, 200)
        self.assertRegex(body["claude"]["checked_line"], r"^Connected\. Claude answered in 1\.3 seconds\. Checked \d\d:\d\d\.$")

    def test_a_check_that_blew_up_says_did_not_answer_and_none_of_what_it_said(self):
        provider = Command()

        def boom():
            raise RuntimeError("secret /Users/someone/.claude token abc123")
        provider.command.command = staticmethod(boom)
        self.svc(claude=provider)
        status, body = self.verify("claude")
        self.assertEqual((status, body["code"], body["message"]), (409, "no_answer", "Claude did not answer."))
        self.assertEqual(provider.requests, [])


class Refusals(Base):
    def refusal(self, name, got, cancelled=False):
        self.svc()
        event = threading.Event()
        if cancelled:
            event.set()
        return self.connect.refusal(name, self.connect.providers[name], got, event)

    def test_a_stop_is_a_cancel_even_when_the_cancel_flag_was_not_seen(self):
        self.assertEqual(self.refusal("claude", ask.Failure(ask.STOPPED))[0], "cancelled")

    def test_a_cancel_wins_over_whatever_the_request_said(self):
        self.assertEqual(self.refusal("claude", ask.Failure("some other words"), cancelled=True)[0], "cancelled")

    def test_each_providers_own_limit_and_slow_words_are_read(self):
        self.assertEqual(self.refusal("claude", ask.Failure(ask_claude.LIMIT_REACHED)), ("limit", ask_claude.LIMIT_REACHED))
        self.assertEqual(self.refusal("chatgpt", ask.Failure(ai_codex.LIMIT_REACHED)), ("limit", ai_codex.LIMIT_REACHED))
        self.assertEqual(self.refusal("claude", ask.Failure(ask_claude.TOO_SLOW))[0], "slow")
        self.assertEqual(self.refusal("chatgpt", ask.Failure(ai_codex.TOO_SLOW))[0], "slow")
        self.assertEqual(self.refusal("claude", ask_claude.Reasoned("x", "slow"))[0], "slow")

    def test_a_failure_it_has_no_kind_for_says_did_not_answer(self):
        for name, label in (("claude", "Claude"), ("chatgpt", "ChatGPT")):
            self.assertEqual(self.refusal(name, ask.Failure("words of its own")), ("no_answer", f"{label} did not answer."))
            self.assertEqual(self.refusal(name, "not even a failure"), ("no_answer", f"{label} did not answer."))


class Tile(Base):
    def test_a_check_no_longer_stands_when_the_sign_in_is_gone(self):
        self.svc()
        self.verify("claude")
        self.assertTrue(self.connect.view()["claude"]["checked"])
        self.claude.signed_in = False
        tile = self.connect.view()["claude"]
        self.assertEqual((tile["connected"], tile["checked"], tile["checked_line"]), (False, False, ""))

    def test_the_card_says_when_it_is_not_in_a_container(self):
        self.svc()
        self.assertIs(self.connect.view()["docker"], False)

    def test_a_chatgpt_check_that_is_not_a_missing_sign_in_keeps_its_own_sentence(self):
        for failed in ("api_key", "untested", "odd_home", "not_native"):
            self.svc(chatgpt=Probe("chatgpt", failed=failed, why=f"its own words for {failed}"))
            status, body = self.connect.connect({"provider": "chatgpt"})
            self.assertEqual((status, body["message"]), (409, f"its own words for {failed}"), failed)
        self.svc(chatgpt=Probe("chatgpt", failed="no_login", why="x"))
        self.assertEqual(self.connect.connect({"provider": "chatgpt"})[1]["message"], ac.NOT_SIGNED_IN["chatgpt"])


@unittest.skipUnless(shutil.which("node"), "node is needed")
class PageCalls(unittest.TestCase):
    """publishApi.js and askCheck.js, bundled by the pinned esbuild and run in node with a fetch of their own: no browser."""

    @classmethod
    def setUpClass(cls):
        import build_page
        import esbuild
        cls.tmp = tempfile.mkdtemp(prefix="clark-test-")
        edit = Path(SRC) / "clark" / "page" / "src" / "edit"
        entry = Path(cls.tmp) / "entry.js"
        entry.write_text(f'import * as P from "{edit / "publishApi.js"}"; import * as K from "{edit / "askCheck.js"}"; globalThis.P = P; globalThis.K = K;', encoding="utf-8")
        out = Path(cls.tmp) / "bundle.js"
        done = esbuild.run(["--bundle", "--format=iife", "--platform=node", *build_page.preact_flags(), str(entry), f"--outfile={out}"], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        cls.bundle = out.read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    def run_node(self, body):
        script = Path(self.tmp) / "probe.js"
        script.write_text("globalThis.window = globalThis; globalThis.addEventListener = () => {}; globalThis.removeEventListener = () => {}; globalThis.document = {cookie: '', addEventListener() {}, querySelector: () => null, documentElement: {dataset: {}}}; globalThis.location = {href: 'http://x/', hash: '', search: ''};\n" + self.bundle + ";\n(async () => {\n" + body + "\n})().catch((e) => { console.error(e); process.exit(1); });", encoding="utf-8")
        got = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=60)
        self.assertEqual(got.returncode, 0, got.stderr)
        return json.loads(got.stdout)

    def test_a_check_drops_the_kept_answer_of_the_ask_panel_and_a_cancel_asks_for_no_wait(self):
        got = self.run_node("""
          const ok = (b) => Promise.resolve({status: 200, json: () => Promise.resolve(b)});
          globalThis.fetch = (u) => ok(String(u).includes("/api/ask/status") ? {ok: true, ask_enabled: true, connected: true} : {ok: true});
          await K.runCheck();
          const kept = !!K.keptCheck();
          await P.aiVerifySend("claude");
          const afterVerify = !!K.keptCheck();
          console.log(JSON.stringify([kept, afterVerify]));""")
        self.assertEqual(got, [True, False], "a check changes what the ask panel's connection check would answer")

    def test_the_wait_is_35_seconds_and_a_late_server_ends_in_no_answer_and_an_answer_clears_it(self):
        got = self.run_node("""
          const delays = [], cleared = [], ids = [];
          const st = globalThis.setTimeout, ct = globalThis.clearTimeout;
          globalThis.setTimeout = (fn, ms) => { const id = st(fn, ms > 1000 ? 100 : ms); delays.push(ms); ids.push(id); return id; };
          globalThis.clearTimeout = (id) => { cleared.push(id); return ct(id); };
          let signal = null;
          globalThis.fetch = (u, i) => { signal = i.signal || null; return new Promise((res, rej) => { if (i.signal) i.signal.addEventListener("abort", () => rej(new Error("aborted"))); }); };
          const late = await P.aiVerifySend("claude");
          const hung = {delays: delays.slice(), signal: !!signal, late};
          globalThis.fetch = (u, i) => Promise.resolve({status: 200, json: () => Promise.resolve({ok: true})});
          delays.length = 0; ids.length = 0; cleared.length = 0;
          const quick = await P.aiVerifySend("claude");
          const none = await P.aiCancelSend("claude");
          console.log(JSON.stringify([hung, quick.status, delays, cleared.includes(ids[0]), none.status, ids.length]));""")
        hung, quick, delays, cleared, cancel, timers = got
        self.assertEqual(hung["delays"], [35000])
        self.assertTrue(hung["signal"], "the wait is an abort signal on the request")
        self.assertEqual(hung["late"], {"status": 0, "body": None})
        self.assertEqual((quick, delays, cleared, cancel, timers), (200, [35000], True, 200, 1), "the wait is cleared when the answer comes; Cancel has no wait of its own")


if __name__ == "__main__":
    unittest.main()
