"""P12-12: a plain pull request push is the cheap path: the named tests job, the affected tests, the newest Python, the 3.9 compile check

Run: python3 dev/run_tests.py test_cheap_path_p12_12   (quick tier)

Pins the as-built .github/workflows/tests.yml for a plain pull_request. The plan step and the Tests step's own bash are run for real
(a fake `gh` and a fake `python3` are shell functions defined before the script, so nothing is fetched and nothing is tested).
As built, the named job does NOT run before the shards: both only need `plan`, so they start together (GAP against "fast job first").
The full-path events are pinned elsewhere (P12-13); macOS is P12-17. Tests only, standard library only.
"""
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
    def plan(self, **env):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "out")
            open(out, "w", encoding="utf-8").close()
            fake = "gh() { printf '%s\\n' src/clark/foo.py tests/test_foo.py; }\n"
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


if __name__ == "__main__":
    unittest.main()
