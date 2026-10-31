"""#47c: the Claude command provider (src/clark/ask_claude.py, guarded-derived), against a FAKE command. Nothing here runs the real
`claude` (it would spend the person's plan); the fake is a small Python script written into a temporary folder that records what it
was given (its arguments, its environment, its working folder, standard input) and answers as each test asks.

Run: python3 dev/run_tests.py test_ask_claude
These tests pin the arguments, standard input, the fixed places, the scrubbed environment and the process handling. They cannot
prove that the real command honours --safe-mode; that is the manual smoke test the design note asks for, run once by hand.
"""
import json
import os
import shutil
import stat
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

from clark import ask, ask_claude as ac

HELP = "\n".join(f"  {f} <x>   something" for f in ac.NEEDED_FLAGS)

FAKE = r'''#!{python}
import json, os, sys, time
here = os.path.dirname(os.path.abspath(__file__))
mode = open(os.path.join(here, "mode")).read().strip()
args = sys.argv[1:]
if args == ["--version"]:
    if mode == "badversion":
        print("not a version")
    else:
        print("2.1.312 (Claude Code)")
    sys.exit(0)
if args == ["--help"]:
    text = open(os.path.join(here, "help")).read()
    print(text)
    sys.exit(0)
data = sys.stdin.read()
with open(os.path.join(here, "seen.json"), "w") as f:
    json.dump({{"args": args, "env": dict(os.environ), "cwd": os.getcwd(), "stdin": data, "pid": os.getpid(),
               "pgid": os.getpgid(0)}}, f)
if mode == "slow":
    time.sleep(60)
if mode == "helper":
    import subprocess
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    open(os.path.join(here, "helper.pid"), "w").write(str(p.pid))
    time.sleep(60)
if mode == "flood":
    sys.stdout.write("x" * 10000000)
    sys.stdout.flush()
    time.sleep(60)
if mode == "fail":
    sys.stderr.write("secret request text in an error\n")
    sys.exit(1)
if mode == "empty":
    sys.exit(0)
print("The plan is on track.")
print("CITE: P1")
'''


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:                                   # a zombie that has not been reaped yet counts as gone
        with os.popen(f"ps -o stat= -p {pid}") as p:
            return not p.read().strip().startswith("Z")
    except OSError:
        return True


class Fake(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-fake-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.bin = self.d / "bin"
        self.bin.mkdir()
        self.cmd = self.bin / "claude"
        self.cmd.write_text(FAKE.format(python=sys.executable), encoding="utf-8")
        self.cmd.chmod(self.cmd.stat().st_mode | stat.S_IXUSR)
        self.mode("ok")
        (self.bin / "help").write_text(HELP, encoding="utf-8")
        self.provider = ac.ClaudeCommand(places=(str(self.cmd),), env=ac.child_env(home=str(self.d), user="tester"), limit=10)

    def mode(self, m):
        (self.bin / "mode").write_text(m, encoding="utf-8")

    def seen(self):
        p = self.bin / "seen.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def request(self, question="How is the plan?"):
        return ask.build_request(question, [ask.Passage("report: actions", "ABC-A-001 Send the plan | owner: Sam Lee")])


class Arguments(Fake):
    def test_the_run_is_started_with_the_isolating_flags_and_the_request_on_standard_input(self):
        req = self.request()
        got = self.provider.ask(req)
        self.assertIn("The plan is on track.", got)
        seen = self.seen()
        args = seen["args"]
        for flag in ("--print", "--safe-mode", "--disable-slash-commands", "--strict-mcp-config", "--no-session-persistence"):
            self.assertIn(flag, args)
        self.assertEqual(args[args.index("--tools") + 1], "", "no tool at all")
        self.assertEqual(args[args.index("--output-format") + 1], "text")
        self.assertEqual(args[args.index("--max-budget-usd") + 1], ac.MAX_BUDGET_USD)
        self.assertEqual(args[args.index("--system-prompt") + 1], ask.RULES, "the default prompt is replaced by the fixed rules")
        for flag in ac.NEVER_FLAGS:
            self.assertNotIn(flag, args)
        self.assertEqual(seen["stdin"], req.text, "the request arrives on standard input")
        self.assertFalse(any(req.question in a for a in args), "the question is never in the arguments")
        self.assertFalse(any("Send the plan" in a for a in args), "no passage is in the arguments")

    def test_the_arguments_hold_nothing_but_the_fixed_flags(self):
        self.assertEqual(ac.arguments("/x/claude"), ["/x/claude", "--print", "--safe-mode", "--disable-slash-commands", "--tools", "",
                                                     "--strict-mcp-config", "--no-session-persistence", "--output-format", "text",
                                                     "--max-budget-usd", ac.MAX_BUDGET_USD, "--system-prompt", ask.RULES])

    def test_it_runs_in_an_empty_folder_of_its_own_that_is_removed_afterwards(self):
        self.provider.ask(self.request())
        cwd = self.seen()["cwd"]
        self.assertTrue(Path(cwd).name.startswith("clark-ask-"))
        self.assertNotEqual(Path(cwd).resolve(), Path.cwd().resolve())
        self.assertFalse(Path(cwd).exists(), "the folder is removed after the run")

    def test_its_own_process_group(self):
        self.provider.ask(self.request())
        seen = self.seen()
        self.assertEqual(seen["pid"], seen["pgid"], "started in a new session, so Stop can end the whole group")


class Environment(Fake):
    CANARIES = {"ANTHROPIC_API_KEY": "sk-ant-canary", "ANTHROPIC_BASE_URL": "https://example.test", "ANTHROPIC_AUTH_TOKEN": "c",
                "CLAUDE_CODE_USE_BEDROCK": "1", "CLAUDE_CODE_USE_VERTEX": "1", "CLAUDE_CODE_OAUTH_TOKEN": "c",
                "CLAUDE_CODE_SIMPLE": "1", "CLAUDE_CONFIG_DIR": "/tmp/elsewhere", "AWS_SECRET_ACCESS_KEY": "c", "AWS_PROFILE": "c",
                "GITHUB_TOKEN": "c", "OPENAI_API_KEY": "c", "CLARK_SECRET_CANARY": "c", "PYTHONPATH": "/tmp/evil",
                "DYLD_INSERT_LIBRARIES": "/tmp/evil.dylib", "NODE_OPTIONS": "--require /tmp/evil.js", "HTTPS_PROXY": "http://example.test"}

    def test_the_child_inherits_nothing_but_the_kept_names(self):
        with mock.patch.dict(os.environ, self.CANARIES):
            provider = ac.ClaudeCommand(places=(str(self.cmd),), limit=10)          # the real child_env(), from this process
            provider.ask(self.request())
        env = self.seen()["env"]
        for name in self.CANARIES:
            self.assertNotIn(name, env, name)
        self.assertFalse([k for k in env if k.startswith(("ANTHROPIC", "CLAUDE"))], env.keys())
        allowed = set(ac.KEEP_ENV) | {"PATH", "__CF_USER_TEXT_ENCODING", "PWD", "SHLVL", "_"}      # the last are added by the system or Python
        self.assertLessEqual(set(env), allowed, sorted(set(env) - allowed))
        self.assertEqual(env["PATH"], ac.SAFE_PATH)
        self.assertEqual(env["HOME"], os.path.expanduser("~"), "the command finds its own sign-in")

    def test_child_env_is_built_from_nothing(self):
        with mock.patch.dict(os.environ, self.CANARIES):
            env = ac.child_env(home="/Users/tester", user="tester")
        self.assertEqual(env, {"PATH": ac.SAFE_PATH, "LANG": "en_GB.UTF-8", "HOME": "/Users/tester", "USER": "tester", "LOGNAME": "tester"})
        self.assertNotIn("USER", ac.child_env(home="/h", user="bad user;rm"), "an odd user name is left out")

    def test_the_version_and_help_checks_are_scrubbed_too(self):
        with mock.patch.dict(os.environ, self.CANARIES), mock.patch.object(ac, "run", wraps=ac.run) as run:
            ac.ClaudeCommand(places=(str(self.cmd),), limit=10).status()
        for call in run.call_args_list:
            env = call.args[2]
            self.assertFalse(set(self.CANARIES) & set(env))


class FoundAndChecked(Fake):
    def test_only_the_fixed_places_are_used_never_the_path(self):
        self.assertTrue(all(Path(os.path.expanduser(p)).is_absolute() for p in ac.PLACES))
        with mock.patch.dict(os.environ, {"PATH": str(self.bin)}):
            provider = ac.ClaudeCommand(places=(str(self.d / "nowhere" / "claude"),), limit=10)
            self.assertEqual(provider.status(), {"connected": False, "why": ac.NOT_INSTALLED})
            got = provider.ask(self.request())
        self.assertEqual(got, ask.Failure(ac.NOT_INSTALLED))
        self.assertIsNone(self.seen(), "a command on PATH is never run")

    def test_a_relative_place_is_never_used(self):
        self.assertIsNone(ac.find_command(("claude", "bin/claude")))

    def test_ready_with_a_good_version_and_every_flag(self):
        self.assertEqual(self.provider.status(), {"connected": True, "why": ac.READY})

    def test_a_missing_flag_sends_nothing(self):
        for flag in ac.NEEDED_FLAGS:
            (self.bin / "help").write_text("\n".join(f"  {f}" for f in ac.NEEDED_FLAGS if f != flag), encoding="utf-8")
            provider = ac.ClaudeCommand(places=(str(self.cmd),), env=ac.child_env(home=str(self.d), user="tester"), limit=10)
            self.assertEqual(provider.status(), {"connected": False, "why": ac.CANT_USE}, flag)
            self.assertEqual(provider.ask(self.request()), ask.Failure(ac.CANT_USE), flag)
            self.assertIsNone(self.seen(), f"nothing was sent without {flag}")

    def test_a_flag_named_only_inside_a_longer_one_does_not_count(self):
        (self.bin / "help").write_text(HELP.replace("--safe-mode ", "--safe-modes ").replace("--tools ", "--toolset "), encoding="utf-8")
        self.assertEqual(self.provider.status()["connected"], False)

    def test_an_unreadable_version_sends_nothing(self):
        self.mode("badversion")
        self.assertEqual(self.provider.status(), {"connected": False, "why": ac.CANT_USE})
        self.mode("ok")
        self.assertEqual(self.provider.ask(self.request()), ask.Failure(ac.CANT_USE), "the check is kept for the same file")
        self.assertIsNone(self.seen())

    def test_a_changed_command_is_checked_again(self):
        self.assertTrue(self.provider.status()["connected"])
        (self.bin / "help").write_text("nothing useful", encoding="utf-8")
        self.cmd.write_text(self.cmd.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
        self.assertFalse(self.provider.status()["connected"])


class Limits(Fake):
    def test_too_slow_is_stopped_with_its_whole_group(self):
        self.mode("slow")
        provider = ac.ClaudeCommand(places=(str(self.cmd),), env=ac.child_env(home=str(self.d), user="tester"), limit=1.5)
        began = time.monotonic()
        self.assertEqual(provider.ask(self.request()), ask.Failure(ac.TOO_SLOW))
        self.assertLess(time.monotonic() - began, 10)
        self.assertFalse(alive(self.seen()["pid"]))

    def test_a_helper_in_its_group_is_ended_too(self):
        self.mode("helper")
        provider = ac.ClaudeCommand(places=(str(self.cmd),), env=ac.child_env(home=str(self.d), user="tester"), limit=2)
        self.assertEqual(provider.ask(self.request()), ask.Failure(ac.TOO_SLOW))
        helper = int((self.bin / "helper.pid").read_text(encoding="utf-8"))
        deadline = time.monotonic() + 5
        while alive(helper) and time.monotonic() < deadline:
            time.sleep(0.1)
        self.assertFalse(alive(helper), "the command's helper went with it")

    def test_a_flood_of_output_is_cut_off(self):
        self.mode("flood")
        provider = ac.ClaudeCommand(places=(str(self.cmd),), env=ac.child_env(home=str(self.d), user="tester"), limit=20,
                                    max_out=100000)
        began = time.monotonic()
        self.assertEqual(provider.ask(self.request()), ask.Failure(ac.TOO_LONG_REPLY))
        self.assertLess(time.monotonic() - began, 10)

    def test_a_failing_command_gives_a_fixed_sentence_and_none_of_its_error_text(self):
        self.mode("fail")
        got = self.provider.ask(self.request())
        self.assertEqual(got, ask.Failure(ac.NO_ANSWER))
        self.assertNotIn("secret", got.message)
        self.mode("empty")
        self.assertEqual(self.provider.ask(self.request()), ask.Failure(ac.NO_ANSWER))

    def test_stop_ends_the_answer_and_its_group(self):
        self.mode("slow")
        provider = ac.ClaudeCommand(places=(str(self.cmd),), env=ac.child_env(home=str(self.d), user="tester"), limit=30)
        out = {}
        t = threading.Thread(target=lambda: out.setdefault("got", provider.ask(self.request())))
        t.start()
        deadline = time.monotonic() + 10
        while self.seen() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(provider.stop())
        t.join(10)
        self.assertEqual(out["got"], ask.Failure(ask.STOPPED))
        self.assertFalse(alive(self.seen()["pid"]))
        self.assertFalse(provider.stop(), "nothing left to stop")

    def test_one_question_at_a_time(self):
        self.mode("slow")
        provider = ac.ClaudeCommand(places=(str(self.cmd),), env=ac.child_env(home=str(self.d), user="tester"), limit=30)
        t = threading.Thread(target=lambda: provider.ask(self.request()))
        t.start()
        deadline = time.monotonic() + 10
        while self.seen() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertEqual(provider.ask(self.request()), ask.Failure(ac.BUSY))
        provider.stop()
        t.join(10)


class Source(unittest.TestCase):
    TEXT = (Path(ac.__file__)).read_text(encoding="utf-8")

    def test_never_a_shell_and_never_bare(self):
        self.assertNotIn("shell=True", self.TEXT)
        self.assertNotIn("os.system", self.TEXT)
        self.assertNotIn("\"--bare\"", self.TEXT.split("NEVER_FLAGS")[0])

    def test_the_messages_never_start_with_the_product_name(self):
        for name in ("NOT_INSTALLED", "CANT_USE", "READY", "NO_ANSWER", "TOO_SLOW", "TOO_LONG_REPLY", "BUSY"):
            self.assertFalse(getattr(ac, name).lower().startswith(("clark", "ask clark")), name)


if __name__ == "__main__":
    unittest.main()
