#!/usr/bin/env python3
"""ci_run.py: run ONE Bifrost check on ONE pull request inside GitHub Actions (report-only first).

(No --pr, or an empty one, is a merge_group run: prints NOT CHECKED and exits 0.)
Usage: ci_run.py --check point-map|closes-guard|test-exists [--pr N] [--repo owner/name]
Reads GitHub with `gh api` GET only, using the job's own GITHUB_TOKEN (GH_TOKEN). Never writes to GitHub.
Exit 1 only when the verdict is FAIL and BIFROST_ENFORCE=1. With BIFROST_ENFORCE=0 (the default) a FAIL is
reported in the log and the job summary and the job still succeeds.
LEGACY (PR written before the Point map format) is a pass. A ticket that the job token cannot read (the plan repo
is private) is reported as NOT CHECKED and is not a failure.
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pr_checks_report as P

NOT_CHECKED_PREFIX = "cannot read ticket"


class CI(P.GH):
    def pr(self, n):
        """The pull request. On a pull_request run the event payload already holds it (number, title, body, head sha):
        no API call. Anything else (a rerun, a run by hand, another number, a payload without those fields) is one API call."""
        path = os.environ.get("GITHUB_EVENT_PATH")
        # A rerun (attempt 2 and up) reuses the ORIGINAL payload, whose body may be stale: only attempt 1 trusts it.
        if path and os.environ.get("GITHUB_RUN_ATTEMPT", "1") == "1":
            try:
                with open(path, encoding="utf-8") as f:
                    pr = json.load(f).get("pull_request") or {}
                if pr.get("number") == n and pr.get("title") is not None and (pr.get("head") or {}).get("sha"):
                    return pr
            except (OSError, ValueError):
                pass
        return P.gh_json(f"repos/{self.repo}/pulls/{n}")


def not_checked_fail(check, reason):
    """A required check must never pass without checking: a rate limit that outlasts the retries FAILS the job (exit 1), whatever BIFROST_ENFORCE says."""
    line = f"bifrost-{check}: NOT CHECKED: {reason}"
    print(line)
    print(f"::error::{line}")
    summ = os.environ.get("GITHUB_STEP_SUMMARY")
    if summ:
        with open(summ, "a") as f:
            f.write(f"### bifrost-{check}: NOT CHECKED\n\n{reason}\n")
    return 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", required=True, choices=P.CHECKS)
    ap.add_argument("--pr", default="", help="pull request number; empty or missing on a merge_group run")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "insyncalan/clark"))
    ap.add_argument("--plan-repo", default=os.environ.get("BIFROST_PLAN_REPO", ""))
    a = ap.parse_args(argv)
    if a.pr == "":
        # merge_group has no pull request: nothing to read, nothing to judge
        line = f"bifrost-{a.check}: NOT CHECKED: merge_group has no pull request"
        print(line)
        summ = os.environ.get("GITHUB_STEP_SUMMARY")
        if summ:
            with open(summ, "a") as f:
                f.write(f"### bifrost-{a.check}: NOT CHECKED\n\nNOT CHECKED: merge_group has no pull request\n")
        return 0
    if not a.pr.isdigit():
        ap.error("--pr must be a number")
    a.pr = int(a.pr)
    gh = CI(a.repo, a.plan_repo)
    try:
        row = P.run_pr(gh.pr(a.pr), gh)
    except P.RateLimited as e:
        # not a verdict on the pull request, but nothing was checked, so the job fails (rerun it)
        return not_checked_fail(a.check, "GitHub rate limit after retries, rerun")
    res = row["checks"][a.check]
    verdict, reason = res["result"], res["reason"]
    if verdict == "FAIL" and reason.startswith(NOT_CHECKED_PREFIX):
        verdict = "NOT CHECKED"
    enforce = os.environ.get("BIFROST_ENFORCE", "0") == "1"
    line = f"bifrost-{a.check}: {verdict} on PR #{a.pr} head {row['sha']}: {reason}"
    print(line)
    summ = os.environ.get("GITHUB_STEP_SUMMARY")
    mode = "ENFORCED" if enforce else "report-only (BIFROST_ENFORCE=0)"
    if summ:
        with open(summ, "a") as f:
            f.write(f"### bifrost-{a.check}: {verdict}\n\n{reason}\n\nMode: {mode}\n")
    if verdict == "FAIL":
        print(f"::{'error' if enforce else 'warning'}::{line}")
        return 1 if enforce else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
