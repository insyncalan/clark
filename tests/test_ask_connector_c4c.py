"""Row 1306 C4c: what the target machine needs on top of the safe set. (a) the command is looked for in the fixed places and a missing one says so for a
connector run too; (b) every known claude.ai server except the one that is On is denied whole by its prefix; (c) a run whose init event lacks the allowed
connector tool is refused with its own words. Run: python3 dev/run_tests.py test_ask_connector_c4c
"""
import json
import shutil
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401
from clark import ask, ask_claude as ac, ask_connector_args as ca, ask_connector_stream as cs, ask_connectors
from test_ask_connector_wiring import PATH, Run, event, final, got, stream, use

P = "mcp__claude_ai_Microsoft_365"
FOUND = [{"connector": c, "label": c, "server": "claude.ai Microsoft 365"} for c in ("mail",)]


def init(*tools):
    return json.dumps({"type": "system", "subtype": "init", "tools": list(tools)})


class Missing(unittest.TestCase):
    def provider(self):
        return ac.ClaudeCommand(places=("/nowhere/claude",), env={}, limit=5)

    def test_a_connector_run_with_no_command_says_the_missing_words(self):
        for found, words in ((None, ac.NOT_INSTALLED), ("/somewhere/claude", ac.NOT_ELSEWHERE)):
            with mock.patch.object(shutil, "which", return_value=found), mock.patch.object(ac.platform, "system", return_value=ac.platform.MAC), \
                    mock.patch.object(ac.platform, "container_mode", return_value=False):
                p = self.provider()
                self.assertEqual(p.command(), (None, words))
                self.assertEqual(p.ask(ask.Request(text="Q", question="Q", connectors=("mail",))), ask.Failure(words))


class Servers(unittest.TestCase):
    KNOWN = ("Claude_Docs", "Gmail", "Google_Calendar", "Google_Drive", "Linear", "Microsoft_365", "Plaud", "Slides_AI", "Todoist", "Uber", "Vercel")

    def test_the_known_servers_are_pinned(self):
        self.assertEqual(ca.KNOWN_SERVERS, self.KNOWN)

    def test_every_known_server_but_the_on_one_is_denied_whole_by_prefix(self):
        args = ca.connector_args(FOUND, ["mail"])
        whole = {a for a in args if a.startswith("--disallowedTools=mcp__claude_ai_") and a.count("__") == 1}
        want = {f"--disallowedTools=mcp__claude_ai_{k}" for k in self.KNOWN if k != "Microsoft_365"}
        self.assertEqual(whole, want)
        self.assertNotIn(f"--disallowedTools={P}", args, "the On server itself is not denied whole")
        self.assertIn(f"--allowedTools={P}__outlook_email_search", args)

    def test_no_connector_on_adds_nothing(self):
        self.assertEqual(ca.connector_args(FOUND, []), [f"--disallowedTools={P}"])


class Init(Run):
    """The init event of a real run with `--tools ToolSearch` lists exactly [ToolSearch] (the connector tool is deferred, so it is not listed)."""
    def run_with(self, *lines):
        self.out = stream(*lines)
        return self.provider.ask(ask.Request(text="Q", question="Q", connectors=("mail",)))

    def test_the_words_are_the_approved_ones(self):
        self.assertEqual(ac.CONNECTOR_UNAVAILABLE, "A connector that is turned on was not available in this run, so nothing from it is shown.")
        self.assertEqual(ac.CONNECTOR_EXTRA_TOOLS, "This run had tools clark did not allow, so nothing from it is shown.")

    def test_an_init_with_exactly_the_loader_is_answered(self):
        self.assertEqual(self.run_with(init("ToolSearch"), final("Answer")), "Answer")

    def test_any_other_tool_in_the_init_refuses_with_the_second_words(self):
        for tools in (("ToolSearch", "DesignSync"), ("ToolSearch", "Bash"), ("ToolSearch", f"{P}__outlook_email_search"), ("DesignSync", "ListAgents", "ReportFindings", "ToolSearch")):
            self.assertEqual(self.run_with(init(*tools), final("Answer")), ask.Failure(ac.CONNECTOR_EXTRA_TOOLS), tools)

    def test_an_init_without_the_loader_refuses_with_the_first_words(self):
        self.assertEqual(self.run_with(init(), final("Answer")), ask.Failure(ac.CONNECTOR_UNAVAILABLE))

    def test_a_stream_without_an_init_event_is_judged_by_its_calls_alone(self):
        self.assertEqual(self.run_with(final("Answer")), "Answer")

    def test_init_problem_names_each_case(self):
        self.assertEqual(cs.init_problem(stream(init("ToolSearch"), final())), "")
        self.assertEqual(cs.init_problem(stream(final())), "")
        self.assertEqual(cs.init_problem(stream(init(), final())), "absent")
        self.assertEqual(cs.init_problem(stream(init("ToolSearch", "Read"), final())), "extra")
        self.assertEqual(cs.init_problem(stream(init("Read"), final())), "extra")
        self.assertFalse(cs.checked(stream(init("ToolSearch", "Read"), final()), {"Mail"})[0])
        self.assertTrue(cs.checked(stream(init("ToolSearch"), final()), {"Mail"})[0])


if __name__ == "__main__":
    unittest.main()
