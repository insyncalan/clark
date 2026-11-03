"""#446, #54: Settings › AI on the server side (src/clark/ai_connect.py, the keychain calls in platform.py, the four routes in server.py).
No browser, no network, and the real keychain is never touched: every test uses a FAKE key store and a FAKE provider caller, or a fake
`run` for the program that would reach the keychain.

Run: python3 dev/run_tests.py test_ai_connect
The things this pins:
- a key is tested with the provider's model list and only then kept, ONLY by the key store, and never appears in any reply, any log
  line, the settings file or anything in the data folder; a refused key says why (the provider and the status), and keeps nothing;
- Disconnect takes it out, and a model of that provider goes back to the recommended one;
- the model list shows connected providers only, recommended marked and the default; a weaker choice asks first and is remembered;
- a body of the wrong shape, type or fields is refused and keeps nothing;
- the routes have the same doors as every other POST route (token, Host, Origin, JSON, length);
- the program that keeps the key is given it on standard input only, with no trusted program; it is read back (-w) by keychain_read
  only, and only providers.py calls that;
- the published file has none of the card's words and no route.
Every key here ends in TESTONLY.
"""
import json
import logging
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401
from test_app_settings_route import Running

from clark import ai_connect, platform, providers, server as sv, settings

KEY = "fake-good-0123456789abcdef-TESTONLY"
OPENAI_KEY = "fake-good-openai-9876543210-TESTONLY"
PIECES = (KEY, KEY[-12:], KEY[:20], "0123456789abcdef-TESTONLY", OPENAI_KEY, OPENAI_KEY[:24])
GOOD = {"provider": "claude", "how": "key", "key": KEY}
OPENAI = {"provider": "openai", "how": "key", "key": OPENAI_KEY}
ROOT = Path(__file__).resolve().parents[1]


class FakeStore(providers.MemoryStore):
    """The key store as the service sees it, in memory. Never reached by anything real."""

    def __init__(self, fail=False):
        super().__init__()
        self.fail, self.calls = fail, []

    def put(self, provider, key):
        self.calls.append(("put", provider))
        if self.fail:
            raise platform.PlatformError(platform.KEYCHAIN_FAILED)
        return super().put(provider, key)

    def has(self, provider):
        return super().has(provider)

    def remove(self, provider):
        self.calls.append(("remove", provider))
        return super().remove(provider)

    def peek(self, provider):
        self.calls.append(("peek", provider))
        return super().peek(provider)

    @property
    def secret(self):
        return self.keys.get("claude")


class FakeCaller(providers.FakeHttps):
    """The provider calls, with the answer chosen by the test: a status to refuse with, or None for the fake's own behaviour."""

    def __init__(self):
        super().__init__()
        self.listed, self.status = [], None

    def models(self, provider, key):
        self.listed.append(provider)
        if self.status == 429:
            raise providers.Limited(provider, 429)
        if self.status:
            raise providers.KeyRefused(provider, self.status)
        return super().models(provider, key)


class Signed:
    """A Claude command whose sign-in is there, or is not."""

    def __init__(self, connected=True):
        self.connected = connected

    def status(self):
        return {"connected": self.connected, "why": "Claude isn't signed in on this computer. Open Terminal, type claude, and sign in when it asks. Then ask again."
                if not self.connected else "ready"}


class Lines(logging.Handler):
    """Every log line from any thread, as the person would find it in the log file, with any traceback."""

    def __init__(self):
        super().__init__(level=1)
        self.text = []
        self.setFormatter(logging.Formatter("%(name)s %(levelname)s %(message)s"))

    def emit(self, record):
        self.text.append(self.format(record) + (record.exc_text or ""))


class Base(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.keys = FakeStore()
        self.caller = FakeCaller()
        self.provider = Signed()
        self.service = ai_connect.AiConnect(self.d, provider=self.provider, store=self.keys, https=self.caller)
        self.s = Running()
        self.s.httpd.ai_connect = self.service
        self.addCleanup(self.s.close)
        self.lines = Lines()
        root = logging.getLogger()
        self.was = root.level
        root.setLevel(1)
        root.addHandler(self.lines)
        self.addCleanup(root.removeHandler, self.lines)
        self.addCleanup(root.setLevel, self.was)
        self.replies = []                       # every reply's whole bytes, headers and all, to be searched at the end

    def call(self, method, path, body=None, **kw):
        raw = body if isinstance(body, bytes) else None if body is None else json.dumps(body).encode()
        status, headers, data = self.s.api(method, path, raw, **kw)
        self.replies.append(str(headers).encode() + data)
        try:
            return status, json.loads(data)
        except ValueError:
            return status, None

    def saved(self):
        p = self.d / "settings.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def keep_nothing_of_the_key(self):
        """The key, or a piece of it, is in no reply, no log line, no file of the data folder."""
        text = "\n".join(self.lines.text)
        files = [p.read_bytes() for p in self.d.rglob("*") if p.is_file()]
        for piece in PIECES:
            for where, haystack in (("a reply", self.replies), ("the data folder", files)):
                for h in haystack:
                    self.assertNotIn(piece.encode(), h, f"{piece!r} is in {where}")
            self.assertNotIn(piece, text, f"{piece!r} is in the log")


class Connecting(Base):
    def test_a_key_is_tested_then_kept_and_comes_back_nowhere(self):
        status, got = self.call("POST", "/api/ai-connect", GOOD)
        self.assertEqual((status, got["ok"], got["claude"]), (200, True, {"connected": True, "how": "key"}))
        self.assertEqual(self.caller.listed, ["claude"], "tested with the model list first")
        self.assertEqual(self.keys.secret, KEY, "the key store was given the key")
        self.assertEqual(set(got), {"ok", "connected", "model", "models", "note", "accepted", "claude", "openai", "message"})
        self.assertEqual(got["message"], "Claude connected.")
        status, got = self.call("GET", "/api/ai-connect")
        self.assertEqual([m["id"] for m in got["models"]], ["claude-opus", "claude-sonnet", "claude-haiku"])
        self.assertEqual(got["openai"], {"connected": False, "how": "", "chatgpt": "later"})
        self.keep_nothing_of_the_key()
        self.assertEqual(self.saved(), {"ai_claude_how": "key", "ai_model": "claude-opus",
                                        "ai_claude_ids": "claude-opus-fake claude-sonnet-fake claude-haiku-fake"}, "only ordinary words are kept")

    def test_a_refused_key_says_why_and_keeps_nothing(self):
        for status_code, code, words in ((401, "refused", "Claude did not accept this key (401)."), (403, "refused", "Claude did not accept this key (403)."),
                                         (429, "limited", "Claude says this key is over its limit (429).")):
            self.caller.status = status_code
            status, got = self.call("POST", "/api/ai-connect", GOOD)
            self.assertEqual((status, got["ok"], got["connected"], got["code"]), (200, False, False, code))
            self.assertTrue(got["message"].startswith(words), got["message"])
        self.caller.status = None
        status, got = self.call("POST", "/api/ai-connect", {**OPENAI, "key": "not-a-good-one-0000-TESTONLY"})
        self.assertEqual((got["code"], got["message"].split(" Check")[0]), ("refused", "OpenAI did not accept this key (401)."))
        status, got = self.call("POST", "/api/ai-connect", {**OPENAI, "key": "fake-net-000000000-TESTONLY"})
        self.assertEqual(got["code"], "unreachable")
        self.assertIn("couldn't reach OpenAI", got["message"])
        self.assertEqual(self.keys.keys, {}, "nothing was kept")
        self.assertIsNone(self.saved())
        self.keep_nothing_of_the_key()

    def test_openai_by_key_lists_its_chat_models_only(self):
        status, got = self.call("POST", "/api/ai-connect", OPENAI)
        self.assertEqual((status, got["openai"]["connected"], got["claude"]["connected"]), (200, True, False))
        self.assertEqual([m["id"] for m in got["models"]], ["openai:gpt-fake-large", "openai:gpt-fake-small"], "no embedding model")
        self.assertEqual(got["model"], "openai:gpt-fake-large")
        self.assertEqual(self.keys.keys, {"openai": OPENAI_KEY})
        self.keep_nothing_of_the_key()

    def test_a_refusal_never_repeats_what_it_was_given(self):
        for body in ({**GOOD, "key": KEY + " with spaces"}, {**GOOD, "key": KEY + '"'}, {**GOOD, "key": KEY + "\n"}, {**GOOD, "key": "short"},
                     {**GOOD, "key": "é" + KEY}, {**GOOD, "key": KEY * 40}):
            status, got = self.call("POST", "/api/ai-connect", body)
            self.assertEqual((status, got["ok"], got["code"]), (400, False, "bad_key"), body["key"][:12])
        self.assertEqual(self.caller.listed, [], "nothing went to the provider")
        self.assertIsNone(self.keys.secret)
        self.assertFalse((self.d / "settings.json").exists())
        self.keep_nothing_of_the_key()

    def test_a_body_of_the_wrong_shape_is_refused_and_keeps_nothing(self):
        bad = [{**GOOD, "key": 12345}, {**GOOD, "key": [KEY]}, {**GOOD, "key": {"a": KEY}}, {**GOOD, "key": None}, {**GOOD, "key": True},
               {**GOOD, "extra": KEY}, {**GOOD, "provider": "deepseek"}, {**GOOD, "provider": 1}, {**GOOD, "how": "token"}, {**GOOD, "how": ["key"]},
               {"provider": "openai", "how": "subscription"}, {"provider": "claude", "how": "key"}, {"how": "key", "key": KEY},
               {"provider": "claude", "key": KEY}, {"provider": "claude", "how": "subscription", "key": KEY},
               {"provider": "claude", "how": "subscription", "extra": 1}, [GOOD], [KEY], KEY, None, 7, {}]
        for body in bad:
            raw = json.dumps(body).encode()
            status, got = self.call("POST", "/api/ai-connect", raw)
            self.assertEqual((status, got["ok"], got["code"]), (400, False, "bad_request"), body)
        self.assertEqual(self.keys.calls, [], "nothing reached the key store")
        self.assertEqual(self.caller.listed, [])
        self.assertFalse((self.d / "settings.json").exists())
        self.keep_nothing_of_the_key()

    def test_a_keychain_that_cannot_keep_it_says_so_and_connects_nothing(self):
        self.keys.fail = True
        status, got = self.call("POST", "/api/ai-connect", GOOD)
        self.assertEqual((status, got["ok"], got["connected"], got["code"]), (200, False, False, "keychain"))
        self.assertEqual(self.call("GET", "/api/ai-connect")[1]["connected"], False)
        self.assertFalse((self.d / "settings.json").exists())
        self.keep_nothing_of_the_key()

    def test_a_fault_inside_a_seam_does_not_put_the_key_in_the_log_or_the_reply(self):
        def boom(provider, secret):
            raise RuntimeError("could not store " + secret)       # even a careless seam's fault text must not reach the log or the page
        self.keys.put = boom
        status, got = self.call("POST", "/api/ai-connect", GOOD)
        self.assertEqual((status, got["connected"], got["code"]), (200, False, "keychain"))
        def boom_list(provider, secret):
            raise RuntimeError("refused " + secret)
        self.caller.models = boom_list
        status, got = self.call("POST", "/api/ai-connect", OPENAI)
        self.assertEqual(got["code"], "unreachable")
        self.keep_nothing_of_the_key()

    def test_the_subscription_needs_the_sign_in_and_asks_for_no_key(self):
        self.provider.connected = False
        status, got = self.call("POST", "/api/ai-connect", {"provider": "claude", "how": "subscription"})
        self.assertEqual((status, got["connected"], got["code"]), (200, False, "not_signed_in"))
        self.assertIn("isn't signed in", got["message"])
        self.provider.connected = True
        status, got = self.call("POST", "/api/ai-connect", {"provider": "claude", "how": "subscription"})
        self.assertEqual((status, got["claude"]), (200, {"connected": True, "how": "subscription"}))
        self.assertEqual(self.keys.calls, [("remove", "claude")], "no key was kept, and none is left from before")
        self.assertEqual(self.caller.listed, [], "the subscription is not a network call")

    def test_switching_to_the_subscription_takes_a_kept_key_out(self):
        self.call("POST", "/api/ai-connect", GOOD)
        self.call("POST", "/api/ai-connect", {"provider": "claude", "how": "subscription"})
        self.assertIsNone(self.keys.secret)

    def test_a_key_that_has_gone_from_the_keychain_reads_as_not_connected(self):
        self.call("POST", "/api/ai-connect", GOOD)
        self.keys.keys.clear()                                    # taken out by hand, in Keychain Access
        status, got = self.call("GET", "/api/ai-connect")
        self.assertEqual((got["connected"], got["models"], got["model"]), (False, [], ""))

    def test_the_connect_box_words_are_pinned(self):
        """FR-63, FR-65: passages leave the computer, are billed to that account, and go to either provider the same way."""
        self.assertEqual(ai_connect.CONNECT_NOTE, "The passages ask clark and the AI menu send go to the provider you connect: they leave this "
                         "computer and are billed to that account, the same way for Claude and OpenAI. A key is kept in this Mac's keychain, "
                         "never in clark's files or backups, and is never shown again.")
        self.assertEqual(self.call("GET", "/api/ai-connect")[1]["note"], ai_connect.CONNECT_NOTE)


class Disconnecting(Base):
    def test_disconnect_takes_the_key_out_and_the_models_with_it(self):
        self.call("POST", "/api/ai-connect", GOOD)
        self.call("POST", "/api/ai-model", {"model": "claude-haiku", "accept": True})
        status, got = self.call("POST", "/api/ai-disconnect", {"provider": "claude"})
        self.assertEqual((status, got["ok"], got["connected"], got["models"], got["model"]), (200, True, False, [], ""))
        self.assertIsNone(self.keys.secret)
        self.assertEqual(self.saved(), {"ai_claude_how": "none"}, "the choice of a model of that provider is gone with it")
        self.assertEqual(self.call("GET", "/api/ai-connect")[1]["connected"], False)
        self.keep_nothing_of_the_key()

    def test_a_model_of_the_disconnected_provider_goes_back_to_the_recommended_model(self):
        self.call("POST", "/api/ai-connect", GOOD)
        self.call("POST", "/api/ai-connect", OPENAI)
        status, got = self.call("POST", "/api/ai-model", {"model": "openai:gpt-fake-small", "accept": True})
        self.assertEqual((status, got["model"]), (200, "openai:gpt-fake-small"))
        status, got = self.call("POST", "/api/ai-disconnect", {"provider": "openai"})
        self.assertEqual((status, got["model"], got["accepted"]), (200, "claude-opus", []))
        self.assertEqual(self.saved()["ai_model"], "claude-opus")
        self.assertNotIn("ai_accepted", self.saved(), "a use-it-anyway for a model that has gone is dropped")
        self.assertEqual(self.keys.keys, {"claude": KEY}, "only that provider's key was taken out")

    def test_a_key_that_cannot_be_taken_out_is_still_connected_and_says_so(self):
        self.call("POST", "/api/ai-connect", GOOD)
        self.keys.remove = lambda provider: False
        status, got = self.call("POST", "/api/ai-disconnect", {"provider": "claude"})
        self.assertEqual((status, got["connected"], got["code"]), (409, True, "cant_remove"))
        self.assertEqual(self.call("GET", "/api/ai-connect")[1]["connected"], True)

    def test_disconnect_takes_only_the_provider(self):
        for body in ({}, {"provider": "deepseek"}, {"provider": "claude", "extra": 1}, {"provider": ["claude"]}, [], None, "claude"):
            status, got = self.call("POST", "/api/ai-disconnect", json.dumps(body).encode())
            self.assertEqual((status, got["code"]), (400, "bad_request"), body)


class Model(Base):
    def test_only_the_connected_models_and_the_recommended_one_first(self):
        status, got = self.call("POST", "/api/ai-model", {"model": "claude-sonnet"})
        self.assertEqual((status, got["code"]), (409, "not_connected"))
        self.call("POST", "/api/ai-connect", GOOD)
        got = self.call("GET", "/api/ai-connect")[1]
        self.assertEqual(got["model"], "claude-opus", "Opus, the recommended one, to start with")
        self.assertEqual([m["recommended"] for m in got["models"]], [True, False, False])
        status, got = self.call("POST", "/api/ai-model", {"model": "openai:gpt-fake-large"})
        self.assertEqual((status, got["code"]), (409, "not_offered"), "OpenAI isn't connected, so its models aren't in the list")
        for body in ({"model": "gpt-5"}, {"model": "oa-flagship"}, {"model": ""}, {"model": 3}, {"model": ["claude-opus"]}, {"model": "claude-opus", "x": 1},
                     {"model": "claude-haiku", "accept": "yes"}, {"model": "claude-haiku", "accept": False}, {}, [], None):
            status, got = self.call("POST", "/api/ai-model", json.dumps(body).encode())
            self.assertEqual((status, got["code"]), (400, "bad_request"), body)
        self.assertEqual(ai_connect.chosen_model(self.d), "claude-opus")

    def test_a_weaker_model_asks_first_and_the_answer_is_remembered(self):
        self.call("POST", "/api/ai-connect", GOOD)
        status, got = self.call("POST", "/api/ai-model", {"model": "claude-sonnet"})
        self.assertEqual((status, got["code"], got["ask"]), (409, "weaker", True))
        self.assertTrue(got["message"].startswith("Claude Sonnet 5.5 isn't the recommended model."))
        self.assertEqual(ai_connect.chosen_model(self.d), "claude-opus", "nothing changed until the person said so")
        status, got = self.call("POST", "/api/ai-model", {"model": "claude-sonnet", "accept": True})
        self.assertEqual((status, got["model"], got["accepted"]), (200, "claude-sonnet", ["claude-sonnet"]))
        self.call("POST", "/api/ai-model", {"model": "claude-opus"})
        status, got = self.call("POST", "/api/ai-model", {"model": "claude-sonnet"})
        self.assertEqual((status, got["model"]), (200, "claude-sonnet"), "asked once: the use-it-anyway is remembered")
        self.assertEqual(self.saved()["ai_accepted"], "claude-sonnet")

    def test_the_claude_models_are_the_prototypes(self):
        proto = (ROOT / "system" / "prototype" / "views.js").read_text(encoding="utf-8")
        listed = re.search(r"const AI_MODELS = \{ claude: \[(.*?)\], openai", proto).group(1)
        theirs = re.findall(r"\['(claude-[a-z]+)', '([^']+)'(?:, (1))?\]", listed)
        self.assertEqual(theirs, [(i, t, "1" if r else "") for i, t, r in ai_connect.MODELS])

    def test_a_saved_word_that_is_not_a_listed_model_is_not_read_as_one(self):
        (self.d / "settings.json").write_text(json.dumps({"ai_model": "gpt-5", "ai_claude_how": "token"}), encoding="utf-8")
        self.assertEqual(ai_connect.chosen_model(self.d), "")
        self.assertEqual(self.call("GET", "/api/ai-connect")[1]["connected"], False)

    def test_a_settings_file_that_cannot_be_read_is_not_replaced(self):
        (self.d / "settings.json").write_text("not json at all", encoding="utf-8")
        status, got = self.call("POST", "/api/ai-connect", {"provider": "claude", "how": "subscription"})
        self.assertEqual((status, got["code"]), (200, "cant_save"))
        self.assertEqual((self.d / "settings.json").read_text(encoding="utf-8"), "not json at all")


class Choice(Base):
    """What providers.Router is told for each question."""

    def test_nothing_ever_chosen_is_the_claude_command_as_before(self):
        self.assertIsNone(self.service.choice())
        self.assertIsNone(self.service.command_model())

    def test_the_subscription_gives_the_command_its_alias(self):
        self.call("POST", "/api/ai-connect", {"provider": "claude", "how": "subscription"})
        self.assertEqual(self.service.choice(), {"provider": "claude", "how": "subscription", "model": "opus", "offer_other": ""})
        self.call("POST", "/api/ai-model", {"model": "claude-haiku", "accept": True})
        self.assertEqual(self.service.command_model(), "haiku")

    def test_a_claude_key_gives_the_listed_id_and_another_provider_is_offered(self):
        self.call("POST", "/api/ai-connect", GOOD)
        self.call("POST", "/api/ai-connect", OPENAI)
        self.assertEqual(self.service.choice(), {"provider": "claude", "how": "key", "model": "claude-opus-fake", "offer_other": "OpenAI"})
        self.assertIsNone(self.service.command_model(), "a key is not the command")

    def test_after_disconnecting_everything_nothing_is_set_up(self):
        self.call("POST", "/api/ai-connect", {"provider": "claude", "how": "subscription"})
        self.call("POST", "/api/ai-disconnect", {"provider": "claude"})
        self.assertEqual(self.service.choice()["provider"], "", "an explicit Disconnect never falls back to the command")


class Doors(Base):
    """The same doors as every other route: the token, the Host, the Origin, JSON, the length."""
    ROUTES = (("POST", "/api/ai-connect", GOOD), ("GET", "/api/ai-connect", None), ("POST", "/api/ai-disconnect", {"provider": "claude"}),
              ("POST", "/api/ai-model", {"model": "claude-haiku"}))

    def check(self):
        self.assertIsNone(self.keys.secret)
        self.assertEqual(self.keys.calls, [])
        self.keep_nothing_of_the_key()

    def test_no_token_or_a_wrong_one(self):
        for method, path, body in self.ROUTES:
            self.assertEqual(self.call(method, path, body, token="")[0], 403, path)
            status, got = self.call(method, path, body, token="not-the-token")
            self.assertEqual((status, got["code"]), (403, "stale"), path)
        self.check()

    def test_a_host_that_is_not_this_machine(self):
        for method, path, body in self.ROUTES:
            for host in ("evil.example", f"evil.example:{self.s.port}", f"127.0.0.1.evil.example:{self.s.port}", "10.0.0.5"):
                self.assertEqual(self.call(method, path, body, host=host)[0], 403, (path, host))
        self.check()

    def test_a_page_on_another_site(self):
        for method, path, body in self.ROUTES:
            for origin in ("https://evil.example", "http://127.0.0.1.evil.example", "null"):
                self.assertEqual(self.call(method, path, body, extra={"Origin": origin})[0], 403, (path, origin))
            self.assertEqual(self.s.api("OPTIONS", path)[0], 403)
        self.check()

    def test_not_json_no_length_a_big_body_and_broken_json(self):
        good = json.dumps(GOOD).encode()
        for ctype in ("text/plain", "application/x-www-form-urlencoded", "multipart/form-data"):
            self.assertEqual(self.s.api("POST", "/api/ai-connect", good, ctype=ctype)[0], 415)
        status, _, _ = self.s.ask("POST", "/api/ai-connect", {sv.TOKEN_HEADER: sv.TOKEN, "Content-Type": "application/json", "Transfer-Encoding": "chunked"}, None)
        self.assertIn(status, (411, 400))
        self.assertEqual(self.call("POST", "/api/ai-connect", json.dumps({**GOOD, "key": "a" * 5000}).encode())[0], 400, "over the 2 KB limit")
        self.assertEqual(self.call("POST", "/api/ai-disconnect", b"x" * 2000)[0], 400, "over the 1 KB limit")
        self.assertEqual(self.call("POST", "/api/ai-connect", b'{"provider": "claude", "how": "key", "key": "' + KEY.encode())[0], 400, "broken json")
        self.assertEqual(self.call("POST", "/api/ai-connect", b"[" * 5000 + b"]" * 5000)[0], 400)
        self.check()

    def test_without_a_service_the_routes_are_not_found(self):
        self.s.httpd.ai_connect = None
        for method, path, body in self.ROUTES:
            self.assertEqual(self.call(method, path, body)[0], 404, path)

    def test_the_routes_are_in_the_planned_lists(self):
        import _routes
        self.assertEqual(_routes.unplanned(sv), {})
        for path in ("/api/ai-connect", "/api/ai-disconnect", "/api/ai-model"):
            self.assertIn(path, _routes.POST_ROUTES)
        self.assertIn("/api/ai-connect", _routes.GET_ROUTES)
        for path in ("/api/ai-connect", "/api/ai-disconnect", "/api/ai-model"):
            self.assertIn(path, sv.ROUTE_BODY_LIMITS, "a small limit of its own")
            self.assertLessEqual(sv.ROUTE_BODY_LIMITS[path], 2048)


class TheKeychainCalls(unittest.TestCase):
    """platform.keychain_*: the key goes to the program on standard input and nowhere else. `run` is a fake, so no program starts."""
    SERVICE = "clark.ai.0123456789ab.claude"

    def make_run(self, keep=True, code=0, out=KEY + "\n"):
        calls = []

        def run(args, **kw):
            calls.append((list(args), kw))
            done = mock.Mock(returncode=0, stdout="", stderr="")
            if args[1:2] == ["find-generic-password"]:
                done.returncode = 0 if (keep and any(c[0][1:2] == ["-i"] for c in calls)) else 44
                if "-w" in args:
                    done.returncode, done.stdout = code, out
            return done
        return run, calls

    def test_the_key_is_on_standard_input_only(self):
        run, calls = self.make_run()
        self.assertTrue(platform.keychain_save(self.SERVICE, "clark", KEY, run=run, on=platform.MAC))
        for args, kw in calls:
            self.assertNotIn(KEY, " ".join(args), "never in the arguments")
            self.assertNotIn(KEY, json.dumps({k: v for k, v in kw.items() if k not in ("input",)}, default=str), "never in the environment or anywhere else")
        (add,) = [c for c in calls if c[0][1:2] == ["-i"]]
        self.assertEqual(add[0], ["/usr/bin/security", "-i"])
        self.assertIn(KEY, add[1]["input"])
        self.assertIn('-T ""', add[1]["input"], "no program is trusted to read it back without the person's approval")
        self.assertTrue(add[1]["input"].startswith("add-generic-password "))
        self.assertEqual(set(add[1]["env"]), {"HOME", "PATH"}, "nothing of clark's own environment")
        self.assertTrue(add[1]["capture_output"], "the program's own output is not shown or logged")
        self.assertEqual(add[1]["timeout"], platform.KEYCHAIN_LIMIT)

    def test_it_reports_what_is_there_afterwards(self):
        run, _ = self.make_run(keep=False)
        self.assertFalse(platform.keychain_save(self.SERVICE, "clark", KEY, run=run, on=platform.MAC))

    def test_has_and_remove_never_ask_for_the_secret(self):
        run, calls = self.make_run()
        platform.keychain_has(self.SERVICE, "clark", run=run, on=platform.MAC)
        platform.keychain_remove(self.SERVICE, "clark", run=run, on=platform.MAC)
        flat = [a for args, _ in calls for a in args]
        for flag in ("-w", "-g", "-D"):
            self.assertNotIn(flag, flat, "reading the secret out is never asked for")
        self.assertIn("delete-generic-password", flat)

    def test_read_gives_the_key_only_when_it_is_one_line_of_key_characters(self):
        run, calls = self.make_run()
        self.assertEqual(platform.keychain_read(self.SERVICE, "clark", run=run, on=platform.MAC), KEY)
        (args, kw), = calls
        self.assertEqual(args, ["/usr/bin/security", "find-generic-password", "-s", self.SERVICE, "-a", "clark", "-w"])
        self.assertTrue(kw["capture_output"])
        self.assertEqual(set(kw["env"]), {"HOME", "PATH"})
        for out, code in (("", 0), ("has a space in it 1234567", 0), (KEY, 44), ("x" * 600, 0)):
            run, _ = self.make_run(code=code, out=out)
            self.assertIsNone(platform.keychain_read(self.SERVICE, "clark", run=run, on=platform.MAC), (out[:10], code))

    def test_a_secret_that_could_not_be_passed_safely_is_refused_before_anything_runs(self):
        run, calls = self.make_run()
        for bad in ("", "short", "has space in it 123456", 'quote"in-it-123456', "back\\slash-123456", "new\nline-123456", "-leading-dash-123456", "é" * 20, "a" * 600, None, 12345, b"x" * 20):
            with self.assertRaises(ValueError):
                platform.keychain_save(self.SERVICE, "clark", bad, run=run, on=platform.MAC)
        self.assertEqual(calls, [])

    def test_the_names_are_fixed_words(self):
        run, calls = self.make_run()
        for bad in ("", "A", 'x" -w "y', "a b c", "../x", None):
            with self.assertRaises(ValueError):
                platform.keychain_has(bad, "clark", run=run, on=platform.MAC)
            with self.assertRaises(ValueError):
                platform.keychain_read(bad, "clark", run=run, on=platform.MAC)
        self.assertEqual(calls, [])

    def test_a_program_that_cannot_run_is_one_plain_line_without_the_key(self):
        import subprocess
        for fault in (OSError("no such file " + KEY), subprocess.TimeoutExpired(["security", "-i", KEY], 15)):
            def run(args, **kw):
                raise fault
            for call in (lambda: platform.keychain_save(self.SERVICE, "clark", KEY, run=run, on=platform.MAC),
                         lambda: platform.keychain_read(self.SERVICE, "clark", run=run, on=platform.MAC)):
                with self.assertRaises(platform.PlatformError) as caught:
                    call()
                self.assertEqual(str(caught.exception), platform.KEYCHAIN_FAILED)
                self.assertIsNone(caught.exception.__cause__)
                self.assertTrue(caught.exception.__suppress_context__)

    def test_other_systems_are_not_built_yet(self):
        for call in (lambda: platform.keychain_save(self.SERVICE, "clark", KEY, on=platform.WINDOWS),
                     lambda: platform.keychain_has(self.SERVICE, "clark", on=platform.WINDOWS),
                     lambda: platform.keychain_read(self.SERVICE, "clark", on=platform.WINDOWS),
                     lambda: platform.keychain_remove(self.SERVICE, "clark", on=platform.WINDOWS)):
            with self.assertRaises(platform.NotBuiltYet):
                call()

    def test_the_keychain_store_uses_the_data_folder_id_and_the_fixed_account(self):
        seen = []
        with mock.patch.object(platform, "keychain_save", lambda *a, **k: seen.append(a) or True), \
                mock.patch.object(platform, "keychain_has", lambda *a, **k: seen.append(a) or True), \
                mock.patch.object(platform, "keychain_read", lambda *a, **k: seen.append(a) or KEY), \
                mock.patch.object(platform, "keychain_remove", lambda *a, **k: seen.append(a) or True):
            k = providers.KeychainStore("/tmp/some-data-folder")
            for p in ("claude", "openai"):
                k.put(p, KEY), k.has(p), k.peek(p), k.remove(p)
            with self.assertRaises(ValueError):
                k.has("deepseek")
        fid = providers.folder_id("/tmp/some-data-folder")
        self.assertRegex(fid, r"^[0-9a-f]{12}$")
        self.assertEqual({a[:2] for a in seen}, {(f"clark.ai.{fid}.claude", "clark"), (f"clark.ai.{fid}.openai", "clark")})
        self.assertTrue(platform.KEYCHAIN_NAME.fullmatch(f"clark.ai.{fid}.openai"))


class TheKeyIsReadInOnePlace(unittest.TestCase):
    """Only platform.py names the program; only keychain_read asks for the secret (-w); only providers.py calls keychain_read."""

    def test_only_platform_names_the_program_or_its_find_command(self):
        for path in sorted((ROOT / "src" / "clark").glob("*.py")):
            if path.name == "platform.py":
                continue
            text = path.read_text(encoding="utf-8")
            for needle in ("find-generic-password", "find-internet-password", "/usr/bin/security", "add-generic-password"):
                self.assertNotIn(needle, text, path.name)

    def test_only_keychain_read_asks_for_the_secret(self):
        text = (ROOT / "src" / "clark" / "platform.py").read_text(encoding="utf-8")
        body = text[text.index("def keychain_has"):text.index("def keychain_read")]
        self.assertNotRegex(body, r'"-[wg]"')
        read = text[text.index("def keychain_read"):text.index("# Opening files and the system's own dialogs")]
        self.assertEqual(re.findall(r'"-[wg]"', read), ['"-w"'])

    def test_only_providers_reads_a_key(self):
        for path in sorted((ROOT / "src" / "clark").rglob("*.py")):
            if path.name in ("platform.py", "providers.py"):
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("keychain_read", text, path.name)
            self.assertNotRegex(text, r"\.peek\(", path.name)


class PublishedFile(unittest.TestCase):
    def test_the_published_page_has_none_of_the_card_and_no_route(self):
        view = (ROOT / "src" / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for needle in ("/api/ai-connect", "/api/ai-disconnect", "/api/ai-model", "ai-connect", "ai-settings", "Model for ask clark", "Connect Claude",
                       "Paste your key", "Claude Opus", "Claude Sonnet", "Claude Haiku", "ChatGPT sign-in", "Claude subscription", "keychain", "ai-prov",
                       "Use it anyway", "TESTONLY"):
            self.assertNotIn(needle, view, "a published file has no Settings, so none of this")

    def test_the_editor_page_has_the_card_and_the_key_box_is_a_password_box_that_is_not_filled_in(self):
        edit = (ROOT / "src" / "clark" / "page" / "page.html").read_text(encoding="utf-8")
        self.assertIn("/api/ai-connect", edit)
        src = (ROOT / "src" / "clark" / "page" / "src" / "edit" / "AiSettings.jsx").read_text(encoding="utf-8")
        box = re.search(r'<input id="ai-key"[^>]*>', src).group(0)
        self.assertIn('type="password"', box)
        self.assertIn('autocomplete="off"', box)
        self.assertNotRegex(box, r"\bvalue=")
        for banned in ("localStorage", "sessionStorage", "console."):
            self.assertNotIn(banned, src)

    def test_nothing_of_the_ai_choice_is_in_the_published_report_inputs(self):
        # the settings file is the data folder's, never a report input: the publisher reads the store, not settings.json
        text = (ROOT / "src" / "clark" / "publish.py").read_text(encoding="utf-8")
        for needle in ("ai_claude_how", "ai_openai", "ai_model", "ai_connect", "providers", "settings.json"):
            self.assertNotIn(needle, text)


if __name__ == "__main__":
    unittest.main()
