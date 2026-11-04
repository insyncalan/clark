"""Item 54, slice 3: the Claude subscription provider, the --model allow-list, the limit result and the import rule.

Run: python3 tests/test_ai_providers.py
FABRICATED FIXTURES: the limit streams below are written for these tests from the shape the Claude command is known to use (a
`rate_limit_event` with a `rejected` status; a failed result with status 429; a failed result whose text says the limit was
reached). They are not recordings. Re-record them against the real command before the wording is final.
"""
import ast
import json
import unittest
from pathlib import Path

from _paths import SRC  # noqa: F401
from test_ask_claude import ANSWER, Fake, result

from clark import ai_providers, ask, ask_claude as ac

ROOT = Path(__file__).resolve().parents[1]

# FABRICATED (see the top of the file)
LIMIT_EVENT = json.dumps([
    {"type": "system", "subtype": "init"},
    {"type": "rate_limit_event", "rate_limit_info": {"status": "rejected", "rateLimitType": "five_hour", "resetsAt": 1900000000}},
    {"type": "result", "subtype": "success", "is_error": True, "result": "x"}])
LIMIT_LINES = "\n".join(json.dumps(x) for x in json.loads(LIMIT_EVENT))
LIMIT_429 = json.dumps({"type": "result", "subtype": "success", "is_error": True, "api_error_status": 429, "result": "anything"})
LIMIT_TEXT = json.dumps({"type": "result", "subtype": "success", "is_error": True, "result": "You've hit your limit. Resets later."})
ALLOWED_EVENT = json.dumps({"type": "rate_limit_event", "rate_limit_info": {"status": "allowed"}})


class Detect(unittest.TestCase):
    def test_the_limit_event_the_429_and_the_text_fallback_are_each_seen(self):
        for text in (LIMIT_EVENT, LIMIT_LINES, LIMIT_429, LIMIT_TEXT):
            self.assertTrue(ac.limit_reached(text.encode("utf-8")), text[:60])

    def test_ordinary_output_is_not_a_limit(self):
        for text in (result(ANSWER), ALLOWED_EVENT, "", "not json", json.dumps({"type": "result", "is_error": False,
                     "result": "You've hit your limit"}), json.dumps({"type": "result", "is_error": True, "result": "boom"})):
            self.assertFalse(ac.limit_reached(text.encode("utf-8")), text[:60])
        self.assertFalse(ac.limit_reached(b"\xff\xfe"))


class Models(Fake):
    def test_the_allow_list_is_the_four_aliases(self):
        self.assertEqual(ac.MODELS, ("opus", "sonnet", "haiku", "fable"))
        self.assertEqual(ai_providers.ClaudeSubscription(command=self.provider).models(), ac.MODELS)

    def test_the_help_text_names_the_aliases_this_list_follows(self):
        # the pinned help line (recorded from the command's --help); the list is not exhaustive there, so the lines are only a floor
        pinned = "an alias for the latest model (e.g. 'fable', 'opus', or 'sonnet') or a model's full name."
        for alias in ("fable", "opus", "sonnet"):
            self.assertIn(alias, pinned)
            self.assertIn(alias, ac.MODELS)

    def test_a_chosen_alias_is_sent_as_model_and_none_leaves_it_out(self):
        for model in ac.MODELS:
            self.assertEqual(self.provider.ask(self.request(), model), ANSWER)
            args = self.seen()["args"]
            self.assertEqual(args[args.index("--model") + 1], model)
        self.assertEqual(self.provider.ask(self.request()), ANSWER)
        self.assertNotIn("--model", self.seen()["args"])

    def test_anything_else_is_refused_before_anything_runs(self):
        for bad in ("claude-opus-4", "OPUS", "opus ", "--bare", "", "opus --add-dir /", 5, ["opus"]):
            self.assertEqual(self.provider.ask(self.request(), bad), ask.Failure(ac.MODEL_REFUSED), repr(bad))
            with self.assertRaises(ValueError):
                ac.arguments("/x/claude", model=bad)
        self.assertEqual(self.calls(), [], "the command was never started")
        self.assertIsNone(self.seen())

    def test_a_help_without_model_is_unusable(self):
        self.put("help", "\n".join(f"  {f} <x>" for f in ac.NEEDED_FLAGS if f != "--model"))
        got = self.provider.ask(self.request())
        self.assertEqual(got, ask.Failure(ac.CANT_USE))


class Limits(Fake):
    def limited(self, text):
        self.put("reply", text)

    def test_each_limit_shape_gives_a_limit_that_offers_the_others_and_does_not_switch(self):
        for text in (LIMIT_EVENT, LIMIT_429, LIMIT_TEXT):
            self.limited(text)
            (self.bin / "calls.jsonl").unlink(missing_ok=True)
            got = self.provider.ask(self.request(), "opus")
            self.assertIsInstance(got, ac.LimitReached)
            self.assertEqual(got.others, ("sonnet", "haiku", "fable"))
            self.assertIn("sonnet, haiku, fable", got.message)
            runs = [c for c in self.calls() if "--print" in c["args"]]
            self.assertEqual(len(runs), 1, "no second run on another model")
            self.assertEqual(runs[0]["args"][runs[0]["args"].index("--model") + 1], "opus")

    def test_a_failed_exit_with_a_limit_stream_is_still_a_limit(self):
        self.assertTrue(ac.limit_reached(LIMIT_LINES.encode("utf-8")))

    def test_a_plain_failure_is_not_called_a_limit(self):
        self.limited("")
        self.assertNotIsInstance(self.provider.ask(self.request(), "opus"), ac.LimitReached)


class Sends(Fake):
    def test_the_per_model_send_limit_is_pinned_and_stops_before_the_command(self):
        self.assertEqual(set(ai_providers.SEND_LIMITS), set(ac.MODELS))
        now = [0.0]
        prov = ai_providers.ClaudeSubscription(command=self.provider, limits={"opus": 2, "sonnet": 1}, clock=lambda: now[0])
        self.assertEqual(prov.ask(self.request(), "opus"), ANSWER)
        self.assertEqual(prov.ask(self.request(), "opus"), ANSWER)
        got = prov.ask(self.request(), "opus")
        self.assertIsInstance(got, ac.LimitReached)
        self.assertEqual(got.others, ("sonnet", "haiku", "fable"))
        self.assertEqual(len([c for c in self.calls() if "--print" in c["args"]]), 2, "the third never reached the command")
        self.assertEqual(prov.ask(self.request(), "sonnet"), ANSWER, "another model is the person's choice, and has its own count")
        now[0] = ai_providers.SEND_WINDOW + 1
        self.assertEqual(prov.ask(self.request(), "opus"), ANSWER, "a new window")

    def test_a_model_with_no_pinned_limit_sends_nothing(self):
        prov = ai_providers.ClaudeSubscription(command=self.provider, limits={})
        self.assertIsInstance(prov.ask(self.request(), "haiku"), ac.LimitReached)

    def test_the_provider_refuses_a_bad_alias_and_is_found_by_name(self):
        prov = ai_providers.provider_for("claude", command=self.provider)
        self.assertEqual(prov.ask(self.request(), "gpt"), ask.Failure(ac.MODEL_REFUSED))
        self.assertIsNone(ai_providers.provider_for("openai"))
        self.assertTrue(prov.status()["connected"])


class Wording(unittest.TestCase):
    def test_the_new_lines_are_marked_for_the_owner(self):
        for line in (ac.MODEL_REFUSED, ac.LIMIT_REACHED, ac.LIMIT_OFFER):
            self.assertTrue(line.startswith("WORDING: owner to rule"))


NETWORK = {"socket", "ssl", "http", "urllib", "urllib3", "requests", "ftplib", "smtplib", "poplib", "imaplib", "telnetlib",
           "xmlrpc", "asyncio", "socketserver", "subprocess", "multiprocessing", "ctypes"}
NOT_NETWORK = {"urllib.parse", "urllib.error"}          # text handling only
# Modules that already had one of these before item 54 (local sockets, the loopback server, the Chrome link, the launcher).
# A new entry here is a reviewed change; a new provider goes in ai_providers.py, never here.
KNOWN = {"platform.py", "ai_providers.py", "server.py", "pdf.py", "launch.py", "__main__.py"}


def network_imports(source):
    found = []
    for node in ast.walk(ast.parse(source)):
        names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
            [node.module or ""] if isinstance(node, ast.ImportFrom) and not node.level else []
        for name in names:
            if name.split(".")[0] in NETWORK and name not in NOT_NETWORK:
                found.append(name)
    return found


class Imports(unittest.TestCase):
    def test_no_network_or_subprocess_import_outside_the_known_files(self):
        bad = {}
        for path in sorted((ROOT / "src" / "clark").rglob("*.py")):
            if path.name in KNOWN:
                continue
            got = network_imports(path.read_text(encoding="utf-8"))
            if got:
                bad[str(path.relative_to(ROOT))] = got
        self.assertEqual(bad, {})

    def test_the_two_provider_modules_start_nothing_themselves(self):
        for name in ("ai_providers.py", "ask_claude.py"):
            self.assertEqual(network_imports((ROOT / "src" / "clark" / name).read_text(encoding="utf-8")), [], name)

    def test_the_rule_sees_an_import(self):
        self.assertEqual(network_imports("import socket\nfrom http import client\nimport urllib.request\nimport urllib.parse"),
                         ["socket", "http", "urllib.request"])


if __name__ == "__main__":
    unittest.main()
