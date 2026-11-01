"""#70: the CI workflow (.github/workflows/tests.yml) keeps the rules of the team repo

Run: python3 dev/run_tests.py test_workflow   (quick tier)

Read as text (standard library only, no YAML library): the triggers, read-only permissions, no secrets and never
`pull_request_target`, Ubuntu 24.04: the newest Python runs `--push origin/<base>` on a pull request and every file on
a push to main, a release branch or by hand; Python 3.9 on the quick tier on every run; macOS on release branches and by
hand, required there, with a static name; and one "Tests passed" job that is green only if every required job is and
posts nothing for a cancelled run.
"""
import re
import subprocess
import sys
import unittest

from _paths import ROOT

WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"


def code(text):
    """The workflow without its comments (a rule written in a comment doesn't count)."""
    return "\n".join(re.sub(r"\s+#\s.*$", "", ln) for ln in text.splitlines() if not ln.lstrip().startswith("#"))


def block(text, key, indent=0):
    """The lines under `key:` at `indent` spaces, up to the next key at that indent (text, without the key's own line)."""
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


def jobs(text):
    """{job id: its text}."""
    under = block(text, "jobs")
    ids = re.findall(r"^  ([\w-]+):", under, re.M)
    return {j: block(under, j, 2) for j in ids}


# The browser's names, joined from parts so this file doesn't carry them (they would put it in the browser tier).
MAC_APP = "/Applications/Google" + " Chrome.app/Contents/MacOS/Google" + " Chrome"
ON_PATH = "command -v google-chrome || command -v chrom" + "ium || command -v chrom" + "ium-browser"
BRANCH = "github.head_ref || github.ref_name"
RELEASE_BRANCH = f"(startsWith({BRANCH}, 'release-') || (startsWith({BRANCH}, 'v') && contains({BRANCH}, '-release')))"
WANTS_MACOS = f"{RELEASE_BRANCH} || (github.event_name == 'workflow_dispatch' && github.event.inputs.macos == 'true')"


class Workflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = code(WORKFLOW.read_text(encoding="utf-8"))
        cls.jobs = jobs(cls.text)

    def test_triggers(self):
        on = block(self.text, "on")
        self.assertIn("workflow_dispatch:", on)
        self.assertRegex(block(on, "macos", 6), r"type: boolean")
        self.assertIn("pull_request:", on)
        self.assertRegex(block(on, "push", 2), r"branches: \[main\]")

    def test_a_documents_only_change_still_runs_the_suite(self):
        # tests/test_no_real_names.py reads every tracked file, documents included: skipping the run for a document would
        # let a real name merge with no CI run of the guard. So no trigger may filter by path.
        self.assertNotIn("paths-ignore", self.text)
        self.assertNotRegex(self.text, r"\bpaths:")
        on = block(self.text, "on")
        for event in ("pull_request", "push"):
            self.assertNotRegex(block(on, event, 2), r"paths", event)

    def test_every_action_is_pinned_to_a_full_commit_sha(self):
        raw = WORKFLOW.read_text(encoding="utf-8")
        uses = re.findall(r"^\s*-?\s*uses:\s*(\S+)(.*)$", code(raw), re.M)
        self.assertGreaterEqual(len(uses), 4)
        for ref, rest in uses:
            self.assertRegex(ref, r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$", f"{ref} is not pinned to a 40-hex commit SHA")
        # the tag a SHA stands for is kept as a comment after it (code() drops the comment, so read the raw lines)
        for ln in raw.splitlines():
            if re.match(r"^\s*-?\s*uses:", ln):
                self.assertRegex(ln, r"@[0-9a-f]{40} # v\d+", ln)

    def test_macos_matches_the_release_branch_names_the_docs_use(self):
        # docs/handoff/how-to-run-v0.1.md names the release line v0.1-release; the release process names release-X.Y.Z.
        # Read the two tests out of the workflow's own `if:` and apply them to both names (and to ones that must not match).
        docs = (ROOT / "docs" / "handoff" / "how-to-run-v0.1.md").read_text(encoding="utf-8")
        self.assertIn("v0.1-release", docs)
        cond = re.search(r"if: (.*)\n", self.jobs["macos"] + "\n").group(1)
        starts = re.findall(r"startsWith\(github\.head_ref \|\| github\.ref_name, '([^']*)'\)", cond)
        contains = re.findall(r"contains\(github\.head_ref \|\| github\.ref_name, '([^']*)'\)", cond)
        self.assertEqual((starts, contains), (["release-", "v"], ["-release"]))

        def wants(branch):
            return branch.startswith("release-") or (branch.startswith("v") and "-release" in branch)
        for branch in ("release-0.1.0", "v0.1-release", "v0.2-release"):
            self.assertTrue(wants(branch), branch)
        for branch in ("main", "team-a-70-test-tiers", "v0.1-store", "pm-brief"):
            self.assertFalse(wants(branch), branch)

    def test_never_pull_request_target_no_secrets_read_only(self):
        self.assertNotIn("pull_request_target", self.text)          # the header comment says "never"
        self.assertNotIn("secrets.", self.text)
        self.assertNotIn("secrets:", self.text)
        self.assertEqual(block(self.text, "permissions").split(), ["contents:", "read"])
        self.assertNotRegex(self.text, r"\bwrite\b")
        for job, body in self.jobs.items():
            self.assertNotIn("permissions:", body, f"{job} widens the permissions")
        self.assertEqual(self.text.count("persist-credentials: false"), self.text.count("actions/checkout@"))

    def test_a_newer_run_cancels_the_older(self):
        concurrency = block(self.text, "concurrency")
        self.assertIn("group: tests-", concurrency)
        self.assertRegex(concurrency, r"cancel-in-progress: true")

    def test_ubuntu_24_04_newest_python_auto_scope_and_3_9_on_the_quick_tier(self):
        tests = self.jobs["tests"]
        self.assertRegex(tests, r"runs-on: ubuntu-24\.04\b")
        self.assertNotIn("ubuntu-latest", self.text)
        rows = re.findall(r"- \{(python: .*)\}", tests)
        self.assertEqual(len(rows), 2, rows)
        found = {re.search(r'python: "([\d.x]+)"', r).group(1): re.search(r'scope: "([^"]*)"', r).group(1) for r in rows}
        self.assertEqual(found, {"3.x": "auto", "3.9": "--quick"})
        self.assertIn("python-version: ${{ matrix.python }}", tests)
        self.assertIn("name: ubuntu-24.04 \u00b7 Python ${{ matrix.python }} \u00b7 shard ${{ matrix.shard }}/${{ matrix.shards }}", tests)

    def test_a_pull_request_runs_push_scope_and_the_full_suite_runs_elsewhere(self):
        tests = self.jobs["tests"]
        self.assertIn('if [ "$SCOPE" = "auto" ]; then\n            SCOPE=""', tests)
        self.assertIn('if [ "$EVENT" = "pull_request" ]; then\n              SCOPE="--push origin/$BASE"', tests)
        self.assertIn('case "$HEAD_REF" in\n                release-*|v*-release*) SCOPE="" ;;', tests)
        self.assertIn('python3 dev/run_tests.py -j "$JOBS" $SCOPE --shard "$SHARD/$SHARDS" --max-fail 8 $FILES', tests)

    def test_a_pull_request_fetches_the_whole_history_so_the_base_is_there(self):
        self.assertIn("fetch-depth: ${{ github.event_name == 'pull_request' && '0' || '1' }}", self.jobs["tests"])

    def test_the_branch_and_base_reach_the_shell_only_through_env(self):
        for job, body in self.jobs.items():
            for step in re.split(r"\n      - ", body):
                m = re.search(r"\n        run: (.*?)(?=\n        \w[\w-]*:|\Z)", step, re.S)
                if m:
                    self.assertNotIn("${{", m.group(1), f"{job}: an expression inside a run script")
        tests = self.jobs["tests"]
        self.assertIn("HEAD_REF: ${{ github.head_ref }}", tests)
        self.assertIn("BASE: ${{ github.base_ref }}", tests)

    def test_the_quick_tier_holds_the_no_real_names_and_reuse_record_tests(self):
        # No paths-ignore, and 3.9 runs only the quick tier: so a documents-only change still reaches these two on every run.
        out = subprocess.run([sys.executable, str(ROOT / "dev" / "run_tests.py"), "--quick", "--list"], cwd=ROOT,
                             capture_output=True, text=True, timeout=120).stdout.split()
        self.assertIn("test_no_real_names.py", out)
        self.assertIn("test_app_files.py", out)               # the reuse record's rows (docs/REUSE-FROM-CREAITE.md)

    def test_one_shard_per_python_on_linux_and_two_on_macos(self):
        self.assertEqual(set(re.findall(r"shard: (\d+), shards: (\d+)", self.jobs["tests"])), {("1", "1")})
        self.assertEqual(set(re.findall(r"\{shard: (\d+), shards: (\d+)\}", self.jobs["macos"])), {("1", "2"), ("2", "2")})

    def test_macos_on_release_branches_and_by_hand_and_required_there(self):
        mac = self.jobs["macos"]
        self.assertIn(f"if: {WANTS_MACOS}\n", mac + "\n")
        self.assertRegex(mac, r"runs-on: macos-latest")
        self.assertIn('python-version: "3.x"', mac)
        self.assertNotIn("--quick", mac)
        self.assertNotIn("continue-on-error", mac)
        self.assertIn('--shard "$SHARD/$SHARDS" --max-fail 8', mac)
        self.assertIn("name: macos-latest \u00b7 Python 3.x \u00b7 shard ${{ matrix.shard }}/${{ matrix.shards }}", mac)
        self.assertIn("fail-fast: false", mac)
        self.assertIn("SHARD: ${{ matrix.shard }}", mac)
        self.assertIn("SHARDS: ${{ matrix.shards }}", mac)

    def test_chrome_is_found_as_creaite_finds_it(self):
        for job in ("tests", "macos"):
            step = self.jobs[job]
            self.assertIn("- name: Find Chrome", step, job)
            self.assertIn(ON_PATH, step, job)
            self.assertIn(MAC_APP, step, job)
            self.assertIn('test -n "$CHROME" || { echo "No Chrome on this runner"; exit 1; }', step, job)
            self.assertIn('>> "$GITHUB_ENV"', step, job)

    def test_one_tests_passed_job_green_only_if_every_required_job_is(self):
        passed = self.jobs["passed"]
        self.assertIn("name: Tests passed", passed)
        needs = re.search(r"needs: \[([^\]]*)\]", passed).group(1)
        self.assertEqual({n.strip() for n in needs.split(",")}, set(self.jobs) - {"passed"})
        self.assertIn("if: ${{ !cancelled() }}", passed)         # a run cancelled by a newer one posts no red gate
        self.assertNotIn("always()", passed)
        self.assertIn("TESTS: ${{ needs.tests.result }}", passed)
        self.assertIn("MACOS: ${{ needs.macos.result }}", passed)
        self.assertIn(f"WANT_MACOS: ${{{{ ({WANTS_MACOS}) && '1' || '' }}}}", passed)
        self.assertIn('test "$TESTS" = "success"', passed)
        self.assertIn('if [ -n "$WANT_MACOS" ]; then test "$MACOS" = "success"; else test "$MACOS" = "skipped"; fi', passed)
        for job, body in self.jobs.items():
            self.assertNotIn("continue-on-error", body, job)

    def test_untrusted_text_reaches_the_shell_only_through_the_environment(self):
        for ln in self.text.splitlines():
            if "github.event.inputs" in ln or "github.head_ref" in ln or "github.base_ref" in ln:
                self.assertRegex(ln.strip(), r"^(if:|[A-Z_]+:|run-name:|- \{?python|group:)", ln)


if __name__ == "__main__":
    unittest.main()
