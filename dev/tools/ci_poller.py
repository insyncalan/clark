#!/usr/bin/env python3
"""The tower's pull-request tester: tests each open PR's current head on both Pythons and reports it as a commit status
(`tower/tests`) on that exact commit (development only; standard library only; Python 3.9 or later).

    python3 dev/tools/ci_poller.py --repo OWNER/NAME --trusted-authors LOGIN[,LOGIN] --once          # a DRY RUN: changes nothing
    python3 dev/tools/ci_poller.py --repo OWNER/NAME --trusted-authors LOGIN --once --post           # tests each untested PR once
    python3 dev/tools/ci_poller.py --repo OWNER/NAME --trusted-authors LOGIN --loop --every 60 --post  # the service

Deployed alone (e.g. /opt/ci/ci_poller.py)? Copy dev/tools/run_support.py beside it: the Chrome check uses it.

Safety: --repo has no default (a repository rename must never re-aim the poller) and --trusted-authors is required for a real
repository (a PR's code runs as the poller's user, so only PRs by the listed GitHub logins are tested; any other is skipped).
Only --local (a rehearsal, nothing goes to GitHub) may omit --trusted-authors.

Why it exists: GitHub's runners bill a minute for each minute of a full run (about 15 per push). The suite takes about 3 minutes on
a box of our own. docs: comms/CI-PLAN-AVENGERS-TOWER.md (the plan), Team/04 (the merge rule: merge only on a green `tower/tests`
on the PR's CURRENT head sha). GitHub cannot make a check required on this private repo, so the rule is the Head's.

What one pass does, for each open pull request:
  1. skips a draft, a PR from a fork, a PR whose current head already has a result here (the state file) or a `tower/tests` status on
     GitHub (success or failure, or a `pending` less than CLAIM_MINUTES old: another runner has it);
  2. posts `pending` ("running on <host>") on the head sha, so two runners never test the same commit;
  3. fetches GitHub's own merge of the head with main (refs/pull/N/merge, what Actions tests); a PR that does not merge cleanly gets a
     `failure` that says so, and nothing is run;
  4. in a fresh folder, runs `dev/run_tests.py -j N` on each Python, one after the other, through `clark-one-suite` when it exists
     (the box's lock: at most 2 suites at once), with the token variables taken out of the tests' environment;
  5. posts `success` only if every Python passed (the runner already re-runs a failing file once alone), else `failure` (the PR's tests failed;
     a PR that does not merge cleanly is also a `failure`), or `error` when the RUNNER was at fault (no Chrome, no lock, the checkout could
     not be fetched, a timeout, a suite that crashed without a summary), so a red `failure` always means the PR. It posts the
     seconds and counts, and (with --post) one comment on the PR naming the sha.
Anything that goes wrong in the poller itself posts nothing final: the `pending` ages out, and the PR is tried again.

This file holds no token. It uses the `gh` command's sign-in (the user the service runs as). The statuses need a token with commit
statuses: write; the comment needs pull requests: write. Never run it as a user that has more than that. It never merges, pushes,
deletes, closes or edits anything. A PR's code runs as the user running the poller: see the plan's section 4 for the split into
two users that keeps the token away from it (phase 2)."""
import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import run_support                # a redeploy of this file must copy run_support.py beside it
except ImportError:
    sys.exit("ci_poller: run_support.py must sit beside ci_poller.py (copy dev/tools/run_support.py there)")

CONTEXT = "tower/tests"
CLAIM_MINUTES = 30                    # a `pending` from another runner counts for this long, then the PR is tried again
DESC_MAX = 140                        # the Statuses API's limit for a description
SUMMARY = re.compile(r"Python (\d+\.\d+)(?:\.\d+)?: (pass|FAIL),? (\d+) tests? in ([\d.]+) s")
FILES = re.compile(r"(\d+) files? passed, (\d+) failed")
TOKEN_VARIABLES = ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN", "GH_HOST")


def now():
    return datetime.now(timezone.utc)


def parse_time(text):
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


# ---- the forge: GitHub through `gh`, or a local folder for the scratch test ---------------------------------------------------------------

class GhForge:
    """GitHub, through the `gh` command. Reads freely; writes only the commit status and the one comment."""

    def __init__(self, repo, git_dir):
        self.repo, self.git_dir = repo, str(git_dir)

    def _gh(self, args, data=None):
        proc = subprocess.run(["gh"] + args, input=data, capture_output=True)
        if proc.returncode != 0:
            raise RuntimeError("gh %s failed: %s" % (" ".join(args[:3]), proc.stderr.decode("utf-8", "replace")[-200:]))
        return proc.stdout.decode("utf-8", "replace")

    def open_prs(self):
        fields = "number,headRefOid,headRefName,author,isDraft,isCrossRepository,mergeStateStatus,updatedAt"
        return json.loads(self._gh(["pr", "list", "-R", self.repo, "--state", "open", "--limit", "300", "--json", fields]))

    def statuses(self, sha):
        """[{context, state, created_at}] for the commit (the combined view's list)."""
        body = json.loads(self._gh(["api", "repos/%s/commits/%s/status" % (self.repo, sha)]))
        return [{"context": s["context"], "state": s["state"], "created_at": s["created_at"]} for s in body.get("statuses", [])]

    def fetch_merge(self, number, dest):
        """GitHub's merge of the PR with main into `dest` (a fresh folder): True; "conflict" when the PR does not merge cleanly (the
        PR's fault); "error" when the runner could not fetch it (the runner's fault: network, token, disk)."""
        url = "https://github.com/%s.git" % self.repo
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env["GIT_TERMINAL_PROMPT"] = "0"
        run = lambda *a: subprocess.run(["git", "-C", str(dest)] + list(a), capture_output=True, env=env)   # noqa: E731
        subprocess.run(["git", "init", "-q", str(dest)], check=True, capture_output=True)
        got = run("-c", "credential.helper=!gh auth git-credential", "fetch", "-q", "--depth=1", url, "refs/pull/%d/merge" % number)
        if got.returncode != 0:
            # GitHub makes refs/pull/N/merge only when the PR merges cleanly: say which it is by asking whether the PR itself is known
            known = subprocess.run(["gh", "pr", "view", str(number), "-R", self.repo, "--json", "mergeable", "--jq", ".mergeable"], capture_output=True)
            return "conflict" if known.returncode == 0 and known.stdout.decode().strip() == "CONFLICTING" else "error"
        return True if run("checkout", "-q", "--detach", "FETCH_HEAD").returncode == 0 else "error"

    def post_status(self, sha, state, description):
        self._gh(["api", "-X", "POST", "repos/%s/statuses/%s" % (self.repo, sha), "-f", "state=" + state,
                  "-f", "context=" + CONTEXT, "-f", "description=" + description[:DESC_MAX]])

    def comment(self, number, text):
        self._gh(["pr", "comment", str(number), "-R", self.repo, "--body-file", "-"], data=text.encode("utf-8"))


class LocalForge:
    """A rehearsal: the PRs are listed in a JSON file, their merged trees are branches of a local repo, and every write is recorded
    in a JSON file instead of being sent anywhere. Used by tests/test_ci_poller.py, and by a person rehearsing."""

    def __init__(self, folder):
        self.folder = Path(folder)
        self.log = self.folder / "posted.json"
        self.posted = json.loads(self.log.read_text(encoding="utf-8")) if self.log.exists() else {"statuses": [], "comments": []}

    def open_prs(self):
        return json.loads((self.folder / "prs.json").read_text(encoding="utf-8"))

    def statuses(self, sha):
        return [{"context": s["context"], "state": s["state"], "created_at": s["at"]}
                for s in self.posted["statuses"] if s["sha"] == sha]

    def fetch_merge(self, number, dest):
        pr = next(p for p in self.open_prs() if p["number"] == number)
        if pr.get("fetch_error"):
            return "error"
        if pr.get("conflict"):
            return "conflict"
        subprocess.run(["git", "clone", "-q", str(self.folder / "repo.git"), str(dest)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(dest), "checkout", "-q", "--detach", "origin/" + pr["headRefName"]], check=True, capture_output=True)
        return True

    def post_status(self, sha, state, description):
        self.posted["statuses"].append({"sha": sha, "context": CONTEXT, "state": state, "description": description[:DESC_MAX],
                                        "at": now().strftime("%Y-%m-%dT%H:%M:%SZ")})
        self.log.write_text(json.dumps(self.posted), encoding="utf-8")

    def comment(self, number, text):
        self.posted["comments"].append({"number": number, "text": text})
        self.log.write_text(json.dumps(self.posted), encoding="utf-8")


# ---- the decisions ----------------------------------------------------------------------------------------------------------------------

def wants_test(pr, forge_statuses, state, at=None, retest=False):
    """(True, '') or (False, why): whether this PR's current head should be tested now. `retest` (with --only) ignores an earlier result."""
    at = at or now()
    if retest and not pr.get("isDraft") and not pr.get("isCrossRepository"):
        return True, ""
    sha = pr["headRefOid"]
    if pr.get("isDraft"):
        return False, "draft"
    if pr.get("isCrossRepository"):
        return False, "from a fork: never tested here"
    if sha in state:
        return False, "already tested here (%s)" % state[sha]["state"]
    for s in forge_statuses:
        if s["context"] != CONTEXT:
            continue
        if s["state"] in ("success", "failure", "error"):
            return False, "has a %s status already" % s["state"]
        if s["state"] == "pending" and (at - parse_time(s["created_at"])).total_seconds() < CLAIM_MINUTES * 60:
            return False, "another runner has it (pending)"
    return True, ""


CHROME_CANDIDATES = ("/usr/local/bin/clark-chrome", "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser")


def find_chrome():
    """The browser the tests need: CLARK_CHROME if set, else the first of the usual places that exists; '' when none."""
    named = os.environ.get("CLARK_CHROME")
    if named and os.access(named, os.X_OK):
        return named
    return next((c for c in CHROME_CANDIDATES if os.access(c, os.X_OK)), "")


def chrome_starts(chrome, settle=3.0):
    """True when `chrome`, started the way the tests start it (run_support.chrome_command and start_chrome: both keychain flags,
    a throwaway profile), is still running after `settle` seconds; the profile is removed afterwards."""
    profile = tempfile.mkdtemp(prefix=run_support.PROFILE_PREFIX)
    to_r, to_w = os.pipe()
    from_r, from_w = os.pipe()
    proc = None
    try:
        proc = run_support.start_chrome(run_support.chrome_command(chrome, profile), to_r, from_w)
        try:
            proc.wait(settle)
        except subprocess.TimeoutExpired:
            return True                      # still running: it started
        return False                         # it exited by itself
    except (OSError, ValueError):
        return False
    finally:
        if proc is not None:
            run_support.stop_chrome(proc)
        for fd in (to_r, to_w, from_r, from_w):
            try:
                os.close(fd)
            except OSError:
                pass
        run_support.remove_profile(profile)


def clean_env(home, chrome=""):
    env = {k: v for k, v in os.environ.items() if k not in TOKEN_VARIABLES and not k.startswith("GIT_")}
    if chrome:
        env["CLARK_CHROME"] = chrome
    env["HOME"] = str(home)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["CLARK_SUITE_LOW"] = "1"             # the poller yields the suite slot to any lead who is waiting (clark-one-suite)
    return env


def run_python(python, checkout, jobs, env, extra=(), timeout=3600):
    """(passed, summary) for `dev/run_tests.py` run by `python` in `checkout`; the suite goes through clark-one-suite when it exists."""
    lock = shutil.which("clark-one-suite")
    cmd = ([lock] if lock else []) + [python, "dev/run_tests.py", "-j", str(jobs)] + list(extra)
    try:
        proc = subprocess.run(cmd, cwd=str(checkout), env=env, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, {"version": "?", "tests": 0, "seconds": timeout, "note": "timed out", "runner_fault": True}
    except OSError as err:
        return False, {"version": "?", "tests": 0, "seconds": 0, "note": "could not start (%s)" % (err.strerror or "error"), "runner_fault": True}
    out = proc.stdout.decode("utf-8", "replace")
    summary = {"version": "?", "tests": 0, "seconds": 0.0, "note": "", "files_failed": 0}
    found = SUMMARY.findall(out)
    if found:
        v, verdict, tests, seconds = found[-1]
        summary.update(version=v, tests=int(tests), seconds=float(seconds))
    fm = FILES.findall(out)
    if fm:
        summary["files_failed"] = int(fm[-1][1])
    if proc.returncode != 0 and not found:
        summary["note"] = "no test summary, exit %d" % proc.returncode
        summary["runner_fault"] = True            # the suite did not run to a verdict (a missing lock, a crash): the runner's fault, never the PR's
    elif proc.returncode != 0 and not summary["files_failed"]:
        summary["note"] = "exit %d" % proc.returncode
    return proc.returncode == 0, summary


def describe(results):
    """One short line for the status: each Python's verdict, tests and seconds."""
    parts = []
    for passed, s in results:
        text = "%s %s %d tests %ds" % (s["version"], "ok" if passed else "FAILED", s["tests"], round(s["seconds"]))
        if s.get("files_failed"):
            text += " (%d files failed)" % s["files_failed"]
        if s.get("note"):
            text += " " + s["note"]
        parts.append(text)
    return ("; ".join(parts) + " on " + socket.gethostname().split(".")[0])[:DESC_MAX]


def test_pr(pr, forge, args, work, say):
    """Tests one PR's head; returns (state, description). Never raises for a test failure."""
    number, sha = pr["number"], pr["headRefOid"]
    Path(work).mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix="pr-%d-" % number, dir=str(work)))
    home = folder / "home"
    home.mkdir()
    checkout = folder / "checkout"
    try:
        checkout.mkdir()
        fetched = forge.fetch_merge(number, checkout)
        if fetched == "conflict":
            return "failure", "does not merge cleanly with main: update the branch"
        if fetched is not True:
            return "error", "RUNNER FAULT: the pull request could not be fetched; not a test result"
        results = []
        for python in args.pythons:
            say("    %s on %s" % (python, sha[:8]))
            results.append(run_python(python, checkout, args.jobs, clean_env(home, args.chrome)))
        if any(s.get("runner_fault") for _, s in results):
            return "error", ("RUNNER FAULT: " + describe(results))[:DESC_MAX]
        ok = all(p for p, _ in results)
        return ("success" if ok else "failure"), describe(results)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def one_pass(forge, args, state, say=print):
    """One look at the open PRs. Returns the number tested."""
    tested = 0
    prs = sorted(forge.open_prs(), key=lambda p: p.get("updatedAt") or "9999", reverse=True)      # the newest push first: that is the one waiting
    if args.only:
        prs = [p for p in prs if p["number"] in args.only]
    for pr in prs:
        sha = pr["headRefOid"]
        if pr.get("updatedAt") and args.max_age_days and (now() - parse_time(pr["updatedAt"])).days >= args.max_age_days:
            say("  #%d %s: skipped, not updated for %d days (push to it to have it tested)" % (pr["number"], sha[:8], args.max_age_days))
            continue
        if args.trusted_authors and ((pr.get("author") or {}).get("login") or "") not in args.trusted_authors:
            say("  #%d %s: skipped, author not on the trusted list" % (pr["number"], sha[:8]))
            continue
        try:
            ask, why = wants_test(pr, forge.statuses(sha), state, retest=bool(args.retest and args.only))
        except RuntimeError as err:
            say("  #%d: could not read its statuses (%s): left for the next pass" % (pr["number"], err))
            continue
        if not ask:
            say("  #%d %s: skipped, %s" % (pr["number"], sha[:8], why))
            continue
        if args.max and tested >= args.max:
            say("  #%d %s: would test (the --max limit is reached)" % (pr["number"], sha[:8]))
            continue
        if not args.post:
            say("  #%d %s: WOULD test on %s and post %s (dry run: nothing run or posted)" % (
                pr["number"], sha[:8], ", ".join(args.pythons), CONTEXT))
            continue
        say("  #%d %s: testing" % (pr["number"], sha[:8]))
        forge.post_status(sha, "pending", "running on %s" % socket.gethostname().split(".")[0])
        start = time.time()
        try:
            result, description = test_pr(pr, forge, args, Path(args.work), say)
        except Exception as err:                               # never a final status from a fault of the poller's own
            say("  #%d: the poller itself failed (%s); no final status posted, the pending one ages out" % (pr["number"], type(err).__name__))
            continue
        forge.post_status(sha, result, description)
        state[sha] = {"state": result, "at": now().strftime("%Y-%m-%dT%H:%M:%SZ"), "seconds": round(time.time() - start)}
        if not args.no_comment:
            forge.comment(pr["number"], "tower/tests **%s** on head `%s` (%s)." % (result, sha[:12], description) +
                          (" This is a fault of the runner, not a test result: the PR's tests did not run to a verdict." if result == "error" else ""))
        say("  #%d %s: %s: %s" % (pr["number"], sha[:8], result, description))
        tested += 1
    return tested


def load_state(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(path, state):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tmp = str(path) + ".tmp"
    Path(tmp).write_text(json.dumps(state, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", required=True, help="owner/name; no default, so a rename can never re-aim the poller")
    ap.add_argument("--trusted-authors", type=lambda v: {a for a in v.split(",") if a}, default=set(), help="only PRs by these GitHub logins are tested (empty: refuse to run)")
    ap.add_argument("--work", default=str(Path.home() / "ci" / "work"), help="where the temporary checkouts go")
    ap.add_argument("--state", default=str(Path.home() / "ci" / "state.json"), help="the shas already tested here")
    ap.add_argument("--pythons", default="python3.9,python3.15", help="comma-separated interpreters: the oldest and the newest")
    ap.add_argument("--jobs", type=int, default=4, help="files at once inside one suite (the box's lock limits the suites)")
    ap.add_argument("--only", help="comma-separated PR numbers")
    ap.add_argument("--retest", action="store_true", help="with --only: test the PR again even if its head already has a result (a new status replaces the old one)")
    ap.add_argument("--chrome", default="", help="the browser for the tests (default: CLARK_CHROME or the usual places)")
    ap.add_argument("--no-comment", action="store_true", help="post the status only, no PR comment (the status is what the merge rule reads)")
    ap.add_argument("--max-age-days", type=int, default=3, help="skip a PR not updated for this many days (0: none)")
    ap.add_argument("--max", type=int, default=0, help="test at most this many PRs in one pass (0: all)")
    ap.add_argument("--every", type=int, default=60, help="with --loop: seconds between passes")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--loop", action="store_true")
    ap.add_argument("--post", action="store_true", help="really run the tests and post (without it: a dry run)")
    ap.add_argument("--local", help="a folder holding prs.json and repo.git: a rehearsal, nothing goes to GitHub")
    args = ap.parse_args(argv)
    args.pythons = [p for p in args.pythons.split(",") if p]
    args.only = {int(x) for x in args.only.split(",")} if args.only else set()
    if len(args.pythons) < 2:
        ap.error("name at least two Pythons (the oldest and the newest)")
    return args


def main(argv=None):
    args = parse_args(argv)
    if not args.local and not args.trusted_authors:
        print("ci_poller: --trusted-authors is required for a real repository: refusing to test anyone else's code.", file=sys.stderr)
        return 2
    if not args.local and not args.chrome:
        args.chrome = find_chrome()
    if args.post and not args.local and not (args.chrome and chrome_starts(args.chrome)):
        print("ci_poller: no working Chrome for the tests (CLARK_CHROME or /usr/local/bin/clark-chrome): refusing to post, because every browser test would fail and "
              "a red status would blame the PR for the runner's own fault.", file=sys.stderr)
        return 2
    Path(args.work).mkdir(parents=True, exist_ok=True)
    forge = LocalForge(args.local) if args.local else GhForge(args.repo, Path(args.work))
    state = load_state(args.state)
    say = lambda line="": print(line, flush=True)       # noqa: E731
    say("ci_poller: %s, %s" % ("posting" if args.post else "DRY RUN (add --post to run and post)", "every %ds" % args.every if args.loop else "once"))
    while True:
        try:
            one_pass(forge, args, state, say)
        except RuntimeError as err:
            say("  could not list the pull requests (%s): trying again next pass" % err)
        if args.post:
            save_state(args.state, state)
        if args.once:
            return 0
        time.sleep(args.every)


if __name__ == "__main__":
    sys.exit(main())
