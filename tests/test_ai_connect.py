"""#446: Settings › AI on the server side (src/clark/ai_connect.py, the keychain calls in platform.py, the four routes in server.py).
No browser, and the real keychain is never touched: every test uses a FAKE keychain, or a fake `run` for the program that would.

Run: python3 dev/run_tests.py test_ai_connect
The things this pins:
- the key is kept ONLY by the keychain seam, and never appears in any reply, any log line, the settings file or anything in the data folder;
- Disconnect takes it out; a body of the wrong shape, type or fields is refused and keeps nothing;
- the routes have the same doors as every other POST route (token, Host, Origin, JSON, length);
- the program that keeps the key is given the key on standard input only, with no trusted program, and never anywhere else;
- the model is an ordinary setting, only one of the three the prototype lists;
- the published file has none of the card's words and no route.
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

from clark import ai_connect, platform, server as sv, settings

KEY = "zz-fakekey-TESTONLY-0123456789abcdef"
PIECES = (KEY, KEY[-4:], KEY[-8:], KEY[:20], "TESTONLY-0123456789")     # the whole key and the bits a careless reply might carry
GOOD = {"provider": "claude", "how": "key", "key": KEY}


class FakeKeychain:
    """What the keychain is to the service: it holds the one secret, in memory. Never reached by anything real."""

    def __init__(self, fail=False):
        self.secret, self.fail, self.calls = None, fail, []

    def save(self, secret):
        self.calls.append("save")
        if self.fail:
            raise platform.PlatformError(platform.KEYCHAIN_FAILED)
        self.secret = secret
        return True

    def has(self):
        return self.secret is not None

    def remove(self):
        self.calls.append("remove")
        self.secret = None
        return True


class Signed:
    """A provider whose Claude sign-in is there, or is not."""

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
        self.keys = FakeKeychain()
        self.provider = Signed()
        self.service = ai_connect.AiConnect(self.d, provider=self.provider, keychain=self.keys)
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
    def test_a_key_goes_to_the_keychain_and_comes_back_nowhere(self):
        status, got = self.call("POST", "/api/ai-connect", GOOD)
        self.assertEqual((status, got["ok"], got["connected"], got["how"]), (200, True, True, "key"))
        self.assertEqual(self.keys.secret, KEY, "the keychain seam was given the key")
        self.assertEqual(set(got), {"ok", "provider", "connected", "how", "model", "models", "openai", "message"})
        status, got = self.call("GET", "/api/ai-connect")
        self.assertEqual((status, got["connected"], got["how"]), (200, True, "key"))
        self.assertEqual([m["id"] for m in got["models"]], ["claude-opus", "claude-sonnet", "claude-haiku"])
        self.assertEqual(got["openai"], {"later": True})
        self.keep_nothing_of_the_key()
        settings_file = (self.d / "settings.json").read_text(encoding="utf-8")
        self.assertEqual(json.loads(settings_file), {"ai_claude_how": "key", "ai_model": "claude-opus"}, "only ordinary words are kept")

    def test_a_refusal_never_repeats_what_it_was_given(self):
        for body in ({**GOOD, "key": KEY + " with spaces"}, {**GOOD, "key": KEY + '"'}, {**GOOD, "key": KEY + "\n"}, {**GOOD, "key": "short"},
                     {**GOOD, "key": "é" + KEY}, {**GOOD, "key": KEY * 40}):
            status, got = self.call("POST", "/api/ai-connect", body)
            self.assertEqual((status, got["ok"], got["code"]), (400, False, "bad_key"), body["key"][:12])
        self.assertIsNone(self.keys.secret)
        self.assertFalse((self.d / "settings.json").exists())
        self.keep_nothing_of_the_key()

    def test_a_body_of_the_wrong_shape_is_refused_and_keeps_nothing(self):
        bad = [{**GOOD, "key": 12345}, {**GOOD, "key": [KEY]}, {**GOOD, "key": {"a": KEY}}, {**GOOD, "key": None}, {**GOOD, "key": True},
               {**GOOD, "extra": KEY}, {**GOOD, "provider": "openai"}, {**GOOD, "provider": 1}, {**GOOD, "how": "token"}, {**GOOD, "how": ["key"]},
               {"provider": "claude", "how": "key"}, {"how": "key", "key": KEY}, {"provider": "claude", "key": KEY},
               {"provider": "claude", "how": "subscription", "key": KEY}, {"provider": "claude", "how": "subscription", "extra": 1},
               [GOOD], [KEY], KEY, None, 7, {}]
        for body in bad:
            raw = json.dumps(body).encode()
            status, got = self.call("POST", "/api/ai-connect", raw)
            self.assertEqual((status, got["ok"], got["code"]), (400, False, "bad_request"), body)
        self.assertEqual(self.keys.calls, [], "nothing reached the keychain")
        self.assertFalse((self.d / "settings.json").exists())
        self.keep_nothing_of_the_key()

    def test_a_keychain_that_cannot_keep_it_says_so_and_connects_nothing(self):
        self.keys.fail = True
        status, got = self.call("POST", "/api/ai-connect", GOOD)
        self.assertEqual((status, got["ok"], got["connected"], got["code"]), (200, False, False, "keychain"))
        self.assertEqual(self.call("GET", "/api/ai-connect")[1]["connected"], False)
        self.assertFalse((self.d / "settings.json").exists())
        self.keep_nothing_of_the_key()

    def test_a_fault_inside_the_keychain_seam_does_not_put_the_key_in_the_log_or_the_reply(self):
        def boom(secret):
            raise RuntimeError("could not store " + secret)       # even a careless seam's fault text must not reach the log or the page
        self.keys.save = boom
        status, got = self.call("POST", "/api/ai-connect", GOOD)
        self.assertEqual((status, got["connected"], got["code"]), (200, False, "keychain"))
        self.keep_nothing_of_the_key()

    def test_the_subscription_needs_the_sign_in_and_asks_for_no_key(self):
        self.provider.connected = False
        status, got = self.call("POST", "/api/ai-connect", {"provider": "claude", "how": "subscription"})
        self.assertEqual((status, got["connected"], got["code"]), (200, False, "not_signed_in"))
        self.assertIn("isn't signed in", got["message"])
        self.provider.connected = True
        status, got = self.call("POST", "/api/ai-connect", {"provider": "claude", "how": "subscription"})
        self.assertEqual((status, got["connected"], got["how"]), (200, True, "subscription"))
        self.assertEqual(self.keys.calls, ["remove"], "no key was kept, and none is left from before")

    def test_switching_to_the_subscription_takes_a_kept_key_out(self):
        self.call("POST", "/api/ai-connect", GOOD)
        self.call("POST", "/api/ai-connect", {"provider": "claude", "how": "subscription"})
        self.assertIsNone(self.keys.secret)

    def test_a_key_that_has_gone_from_the_keychain_reads_as_not_connected(self):
        self.call("POST", "/api/ai-connect", GOOD)
        self.keys.secret = None                                   # taken out by hand, in Keychain Access
        status, got = self.call("GET", "/api/ai-connect")
        self.assertEqual((got["connected"], got["models"], got["model"]), (False, [], ""))


class Disconnecting(Base):
    def test_disconnect_takes_the_key_out_and_the_models_with_it(self):
        self.call("POST", "/api/ai-connect", GOOD)
        self.call("POST", "/api/ai-model", {"model": "claude-haiku"})
        status, got = self.call("POST", "/api/ai-disconnect", {"provider": "claude"})
        self.assertEqual((status, got["ok"], got["connected"], got["models"], got["model"]), (200, True, False, [], ""))
        self.assertIsNone(self.keys.secret)
        self.assertEqual(json.loads((self.d / "settings.json").read_text(encoding="utf-8")), {})
        self.assertEqual(self.call("GET", "/api/ai-connect")[1]["connected"], False)
        self.keep_nothing_of_the_key()

    def test_a_key_that_cannot_be_taken_out_is_still_connected_and_says_so(self):
        self.call("POST", "/api/ai-connect", GOOD)
        self.keys.remove = lambda: False
        status, got = self.call("POST", "/api/ai-disconnect", {"provider": "claude"})
        self.assertEqual((status, got["connected"], got["code"]), (409, True, "cant_remove"))
        self.assertEqual(self.call("GET", "/api/ai-connect")[1]["connected"], True)

    def test_disconnect_takes_only_the_provider(self):
        for body in ({}, {"provider": "openai"}, {"provider": "claude", "extra": 1}, {"provider": ["claude"]}, [], None, "claude"):
            status, got = self.call("POST", "/api/ai-disconnect", json.dumps(body).encode())
            self.assertEqual((status, got["code"]), (400, "bad_request"), body)


class Model(Base):
    def test_only_the_three_models_and_only_when_connected(self):
        status, got = self.call("POST", "/api/ai-model", {"model": "claude-sonnet"})
        self.assertEqual((status, got["code"]), (409, "not_connected"))
        self.call("POST", "/api/ai-connect", GOOD)
        self.assertEqual(self.call("GET", "/api/ai-connect")[1]["model"], "claude-opus", "Opus, the recommended one, to start with")
        status, got = self.call("POST", "/api/ai-model", {"model": "claude-sonnet"})
        self.assertEqual((status, got["model"]), (200, "claude-sonnet"))
        self.assertEqual(json.loads((self.d / "settings.json").read_text(encoding="utf-8"))["ai_model"], "claude-sonnet", "an ordinary setting")
        self.assertEqual(ai_connect.chosen_model(self.d), "claude-sonnet")
        for body in ({"model": "gpt-5"}, {"model": "oa-flagship"}, {"model": ""}, {"model": 3}, {"model": ["claude-opus"]}, {"model": "claude-opus", "x": 1}, {}, [], None):
            status, got = self.call("POST", "/api/ai-model", json.dumps(body).encode())
            self.assertEqual((status, got["code"]), (400, "bad_request"), body)
        self.assertEqual(ai_connect.chosen_model(self.d), "claude-sonnet")

    def test_the_models_are_the_prototypes(self):
        proto = (Path(__file__).resolve().parents[1] / "system" / "prototype" / "views.js").read_text(encoding="utf-8")
        listed = re.search(r"const AI_MODELS = \{ claude: \[(.*?)\], openai", proto).group(1)
        theirs = re.findall(r"\['(claude-[a-z]+)', '([^']+)'(?:, (1))?\]", listed)
        self.assertEqual(theirs, [(i, t, "1" if r else "") for i, t, r in ai_connect.MODELS])
        self.assertEqual(len(theirs), 3)

    def test_a_saved_word_that_is_not_a_listed_model_is_not_read_as_one(self):
        (self.d / "settings.json").write_text(json.dumps({"ai_model": "gpt-5", "ai_claude_how": "token"}), encoding="utf-8")
        self.assertEqual(ai_connect.chosen_model(self.d), "")
        self.assertEqual(self.call("GET", "/api/ai-connect")[1]["connected"], False)

    def test_a_settings_file_that_cannot_be_read_is_not_replaced(self):
        (self.d / "settings.json").write_text("not json at all", encoding="utf-8")
        status, got = self.call("POST", "/api/ai-connect", {"provider": "claude", "how": "subscription"})
        self.assertEqual((status, got["code"]), (200, "cant_save"))
        self.assertEqual((self.d / "settings.json").read_text(encoding="utf-8"), "not json at all")


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

    def make_run(self, keep=True, code=0):
        calls = []

        def run(args, **kw):
            calls.append((list(args), kw))
            done = mock.Mock(returncode=0, stdout="", stderr="")
            if args[1:2] == ["find-generic-password"]:
                done.returncode = 0 if (keep and any(c[0][1:2] == ["-i"] for c in calls)) else 44
            return done
        return run, calls

    def test_the_key_is_on_standard_input_only(self):
        run, calls = self.make_run()
        self.assertTrue(platform.keychain_save("clark-ai-claude", "claude-api-key", KEY, run=run, on=platform.MAC))
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
        self.assertFalse(platform.keychain_save("clark-ai-claude", "claude-api-key", KEY, run=run, on=platform.MAC))

    def test_has_and_remove_never_ask_for_the_secret(self):
        run, calls = self.make_run()
        platform.keychain_has("clark-ai-claude", "claude-api-key", run=run, on=platform.MAC)
        platform.keychain_remove("clark-ai-claude", "claude-api-key", run=run, on=platform.MAC)
        flat = [a for args, _ in calls for a in args]
        for flag in ("-w", "-g", "-D"):
            self.assertNotIn(flag, flat, "reading the secret out is never asked for")
        self.assertIn("delete-generic-password", flat)

    def test_a_secret_that_could_not_be_passed_safely_is_refused_before_anything_runs(self):
        run, calls = self.make_run()
        for bad in ("", "short", "has space in it 123456", 'quote"in-it-123456', "back\\slash-123456", "new\nline-123456", "-leading-dash-123456", "é" * 20, "a" * 600, None, 12345, b"x" * 20):
            with self.assertRaises(ValueError):
                platform.keychain_save("clark-ai-claude", "claude-api-key", bad, run=run, on=platform.MAC)
        self.assertEqual(calls, [])

    def test_the_names_are_fixed_words(self):
        run, calls = self.make_run()
        for bad in ("", "A", 'x" -w "y', "a b c", "../x", None):
            with self.assertRaises(ValueError):
                platform.keychain_has(bad, "claude-api-key", run=run, on=platform.MAC)
        self.assertEqual(calls, [])

    def test_a_program_that_cannot_run_is_one_plain_line_without_the_key(self):
        import subprocess
        for fault in (OSError("no such file " + KEY), subprocess.TimeoutExpired(["security", "-i", KEY], 15)):
            def run(args, **kw):
                raise fault
            with self.assertRaises(platform.PlatformError) as caught:
                platform.keychain_save("clark-ai-claude", "claude-api-key", KEY, run=run, on=platform.MAC)
            self.assertEqual(str(caught.exception), platform.KEYCHAIN_FAILED)
            self.assertIsNone(caught.exception.__cause__)
            self.assertTrue(caught.exception.__suppress_context__)

    def test_other_systems_are_not_built_yet(self):
        for call in (lambda: platform.keychain_save("clark-ai-claude", "claude-api-key", KEY, on=platform.WINDOWS),
                     lambda: platform.keychain_has("clark-ai-claude", "claude-api-key", on=platform.WINDOWS),
                     lambda: platform.keychain_remove("clark-ai-claude", "claude-api-key", on=platform.WINDOWS)):
            with self.assertRaises(platform.NotBuiltYet):
                call()

    def test_the_real_keychain_wrapper_uses_only_the_fixed_names(self):
        seen = []
        with mock.patch.object(platform, "keychain_save", lambda *a, **k: seen.append(a) or True), \
                mock.patch.object(platform, "keychain_has", lambda *a, **k: seen.append(a) or True), \
                mock.patch.object(platform, "keychain_remove", lambda *a, **k: seen.append(a) or True):
            k = ai_connect.Keychain()
            k.save(KEY), k.has(), k.remove()
        self.assertEqual({a[:2] for a in seen}, {("clark-ai-claude", "claude-api-key")})


class TheKeyIsNeverRead(unittest.TestCase):
    """Nothing in this version reads the key back out of the keychain, and no module but platform.py starts the program."""

    def test_only_platform_names_the_program_or_its_find_command(self):
        for path in sorted((Path(__file__).resolve().parents[1] / "src" / "clark").glob("*.py")):
            if path.name == "platform.py":
                continue
            text = path.read_text(encoding="utf-8")
            for needle in ("find-generic-password", "find-internet-password", "/usr/bin/security", "add-generic-password"):
                self.assertNotIn(needle, text, path.name)

    def test_the_two_secret_flags_are_not_in_platform_either(self):
        text = (Path(__file__).resolve().parents[1] / "src" / "clark" / "platform.py").read_text(encoding="utf-8")
        body = text[text.index("def keychain_has"):text.index("# Opening files and the system's own dialogs")]
        self.assertNotRegex(body, r'"-[wg]"')


class PublishedFile(unittest.TestCase):
    def test_the_published_page_has_none_of_the_card_and_no_route(self):
        view = (Path(__file__).resolve().parents[1] / "src" / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for needle in ("/api/ai-connect", "/api/ai-disconnect", "/api/ai-model", "ai-connect", "ai-settings", "Model for ask clark", "Connect Claude",
                       "Paste your key", "Claude Opus", "Claude Sonnet", "Claude Haiku", "ChatGPT sign-in", "Claude subscription", "keychain", "ai-prov"):
            self.assertNotIn(needle, view, "a published file has no Settings, so none of this")

    def test_the_editor_page_has_the_card_and_the_key_box_is_a_password_box_that_is_not_filled_in(self):
        edit = (Path(__file__).resolve().parents[1] / "src" / "clark" / "page" / "page.html").read_text(encoding="utf-8")
        self.assertIn("/api/ai-connect", edit)
        src = (Path(__file__).resolve().parents[1] / "src" / "clark" / "page" / "src" / "edit" / "AiSettings.jsx").read_text(encoding="utf-8")
        box = re.search(r'<input id="ai-key"[^>]*>', src).group(0)
        self.assertIn('type="password"', box)
        self.assertIn('autocomplete="off"', box)
        self.assertNotRegex(box, r"\bvalue=")
        for banned in ("localStorage", "sessionStorage", "console."):
            self.assertNotIn(banned, src)

    def test_nothing_of_the_ai_choice_is_in_the_published_report_inputs(self):
        # the settings file is the data folder's, never a report input: the publisher reads the store, not settings.json
        text = (Path(__file__).resolve().parents[1] / "src" / "clark" / "publish.py").read_text(encoding="utf-8")
        for needle in ("ai_claude_how", "ai_model", "ai_connect", "settings.json"):
            self.assertNotIn(needle, text)


if __name__ == "__main__":
    unittest.main()
