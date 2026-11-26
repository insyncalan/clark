"""Pre-CI: the six checks a head must pass before its pull request is marked Ready for QA (development only; standard library only).

    bash ~/wo/loadgate.sh -p 70 -- python3 dev/tools/pre_ci.py --ticket TICKET.json [--base origin/main] [--record DIR]

One command, the same tools CI uses, so green here should mean green there. Run it once per push, on a committed head:
1. the scan (dev/tools/ci_scan.py) over what the head changes;
2. the test-honesty script (dev/tools/honesty_check.py) and the scope script (dev/tools/scope_check.py);
3. the ticket's named tests;
4. the affected tests: the test files that can reach a changed file (dev/run_tests.py --changed);
5. the Python 3.9 compile check: every tracked .py file must parse on the oldest Python clark supports;
6. the smoke suite: the test files listed in dev/tools/pre_ci_smoke.txt.
Every check runs even when an earlier one fails, so one run gives the whole list. The size of the change is logged and never
blocks. The result is written as <DIR>/<head sha>.json and as one line in <DIR>/log.jsonl (default DIR: the repository's git
folder, pre-ci/, so it is never committed). Exit 0: all pass. Exit 1: a check failed or was not checked. Exit 2: it did not start.

The ticket file is the one dev/tools/scope_check.py reads: {"ticket", "files", "named_tests"}.

LIMITS (what a green record does not prove):
- It runs the copies of the tools in this checkout, so a change to a tool is checked by the changed tool. CI runs the scan from
  the base branch; the full suite runs once, in the merge queue.
- A change that can reach any test (a stylesheet, the page, a workflow, the runner) runs only the close test files (see `narrow`),
  at most AFFECTED_CAP of them, and the record says "capped". The full suite is not run here.
- Without a Python 3.9 on the machine (python3.9 on the PATH, or CLARK_PY39) check 5 parses with this Python's 3.9 grammar
  switch, which misses some newer syntax; the record says which was used. CI compiles with a real 3.9.
"""
import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TOOLS = ROOT / "dev" / "tools"
RUNNER = ROOT / "dev" / "run_tests.py"
SMOKE = TOOLS / "pre_ci_smoke.txt"
AFFECTED_CAP = 40                 # test files; over this the change is "wide" and only the files that name a changed file run
TARGET_SECONDS = 300              # the target for the whole run; logged when passed, never a failure
TAIL_LINES = 12
DUBAI = timezone(timedelta(hours=4))
PY39_PROBE = ("import sys\nbad = 0\nfor p in sys.stdin.read().split('\\0'):\n    if not p:\n        continue\n    try:\n"
              "        compile(open(p, 'rb').read(), p, 'exec', dont_inherit=True)\n    except (SyntaxError, ValueError) as e:\n"
              "        bad = 1\n        print('%s: line %s: %s' % (p, getattr(e, 'lineno', '?'), getattr(e, 'msg', e)))\nsys.exit(bad)\n")

sys.path.insert(0, str(TOOLS))


def dubai_now():
    return datetime.now(DUBAI).strftime("%d-%m-%Y %H:%M:%S +04")


def git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("pre-CI did not start: git %s failed: %s" % (args[0], r.stderr.strip()))
    return r.stdout


def size_of(shortstat):
    """`git diff --shortstat` as numbers."""
    def num(word):
        m = re.search(r"(\d+) %s" % word, shortstat)
        return int(m.group(1)) if m else 0
    return {"files": num("file"), "additions": num("insertion"), "deletions": num("deletion")}


def smoke_names(text):
    """The test files of the smoke list: one name a line, `#` starts a comment."""
    return [ln.split("#")[0].strip() for ln in text.splitlines() if ln.split("#")[0].strip()]


def tail(text):
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    return "\n".join(lines[-TAIL_LINES:])


def run(argv, stdin=None):
    """(exit code or None when it could not start, output, seconds)."""
    start = time.time()
    try:
        r = subprocess.run(argv, cwd=ROOT, input=stdin, capture_output=True, text=True)
    except OSError as exc:
        return None, "could not start: %s" % type(exc).__name__, time.time() - start
    return r.returncode, r.stdout + r.stderr, time.time() - start


def narrow(listed, changed, text_of, cap=AFFECTED_CAP):
    """(the affected test files to run, capped?). Up to the cap the whole list runs. Over it, only the close files run: a test
    file that is itself changed, test_<name>.py for a changed <name>, and the files that name a changed file by its file name.
    A name that more than `cap` files hold (every test file names the runner in its "Run:" line) tells nothing and is not
    followed. In name order, cut at the cap."""
    if len(listed) <= cap:
        return list(listed), False
    close = set()
    for name in sorted({Path(p).name for p in changed}):
        own = {name, "test_" + Path(name).stem + ".py"} & set(listed)
        naming = [f for f in listed if name in (text_of(f) or "")]
        close |= own | (set(naming) if len(naming) <= cap else set())
    return sorted(close)[:cap], True


def cannot_parse_39(sources):
    """[(path, why)] for the files Python 3.9's grammar refuses, read with this Python (the fallback for check 5)."""
    bad = []
    for path in sorted(sources):
        try:
            ast.parse(sources[path], filename=path, feature_version=(3, 9))
        except (SyntaxError, ValueError) as exc:
            bad.append((path, "line %s: %s" % (getattr(exc, "lineno", "?"), getattr(exc, "msg", exc))))
    return bad


def python39():
    """The path of a Python 3.9, or "". CLARK_PY39, then python3.9 on the PATH, then this Python when it is one."""
    for cand in (os.environ.get("CLARK_PY39"), shutil.which("python3.9"), sys.executable if sys.version_info[:2] == (3, 9) else None):
        if not cand:
            continue
        code, out, _ = run([cand, "-c", "import sys; print('%d.%d' % sys.version_info[:2])"])
        if code == 0 and out.strip() == "3.9":
            return cand
    return ""


class PreCi:
    def __init__(self, ticket_path, base, head):
        self.ticket_path, self.base, self.head = ticket_path, base, head
        self.checks = []

    def add(self, n, name, argv, code, out, secs, **more):
        """Record one check. Exit 0 is pass; a check that could not start, or the scan's and the scripts' exit 2, is not checked."""
        result = "pass" if code == 0 else "not checked" if code is None or (code == 2 and n in (1, 2)) else "fail"
        check = {"n": n, "name": name, "result": result, "command": " ".join(argv), "exit": code, "seconds": round(secs, 1),
                 "tail": tail(out)}
        check.update(more)
        self.checks.append(check)
        print("%d %-18s %-11s %5.1f s" % (n, name, result, secs), flush=True)
        if result != "pass":
            print("\n".join("    " + ln for ln in check["tail"].splitlines()), flush=True)
        return check

    def tool(self, n, name, script, *args):
        argv = [sys.executable, str(script.relative_to(ROOT)), *args]
        return self.add(n, name, argv, *run(argv))

    def named(self, tests):
        argv = [sys.executable, "dev/run_tests.py", *tests]
        if not tests:
            return self.add(3, "named tests", argv, 1, "the ticket names no test", 0.0)
        code, out, secs = run(argv)
        ran = re.search(r"(\d+) tests in", out)
        if code == 0 and not ran:
            code, out = 1, out + "\nno named test ran"
        return self.add(3, "named tests", argv, code, out, secs)

    def affected(self, changed):
        listing = [sys.executable, "dev/run_tests.py", "--changed", self.base, "--list"]
        code, out, secs = run(listing)
        if code != 0:
            return self.add(4, "affected tests", listing, code, out, secs)
        listed = [ln.split()[0] for ln in out.splitlines() if ln.startswith("test_") and ".py" in ln]
        if not listed:
            return self.add(4, "affected tests", listing, 0, out + "\nno test file is affected", secs, files=0, capped=False)
        chosen, capped = narrow(listed, changed, lambda f: (ROOT / "tests" / f).read_text(encoding="utf-8", errors="replace"))
        if not capped:
            argv = [sys.executable, "dev/run_tests.py", "--changed", self.base]
        elif chosen:
            argv = [sys.executable, "dev/run_tests.py", *chosen]
        else:
            return self.add(4, "affected tests", listing, 0, "%d test files reach this change; none names a changed file, none run "
                            "here (capped)" % len(listed), secs, files=0, reached=len(listed), capped=True)
        code, out, more = run(argv)
        return self.add(4, "affected tests", argv, code, out, secs + more, files=len(chosen), reached=len(listed), capped=capped)

    def compile39(self):
        files = [p for p in git("ls-files", "-z", "--", "*.py").split("\0") if p]
        py = python39()
        if py:
            argv = [py, "-c", PY39_PROBE]
            code, out, secs = run(argv, stdin="\0".join(files))
            return self.add(5, "Python 3.9 compile", [py, "-c", "<compile every tracked .py file>"], code,
                            out or "%d files compile" % len(files), secs, files=len(files), interpreter="python3.9")
        start = time.time()
        bad = cannot_parse_39({p: (ROOT / p).read_bytes() for p in files})
        out = "\n".join("%s: %s" % b for b in bad) or "%d files parse" % len(files)
        return self.add(5, "Python 3.9 compile", ["ast.parse(feature_version=(3, 9))"], 1 if bad else 0, out, time.time() - start,
                        files=len(files), interpreter="this Python with the 3.9 grammar switch (LIMIT: misses some newer syntax)")

    def smoke(self):
        try:
            names = smoke_names(SMOKE.read_text(encoding="utf-8"))
        except OSError:
            names = []
        argv = [sys.executable, "dev/run_tests.py", *names]
        if not names:
            return self.add(6, "smoke suite", argv, None, "dev/tools/pre_ci_smoke.txt lists no test file", 0.0)
        return self.add(6, "smoke suite", argv, *run(argv))

    def run_all(self, ticket, changed):
        self.tool(1, "scan", TOOLS / "ci_scan.py", "--repo", ".", "--base", self.base, "--head", self.head)
        self.tool(2, "test honesty", TOOLS / "honesty_check.py", "--repo", ".", "--base", self.base, "--head", self.head)
        self.tool(2, "scope", TOOLS / "scope_check.py", "--repo", ".", "--base", self.base, "--head", self.head,
                  "--ticket", self.ticket_path)
        self.named(list(ticket.get("named_tests") or []))
        self.affected(changed)
        self.compile39()
        self.smoke()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ticket", required=True, help="the ticket file: {ticket, files, named_tests}")
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--record", default="", metavar="DIR")
    a = ap.parse_args(argv)
    import scope_check
    try:
        ticket = scope_check.load_ticket(a.ticket)
    except scope_check.CannotCheck as exc:
        print("pre-CI did not start: %s" % exc)
        return 2
    if git("status", "--porcelain").strip():
        print("pre-CI did not start: there is uncommitted work. The record names a head, so commit first.")
        return 2
    head = git("rev-parse", "HEAD").strip()
    base = git("merge-base", a.base, head).strip()
    changed = [p for p in git("diff", "--name-only", "--no-renames", "-z", base, head).split("\0") if p]
    size = size_of(git("diff", "--shortstat", base, head))
    started, clock = dubai_now(), time.time()
    print("pre-CI on %s (base %s, ticket %s, %d files, +%d -%d)" % (head[:8], base[:8], ticket.get("ticket", "not given"),
                                                                 size["files"], size["additions"], size["deletions"]), flush=True)
    run_ = PreCi(str(Path(a.ticket).resolve()), base, head)
    run_.run_all(ticket, changed)
    ok = all(c["result"] == "pass" for c in run_.checks)
    seconds = round(time.time() - clock, 1)
    doc = {"head": head, "base": base, "ticket": str(ticket.get("ticket", "")), "result": "pass" if ok else "fail",
           "started": started, "finished": dubai_now(), "seconds": seconds, "over_target": seconds > TARGET_SECONDS,
           "size": size, "checks": run_.checks}
    folder = Path(a.record) if a.record else Path(git("rev-parse", "--path-format=absolute", "--git-common-dir").strip()) / "pre-ci"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / (head + ".json")).write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    line = {k: doc[k] for k in ("head", "base", "ticket", "result", "finished", "seconds")}
    line["checks"] = {c["name"]: c["result"] for c in run_.checks}
    with open(folder / "log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")
    if seconds > TARGET_SECONDS:
        print("note: %.0f s, over the %d s target (logged, never blocks)" % (seconds, TARGET_SECONDS))
    print("record: %s" % (folder / (head + ".json")))
    print("PRE-CI %s %s" % ("pass" if ok else "FAIL", head))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
