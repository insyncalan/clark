"""P12-13: the full Ubuntu suite runs only in Mergify's combined run (and the nightly and the listed reasons); a plain pull request is cheap

Run: python3 dev/run_tests.py test_full_suite_only_in_merge_queue_p12_13   (quick tier)

Pins the as-built plan step of .github/workflows/tests.yml by running it for real in bash, with a fake `gh` (a shell function defined before the step, so no network):
what is full (ten shards) and what is cheap (three shards). The row's wording "only in Mergify's run" is not literal: the nightly,
a hand-started run, release lines, the label full-ci, guarded files and a failed file listing are full too. Tests only.
"""
import os
import re
import subprocess
import tempfile
import unittest

from _paths import ROOT

WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"
TEN = "[1,2,3,4,5,6,7,8,9,10]"
THREE = "[1,2,3]"


def code(text):
    return "\n".join(re.sub(r"\s+#\s.*$", "", ln) for ln in text.splitlines() if not ln.lstrip().startswith("#"))


def block(text, key, indent=0):
    lines, out, inside = text.splitlines(), [], False
    for ln in lines:
        if inside:
            if ln.strip() and len(ln) - len(ln.lstrip()) <= indent:
                break
            out.append(ln)
        elif re.match(rf"^{' ' * indent}{re.escape(key)}:", ln):
            inside = True
            out.append(ln.split(":", 1)[1])
    return "\n".join(out)


def plan_script():
    """The plan step's bash, comments stripped, de-indented."""
    under = block(code(WORKFLOW.read_text(encoding="utf-8")), "jobs")
    plan = block(under, "plan", 2)
    body = plan[plan.index("run: |\n") + len("run: |\n"):]
    body = body[:body.index("\n\n")] if "\n\n" in body else body
    return "\n".join(ln[10:] if ln.startswith(" " * 10) else ln for ln in body.splitlines())


class FullSuiteOnlyInMergeQueueTest(unittest.TestCase):
    def plan(self, files=("src/clark/foo.py",), gh_fails=False, **env):
        """Run the real plan step; `gh` is a fake that prints `files` (or fails); returns the outputs."""
        with tempfile.TemporaryDirectory() as d:
            if gh_fails:
                fake = "gh() { echo boom >&2; return 1; }\n"
            else:
                fake = "gh() { printf '%s\\n' " + " ".join("'" + f + "'" for f in files) + "; }\n"      # a shell function beats any `gh` on PATH: no network
            out = os.path.join(d, "out")
            open(out, "w", encoding="utf-8").close()
            base = {"PATH": os.environ["PATH"], "GITHUB_OUTPUT": out, "RUNNER_TEMP": d, "EVENT": "pull_request",
                    "BRANCH": "feature-x", "BASE_REF": "main", "LABELS": "", "MACOS_INPUT": "", "SCHEDULE": "", "REPO": "x/y",
                    "PR_NUMBER": "7", "GH_TOKEN": "", "FILES_INPUT": ""}
            base.update(env)
            r = subprocess.run(["bash", "-c", fake + plan_script()], env=base, capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(out, encoding="utf-8") as f:
                return dict(ln.split("=", 1) for ln in f.read().splitlines() if "=" in ln)

    def assertFull(self, out):
        self.assertEqual((out["full"], out["count"], out["shards"]), ("1", "10", TEN))

    def assertCheap(self, out):
        self.assertEqual((out["full"], out["count"], out["shards"]), ("", "3", THREE))

    def test_plain_pull_request_is_cheap(self):
        out = self.plan()
        self.assertCheap(out)
        self.assertEqual((out["macos"], out["smoke"], out["advisory"]), ("", "", ""))

    def test_mergify_branch_is_full(self):
        out = self.plan(BRANCH="mergify/merge-queue/abc")
        self.assertFull(out)
        self.assertEqual(out["macos"], "")

    def test_look_alike_branches_are_not_full(self):
        for branch in ("feature/merge-queue-x", "mergify/other", "x/mergify/merge-queue/abc", "mergify/merge-queue"):
            with self.subTest(branch=branch):
                self.assertCheap(self.plan(BRANCH=branch))

    def test_merge_group_is_full(self):
        out = self.plan(EVENT="merge_group", BRANCH="gh-readonly-queue/main/pr-1")
        self.assertFull(out)
        self.assertEqual(out["macos"], "")

    def test_schedule_is_full_with_macos_advisory(self):
        out = self.plan(EVENT="schedule", BRANCH="main")
        self.assertFull(out)
        self.assertEqual((out["macos"], out["advisory"]), ("1", "1"))

    def test_only_the_listed_reasons_make_a_pull_request_full(self):
        for files, labels in ((("docs/readme.md",), ""), (("tests/test_x.py",), ""), (("src/clark/foo.py",), "bug"),
                              (("src/clark/foo.py", "README.md"), "bug,docs")):
            with self.subTest(files=files, labels=labels):
                self.assertCheap(self.plan(files=files, LABELS=labels))
        full = (
            dict(LABELS="full-ci"),
            dict(LABELS="bug,full-ci,docs"),
            dict(files=("src/clark/server.py",)),
            dict(files=(".github/workflows/tests.yml",)),
            dict(BASE_REF="release-1.2"),
            dict(BRANCH="cut-v1.2.3"),
            dict(gh_fails=True),
            dict(files=["f%d.txt" % i for i in range(3000)]),
        )
        for kw in full:
            with self.subTest(case=sorted(kw)):
                self.assertFull(self.plan(**{k: v for k, v in kw.items()}))

    def test_a_look_alike_label_is_not_full_ci(self):
        self.assertCheap(self.plan(LABELS="full-ci-not,xfull-ci"))

    def test_no_push_arm_and_full_starts_empty(self):
        script = plan_script()
        self.assertIsNone(re.search(r"(?m)^\s*push\)", script))
        self.assertIsNone(re.search(r"(?m)^\s*pull_request\)", script))
        self.assertTrue(script.startswith('FULL=""; '), script[:40])


if __name__ == "__main__":
    unittest.main()
