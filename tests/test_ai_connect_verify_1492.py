"""Row 1492: Check again, the server side. Connected only after ONE real small request was answered; one fixed sentence for each failure; one deadline
(30 seconds) and a Cancel; one status check for each provider; nothing of the question or the answer kept. Fake providers, and the real Claude command
against a fake script (test_ask_claude.Fake). No sign-in, no model, no network.

Run: python3 dev/run_tests.py test_ai_connect_verify_1492
"""
import json
import os
import shutil
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
        self.status_calls, self.requests = 0, []

    def status(self):
        self.status_calls += 1
        return {"connected": self.signed_in, "why": "" if self.signed_in else self.why}

    def failed_check(self):
        return self.failed

    def ask(self, request, model=None, prefer=False):
        self.requests.append((request.text, model, prefer))
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

    def test_expired_and_no_network_end_in_words(self):
        for text, code, words in (("OAuth token has expired. Please run /login", "expired", "Your Claude sign-in has run out. Sign in again in Terminal, then press Check again."),
                                  ("getaddrinfo ENOTFOUND api.anthropic.com", "no_network", "Claude could not be reached. Check your internet connection, then press Check again.")):
            self.put("reply", json.dumps({"type": "result", "subtype": "success", "is_error": True, "result": text}))
            status, body = self.svc.verify({"provider": "claude"})
            self.assertEqual((status, body["code"], body["message"]), (409, code, words))
            self.assertNotIn("ENOTFOUND", body["message"])
        self.put("reply", "")
        self.assertEqual(self.svc.verify({"provider": "claude"})[1]["code"], "no_answer")

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


if __name__ == "__main__":
    unittest.main()
