"""#47c slice 3: the smoke-test script for the real Claude command (dev/tools/ask_claude_smoke.py), tested with fake commands.
Run: python3 dev/run_tests.py test_ask_claude_smoke

The script is run for real by hand on a Mac with the real command (the report goes in the PR); these tests show that it can tell the
cases apart: a command that honours the isolating flags passes; one that still runs the hooks, helper, MCP server or CLAUDE.md fails,
naming the canary; one whose sign-in check runs the helper, or still reports it while refusing, fails; one whose sign-in check would
accept the throw-away home fails; and a canary no control armed (or a run that never answered) is INCONCLUSIVE, never a pass, unless
the same canary passed in the other isolated run. The fake is signed in only in a stand-in home folder made for each test. Nothing here
starts the real command or touches the real ~/.claude, except the opt-in class RealCommand at the end.

RealCommand (skipped unless CLARK_SMOKE_REAL_CLAUDE=1, and only on a Mac) runs the whole smoke test against the real `claude` in its
fixed places, with the person's own sign-in: it spends three or four one-word questions of their plan. Run it by hand:
    CLARK_SMOKE_REAL_CLAUDE=1 python3 dev/run_tests.py test_ask_claude_smoke
and paste the printed report into the PR.
"""
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401
from _paths import TOOLS

sys.path.insert(0, str(TOOLS))
import ask_claude_smoke as smoke  # noqa: E402
from clark import ask_claude, platform  # noqa: E402

FAKE = """#!/usr/bin/env python3
import json, os, subprocess, sys
mode = %r
args = sys.argv[1:]
data = sys.stdin.read()
home, cwd = os.environ.get("HOME", ""), os.getcwd()
signed_in = os.path.exists(os.path.join(home, ".fake-signed-in"))
def load(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return {}
def run(cmd):
    if not (mode == "nohelper" and "apiKeyHelper" in cmd):
        subprocess.run([cmd], stdout=subprocess.DEVNULL)
off = "--setting-sources" in args and args[args.index("--setting-sources") + 1] == ""
if args == ["--version"]:
    print("2.1.0 (fake)"); sys.exit(0)
if args == ["--help"]:
    print("\\n".join("  " + f for f in %r)); sys.exit(0)
if args[-2:] == ["auth", "status"]:
    reads = (not off or mode in ("checkfires", "readshelper")) and mode != "authblind"
    cfg = load(os.path.join(home, ".claude", "settings.json")) if reads else {}
    if cfg.get("apiKeyHelper") and mode != "readshelper":
        run(cfg["apiKeyHelper"])
    if mode == "lax":
        print(json.dumps({"loggedIn": True, "authMethod": "claude.ai"})); sys.exit(0)
    if cfg.get("apiKeyHelper"):
        print(json.dumps({"loggedIn": True, "authMethod": "api_key_helper"})); sys.exit(0)
    if signed_in:
        print(json.dumps({"loggedIn": True, "authMethod": "claude.ai"})); sys.exit(0)
    print(json.dumps({"loggedIn": False, "authMethod": "none"})); sys.exit(1)
isolated = "--safe-mode" in args
if isolated and mode == "silent":
    sys.exit(1)
opened = not isolated or mode in ("ignores", "writes")
places = []
if opened and mode != "quiet":
    places.append(("home", os.path.join(home, ".claude", "settings.json"), os.path.join(home, ".claude", "CLAUDE.md"),
                   load(os.path.join(home, ".claude.json")).get("mcpServers", {})))
    if mode != "noproject":
        places.append(("project", os.path.join(cwd, ".claude", "settings.json"), os.path.join(cwd, "CLAUDE.md"),
                       load(os.path.join(cwd, ".mcp.json")).get("mcpServers", {})))
cfgs = [load(p[1]) for p in places]
def hooks(event):
    for cfg in cfgs:
        for g in cfg.get("hooks", {}).get(event, []):
            for h in g["hooks"]:
                run(h["command"])
key = False
for cfg in cfgs:
    if cfg.get("apiKeyHelper") and not key:
        run(cfg["apiKeyHelper"]); key = True
    if cfg.get("env", {}).get("CLAUDE_CODE_TMPDIR"):
        os.makedirs(os.path.join(cfg["env"]["CLAUDE_CODE_TMPDIR"], "claude-501"), exist_ok=True)
for p in places:
    for server in p[3].values():
        if mode != "partial":
            run(server["command"])
hooks("SessionStart"); hooks("UserPromptSubmit")
answers = signed_in and not key
text = "OK"
if answers:
    hooks("PreToolUse"); hooks("Stop")
    if any(os.path.exists(p[2]) for p in places):
        text = "SMOKE-CLAUDE-MD-7F3A OK"
hooks("SessionEnd")
if mode == "writes" and isolated:
    os.makedirs(os.path.join(home, ".claude", "projects", os.path.basename(cwd)), exist_ok=True)
    open(os.path.join(home, ".claude", "projects", os.path.basename(cwd), "s.jsonl"), "w", encoding="utf-8").write("saved")
    open(os.path.join(home, ".claude.json"), "a", encoding="utf-8").write(" ")
if not answers:
    print(json.dumps({"type": "result", "subtype": "success", "is_error": True, "result": "Not logged in, please run /login"}))
    sys.exit(1)
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": text}))
"""


def fake(folder, mode, flags=None):
    path = Path(folder) / f"claude-{mode}"
    path.write_text(FAKE % (mode, list(ask_claude.NEEDED_FLAGS if flags is None else flags)), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


HOOKS_AT_START = ["hook-SessionStart", "hook-UserPromptSubmit", "hook-SessionEnd"]
NEED_SIGN_IN = ["hook-PreToolUse", "hook-Stop", "CLAUDE.md"]
THROW, PROJECT = "isolated, throw-away home", "isolated, project folder"
SIGN_RUN = "sign-in check: the settings file's apiKeyHelper does not run"
SIGN_ANSWER = "sign-in check: the settings file's apiKeyHelper cannot change the answer"
SIGN_REFUSES = "the sign-in check refuses a home with no Claude sign-in"


class Smoke(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.was, smoke.SETTLE = smoke.SETTLE, 0.2                      # the real run waits 2 s for a late helper; a fake needs no wait
        self.addCleanup(setattr, smoke, "SETTLE", self.was)
        self.home = Path(self.tmp.name) / "signed-in-home"              # stands in for the person's home: never the real one
        (self.home / ".claude").mkdir(parents=True)
        (self.home / ".fake-signed-in").write_text("", encoding="utf-8")
        for patch in (mock.patch.object(platform, "system", return_value=platform.MAC),      # the fakes are scripts, and CI is Linux
                      mock.patch.object(ask_claude, "native_problem", return_value=None),
                      mock.patch.object(ask_claude, "hints", return_value=[])):
            patch.start()
            self.addCleanup(patch.stop)

    def states(self, mode, real=True, flags=None):
        report = smoke.smoke(fake(self.tmp.name, mode, flags), real=real, real_home=self.home)
        return {name: state for name, state, _ in report}, report

    def result(self, report):
        return smoke.text_report("fake", report).splitlines()[-1]

    def test_a_command_that_honours_the_flags_passes_every_check(self):
        states, report = self.states("honours")
        self.assertEqual({s for s in states.values()} - {smoke.PASS, smoke.NOTE}, set(), report)
        for name in smoke.CANARIES:
            self.assertEqual(states[f"{PROJECT}: {name} did not run"], smoke.PASS, name)
        for name in HOOKS_AT_START + ["apiKeyHelper", "mcp-server", "settings-env"]:
            self.assertEqual(states[f"{THROW}: {name} did not run"], smoke.PASS, name)
        for name in NEED_SIGN_IN:
            self.assertEqual(states[f"{THROW}: {name} did not run"], smoke.NOTE, "never fires with no sign-in; covered by the project run")
        for line in (SIGN_RUN, SIGN_ANSWER, SIGN_REFUSES, "real: one question with the person's own sign-in",
                     "real: no file for the provider's runs under ~/.claude"):
            self.assertEqual(states[line], smoke.PASS, line)
        self.assertEqual(self.result(report), "RESULT: PASS")

    def test_without_the_signed_in_parts_it_never_passes(self):
        states, report = self.states("honours", real=False)
        for name in NEED_SIGN_IN:
            self.assertEqual(states[f"{THROW}: {name} did not run"], smoke.INCONCLUSIVE, name)
        self.assertNotEqual(self.result(report), "RESULT: PASS")

    def test_a_command_that_still_runs_the_canaries_fails_and_names_each(self):
        states, report = self.states("ignores")
        for name in HOOKS_AT_START + ["apiKeyHelper", "mcp-server", "settings-env"]:
            self.assertEqual(states[f"{THROW}: {name} did not run"], smoke.FAIL, name)
        for name in HOOKS_AT_START + ["apiKeyHelper", "mcp-server", "settings-env"]:
            self.assertEqual(states[f"{PROJECT}: {name} did not run"], smoke.FAIL, name)
        self.assertIn("must not merge", self.result(report))

    def test_a_sign_in_check_that_runs_the_helper_fails(self):
        states, _ = self.states("checkfires")
        self.assertEqual(states[SIGN_RUN], smoke.FAIL)
        self.assertEqual(states["checks: apiKeyHelper did not run"], smoke.FAIL)

    def test_a_check_that_still_sees_the_helper_fails_although_it_refuses(self):
        # refused for the wrong reason: it reports the helper (an API key login), so it refuses, but the setting reached it
        states, report = self.states("readshelper")
        self.assertEqual(states[SIGN_REFUSES], smoke.PASS)
        self.assertEqual(states[SIGN_RUN], smoke.PASS, "its auth status never runs the helper, but a question with settings on does")
        self.assertEqual(states[SIGN_ANSWER], smoke.FAIL)
        self.assertNotEqual(self.result(report), "RESULT: PASS")

    def test_a_refusal_with_no_working_control_is_inconclusive_never_a_pass(self):
        # auth status that never reads a settings file: it refuses only because nobody is signed in, which shows nothing
        states, report = self.states("authblind")
        self.assertEqual(states[SIGN_REFUSES], smoke.PASS)
        self.assertEqual(states[SIGN_ANSWER], smoke.INCONCLUSIVE)
        self.assertNotEqual(self.result(report), "RESULT: PASS")

    def test_a_helper_no_run_ever_starts_leaves_the_sign_in_check_inconclusive(self):
        states, report = self.states("nohelper")
        self.assertEqual(states[SIGN_RUN], smoke.INCONCLUSIVE)
        self.assertEqual(states[SIGN_ANSWER], smoke.PASS, "it still reports the helper with settings on, and not with them off")
        self.assertNotEqual(self.result(report), "RESULT: PASS")

    def test_a_sign_in_check_that_would_accept_the_throw_away_home_fails(self):
        states, _ = self.states("lax")
        self.assertEqual(states[SIGN_REFUSES], smoke.FAIL)

    def test_a_command_that_writes_under_the_home_fails(self):
        states, _ = self.states("writes")
        self.assertEqual(states[f"{THROW}: no new file under its ~/.claude"], smoke.FAIL)
        self.assertEqual(states[f"{THROW}: its ~/.claude.json is byte for byte as it was"], smoke.FAIL)
        self.assertEqual(states["real: no file for the provider's runs under ~/.claude"], smoke.FAIL)
        self.assertEqual(states["real: ~/.claude.json changed size or time during the provider's runs"], smoke.NOTE)

    def test_canaries_that_were_never_armed_are_inconclusive_never_a_pass(self):
        states, report = self.states("quiet")
        for name, state in states.items():
            if name.startswith((THROW + ": hook-", PROJECT + ": hook-", "checks: hook-")) or name.endswith(("apiKeyHelper did not run", "mcp-server did not run")):
                self.assertEqual(state, smoke.INCONCLUSIVE, name)
        self.assertEqual(states[f"{PROJECT}: settings-env did not run"], smoke.NOTE, "an unarmed optional canary is a note")
        self.assertNotEqual(self.result(report), "RESULT: PASS")

    def test_a_canary_is_covered_only_by_a_pass_in_the_other_run(self):
        # project settings never read: the start-time hooks are covered by the throw-away run, the stop hook nowhere
        states, report = self.states("noproject")
        for name in HOOKS_AT_START + ["mcp-server"]:
            self.assertEqual(states[f"{PROJECT}: {name} did not run"], smoke.NOTE, name)
        for name in NEED_SIGN_IN:
            self.assertEqual(states[f"{PROJECT}: {name} did not run"], smoke.INCONCLUSIVE, name)
            self.assertEqual(states[f"{THROW}: {name} did not run"], smoke.INCONCLUSIVE, name)
        self.assertNotEqual(self.result(report), "RESULT: PASS")

    def test_an_isolated_run_with_no_answer_never_passes_a_canary_check(self):
        states, report = self.states("silent")
        self.assertEqual(states["checks: apiKeyHelper did not run"], smoke.PASS, "the checks ran through, so they are judged")
        for name in smoke.CANARIES:
            self.assertEqual(states[f"{THROW}: {name} did not run"], smoke.INCONCLUSIVE, name)
            self.assertEqual(states[f"{PROJECT}: {name} did not run"], smoke.INCONCLUSIVE, name)
        self.assertEqual(states[f"{THROW}: no new file under its ~/.claude"], smoke.PASS, "the run started and ended")
        self.assertNotEqual(self.result(report), "RESULT: PASS")

    def test_each_canary_is_judged_against_its_own_arming(self):
        states, report = self.states("partial")                  # no MCP server ever starts, the rest do
        for label in (THROW, PROJECT, "checks"):
            self.assertEqual(states[f"{label}: mcp-server did not run"], smoke.INCONCLUSIVE, label)
        self.assertEqual(states[f"{PROJECT}: apiKeyHelper did not run"], smoke.PASS)
        self.assertNotEqual(self.result(report), "RESULT: PASS")

    def test_a_command_the_check_refuses_fails_the_check(self):
        path = Path(self.tmp.name) / "claude-old"
        path.write_text("#!/bin/sh\necho 1.0.0\n", encoding="utf-8")        # a version, but --help lists none of the flags
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        states = {n: s for n, s, _ in smoke.smoke(path, real=True, real_home=self.home)}
        self.assertEqual(states["the native-program, version and flag checks accept this command"], smoke.FAIL)
        self.assertEqual(states["real: one question with the person's own sign-in"], smoke.FAIL)

    def test_a_refused_command_never_passes_an_isolated_check(self):
        for flag in ("--setting-sources", ask_claude.NEEDED_FLAGS[-1]):      # each missing flag is pinned in test_ask_claude
            states, report = self.states("honours", flags=[f for f in ask_claude.NEEDED_FLAGS if f != flag])
            self.assertEqual(states["the native-program, version and flag checks accept this command"], smoke.FAIL, flag)
            for name in smoke.CANARIES:
                self.assertEqual(states[f"{THROW}: {name} did not run"], smoke.INCONCLUSIVE, (flag, name))
                self.assertEqual(states[f"{PROJECT}: {name} did not run"], smoke.INCONCLUSIVE, (flag, name))
            self.assertNotEqual(self.result(report), "RESULT: PASS", flag)

    def test_the_canaries_are_planted_in_a_throw_away_home_and_markers_start_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, markers = Path(tmp) / "h", Path(tmp) / "m"
            home.mkdir()
            marks = smoke.plant(home, markers)
            self.assertEqual(sorted(marks), sorted(smoke.CANARIES))
            self.assertFalse(any(p.exists() for p in marks.values()))
            cfg = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
            self.assertEqual(sorted(cfg["hooks"]), sorted(smoke.HOOK_EVENTS))
            self.assertEqual(cfg["env"]["CLAUDE_CODE_TMPDIR"], str(marks["settings-env"]))
            self.assertIn(smoke.CANARY_WORD, (home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8"))
            self.assertNotEqual(str(home), os.path.expanduser("~"))
            bare = Path(tmp) / "b"
            bare.mkdir()
            self.assertNotIn("apiKeyHelper", smoke.plant(bare, Path(tmp) / "mb", helper=False))
            self.assertNotIn("apiKeyHelper", json.loads((bare / ".claude" / "settings.json").read_text(encoding="utf-8")))

    def test_project_canaries_go_only_into_the_run_folder_and_the_patch_is_undone(self):
        was = platform.tempfile.mkdtemp
        with tempfile.TemporaryDirectory() as tmp:
            with smoke.Planted(smoke.RUN_FOLDER, Path(tmp) / "m") as plan:
                other = tempfile.mkdtemp(prefix="something-else-", dir=tmp)
                mine = tempfile.mkdtemp(prefix=smoke.RUN_FOLDER, dir=tmp)
            self.assertIs(platform.tempfile.mkdtemp, was)
            self.assertEqual(os.listdir(other), [])
            self.assertEqual(sorted(os.listdir(mine)), [".claude", ".mcp.json", "CLAUDE.md", "canary.txt"])
            cfg = json.loads((Path(mine) / ".claude" / "settings.json").read_text(encoding="utf-8"))
            self.assertEqual(sorted(cfg["hooks"]), sorted(smoke.HOOK_EVENTS))
            self.assertIn("apiKeyHelper", cfg)
            self.assertEqual(sorted(plan.marks), sorted(smoke.CANARIES))
            self.assertTrue(all(Path(tmp) in p.parents for p in plan.marks.values()))

    def test_error_words_never_carry_the_home_folder_or_an_address(self):
        self.assertEqual(smoke.plain("x /Users/someone/a b@c.example y", "/Users/someone"), "x ~/a [address] y")

    def test_the_script_never_writes_under_the_real_claude_folder(self):
        text = (TOOLS / "ask_claude_smoke.py").read_text(encoding="utf-8")
        self.assertNotIn('expanduser("~/.claude")', text)
        self.assertNotIn("Path.home()", text)
        real_part = text.split("# ----- B:")[1].split("def text_report")[0]
        for writer in ("write_text", "write_bytes", "open(", "unlink", "rmtree", "mkdir"):
            self.assertNotIn(writer, real_part, "the real home's folder is only listed, by file name")


@unittest.skipUnless(os.environ.get("CLARK_SMOKE_REAL_CLAUDE") == "1" and sys.platform == "darwin",
                     "the real-command smoke test runs only by hand on a Mac: CLARK_SMOKE_REAL_CLAUDE=1")
class RealCommand(unittest.TestCase):
    """The merge blocker: the whole smoke test against the real command, with its report printed for the PR."""

    def test_the_real_command_passes_every_check(self):
        command, why = ask_claude.find_command()
        self.assertIsNotNone(command, why)
        report = smoke.smoke(command, real=True)
        text = smoke.text_report(command, report)
        print("\n" + text)
        self.assertEqual(text.splitlines()[-1], "RESULT: PASS", text)


if __name__ == "__main__":
    unittest.main()
