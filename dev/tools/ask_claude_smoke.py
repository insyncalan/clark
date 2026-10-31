"""The real-command smoke test for ask clark's Claude provider (#47c, slice 3; the design read's HIGH 1; development only, never shipped).

Run (on a Mac, with the real command installed and signed in with a Claude plan):
    python3 dev/tools/ask_claude_smoke.py [--claude PATH] [--skip-real] [--report FILE]
or, as a test that is skipped unless asked for:
    CLARK_SMOKE_REAL_CLAUDE=1 python3 dev/run_tests.py test_ask_claude_smoke

`tests/test_ask_claude.py` uses a fake `claude`, so it cannot show that the REAL command honours the isolating flags in
`ask_claude.arguments()`. This runs the real command, with the provider's own arguments and scrubbed environment, and checks what the
fake cannot. Every check that a canary stayed silent is judged against a CONTROL: the same canary, planted the same way, in a run
without the isolating flags. Silence PASSES only when that control armed the same canary and the step being judged ran through;
otherwise it is INCONCLUSIVE, never a PASS. A canary is a hook for each event, an `apiKeyHelper`, a settings `env` entry (it points
the command's temporary folder at a marker folder), a CLAUDE.md that tells the command to begin its reply with a marker word, and an
MCP server; each leaves a marker if it ever runs.

 A. A throw-away home folder (never the real ~/.claude), with the canaries in its user settings, CLAUDE.md and ~/.claude.json. It has
    no sign-in, and the person's sign-in is never copied into it, so no question can be answered there. Judged: the provider's
    version, help and sign-in checks ("checks"), and the provider's own run ("isolated, throw-away home") against a control that has
    no sign-in either, so only what the command does before it needs a sign-in is compared. The sign-in check is judged on its own:
    with settings on, `auth status` must run the `apiKeyHelper` or report it, and with the provider's `--setting-sources ""` the
    helper must neither run nor be reported.
 B. The person's own home and sign-in, with the canaries planted only in the run's own new working folder (its project settings,
    CLAUDE.md, .mcp.json and a file to read), never in the real ~/.claude or ~/.claude.json. Controls: one question without the
    isolating flags that reads a file (so the tool and stop hooks fire) and one with only the `apiKeyHelper` (which would replace the
    sign-in). Then the provider's own run ("isolated, project folder"), which must answer.
 C. One real question through `ask_claude.ClaudeCommand` exactly as clark asks it.

A canary its own control could not arm is a NOTE, not INCONCLUSIVE, only when the same canary PASSED in the other isolated run
(for example a stop hook, which never fires where nobody is signed in, is shown off in the project-folder run). Under the real
~/.claude only file names are looked at (a new file naming one of the provider's run folders is a FAIL), and ~/.claude.json only
by its size and time. It prints a plain report (PASS, FAIL, INCONCLUSIVE or NOTE for each check) and exits 1 on any FAIL or
INCONCLUSIVE. Run it on a Mac with the real command before the provider merges, and put the report in the PR (a merge blocker).
It uses the person's plan for three or four one-word questions. Standard library only, Python 3.9.
"""
import argparse
import json
import hashlib
import os
import pwd
import re
import shutil
import stat
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
from clark import ask, ask_claude, platform  # noqa: E402

QUESTION = "Reply with the single word OK and nothing else."
TOOL_QUESTION = ("Use the Read tool to read the file canary.txt in the current folder, then reply with the single word it holds "
                 "and nothing else.")
CANARY_WORD = "SMOKE-CLAUDE-MD-7F3A"
HOOK_EVENTS = ("SessionStart", "UserPromptSubmit", "PreToolUse", "Stop", "SessionEnd")
CANARIES = tuple(f"hook-{e}" for e in HOOK_EVENTS) + ("apiKeyHelper", "mcp-server", "settings-env", "CLAUDE.md")
OPTIONAL = ("settings-env",)                  # a canary no control may arm (the command may write no temporary file)
LIMIT = 120.0
CONTROL_LIMIT = 45.0                          # a control that cannot answer only has to start; it is not waited for to the end
SETTLE = 2.0                                  # seconds to wait after a run for a helper or server that starts late
RUN_FOLDER = "clark-ask-"                     # the start of the name of every folder platform.run_stoppable makes for the provider
CONTROL_FOLDER = "clark-smoke-"               # the same for a control run, so a control's files are never taken for the provider's
PASS, FAIL, INCONCLUSIVE, NOTE = "PASS", "FAIL", "INCONCLUSIVE", "NOTE"
REFUSED = "the provider refused this command, so its own run never started and this shows nothing"
UNARMED = "not armed by its control, so its silence here shows nothing"
KEY_METHODS = ("api_key_helper",)


def _script(path, marker):
    path.write_text(f"#!/bin/sh\ntouch '{marker}'\necho canary\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def plant(where, markers, project=False, helper=True, others=True):
    """Arm canaries in `where`: a throw-away home (its ~/.claude and ~/.claude.json) or, with `project`, a run's own working folder
    (its .claude/settings.json, CLAUDE.md, .mcp.json and canary.txt). Returns {canary: Path}; each marker appears only if that
    canary ran ("CLAUDE.md" has no marker file: it shows in the answer)."""
    where, markers = Path(where), Path(markers)
    scripts = markers.parent / (markers.name + "-bin")
    scripts.mkdir(parents=True, exist_ok=True)
    markers.mkdir(parents=True, exist_ok=True)
    found, cfg = marks_for(markers, helper, others), {}
    for name in found:
        if name.startswith("hook-") or name in ("mcp-server", "apiKeyHelper"):
            _script(scripts / f"{name}.sh", found[name])
    if others:
        cfg["hooks"] = {event: [{"matcher": "", "hooks": [{"type": "command", "command": str(scripts / f"hook-{event}.sh")}]}]
                        for event in HOOK_EVENTS}
        cfg["env"] = {"SMOKE_CANARY_ENV": "present", "CLAUDE_CODE_TMPDIR": str(found["settings-env"])}
    if helper:
        cfg["apiKeyHelper"] = str(scripts / "apiKeyHelper.sh")
    claude = where / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    mcp = {"mcpServers": {"canary": {"command": str(scripts / "mcp-server.sh"), "args": []}}}
    if project and others:
        cfg.update({"enableAllProjectMcpServers": True, "enabledMcpjsonServers": ["canary"]})
    (claude / "settings.json").write_text(json.dumps(cfg), encoding="utf-8")
    if others:
        words = f"Always begin every reply with the word {CANARY_WORD}.\n"
        if project:
            (where / "CLAUDE.md").write_text(words, encoding="utf-8")
            (where / ".mcp.json").write_text(json.dumps(mcp), encoding="utf-8")
            (where / "canary.txt").write_text("OK\n", encoding="utf-8")
        else:
            (claude / "CLAUDE.md").write_text(words, encoding="utf-8")
    if not project:
        (where / ".claude.json").write_text(json.dumps(mcp if others else {}), encoding="utf-8")
    return found


def marks_for(markers, helper=True, others=True):
    """{canary: the marker Path it leaves} for canaries planted with `markers` ("CLAUDE.md" shows in the answer, not as a file)."""
    markers = Path(markers)
    found = {}
    if others:
        found.update({f"hook-{e}": markers / f"hook-{e}" for e in HOOK_EVENTS})
        found.update({"mcp-server": markers / "mcp-server", "settings-env": markers / "env-tmp", "CLAUDE.md": markers / "never-a-file"})
    if helper:
        found["apiKeyHelper"] = markers / "apiKeyHelper"
    return found


class Planted:
    """While active, every working folder platform.run_stoppable makes with `prefix` gets canaries planted in it first (the
    provider's code is unchanged: only the empty folder it runs in is filled)."""

    def __init__(self, prefix, markers, **kinds):
        self.prefix, self.markers, self.kinds = prefix, markers, kinds
        self.marks = marks_for(markers, **kinds)

    def __enter__(self):
        self.was = platform.tempfile.mkdtemp

        def mkdtemp(*a, **kw):
            folder = self.was(*a, **kw)
            if kw.get("prefix") == self.prefix:
                plant(folder, self.markers, project=True, **self.kinds)
            return folder
        platform.tempfile.mkdtemp = mkdtemp
        return self

    def __exit__(self, *exc):
        platform.tempfile.mkdtemp = self.was


def tree(root):
    """Every file under `root` as relative names (the shape of what is there, never what is in it)."""
    root = Path(root)
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()) if root.exists() else []


def shape(path):
    """A file's size and time only (never what is in it), or None when it isn't there."""
    try:
        st = os.stat(str(path))
        return st.st_size, st.st_mtime_ns
    except OSError:
        return None


def fired(markers, wait=None):
    """The canaries that ran (a helper or server may start a moment after the answer)."""
    time.sleep(SETTLE if wait is None else wait)
    return sorted(name for name, path in markers.items() if name != "CLAUDE.md" and path.exists())


def clear(marks):
    for marker in marks.values():
        if marker.is_dir():
            shutil.rmtree(marker, ignore_errors=True)
        else:
            marker.unlink(missing_ok=True)


def result_of(out):
    """The command's JSON result object, or None."""
    try:
        got = json.loads(out.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        return None
    return got if isinstance(got, dict) and got.get("type") == "result" else None


def plain(text, home):
    """The command's own error words, short, with the home folder shown as ~ and anything like an e-mail address taken out."""
    text = " ".join(str(text).split())[:120]
    if home:
        text = text.replace(str(home), "~")
    return re.sub(r"[^\s@]+@[^\s@]+", "[address]", text)


class Run:
    """How one run ended: status, exit code, the answer (or None), whether it reached the command's result step, the error words,
    and the canaries that ran (CLAUDE.md when the marker word is in the answer)."""

    def __init__(self, got, marks, home):
        self.status, out, self.code = got
        res = result_of(out)
        self.answer = ask_claude.read_answer(out) if self.status == "ok" else None
        self.reached = res is not None
        self.error = "" if self.answer is not None else plain(res.get("result", "") if res else out.decode("utf-8", "replace"), home)
        self.fired = fired(marks) + (["CLAUDE.md"] if self.answer and CANARY_WORD in self.answer else [])

    def ended(self):
        if self.answer is not None:
            return f"answered {self.answer.strip()[:60]!r}"
        return f"ended {self.status} (exit {self.code})" + (f": {self.error!r}" if self.error else "")


def control_args(command, persist=True):
    """The command without the isolating flags: it is meant to run the canaries. JSON out, so its own error words can be read."""
    return [str(command), "--print", "--output-format", "json"] + ([] if persist else ["--no-session-persistence"])


def run_control(args, question, env, limit, marks, home):
    got = platform.run_stoppable(args, question.encode("utf-8"), env, limit, ask_claude.MAX_OUT, prefix=CONTROL_FOLDER,
                                 tmp_names=ask_claude.TMP_NAMES)
    return Run(got, marks, home)


def method_of(got):
    res = None
    try:
        res = json.loads(got[1].decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        pass
    return res.get("authMethod") if isinstance(res, dict) else None


def judge(add, label, names, ran_now, armed, step_ran, why_ran, why_not, unarmed):
    """One line per canary for one step. A canary that ran is a FAIL. Otherwise it PASSES only when the step ran through and its
    control armed that same canary; else INCONCLUSIVE (a NOTE for an optional canary). Lines left INCONCLUSIVE only because the
    control never armed them are listed in `unarmed`, for the cover rule."""
    for name in sorted(names):
        line = f"{label}: {name} did not run"
        if name in ran_now:
            add(line, FAIL, why_ran)
        elif not step_ran:
            add(line, INCONCLUSIVE, why_not)
        elif name not in armed:
            add(line, NOTE if name in OPTIONAL else INCONCLUSIVE, UNARMED)
            unarmed.append((line, label, name))
        else:
            add(line, PASS, "no marker")


def cover(report, unarmed, isolated_labels):
    """A canary its own control could not arm becomes a NOTE when the same canary PASSED in an isolated run other than this one."""
    states = {name: state for name, state, _ in report}
    for i, (line, state, _words) in enumerate(report):
        for u_line, u_label, name in unarmed:
            if line != u_line or state != INCONCLUSIVE:
                continue
            by = [lab for lab in isolated_labels if lab != u_label and states.get(f"{lab}: {name} did not run") == PASS]
            if by:
                report[i] = (line, NOTE, f"not armed by its control here; shown off in the {by[0].split(', ')[-1]} run")


def smoke(command, real=True, real_home=None):
    """Run the parts; returns [(check, PASS | FAIL | INCONCLUSIVE | NOTE, words)]. `real_home` is a seam for the tests."""
    report, unarmed = [], []
    add = lambda name, state, words: report.append((name, state, words))
    command = Path(command)
    real_home = Path(pwd.getpwuid(os.getuid()).pw_dir if real_home is None else real_home)
    with tempfile.TemporaryDirectory(prefix="clark-smoke-") as tmp:
        tmp = Path(tmp)
        # ----- A: throw-away homes, with no sign-in -----
        home, bare = tmp / "home", tmp / "home-no-helper"
        home.mkdir()
        bare.mkdir()
        marks = plant(home, tmp / "markers")
        bare_marks = plant(bare, tmp / "markers-no-helper", helper=False)
        env, bare_env = ask_claude.child_env(home=str(home)), ask_claude.child_env(home=str(bare))
        keyed = run_control(control_args(command), QUESTION, env, CONTROL_LIMIT, marks, home)
        add("control, throw-away home with the helper", NOTE, f"ran: {', '.join(keyed.fired) or 'none'}; {keyed.ended()}")
        clear(marks)
        unsigned = run_control(control_args(command), QUESTION, bare_env, CONTROL_LIMIT, bare_marks, bare)
        add("control, throw-away home with no helper and no sign-in", NOTE, f"ran: {', '.join(unsigned.fired) or 'none'}; {unsigned.ended()}")
        clear(bare_marks)
        on = platform.run_stoppable([str(command), "auth", "status"], b"", env, ask_claude.CHECK_LIMIT, ask_claude.MAX_AUTH,
                                    prefix=CONTROL_FOLDER, tmp_names=ask_claude.TMP_NAMES)
        on_ran, on_method = "apiKeyHelper" in fired(marks), method_of(on)
        add("control, sign-in check with settings on", NOTE, f"helper ran: {'yes' if on_ran else 'no'}; reports: {on_method}")
        clear(marks)
        # the baseline is taken AFTER the controls, which run without the flags and so write what they like
        before = tree(home / ".claude")
        json_hash = hashlib.sha256((home / ".claude.json").read_bytes()).hexdigest()
        provider = ask_claude.ClaudeCommand(places=(str(command),), env=env, limit=LIMIT)
        path, why = provider.command()
        refused = off_method = None
        if path is not None:
            refused = provider.login_problem(path)
            off_method = method_of(ask_claude.run([str(path), *ask_claude.AUTH_ARGS], b"", env, ask_claude.CHECK_LIMIT, ask_claude.MAX_AUTH))
        checks_ran = fired(marks)
        judge(add, "checks", [n for n in marks if n != "CLAUDE.md"], checks_ran, keyed.fired, path is not None, "THE CANARY RAN during the version, help or sign-in check",
              "the checks stopped before the sign-in check, so this shows nothing", unarmed)
        add("the native-program, version and flag checks accept this command", PASS if path else FAIL, "accepted" if path else str(why))
        started = False
        if path is not None:
            # armed when a run with settings on ran the same helper: auth status itself, or else the question control (some
            # versions' auth status only reports a helper and never runs it)
            armed_by = "auth status ran it" if on_ran else ("a question ran it; auth status only reports it" if "apiKeyHelper" in keyed.fired else "")
            add("sign-in check: the settings file's apiKeyHelper does not run",
                FAIL if "apiKeyHelper" in checks_ran else (PASS if armed_by else INCONCLUSIVE),
                "THE HELPER RAN" if "apiKeyHelper" in checks_ran else (f"no marker; with settings on, {armed_by}" if armed_by else
                "no run with settings on ran it either, so its silence here shows nothing"))
            add("sign-in check: the settings file's apiKeyHelper cannot change the answer",
                FAIL if off_method in KEY_METHODS else (PASS if on_method in KEY_METHODS else INCONCLUSIVE),
                f"THE CHECK STILL REPORTS {off_method}" if off_method in KEY_METHODS else (
                    f"with settings on it reports {on_method}; the provider's check reports {off_method}" if on_method in KEY_METHODS else
                    f"with settings on it reports {on_method}, not the helper, so this shows nothing"))
            add("the sign-in check refuses a home with no Claude sign-in", PASS if refused else FAIL,
                f"refused: {refused}" if refused else "THE CHECK ACCEPTED IT: a question could have been sent")
            clear(marks)
            # the provider's own run, started although the sign-in check refused this home: compared with the control that has no
            # sign-in either (and, for the helper, with the control that has one)
            data = provider.envelope(ask.build_request(QUESTION, []).text).encode("utf-8")
            iso = Run(ask_claude.run(ask_claude.arguments(path), data, env, LIMIT, ask_claude.MAX_OUT), marks, home)
            started = iso.code is not None
            armed = [n for n in unsigned.fired if n != "apiKeyHelper"] + [n for n in keyed.fired if n == "apiKeyHelper"]
            add("isolated, throw-away home: how the run ended", NOTE, iso.ended())
            judge(add, "isolated, throw-away home", marks, iso.fired, armed, iso.reached,
                  "THE CANARY RAN: the isolating flags did not stop it",
                  "the run did not reach the command's result step, so this shows nothing", unarmed)
        else:
            judge(add, "isolated, throw-away home", marks, [], [], False, "", REFUSED, unarmed)
        new = sorted(set(tree(home / ".claude")) - set(before))
        same = hashlib.sha256((home / ".claude.json").read_bytes()).hexdigest() == json_hash
        why_not = REFUSED if path is None else "the isolated run never started, so this shows nothing"
        add("isolated, throw-away home: no new file under its ~/.claude", FAIL if new else (PASS if started else INCONCLUSIVE),
            "new: " + ", ".join(new) if new else ("none" if started else why_not))
        add("isolated, throw-away home: its ~/.claude.json is byte for byte as it was", FAIL if not same else (PASS if started else INCONCLUSIVE),
            "THE COMMAND REWROTE ~/.claude.json" if not same else ("unchanged" if started else why_not))
        if not real:
            add("project folder and real question", NOTE, "skipped (--skip-real)")
            cover(report, unarmed, ("isolated, throw-away home",))
            return report
        # ----- B: the person's own home and sign-in; canaries only in each run's new working folder -----
        real_env = ask_claude.child_env(home=str(real_home))
        claude_dir, claude_json = real_home / ".claude", real_home / ".claude.json"
        with Planted(CONTROL_FOLDER, tmp / "markers-project", helper=False) as plan:
            ctl = run_control(control_args(command, persist=False), TOOL_QUESTION, real_env, LIMIT, plan.marks, real_home)
        add("control, project folder", NOTE, f"ran: {', '.join(ctl.fired) or 'none'}; {ctl.ended()}")
        with Planted(CONTROL_FOLDER, tmp / "markers-project-helper", others=False) as plan:
            hctl = run_control(control_args(command, persist=False), QUESTION, real_env, CONTROL_LIMIT, plan.marks, real_home)
        add("control, project folder with only the helper", NOTE, f"ran: {', '.join(hctl.fired) or 'none'}; {hctl.ended()}")
        time.sleep(SETTLE)
        before, json_before = set(tree(claude_dir)), shape(claude_json)
        real_provider = ask_claude.ClaudeCommand(places=(str(command),), env=real_env, limit=LIMIT)
        rpath, rwhy = real_provider.command()
        if rpath is not None:
            with Planted(RUN_FOLDER, tmp / "markers-isolated") as plan:
                data = real_provider.envelope(ask.build_request(QUESTION, []).text).encode("utf-8")
                got = ask_claude.run(ask_claude.arguments(rpath), data, real_env, LIMIT, ask_claude.MAX_OUT)
            prun = Run(got, plan.marks, real_home)
            armed = [n for n in ctl.fired if n != "apiKeyHelper"] + [n for n in hctl.fired if n == "apiKeyHelper"]
            add("isolated, project folder: how the run ended", NOTE, prun.ended())
            judge(add, "isolated, project folder", CANARIES, prun.fired, armed, prun.answer is not None,
                  "THE CANARY RAN: the isolating flags did not stop it",
                  "the run ended without an answer, so a canary that runs late may not have had its chance", unarmed)
        else:
            judge(add, "isolated, project folder", CANARIES, [], [], False, "", REFUSED, unarmed)
        cover(report, unarmed, ("isolated, throw-away home", "isolated, project folder"))
        # ----- C: one real question exactly as clark asks it -----
        provider = ask_claude.ClaudeCommand(places=(str(command),), env=real_env)
        st = provider.status()
        add("real: the native-program, version, flag and Claude sign-in checks accept this command", PASS if st["connected"] else FAIL, st["why"])
        got = provider.ask(ask.build_request(QUESTION, []))
        if isinstance(got, str) and got.strip():
            add("real: one question with the person's own sign-in", PASS, f"answered {got.strip()[:60]!r}")
        else:
            add("real: one question with the person's own sign-in", FAIL, f"no answer: {getattr(got, 'message', got)}")
        time.sleep(SETTLE)
        new = sorted(set(tree(claude_dir)) - before)
        ours = [n for n in new if RUN_FOLDER in n]
        sent = st["connected"] and isinstance(got, str) and rpath is not None
        add("real: no file for the provider's runs under ~/.claude", FAIL if ours else (PASS if sent else INCONCLUSIVE),
            "new: " + ", ".join(ours) if ours else ("none" if sent else "a run was not answered, so this shows nothing"))
        if new and not ours:
            add("real: other new files under ~/.claude", NOTE, f"{len(new)} (another Claude window may have written them; close it and run again to be sure)")
        if shape(claude_json) != json_before:
            add("real: ~/.claude.json changed size or time during the provider's runs", NOTE,
                "only its size and time are looked at; the command keeps its own counters there")
    return report


def text_report(command, report):
    lines = [f"ask clark smoke test: {command}", ""]
    lines += [f"{state:<12} {name}: {words}" for name, state, words in report]
    bad = [r for r in report if r[1] in (FAIL, INCONCLUSIVE)]
    lines += ["", "RESULT: " + ("PASS" if not bad else f"{len(bad)} check(s) FAILED or INCONCLUSIVE: the provider must not merge")]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run ask clark's Claude provider against the real command.")
    parser.add_argument("--claude", help="the command to test (default: the first of the provider's fixed places)")
    parser.add_argument("--skip-real", action="store_true", help="skip the parts that use the person's sign-in")
    parser.add_argument("--report", help="also write the report to this file")
    args = parser.parse_args(argv)
    command, why = ask_claude.find_command((args.claude,) if args.claude else ask_claude.PLACES)
    if command is None:
        print(f"Nothing to test: {why}")
        return 1
    report = smoke(command, real=not args.skip_real)
    text = text_report(command, report)
    print(text)
    if args.report:
        Path(args.report).write_text(text + "\n", encoding="utf-8")
    return 1 if any(r[1] in (FAIL, INCONCLUSIVE) for r in report) else 0


if __name__ == "__main__":
    sys.exit(main())
