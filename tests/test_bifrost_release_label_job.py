"""Bifrost A1: the fourth job, bifrost-release-label, in .github/workflows/bifrost-checks.yml (text test, standard library only).

Run: python3 dev/run_tests.py test_bifrost_release_label_job
"""
import re
import unittest

from _paths import ROOT

WORKFLOW = ROOT / ".github" / "workflows" / "bifrost-checks.yml"


def text():
    return WORKFLOW.read_text(encoding="utf-8")


def job_block(src=None):
    src = text() if src is None else src
    m = re.search(r"^  bifrost-release-label:\n(.*?)(?=^  \S|\Z)", src, re.S | re.M)
    return m.group(1) if m else ""


def run_bodies(block):
    """The text of each run: | body (lines indented deeper than the run: key)."""
    bodies = []
    lines = block.split("\n")
    for i, line in enumerate(lines):
        m = re.match(r"^(\s*)run:\s*(.*)$", line)
        if not m:
            continue
        indent, rest = len(m.group(1)), m.group(2)
        body = [rest] if rest and rest != "|" else []
        for nxt in lines[i + 1:]:
            if nxt.strip() and len(nxt) - len(nxt.lstrip()) <= indent:
                break
            body.append(nxt)
        bodies.append("\n".join(body))
    return bodies


class ReleaseLabelJob(unittest.TestCase):
    def test_job_exists_with_its_name(self):
        block = job_block()
        self.assertTrue(block, "no bifrost-release-label job")
        self.assertIn("    name: bifrost-release-label\n", block)

    def test_other_three_jobs_still_there(self):
        for name in ("bifrost-closes-guard", "bifrost-point-map", "bifrost-test-exists"):
            self.assertIn("  %s:\n" % name, text())

    def test_permissions_read_only(self):
        src = text()
        perms = re.search(r"^permissions:\n((?:  .*\n)+)", src, re.M).group(1)
        self.assertEqual(sorted(l.strip() for l in perms.strip().split("\n")),
                         ["contents: read", "pull-requests: read"])
        self.assertNotRegex(job_block(src), r"(?m)^\s*permissions:", "the job must not set its own permissions")
        self.assertNotRegex(src, r":\s*write\b")

    def test_enforce_stays_zero(self):
        self.assertEqual(re.findall(r'^\s*BIFROST_ENFORCE:\s*(.*)$', text(), re.M), ['"0"'])

    def test_release_inputs_empty_by_default(self):
        block = job_block()
        self.assertRegex(block, r'(?m)^      BIFROST_RELEASE_TAG: ""')
        self.assertRegex(block, r'(?m)^      BIFROST_FULL_FILE: ""')
        self.assertRegex(block, r'(?m)^      BIFROST_PLAN_REPO: ""')

    def test_no_expression_in_any_run_body(self):
        bodies = run_bodies(job_block())
        self.assertTrue(bodies)
        for body in bodies:
            self.assertNotIn("${{", body)

    def test_checkout_is_base_sha_with_full_history(self):
        block = job_block()
        self.assertIn("ref: ${{ github.event.pull_request.base.sha || github.event.merge_group.base_sha }}", block)
        self.assertRegex(block, r"(?m)^\s+fetch-depth: 0\s*$")

    def test_exit_two_becomes_exit_zero(self):
        body = "\n".join(run_bodies(job_block()))
        m = re.search(r'"\$rc" -eq 2 \]; then\n(.*?)\n\s*elif', body, re.S)
        self.assertTrue(m, "no exit-2 branch")
        self.assertIn("NOT CHECKED", m.group(1))
        self.assertRegex(m.group(1), r"exit 0\s*$")

    def test_not_checked_when_inputs_missing(self):
        body = "\n".join(run_bodies(job_block()))
        self.assertIn("NOT CHECKED: no release tag / FULL list supplied", body)
        self.assertIn('-z "$BIFROST_RELEASE_TAG"', body)
        self.assertIn('-z "$BIFROST_FULL_FILE"', body)
        self.assertIn('-z "$BIFROST_PLAN_REPO"', body)

    def test_fail_exits_one_only_when_enforced(self):
        body = "\n".join(run_bodies(job_block()))
        m = re.search(r'"\$BIFROST_ENFORCE" = "1" \]; then\n(.*?)\n\s*fi\n', body, re.S)
        self.assertTrue(m)
        self.assertIn("exit 1", m.group(1))
        self.assertEqual(body.count("exit 1"), 1)

    def test_gate_arguments(self):
        body = "\n".join(run_bodies(job_block()))
        self.assertIn('--repo "$BIFROST_PLAN_REPO"', body)
        self.assertNotIn("insyncalan", body)
        self.assertIn("--code-repo .", body)
        self.assertIn('--tag "$BIFROST_RELEASE_TAG"', body)


if __name__ == "__main__":
    unittest.main()
