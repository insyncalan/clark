"""P12-12: a plain pull request push is the cheap path: the named tests job, the affected tests, the newest Python, the 3.9 compile check

Run: python3 dev/run_tests.py test_cheap_path_p12_12   (quick tier)

Pins the as-built .github/workflows/tests.yml for a plain pull_request. The plan step and the Tests step's own bash are run for real
(a fake `gh` and a fake `python3` are shell functions defined before the script, so nothing is fetched and nothing is tested).
As built, the named job does NOT run before the shards: both only need `plan`, so they start together (GAP against "fast job first").
The full-path events are pinned elsewhere (P12-13); macOS is P12-17. Tests only, standard library only.
"""
import json
import os
import re
import subprocess
import tempfile
import unittest

from _paths import ROOT

WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"


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


def jobs():
    under = block(code(WORKFLOW.read_text(encoding="utf-8")), "jobs")
    return {j: block(under, j, 2) for j in re.findall(r"^  ([\w-]+):", under, re.M)}


def run_script(job, step=None):
    """The bash of a job's `run: |` step (the one under `- name: <step>`, or the first), de-indented 10 spaces, ending at the blank line."""
    body = jobs()[job]
    if step:
        body = body[body.index("- name: " + step):]
    body = body[body.index("run: |\n") + len("run: |\n"):]
    body = body.split("\n\n")[0]
    return "\n".join(ln[10:] if ln.startswith(" " * 10) else ln for ln in body.splitlines())


def python_versions(body):
    return re.findall(r'python-version: "([^"]*)"', body)


class CheapPathTest(unittest.TestCase):
    def plan(self, files=None, gh=None, **env):
        """files: the changed files the fake gh lists (default: one source and one test file); gh: a whole fake `gh` function body instead."""
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "out")
            open(out, "w", encoding="utf-8").close()
            files = ["src/clark/foo.py", "tests/test_foo.py"] if files is None else files
            fake = gh if gh is not None else "gh() { printf '%s\\n' " + " ".join("'" + f + "'" for f in files) + "; }\n"
            base = {"PATH": os.environ["PATH"], "GITHUB_OUTPUT": out, "RUNNER_TEMP": d, "EVENT": "pull_request", "BRANCH": "feature-x",
                    "BASE_REF": "main", "LABELS": "", "MACOS_INPUT": "", "SCHEDULE": "", "REPO": "x/y", "PR_NUMBER": "7",
                    "GH_TOKEN": "", "FILES_INPUT": ""}
            base.update(env)
            r = subprocess.run(["bash", "-c", fake + run_script("plan")], env=base,
                               capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(out, encoding="utf-8") as f:
                return dict(ln.split("=", 1) for ln in f.read().splitlines() if "=" in ln)

    def tests_command(self, **env):
        """What the Tests step of the `tests` job would run: its bash, with python3 replaced by a function that prints its arguments."""
        base = {"PATH": os.environ["PATH"], "FILES": "", "JOBS": "4", "SHARD": "1", "SHARDS": "3", "FULL": "", "EVENT": "pull_request",
                "BASE": "main"}
        base.update(env)
        r = subprocess.run(["bash", "-c", 'python3() { echo "RUN $*"; }\n' + run_script("tests", "Tests")], env=base,
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def test_a_plain_pull_request_plan_is_three_shards_and_no_second_python_and_no_macos(self):
        out = self.plan()
        self.assertEqual((out["full"], out["count"], out["shards"]), ("", "3", "[1,2,3]"))
        self.assertEqual((out["py39"], out["macos"], out["smoke"], out["advisory"]), ("", "", "", ""))

    def test_a_plain_pull_request_runs_the_affected_tests_only_not_the_full_suite(self):
        self.assertEqual(self.tests_command(), "RUN dev/run_tests.py -j 4 --changed origin/main --shard 1/3 --max-fail 8")
        self.assertEqual(self.tests_command(BASE="release-1", SHARD="3"), "RUN dev/run_tests.py -j 4 --changed origin/release-1 --shard 3/3 --max-fail 8")

    def test_the_full_path_has_no_changed_scope(self):
        self.assertEqual(self.tests_command(FULL="1", SHARDS="10", SHARD="2"), "RUN dev/run_tests.py -j 4 --shard 2/10 --max-fail 8")
        self.assertEqual(self.tests_command(EVENT="merge_group", FULL="1"), "RUN dev/run_tests.py -j 4 --shard 1/3 --max-fail 8")

    def test_the_named_tests_job_is_pull_request_only_and_starts_with_the_shards_as_built(self):
        j = jobs()
        self.assertEqual(re.findall(r"^    needs: (.*)$", j["named"], re.M), ["plan"])
        self.assertEqual(re.findall(r"^    needs: (.*)$", j["tests"], re.M), ["plan"])      # GAP: no `needs: named`, the fast job is not first
        self.assertEqual(re.findall(r"^    if: (.*)$", j["named"], re.M), ["${{ github.event_name == 'pull_request' }}"])
        self.assertNotIn("named", re.findall(r"needs: (.*)", j["tests"])[0])
        self.assertEqual(re.findall(r"run_tests\.py (.*)", j["named"]), ['-j 4 --max-fail 8 "${NAMED[@]}"'])

    def test_every_shard_job_of_a_pull_request_has_one_python_the_newest(self):
        j = jobs()
        self.assertEqual(python_versions(j["tests"]), ["3.x"])
        self.assertEqual(python_versions(j["named"]), ["3.x"])
        matrix = j["tests"][j["tests"].index("      matrix:"):j["tests"].index("    steps:")]
        self.assertEqual(re.findall(r"^        ([\w-]+):", matrix, re.M), ["shard"])

    def test_the_3_9_compile_check_is_a_compile_step_with_no_tests_and_no_3_9_shards_on_a_pull_request(self):
        j = jobs()
        c = j["py39-compile"]
        self.assertEqual(python_versions(c), ["3.9"])
        self.assertEqual(re.findall(r"^        run: (.*)$", c, re.M), ["python3 dev/tools/pre_ci.py --compile39"])
        self.assertEqual(re.findall(r"^    if: (.*)$", c, re.M), ["${{ github.event_name == 'pull_request' }}"])
        self.assertNotIn("run_tests", c)
        self.assertNotIn("matrix", c)
        # the only job with 3.9 shards is the full-path one, and it needs full AND py39, which a plain pull request has neither of
        three_nine = sorted(k for k, v in j.items() if "3.9" in python_versions(v))
        self.assertEqual(three_nine, ["py39-compile", "tests-py39"])
        self.assertEqual(re.findall(r"^    if: (.*)$", j["tests-py39"], re.M),
                         ["${{ needs.plan.outputs.full == '1' && needs.plan.outputs.py39 == '1' }}"])
        self.assertEqual(self.plan()["py39"], "")

    # ---- plan step: the file list decides the path ----
    def test_a_changed_workflow_file_is_the_full_path_and_a_changed_stylesheet_is_ten_shards_not_full(self):
        out = self.plan(files=[".github/workflows/x.yml"])
        self.assertEqual((out["full"], out["count"]), ("1", "10"))
        out = self.plan(files=["style.css"])
        self.assertEqual((out["full"], out["shards"], out["count"]), ("", "[1,2,3,4,5,6,7,8,9,10]", "10"))
        out = self.plan(files=["src/clark/page/x.html"])
        self.assertEqual((out["full"], out["shards"], out["count"]), ("", "[1,2,3,4,5,6,7,8,9,10]", "10"))
        for f in ("src/clark/brand/x.svg", "src/clark/templates/x.html"):
            self.assertEqual((self.plan(files=[f])["full"], self.plan(files=[f])["count"]), ("", "10"), f)

    def test_each_guarded_store_file_is_the_full_path(self):
        for f in ("src/clark/store.py", "src/clark/schema.sql", "src/clark/history.py", "src/clark/server.py"):
            out = self.plan(files=[f])
            self.assertEqual((out["full"], out["count"]), ("1", "10"), f)
        self.assertEqual(self.plan(files=["src/clark/foo.py"])["full"], "")

    def test_eight_changed_test_files_are_ten_shards_and_seven_are_three(self):
        seven = ["tests/test_%d.py" % i for i in range(7)]
        out = self.plan(files=seven)
        self.assertEqual((out["full"], out["count"], out["shards"]), ("", "3", "[1,2,3]"))
        out = self.plan(files=seven + ["tests/test_7.py"])
        self.assertEqual((out["full"], out["count"], out["shards"]), ("", "10", "[1,2,3,4,5,6,7,8,9,10]"))
        # files that are not tests/test_*.py are not counted
        self.assertEqual(self.plan(files=seven + ["tests/helper.py"])["count"], "3")

    def test_the_file_list_is_read_only_for_a_pull_request_that_is_not_already_full(self):
        # a push event never calls gh: a gh that would answer full is ignored
        out = self.plan(EVENT="push", files=[".github/workflows/x.yml"])
        self.assertEqual((out["full"], out["count"]), ("", "3"))

    def test_a_list_of_3000_files_is_the_full_path_and_2999_is_not(self):
        out = self.plan(gh='gh() { for i in $(seq 1 3000); do echo "docs/f$i.md"; done; }\n')
        self.assertEqual((out["full"], out["count"]), ("1", "10"))
        out = self.plan(gh='gh() { for i in $(seq 1 2999); do echo "docs/f$i.md"; done; }\n')
        self.assertEqual((out["full"], out["count"]), ("", "3"))

    def test_a_failed_file_list_read_is_the_full_path_and_never_macos(self):
        out = self.plan(gh="gh() { return 1; }\n")
        self.assertEqual((out["full"], out["macos"], out["count"]), ("1", "", "10"))

    def test_python_3_9_runs_for_a_hand_start_a_release_base_and_a_mac_specific_file_not_for_a_plain_pull_request(self):
        self.assertEqual(self.plan()["py39"], "")
        self.assertEqual(self.plan(EVENT="workflow_dispatch")["py39"], "1")
        self.assertEqual(self.plan(BASE_REF="release-1")["py39"], "1")
        out = self.plan(files=["src/clark/updates.py"])
        self.assertEqual((out["py39"], out["full"]), ("1", "1"))

    def test_the_plan_outputs_of_a_plain_pull_request_are_all_pinned(self):
        out = self.plan()
        self.assertEqual(out["cut"], "")
        self.assertEqual((out["shards39"], out["count39"]), ("[1,2,3]", "3"))
        mac = json.loads(out["macmatrix"])
        self.assertEqual(len(mac), 9)
        self.assertEqual(mac, [{"shard": i, "shards": 9} for i in range(1, 10)])

    # ---- Tests step ----
    def test_the_tests_step_env_and_matrix_come_from_the_plan_outputs(self):
        t = jobs()["tests"]
        env = block(t[t.index("- name: Tests"):], "env", 8)
        for line in ("SHARDS: ${{ needs.plan.outputs.count }}", "FULL: ${{ needs.plan.outputs.full }}", "BASE: ${{ github.base_ref }}",
                     "JOBS: 4", "SHARD: ${{ matrix.shard }}", "EVENT: ${{ github.event_name }}"):
            self.assertIn("          " + line, env.splitlines())
        self.assertIn("        shard: ${{ fromJSON(needs.plan.outputs.shards) }}", t.splitlines())

    def test_named_files_are_appended_after_max_fail(self):
        self.assertTrue(self.tests_command(FILES="test_a.py").endswith("--max-fail 8 test_a.py"))

    def test_a_push_has_no_changed_scope_and_the_nightly_adds_the_quarantined_files(self):
        self.assertNotIn("--changed", self.tests_command(EVENT="push", FULL=""))
        self.assertIn("--with-quarantined", self.tests_command(EVENT="schedule", FULL="1"))
        self.assertNotIn("--with-quarantined", self.tests_command())

    def test_the_tests_job_fetches_the_history_of_a_pull_request_and_has_no_job_level_if(self):
        j = jobs()
        t = j["tests"]
        self.assertIn("fetch-depth: ${{ github.event_name == 'pull_request' && '0' || '1' }}", t)
        self.assertIn("      fail-fast: false", t.splitlines())
        self.assertEqual(re.findall(r"^    timeout-minutes: (.*)$", t, re.M), ["90"])
        self.assertIn("python3 dev/tools/build_page.py", t)
        self.assertEqual(re.findall(r"^    if: ", t, re.M), [])      # the shards run on every event the plan runs on

    def test_the_named_job_fetches_the_whole_history_and_builds_the_pages(self):
        n = jobs()["named"]
        self.assertIn("fetch-depth: 0", n)
        self.assertIn("python3 dev/tools/build_page.py", n)

    def test_the_3_9_compile_job_needs_only_the_plan(self):
        self.assertEqual(re.findall(r"^    needs: (.*)$", jobs()["py39-compile"], re.M), ["plan"])


if __name__ == "__main__":
    unittest.main()
