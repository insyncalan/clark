"""#52: the ChatGPT sign-in: the three layers from ai_codex.py, each on its own. The wall is tested for real on this Mac with no model and no network;
everything else with a fake run. A real run is a hand check, recorded on item #52.

Run: python3 dev/run_tests.py test_ai_codex
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401
from clark import ai_codex as c, ask


def events(*items, tail=None):
    lines = [{"type": "thread.started"}] + [{"type": "item.completed", "item": i} for i in items] + (tail or [{"type": "turn.completed"}])
    return "\n".join(json.dumps(x) for x in lines).encode("utf-8")


ANSWER = {"type": "agent_message", "text": "Paris."}


class TheWall(unittest.TestCase):
    """Real sandbox-exec, real files. If this fails, nothing else in this file matters."""

    def setUp(self):
        self.home = str(Path.home())
        self.scratch = os.path.realpath(tempfile.gettempdir())
        self.outside = tempfile.mkdtemp(prefix="clark-test-wall-", dir=self.home)
        self.addCleanup(shutil.rmtree, self.outside, True)
        self.other_tmp = tempfile.mkdtemp(prefix="clark-test-other-", dir=self.scratch)
        self.addCleanup(shutil.rmtree, self.other_tmp, True)
        self.own = tempfile.mkdtemp(prefix=c.PREFIX, dir=self.scratch)
        self.addCleanup(shutil.rmtree, self.own, True)
        self.program = "/opt/none/codex"

    def run_in(self, *cmd):
        rules = c.wall(self.home, self.program, self.scratch)
        return subprocess.run([c.SANDBOX, "-p", rules, *cmd], capture_output=True, text=True, timeout=20)

    def plant(self, folder, text="ZQ-PLANTED"):
        p = Path(folder) / "planted.txt"
        p.write_text(text, encoding="utf-8")
        return str(p)

    def test_a_file_in_the_home_folder_cannot_be_read(self):
        got = self.run_in("/bin/cat", self.plant(self.outside))
        self.assertNotEqual(got.returncode, 0)
        self.assertNotIn("ZQ-PLANTED", got.stdout)

    def test_a_file_in_another_temporary_folder_cannot_be_read(self):
        got = self.run_in("/bin/cat", self.plant(self.other_tmp))
        self.assertNotEqual(got.returncode, 0)
        self.assertNotIn("ZQ-PLANTED", got.stdout)

    def test_this_runs_own_folder_can_be_read_and_written(self):
        self.assertEqual(self.run_in("/bin/cat", self.plant(self.own)).stdout, "ZQ-PLANTED")
        self.assertEqual(self.run_in("/usr/bin/touch", os.path.join(self.own, "new")).returncode, 0)

    def test_nothing_can_be_written_outside(self):
        for folder in (self.outside, self.other_tmp):
            self.assertNotEqual(self.run_in("/usr/bin/touch", os.path.join(folder, "new")).returncode, 0, folder)
            self.assertFalse(os.path.exists(os.path.join(folder, "new")))


class TheCommandLine(unittest.TestCase):
    def args(self, **kw):
        return c.arguments("/x/codex", home="/Users/sam", scratch="/tmp/s", **kw)

    def test_the_wall_comes_first_and_every_tool_is_off(self):
        a = self.args()
        self.assertEqual(a[:2], [c.SANDBOX, "-p"])
        self.assertEqual(a[3:5], ["/x/codex", "exec"])
        for name in ("shell_tool", "unified_exec", "apps", "plugins", "multi_agent", "code_mode_host", "view_image", "computer_use"):
            self.assertEqual(a[a.index(name) - 1], "--disable")
        self.assertIn('web_search="disabled"', a)
        for needed in ("--ignore-user-config", "--ignore-rules", "--ephemeral"):
            self.assertIn(needed, a)
        self.assertEqual(a[a.index("--sandbox") + 1], "read-only")
        self.assertEqual(a[-1], "-", "the question goes on standard input, never the command line")

    def test_no_flag_that_would_open_anything(self):
        joined = " ".join(self.args())
        for bad in ("danger-full-access", "workspace-write", "--dangerously", "--add-dir", "--full-auto", "--approve-for-me", "--worktree"):
            self.assertNotIn(bad, joined)

    def test_clarks_rules_replace_codexs_prompt(self):
        a = self.args(canary="zq1", system=ask.RULES)
        rules = [x for x in a if x.startswith("base_instructions=")]
        self.assertEqual(json.loads(rules[0].split("=", 1)[1]), ask.system_prompt("zq1", ask.RULES))

    def test_only_a_listed_model_reaches_the_command_line(self):
        self.assertNotIn("--model", self.args())
        a = self.args(model="gpt-6-luna")
        self.assertEqual(a[a.index("--model") + 1], "gpt-6-luna")
        for bad in ("--evil", "gpt-5.5", 1, ""):
            with self.assertRaises(ValueError):
                self.args(model=bad)


class TheEvents(unittest.TestCase):
    def test_the_last_message_is_the_answer(self):
        self.assertEqual(c.read_events(events({"type": "agent_message", "text": "Thinking."}, ANSWER)), ("answer", "Paris."))

    def test_the_code_mode_notice_is_not_an_answer_or_a_fault(self):
        self.assertEqual(c.read_events(events({"type": "error", "message": "Code Mode is unavailable"}, ANSWER)), ("answer", "Paris."))

    def test_any_tool_use_drops_the_answer_whatever_it_says(self):
        for kind in ("command_execution", "file_change", "mcp_tool_call", "web_search", "something_new"):
            self.assertEqual(c.read_events(events({"type": kind}, ANSWER))[0], "tools", kind)

    def test_a_limit_a_model_and_a_plain_fault_are_told_apart(self):
        fail = lambda m: events(tail=[{"type": "error", "message": m}, {"type": "turn.failed", "error": {"message": m}}])     # noqa: E731
        self.assertEqual(c.read_events(fail("You've hit your usage limit."))[0], "limit")
        self.assertEqual(c.read_events(fail("The 'x' model is not supported when using Codex with a ChatGPT account."))[0], "model")
        self.assertEqual(c.read_events(fail("Something else"))[0], "none")

    def test_rubbish_is_no_answer(self):
        for out in (b"", b"not json", b"\xff\xfe", b"[1,2]", events()):
            self.assertEqual(c.read_events(out), ("none", None))


class TheSignIn(unittest.TestCase):
    def login(self, out, code=0, status="ok"):
        with mock.patch.object(c.platform, "run_stoppable", return_value=(status, out, code)) as run:
            got = c.CodexCommand(env={}).login_problem(Path("/x/codex"))
        self.assertTrue(run.call_args.kwargs["merge_err"])
        return got

    def test_only_a_chatgpt_sign_in_will_do(self):
        self.assertIsNone(self.login(b"Logged in using ChatGPT\n"))
        self.assertEqual(self.login(b"Logged in using an API key - sk-***\n"), c.API_KEY_LOGIN)
        self.assertEqual(self.login(b"Not logged in\n", 1), c.NOT_SIGNED_IN)
        self.assertEqual(self.login(b"", None, "failed"), c.CANT_USE)

    def test_an_answer_with_a_run_is_read_and_faults_are_plain(self):
        p = c.CodexCommand(env={})
        path = Path("/x/codex")
        for got, want in (((("ok", events(ANSWER), 0)), "Paris."),
                          (("ok", events({"type": "command_execution"}, ANSWER), 0), ask.Failure(c.TOOLS_USED)),
                          (("slow", b"", None), ask.Failure(c.TOO_SLOW)), (("too_much", b"", None), ask.Failure(c.TOO_LONG)),
                          (("stopped", b"", None), ask.Failure(ask.STOPPED)), (("failed", b"", 1), ask.Failure(c.NO_ANSWER))):
            with mock.patch.object(c, "run", return_value=got):
                self.assertEqual(p.answer(path, "q", system=ask.RULES), want)

    def test_a_refused_model_is_refused_before_anything_starts(self):
        with mock.patch.object(c, "run") as run:
            got = c.CodexCommand(env={}).ask(ask.Request(text="q", question="q", system=ask.RULES), "nope")
        self.assertIsInstance(got, ask.Failure)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
