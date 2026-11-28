"""P12-17 'Mac never blocks' (owner, 23-11 and 26-11): a macOS failure never blocks a release, a Mac that cannot run (no Mac, timeout) never blocks
either (recorded "not run" by the release cut in the bifrost repository, engine/release/cut_run.py, tested there), and a macOS failure or not-run shard is filed
as a Tech Debt - Priority ticket (a board rule, not codeable here).

What lives in this repository and is pinned here, beside tests/test_workflow.py (gate text, nightly advisory, cut smoke), tests/test_mergify_config_1581.py (the queue's
required checks, equality) and tests/test_release_build_workflow.py (tag trigger, read-only, timeout, artifact):
  - the 'Tests passed' gate, RUN as bash with a failed Mac: a nightly (advisory), a pull request and a release cut stay green on a red Mac;
  - the release build's Mac zip job is the only job of its workflow, nothing needs it and nothing reads its result, so a red or missing zip cannot stop anything;
  - no workflow other than the tests workflow starts a Mac job, and no workflow waits for the release build.

Two gaps this file first recorded are closed by P12-18 (the ruling of 28-11, G1 and G2), and tests/test_workflow.py now pins both: a release-* branch, or a pull request
into one, runs the Mac smoke set reported and never required (CUT=1), and a hand-started run with macos=true runs the full Mac shards advisory. Read this file with P12-18
landed: with it not landed, those two arms still require the Mac. Nothing below depends on either arm.

Text checks only, no YAML parser. Run: python3 dev/run_tests.py test_mac_never_blocks_p12_17"""
import os
import re
import subprocess
import unittest

from _paths import ROOT

WORKFLOWS = ROOT / ".github" / "workflows"
TESTS_YML = WORKFLOWS / "tests.yml"
RELEASE_YML = WORKFLOWS / "release-build.yml"


def code(path):
    return "\n".join(l for l in path.read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("#"))


def job_names(path):
    """The job ids of a workflow: the two-space-indented keys under `jobs:`."""
    text = code(path)
    body = text[text.index("\njobs:\n") + len("\njobs:\n"):]
    return re.findall(r"(?m)^  ([\w-]+):\s*$", body)


def gate_passes(**env):
    """Run the 'Tests passed' step as bash -e (as GitHub runs a step) with these env values and say whether it passes."""
    text = TESTS_YML.read_text(encoding="utf-8")
    passed = text[text.index("\n  passed:\n"):]
    body = passed[passed.index("run: |\n") + len("run: |\n"):]
    script = "\n".join(ln[10:] if ln.startswith(" " * 10) else ln for ln in body.splitlines())
    base = {"PATH": os.environ["PATH"], "PLAN": "success", "TESTS": "success", "PY39": "success", "MACOS": "skipped", "SMOKE": "skipped",
            "WANT_SMOKE": "", "ADVISORY": "", "CUT": "", "WANT_PY39": "1", "WANT_MACOS": "", "EVENT": "workflow_dispatch"}
    ran = "success" if env.get("EVENT") == "pull_request" else "skipped"
    base.update({"NAMED": ran, "COMPILE39": ran})
    base.update(env)
    return subprocess.run(["bash", "-e", "-c", script], env=base, capture_output=True, text=True, timeout=60).returncode == 0


class MacNeverBlocksTest(unittest.TestCase):
    def test_a_red_or_cancelled_full_mac_suite_in_the_nightly_leaves_the_gate_green(self):
        for result in ("failure", "cancelled", "success"):
            self.assertTrue(gate_passes(EVENT="schedule", WANT_MACOS="1", ADVISORY="1", MACOS=result), f"nightly, macOS {result}")
        self.assertFalse(gate_passes(EVENT="schedule", WANT_MACOS="1", ADVISORY="1", TESTS="failure"))      # the Ubuntu tests still stop it

    def test_a_red_or_missing_mac_never_stops_a_pull_request_or_a_cut(self):
        for result in ("failure", "cancelled", "skipped"):
            self.assertTrue(gate_passes(EVENT="pull_request", MACOS=result), f"pull request, macOS {result}")
            self.assertTrue(gate_passes(EVENT="workflow_dispatch", CUT="1", WANT_SMOKE="1", SMOKE=result), f"cut, smoke {result}")
        self.assertFalse(gate_passes(EVENT="pull_request", TESTS="failure"))

    def test_the_mac_zip_job_is_the_only_job_of_the_release_build_and_says_it_never_blocks(self):
        self.assertEqual(job_names(RELEASE_YML), ["mac-zip"])
        self.assertIn("name: Mac zip (never blocks the release)", code(RELEASE_YML))
        self.assertNotIn("needs:", code(RELEASE_YML))
        self.assertNotIn("needs.mac-zip", code(RELEASE_YML))

    def test_no_workflow_needs_the_mac_zip_or_waits_for_the_release_build(self):
        for wf in sorted(WORKFLOWS.glob("*.yml")):
            c = code(wf)
            self.assertNotRegex(c, r"needs:[^\n]*mac-zip", wf.name)
            self.assertNotIn("needs.mac-zip", c, wf.name)
            self.assertNotIn("workflow_run", c, wf.name)
            if wf.name != "release-build.yml":
                self.assertNotIn("Release build", c, wf.name)

    def test_only_the_tests_and_release_build_workflows_start_a_mac(self):
        for wf in sorted(WORKFLOWS.glob("*.yml")):
            if wf.name in ("tests.yml", "release-build.yml"):
                continue
            self.assertNotRegex(code(wf), r"(?i)macos", wf.name)


if __name__ == "__main__":
    unittest.main()
