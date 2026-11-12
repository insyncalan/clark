"""#70: the CI workflow (.github/workflows/tests.yml) keeps the rules of the team repo

Run: python3 dev/run_tests.py test_workflow   (quick tier)

Read as text (standard library only, no YAML library): the triggers (pull_request including labeled/unlabeled), read-only
permissions, no secrets and never `pull_request_target`, Ubuntu 24.04. A `plan` job decides the path: an ordinary pull
request is the cheap path (the newest Python only, `--push origin/<base>`); a push to main, a release branch, the `full-ci`
label and a hand-started run are the full matrix (3.x every file, 3.9 on the quick tier, macOS). One "Tests passed" job is
green only if every required job is, accepts a skipped job only when the cheap path intended it, and posts nothing for a
cancelled run.
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
        self.assertRegex(block(on, "pull_request", 2), r"types: \[opened, synchronize, reopened, labeled, unlabeled\]")
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

    def test_the_plan_matches_the_release_branch_names_the_docs_use(self):
        # docs/handoff/how-to-run-v0.1.md names the release line v0.1-release; the release process names release-X.Y.Z.
        docs = (ROOT / "docs" / "handoff" / "how-to-run-v0.1.md").read_text(encoding="utf-8")
        self.assertIn("v0.1-release", docs)
        plan = self.jobs["plan"]
        self.assertIn("release-*|v*-release*) FULL=1; MACOS=1 ;;", plan)
        self.assertIn("BRANCH: ${{ github.head_ref || github.ref_name }}", plan)
        self.assertIn("*,full-ci,*) FULL=1; MACOS=1 ;;", plan)
        self.assertIn("LABELS: ${{ join(github.event.pull_request.labels.*.name, ',') }}", plan)
        self.assertIn("push) FULL=1 ;;", plan)               # a push to main: full Ubuntu, NO macOS
        self.assertNotIn("push) FULL=1; MACOS=1", plan)
        self.assertIn('workflow_dispatch) FULL=1; if [ "$MACOS_INPUT" = "true" ]; then MACOS=1; fi ;;', plan)
        self.assertNotIn("actions/checkout", plan)               # seconds, nothing from the pull request runs here

    def test_the_plan_sets_full_for_a_guarded_file_and_fails_safe(self):
        plan = self.jobs["plan"]
        self.assertIn("pull-requests: read", plan)
        self.assertNotIn("actions/checkout", plan)
        self.assertNotIn("eval ", plan)
        self.assertIn("GH_TOKEN: ${{ github.token }}", plan)
        self.assertIn("PR_NUMBER: ${{ github.event.pull_request.number }}", plan)
        # #593: a file renamed away from a guarded path is seen too: both the new name and the old one (previous_filename) are listed
        self.assertIn('gh api "repos/$REPO/pulls/$PR_NUMBER/files" --paginate --jq \'.[] | .filename, (.previous_filename // empty)\'', plan)
        for guarded in ("src/clark/store.py", "src/clark/server.py", "src/clark/publish.py", "src/clark/secret_screen.py",
                        "src/clark/updates.py", "src/clark/platform.py", "src/clark/schema.sql", "src/clark/history.py",
                        ".github/*"):
            self.assertIn(guarded, plan)
        # a failed API call is full, not cheap
        self.assertRegex(plan, r"else\s+echo \"could not list[^\n]*\n\s+FULL=1; MACOS=1")
        # the filenames are text from the pull request: only through the shell variable, never in a ${{ }} expression
        self.assertNotRegex(plan, r"\$\{\{[^}]*(filename|files)")

    def test_never_pull_request_target_no_secrets_read_only(self):
        self.assertNotIn("pull_request_target", self.text)          # the header comment says "never"
        self.assertNotIn("secrets.", self.text)
        self.assertNotIn("secrets:", self.text)
        self.assertEqual(block(self.text, "permissions").split(), ["contents:", "read"])
        self.assertNotRegex(self.text, r"\bwrite\b")
        for job, body in self.jobs.items():
            if job != "plan":
                self.assertNotIn("permissions:", body, f"{job} widens the permissions")
        # only the plan job widens, by one read scope (the changed-files API call); every other scope stays absent
        self.assertEqual(code(block(self.jobs["plan"], "permissions", 4)).split(), ["contents:", "read", "pull-requests:", "read"])
        self.assertEqual(self.text.count("pull-requests: read"), 1)
        self.assertEqual(self.text.count("persist-credentials: false"), self.text.count("actions/checkout@"))

    def test_a_newer_pull_request_run_cancels_the_older_and_a_main_or_release_run_never_is(self):
        concurrency = block(self.text, "concurrency")
        self.assertIn("group: tests-${{ github.event_name == 'workflow_dispatch' && github.run_id || github.event.pull_request.number || github.ref }}", concurrency)
        self.assertIn("cancel-in-progress: ${{ github.event_name == 'pull_request' }}", concurrency)
        self.assertNotIn("cancel-in-progress: true", concurrency)

    def test_ubuntu_24_04_newest_python_and_3_9_on_the_quick_tier(self):
        tests, py39 = self.jobs["tests"], self.jobs["tests-py39"]
        for body in (tests, py39, self.jobs["plan"], self.jobs["passed"]):
            self.assertRegex(body, r"runs-on: ubuntu-24\.04\b")
        self.assertNotIn("ubuntu-latest", self.text)
        self.assertIn('python-version: "3.x"', tests)
        self.assertIn('python-version: "3.9"', py39)
        self.assertIn("name: ubuntu-24.04 \u00b7 Python 3.x \u00b7 shard ${{ matrix.shard }}/${{ needs.plan.outputs.count }}", tests)
        self.assertIn("name: ubuntu-24.04 \u00b7 Python 3.9 \u00b7 shard ${{ matrix.shard }}/${{ needs.plan.outputs.count39 }}", py39)
        self.assertIn("SHARDS39='[1,2,3]'; COUNT39=3", self.jobs["plan"])
        self.assertIn("shard: ${{ fromJSON(needs.plan.outputs.shards39) }}", py39)
        # six shards on both paths (the cheap path can reach every file, and as one shard it hit the 30-minute cap): the plan decides, the job reads it
        self.assertIn("shard: ${{ fromJSON(needs.plan.outputs.shards) }}", tests)
        self.assertIn("SHARD: ${{ matrix.shard }}", tests)
        self.assertIn("SHARDS: ${{ needs.plan.outputs.count }}", tests)
        self.assertIn("SHARDS='[1,2,3,4,5,6]'; COUNT=6", self.jobs["plan"])
        self.assertNotIn("SHARDS='[1]'", self.jobs["plan"])
        self.assertIn("fail-fast: false", tests)
        self.assertIn('--quick --shard "$SHARD/$SHARDS" --max-fail 8 $FILES', py39)
        self.assertIn("SHARDS: ${{ needs.plan.outputs.count39 }}", py39)

    def test_an_ordinary_pull_request_is_the_cheap_path_and_the_full_suite_runs_elsewhere(self):
        tests = self.jobs["tests"]
        self.assertIn("needs: plan", tests)
        self.assertIn("FULL: ${{ needs.plan.outputs.full }}", tests)
        self.assertIn('if [ "$EVENT" = "pull_request" ] && [ -z "$FULL" ]; then SCOPE="--push origin/$BASE"; fi', tests)
        self.assertIn('python3 dev/run_tests.py -j "$JOBS" $SCOPE --shard "$SHARD/$SHARDS" --max-fail 8 $FILES', tests)
        # the second Python and macOS exist only on the full path
        self.assertIn("if: ${{ needs.plan.outputs.full == '1' && needs.plan.outputs.py39 == '1' }}", self.jobs["tests-py39"])
        self.assertIn("if: ${{ needs.plan.outputs.macos == '1' }}", self.jobs["macos"])
        # the py39 output must be declared by the plan job and written by its step: without either, the job's `if` is never true,
        # WANT_PY39 is always empty and Python 3.9 would silently never run while the gate stays green
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("py39: ${{ steps.plan.outputs.py39 }}", text)
        self.assertIn('echo "py39=$PY39" >> "$GITHUB_OUTPUT"', text)

    def test_a_pull_request_fetches_the_whole_history_so_the_base_is_there(self):
        self.assertIn("fetch-depth: ${{ github.event_name == 'pull_request' && '0' || '1' }}", self.jobs["tests"])

    def test_the_branch_and_base_reach_the_shell_only_through_env(self):
        for job, body in self.jobs.items():
            for step in re.split(r"\n      - ", body):
                m = re.search(r"\n        run: (.*?)(?=\n        \w[\w-]*:|\Z)", step, re.S)
                if m:
                    self.assertNotIn("${{", m.group(1), f"{job}: an expression inside a run script")
        self.assertIn("BASE: ${{ github.base_ref }}", self.jobs["tests"])

    def test_the_quick_tier_holds_the_no_real_names_and_reuse_record_tests(self):
        # No paths-ignore, and 3.9 runs only the quick tier: so a documents-only change still reaches these two on every run.
        out = subprocess.run([sys.executable, str(ROOT / "dev" / "run_tests.py"), "--quick", "--list"], cwd=ROOT,
                             capture_output=True, text=True, timeout=120).stdout.split()
        self.assertIn("test_no_real_names.py", out)
        self.assertIn("test_app_files.py", out)               # the reuse record's rows (docs/REUSE-FROM-CREAITE.md)

    def test_three_shards_on_macos_and_the_macos_job_is_required_when_it_runs(self):
        mac = self.jobs["macos"]
        self.assertEqual(set(re.findall(r"\{shard: (\d+), shards: (\d+)\}", mac)), {("1", "3"), ("2", "3"), ("3", "3")})
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
        for job in ("tests", "tests-py39", "macos"):
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
        for line in ("PLAN: ${{ needs.plan.result }}", "TESTS: ${{ needs.tests.result }}", "PY39: ${{ needs.tests-py39.result }}",
                     "MACOS: ${{ needs.macos.result }}", "WANT_PY39: ${{ needs.plan.outputs.py39 }}",
                     "WANT_MACOS: ${{ needs.plan.outputs.macos }}"):
            self.assertIn(line, passed)
        self.assertIn('test "$PLAN" = "success"', passed)
        self.assertIn('test "$TESTS" = "success"', passed)
        self.assertIn('if [ -n "$WANT_PY39" ]; then test "$PY39" = "success"; else test "$PY39" = "skipped"; fi', passed)
        self.assertIn('if [ -n "$WANT_MACOS" ]; then test "$MACOS" = "success"; else test "$MACOS" = "skipped"; fi', passed)
        for job, body in self.jobs.items():
            self.assertNotIn("continue-on-error", body, job)

    MAC_FILES = ("platform.py", "updates.py", "clark.command", "launch.py", "doctor.py", "release_files.py", "package.py", "__main__.py")

    def test_macos_runs_for_mac_specific_files_not_for_every_guarded_file(self):
        """The owner, 04-11-2026: macOS runs at the release gate, not on every push of a guarded pull request. A guarded file is the full Ubuntu
        matrix (FULL=1) and no macOS; only the Mac-specific code (platform, updates, the launcher and the package files) also asks for macOS.
        Each pattern is judged on its own: a Mac file must be in a MACOS=1 line, and no other pattern may share one."""
        plan = self.jobs["plan"]
        seen = {}
        for ln in plan.splitlines():
            m = re.match(r"^\s*([A-Za-z0-9_./*|-]+)\)\s+(FULL=1[^#]*)", ln)
            if not m or "/" not in m.group(1):
                continue
            macos = "MACOS=1" in m.group(2)
            for pattern in m.group(1).split("|"):
                is_mac = pattern.rsplit("/", 1)[-1] in self.MAC_FILES and pattern != "clark/__init__.py"
                self.assertEqual(macos, is_mac, f"{pattern}: macOS only for a Mac-specific file, and a Mac file only on a MACOS=1 line")
                seen[pattern.rsplit("/", 1)[-1]] = macos
        for name in self.MAC_FILES:
            self.assertTrue(seen.get(name), f"{name} must be in the plan's Mac-specific list")
        self.assertIn(".github/*) FULL=1 ;;", plan)

    def test_a_pull_request_that_targets_a_release_branch_gets_macos_too(self):
        plan = self.jobs["plan"]
        self.assertIn("BASE_REF: ${{ github.base_ref }}", plan)
        self.assertRegex(plan, r'case "\$BASE_REF" in\s+release-\*\|v\*-release\*\) FULL=1; MACOS=1 ;;')

    def test_the_macos_job_runs_two_files_at_a_time(self):
        """Three Chrome tests at once on the 3-vCPU, 7 GB macOS runner starve each other: that was the flake."""
        mac = self.jobs["macos"]
        self.assertIn("JOBS: 2", mac)
        self.assertNotIn("JOBS: 3", mac)
        self.assertIn('python3 dev/run_tests.py -j "$JOBS" --shard "$SHARD/$SHARDS" --max-fail 8 $FILES', mac)

    def test_the_guarded_list_in_the_plan_job_matches_run_tests_guarded(self):
        """The plan job's case patterns are dev/run_tests.py GUARDED (source files) plus the documented extras and `.github/*`."""
        text = WORKFLOW.read_text(encoding="utf-8")
        plan = block(code(text), "plan", 2)
        listed = set()
        for ln in plan.splitlines():
            m = re.match(r"^\s*([A-Za-z0-9_./*|-]+)\)\s", ln)
            if m and "/" in m.group(1):
                listed.update(m.group(1).split("|"))
        src = (ROOT / "dev" / "run_tests.py").read_text(encoding="utf-8")
        guarded = set(re.findall(r'"([^"]+)"', re.search(r"^GUARDED = \((.*?)\)", src, re.S | re.M).group(1)))
        # .github/* covers the workflow files, so a GUARDED entry under .github/ is handled by that pattern
        sources = {g for g in guarded if not g.startswith(".github/")}
        extras = {"src/clark/publish.py", "src/clark/publish_flow.py", "src/clark/secret_screen.py",
                  "src/clark/platform.py", "src/clark/updates.py", ".github/*",
                  "clark.command", "clark/__main__.py", "clark/launch.py", "clark/doctor.py", "src/clark/launch.py", "src/clark/doctor.py",
                  "src/clark/release_files.py", "dev/tools/package.py",
                  # the WIDE patterns (a stylesheet or the page reaches nearly every test file: six Ubuntu shards, not three), not guarded files
                  "*.css", "src/clark/brand/*", "src/clark/page/*", "src/clark/templates/*",
                  # a changed test file is only counted: eight or more make the pull request WIDE
                  "tests/test_*.py"}
        self.assertTrue(sources, "no source file found in run_tests.GUARDED")
        self.assertIn(".github/*", listed, "the plan job must treat .github/* (the workflows) as guarded")
        missing = sorted(sources - listed)
        self.assertFalse(missing, f"in run_tests.GUARDED but missing from the workflow's plan list: {missing}")
        extra = sorted(listed - sources - extras)
        self.assertFalse(extra, f"in the workflow's plan list but not in GUARDED or the documented extras: {extra}")
        gone = sorted(extras - listed)
        self.assertFalse(gone, f"documented extras missing from the workflow's plan list: {gone}")

    def test_untrusted_text_reaches_the_shell_only_through_the_environment(self):
        for ln in self.text.splitlines():
            if "github.event.inputs" in ln or "github.head_ref" in ln or "github.base_ref" in ln:
                self.assertRegex(ln.strip(), r"^(if:|[A-Z_]+:|run-name:|group:|cancel-in-progress:)", ln)


class WideByTestFiles(unittest.TestCase):
    """A pull request that changes 8 or more tests/test_*.py files runs six Ubuntu shards, not three (PR 1339 timed out three times at
    30 minutes on three). The plan step's own lines are run in bash on a made-up file list."""

    def _wide(self, changed):
        text = WORKFLOW.read_text(encoding="utf-8")
        a = text.index("while IFS= read -r F; do")
        b = text.index('if [ "$NTESTS" -ge 8 ]; then WIDE=1; fi') + len('if [ "$NTESTS" -ge 8 ]; then WIDE=1; fi')
        script = 'FULL=""; MACOS=""; WIDE=""; NTESTS=0\n' + text[a:b].replace("\n              ", "\n") + '\necho "WIDE=$WIDE FULL=$FULL"\n'
        out = subprocess.run(["bash", "-c", script], input="", capture_output=True, text=True, check=True,
                             env={"PATH": "/usr/bin:/bin", "CHANGED": changed}).stdout
        return out.strip()

    def test_eight_test_files_are_wide_and_seven_are_not(self):
        eight = "\n".join(f"tests/test_x{i}.py" for i in range(8))
        seven = "\n".join(f"tests/test_x{i}.py" for i in range(7))
        self.assertEqual(self._wide(eight), "WIDE=1 FULL=")
        self.assertEqual(self._wide(seven), "WIDE= FULL=")

    def test_other_files_do_not_count_and_the_old_rules_still_hold(self):
        many = "\n".join(f"docs/n{i}.md" for i in range(20))
        self.assertEqual(self._wide(many), "WIDE= FULL=")
        self.assertEqual(self._wide("src/clark/page/x.jsx"), "WIDE=1 FULL=")
        self.assertEqual(self._wide("src/clark/server.py"), "WIDE= FULL=1")
        mixed = "\n".join(f"tests/helper{i}.py" for i in range(9))      # not test_*.py
        self.assertEqual(self._wide(mixed), "WIDE= FULL=")


if __name__ == "__main__":
    unittest.main()
