"""P12-15: the nightly runs in its own concurrency group that nothing cancels, and its last job refreshes shard_times.txt.

Run: python3 dev/run_tests.py test_nightly_group_p12_15   (quick tier)

tests/test_workflow.py pins the group and cancel lines with assertIn on the line text, so a second `group:` or `cancel-in-progress:` key
(the last one wins in YAML) passes there. Here the concurrency block is parsed into keys (each exactly once) and the two expressions are
EVALUATED for every event: the nightly's group is unique per run and shared with no other event, and nothing cancels a nightly. The refresh
job is reachable on `schedule` only, runs shard_refresh.py with its default output, and uploads dev/tools/shard_times.txt. Standard library only.
"""
import re
import unittest

from _paths import ROOT

WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"
REFRESH = ROOT / "dev" / "tools" / "shard_refresh.py"


def code(text):
    """The workflow without its comments (a rule written in a comment doesn't count)."""
    return "\n".join(re.sub(r"\s+#\s.*$", "", ln) for ln in text.splitlines() if not ln.lstrip().startswith("#"))


def top_block(text, key):
    """The lines under the top-level `key:` (without the key line), up to the next top-level key."""
    out, inside = [], False
    for ln in text.splitlines():
        if inside:
            if ln.strip() and not ln.startswith(" "):
                break
            out.append(ln)
        elif ln.startswith(key + ":"):
            inside = True
            if ln.split(":", 1)[1].strip():
                out.append(ln)
    return out


def keys_of(lines):
    """[(key, value)] of the `  key: value` lines, in file order, duplicates kept."""
    return [m.groups() for m in (re.match(r"^  ([\w-]+):\s*(.*)$", ln) for ln in lines) if m]


def job_text(text, job):
    out, inside = [], False
    under = False
    for ln in text.splitlines():
        if ln.startswith("jobs:"):
            under = True
        elif under and re.match(r"^  ([\w-]+):", ln):
            inside = ln.startswith(f"  {job}:")
        if inside:
            out.append(ln)
    return "\n".join(out)


def evaluate(expr, event_name, run_id=1, action="", pr=None, ref="refs/heads/main"):
    """An expression of the form ${{ a && b || c }} with GitHub's rules (&& and || return an operand), for the one workflow's own syntax."""
    m = re.fullmatch(r"([\w-]*)\$\{\{ (.*) \}\}", expr.strip())
    assert m, expr
    prefix, body = m.groups()
    assert re.fullmatch(r"[\w .'!=&|(),{}-]+", body), body
    body = body.replace("&&", " and ").replace("||", " or ")
    body = re.sub(r"github\.(\w+(?:\.\w+)*)", lambda g: "G_" + g.group(1).replace(".", "_"), body)
    env = {"G_event_name": event_name, "G_run_id": run_id, "G_ref": ref, "G_event_action": action or None,
           "G_event_pull_request_number": pr,
           "true": True, "false": False, "format": lambda f, *a: f.format(*a)}
    return prefix + str(eval(body, {"__builtins__": {}}, env)) if prefix else eval(body, {"__builtins__": {}}, env)


class NightlyGroupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = code(WORKFLOW.read_text(encoding="utf-8"))
        cls.keys = keys_of(top_block(cls.text, "concurrency"))
        cls.group = dict(cls.keys)["group"]
        cls.cancel = dict(cls.keys)["cancel-in-progress"]

    def groups(self):
        """Every event's group, with the nightly's two run ids first."""
        g = lambda **kw: evaluate(self.group, **kw)
        return {"schedule1": g(event_name="schedule", run_id=1), "schedule2": g(event_name="schedule", run_id=2),
                "dispatch": g(event_name="workflow_dispatch", run_id=1), "pr": g(event_name="pull_request", pr=7, action="opened"),
                "merge_group": g(event_name="merge_group", ref="refs/heads/gh-readonly-queue/main/x"),
                "push": g(event_name="push", ref="refs/heads/main")}

    def test_the_concurrency_block_has_exactly_one_group_and_one_cancel_key(self):
        self.assertEqual([k for k, _ in self.keys], ["group", "cancel-in-progress"], "a repeated key: the last one wins in YAML")
        self.assertEqual(self.text.count("\nconcurrency:"), 1)
        for job, body in ((j, job_text(self.text, j)) for j in ("plan", "tests", "shard-times")):
            self.assertNotIn("concurrency:", body, f"{job} has its own concurrency")

    def test_the_nightly_group_is_its_own_and_unique_per_run(self):
        g = self.groups()
        self.assertEqual(g["schedule1"], "tests-nightly-1")
        self.assertEqual(g["schedule2"], "tests-nightly-2")
        others = {k: v for k, v in g.items() if not k.startswith("schedule")}
        self.assertNotIn(g["schedule1"], others.values())
        self.assertNotIn(g["schedule2"], others.values())
        self.assertEqual(g["pr"], "tests-7")          # a pull request keeps its own group, as before
        self.assertEqual(g["dispatch"], "tests-1")

    def test_nothing_cancels_the_nightly_and_only_a_pull_request_cancels(self):
        c = lambda **kw: evaluate(self.cancel, **kw)
        self.assertIs(c(event_name="schedule"), False)
        self.assertIs(c(event_name="workflow_dispatch"), False)
        self.assertIs(c(event_name="merge_group"), False)
        self.assertIs(c(event_name="push"), False)
        for action in ("opened", "synchronize", "reopened"):
            self.assertIs(c(event_name="pull_request", action=action), True, action)
        for action in ("labeled", "unlabeled"):
            self.assertIs(c(event_name="pull_request", action=action), False, action)
        self.assertIs(c(event_name="schedule", action="synchronize"), False)

    def test_only_the_schedule_reaches_the_refresh_job_and_it_writes_shard_times(self):
        job = job_text(self.text, "shard-times")
        self.assertTrue(job, "the shard-times job is gone")
        self.assertIn("\n    if: ${{ !cancelled() && github.event_name == 'schedule' }}\n", job)
        self.assertEqual(len(re.findall(r"^    if:", job, re.M)), 1)
        self.assertIn("\n    needs: tests\n", job)
        runs = re.findall(r"^\s+run: (.*)$", job, re.M)
        self.assertEqual(runs, ['python3 dev/tools/shard_refresh.py --durations "$DURATIONS"'])      # no --out: the script's default
        self.assertRegex(REFRESH.read_text(encoding="utf-8"), r'add_argument\("--out", default=str\(ROOT / "dev" / "tools" / "shard_times\.txt"\)\)')
        self.assertEqual(re.findall(r"^\s+path: (.*)$", job, re.M)[-1], "dev/tools/shard_times.txt")
        self.assertIn("name: shard-times", job)

    def test_no_other_job_refreshes_or_uploads_shard_times(self):
        for name in re.findall(r"^  ([\w-]+):", "\n".join(top_block(self.text, "jobs")), re.M):
            if name == "shard-times":
                continue
            body = job_text(self.text, name)
            self.assertNotIn("shard_refresh.py", body, name)
            self.assertNotIn("name: shard-times", body, name)

    def test_the_evaluator_tells_a_shared_or_cancelling_expression_apart(self):
        shared = "${{ github.event_name == 'workflow_dispatch' && github.run_id || github.event.pull_request.number || github.ref }}"
        self.assertEqual(evaluate(shared, "schedule", 1), "refs/heads/main")
        self.assertEqual(evaluate(shared, "schedule", 2), "refs/heads/main")
        self.assertIs(evaluate("${{ github.event_name == 'pull_request' }}", "pull_request"), True)


if __name__ == "__main__":
    unittest.main()
