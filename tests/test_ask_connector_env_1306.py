"""Row 1306: a question asked with a connector On hands the command the scrubbed environment (ask_claude.child_env), the discovery
call and the question run alike. Nothing from the process that started clark gets through. Only the command's start is recorded
(platform.run_stoppable); everything else is the real code path. Fictional data only.

Run: python3 dev/run_tests.py test_ask_connector_env_1306
"""
import json
import os
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

from clark import ask, ask_claude as ac, ask_connector_args as ca, ask_connectors

PATH = Path("/x/claude")
LISTING = b"claude.ai Microsoft 365: https://example.invalid/m - \xe2\x9c\x93 Connected"
REPLY = json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "ok"}).encode()
CANARY = "SECRET_CANARY"
ALLOWED = {"HOME", "USER", "LOGNAME", "LANG", "PATH"} | set(ac.PINNED_ENV)


class QuestionEnv(unittest.TestCase):
    def setUp(self):
        ask_connectors.clear_cache()
        self.calls = []
        patches = [mock.patch.dict(os.environ, {CANARY: "do-not-pass", "ANTHROPIC_API_KEY": "do-not-pass"}),
                   mock.patch.object(ac, "find_command", return_value=(PATH, None)),
                   mock.patch.object(ac.platform, "run_stoppable", side_effect=self.record)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(ask_connectors.clear_cache)

    def record(self, args, data, env, *_a, **_k):
        self.calls.append((list(args), dict(env)))
        return ("ok", LISTING, 0) if list(args[1:3]) == ["mcp", "list"] else ("ok", REPLY, 0)

    def asked(self):
        provider = ac.ClaudeCommand(places=())          # the real env: built inside the patched process environment
        with mock.patch.object(provider, "usable", return_value=(PATH, None)):
            provider.ask(ask.Request(text="Q", question="Q", connectors=("mail",)))
        return [c for c in self.calls if list(c[0][1:3]) != ["mcp", "list"]], [c for c in self.calls if list(c[0][1:3]) == ["mcp", "list"]]

    def test_the_question_run_gets_the_scrubbed_env(self):
        runs, lists = self.asked()
        self.assertGreaterEqual(len(lists), 1)          # the connector was found by the real discovery call (and looked for again after the run)
        self.assertEqual(len(runs), 1)
        args, env = runs[0]
        self.assertTrue(any(a.startswith(ca.FLAG_ALLOW) for a in args))   # it is the connector run, not today's plain one
        self.assertEqual(env, ac.child_env())
        self.assertNotIn(CANARY, env)
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertEqual(set(env) - ALLOWED, set())

    def test_the_discovery_call_gets_the_same_env(self):
        _runs, lists = self.asked()
        for _args, env in lists:
            self.assertEqual(env, ac.child_env())
            self.assertNotIn(CANARY, env)


if __name__ == "__main__":
    unittest.main()
