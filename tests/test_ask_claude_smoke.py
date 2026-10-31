"""#47c slice 3: the smoke-test script for the real Claude command (dev/tools/ask_claude_smoke.py), tested with fake commands.
Run: python3 dev/run_tests.py test_ask_claude_smoke

The script is run for real by hand once on a Mac with the real command (the report goes in the PR); these tests show that it can tell the
three cases apart: a command that honours the isolating flags passes; one that still runs the person's hooks, helper, MCP server or
CLAUDE.md fails, naming the canary; and one whose canaries were never armed (it ran none even without the flags) is INCONCLUSIVE, never a
pass. Nothing here starts the real command or touches the real ~/.claude.
"""
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
from _paths import TOOLS

sys.path.insert(0, str(TOOLS))
import ask_claude_smoke as smoke  # noqa: E402
from clark import ask_claude  # noqa: E402

FAKE = '''#!/usr/bin/env python3
import json, os, subprocess, sys
mode = %r
args = sys.argv[1:]
if args == ["--version"]:
    print("2.1.0 (fake)"); sys.exit(0)
if args == ["--help"]:
    print("\\n".join("  " + f for f in %r)); sys.exit(0)
sys.stdin.read()
home = os.environ.get("HOME", "")
isolated = "--safe-mode" in args
armed = mode in ("honours", "ignores", "writes") and (not isolated or mode in ("ignores", "writes"))
text = "OK"
if armed:
    cfg = json.load(open(os.path.join(home, ".claude", "settings.json")))
    for event, groups in cfg.get("hooks", {}).items():
        for g in groups:
            for h in g["hooks"]:
                subprocess.run([h["command"]])
    subprocess.run([cfg["apiKeyHelper"]])
    mcp = json.load(open(os.path.join(home, ".claude.json")))["mcpServers"]["canary"]["command"]
    subprocess.run([mcp])
    text = open(os.path.join(home, ".claude", "CLAUDE.md")).read().split()[-1].rstrip(".") + " OK"
if mode == "writes" and isolated:
    open(os.path.join(home, ".claude", "session.jsonl"), "w").write("saved")
    open(os.path.join(home, ".claude.json"), "a").write(" ")
print(text)
'''


def fake(folder, mode):
    path = Path(folder) / f"claude-{mode}"
    path.write_text(FAKE % (mode, list(ask_claude.NEEDED_FLAGS)), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


class Smoke(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.was, smoke.SETTLE = smoke.SETTLE, 0.3                      # the real run waits 2 s for a late helper; a fake needs no wait
        self.addCleanup(setattr, smoke, "SETTLE", self.was)

    def states(self, mode):
        report = smoke.smoke(fake(self.tmp.name, mode), real=False)
        return {name: state for name, state, _ in report}, report

    def test_a_command_that_honours_the_flags_passes_every_check(self):
        states, report = self.states("honours")
        self.assertEqual({s for s in states.values()} - {smoke.PASS, smoke.NOTE}, set(), report)
        self.assertEqual(states["control: the canaries run when nothing isolates the command"], smoke.PASS)
        self.assertIn("isolated: the answer is not shaped by the CLAUDE.md canary", states)
        self.assertEqual(sorted(n for n in states if n.startswith("isolated: hook-")), [f"isolated: hook-{e} did not run" for e in sorted(smoke.HOOK_EVENTS)])
        self.assertEqual(smoke.text_report("fake", report).splitlines()[-1], "RESULT: PASS")

    def test_a_command_that_still_runs_the_canaries_fails_and_names_each(self):
        states, report = self.states("ignores")
        for name in [f"isolated: hook-{e} did not run" for e in smoke.HOOK_EVENTS] + ["isolated: apiKeyHelper did not run", "isolated: mcp-server did not run"]:
            self.assertEqual(states[name], smoke.FAIL, name)
        self.assertEqual(states["isolated: the answer is not shaped by the CLAUDE.md canary"], smoke.FAIL)
        self.assertIn("must not merge", smoke.text_report("fake", report))

    def test_a_command_that_writes_under_the_home_fails(self):
        states, _ = self.states("writes")
        self.assertEqual(states["isolated: no new file under the throw-away ~/.claude"], smoke.FAIL)
        self.assertEqual(states["isolated: ~/.claude.json is byte for byte as it was"], smoke.FAIL)

    def test_canaries_that_were_never_armed_are_inconclusive_never_a_pass(self):
        states, report = self.states("quiet")
        self.assertEqual(states["control: the canaries run when nothing isolates the command"], smoke.INCONCLUSIVE)
        for name, state in states.items():
            if name.startswith("isolated: hook-") or name in ("isolated: apiKeyHelper did not run", "isolated: mcp-server did not run"):
                self.assertEqual(state, smoke.INCONCLUSIVE, name)
        self.assertNotEqual(smoke.text_report("fake", report).splitlines()[-1], "RESULT: PASS")

    def test_no_answer_under_the_throw_away_home_is_a_note_when_the_canaries_were_armed_and_inconclusive_when_not(self):
        path = Path(self.tmp.name) / "claude-silent"
        path.write_text(FAKE.replace("print(text)", "sys.exit(1)") % ("honours", list(ask_claude.NEEDED_FLAGS)), encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        states = {n: s for n, s, _ in smoke.smoke(path, real=False)}
        self.assertEqual(states["isolated: the CLAUDE.md canary could not be tested"], smoke.NOTE)
        self.assertEqual(smoke.text_report("fake", smoke.smoke(path, real=False)).splitlines()[-1], "RESULT: PASS")
        mute = Path(self.tmp.name) / "claude-mute"
        mute.write_text(FAKE.replace("print(text)", "sys.exit(1)") % ("quiet", list(ask_claude.NEEDED_FLAGS)), encoding="utf-8")
        mute.chmod(mute.stat().st_mode | stat.S_IXUSR)
        quiet = {n: s for n, s, _ in smoke.smoke(mute, real=False)}
        self.assertEqual(quiet["isolated: the CLAUDE.md canary could not be tested"], smoke.INCONCLUSIVE)

    def test_a_command_the_check_refuses_fails_the_check(self):
        path = Path(self.tmp.name) / "claude-old"
        path.write_text("#!/bin/sh\necho 1.0.0\n", encoding="utf-8")        # a version, but --help lists none of the flags
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        states = {n: s for n, s, _ in smoke.smoke(path, real=False)}
        self.assertEqual(states["the version and flag check accepts this command"], smoke.FAIL)

    def test_the_canaries_are_planted_in_a_throw_away_home_and_markers_start_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, markers = Path(tmp) / "h", Path(tmp) / "m"
            home.mkdir()
            marks = smoke.plant(home, markers)
            self.assertEqual(len(marks), len(smoke.HOOK_EVENTS) + 2)
            self.assertFalse(any(p.exists() for p in marks.values()))
            cfg = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
            self.assertEqual(sorted(cfg["hooks"]), sorted(smoke.HOOK_EVENTS))
            self.assertIn(smoke.CANARY_WORD, (home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8"))
            self.assertNotEqual(str(home), os.path.expanduser("~"))

    def test_the_script_never_touches_the_real_claude_folder(self):
        text = (TOOLS / "ask_claude_smoke.py").read_text(encoding="utf-8")
        self.assertNotIn('expanduser("~/.claude")', text)
        self.assertNotIn("Path.home()", text)


if __name__ == "__main__":
    unittest.main()
