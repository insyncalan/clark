"""P12-09: no --repeat / --stress loops in pre-CI or in the workflows (the loop is for a PR that fixes a flaky test only)

Run: python3 dev/run_tests.py test_pre_ci_no_loops_p12_09   (quick tier)

Pins as-built behaviour (green by design). pre-CI's six checks are run with a fake runner that records each argv, and none of them
carries --repeat or --stress. The workflow files are read as text: no run line starts a loop. The one mention in tests.yml code is
the word-skipper that recognises an option's value in the hand-typed `files` input; the one place a loop can enter CI is that
hand-typed input (documented in the tests.yml header), never a line in a file.
NOT pinned (the repo has no hook for it): "a loop is allowed only on a PR that fixes a flaky test". Tests only, standard library only.
"""
import re
import sys
import unittest
from unittest import mock

from _paths import ROOT

sys.path.insert(0, str(ROOT / "dev" / "tools"))
import pre_ci  # noqa: E402

LOOP = re.compile(r"--(?:repeat|stress)\b")


def code(text):
    return "\n".join(re.sub(r"\s+#\s.*$", "", ln) for ln in text.splitlines() if not ln.lstrip().startswith("#"))


class PreCiBuildsNoLoop(unittest.TestCase):
    def test_none_of_the_six_checks_builds_a_repeat_or_stress_argv(self):
        seen = []

        def fake_run(argv, stdin=None):
            seen.append(list(argv))
            if "--list" in argv:
                return 0, "test_alpha.py  quick\n", 0.0
            return 0, "3 tests in 0.1 s", 0.0

        run_ = pre_ci.PreCi("ticket.json", "origin/main", "HEAD")
        with mock.patch.object(pre_ci, "run", fake_run), mock.patch.object(pre_ci, "cannot_parse_39", lambda s: []), \
                mock.patch.object(pre_ci, "python39", lambda: ""):
            run_.run_all({"named_tests": ["test_alpha"]}, ["src/clark/x.py"])
        self.assertEqual([c["n"] for c in run_.checks], [1, 2, 2, 3, 4, 5, 6], "all six checks ran")
        self.assertTrue(seen, "the checks ran something")
        for argv in seen:
            self.assertFalse(any(LOOP.search(w) for w in argv), "a loop flag in: %s" % " ".join(argv))
        for c in run_.checks:
            self.assertIsNone(LOOP.search(c["command"]), "a loop flag in the recorded command of check %d" % c["n"])

    def test_the_pre_ci_source_and_smoke_list_name_no_loop_flag(self):
        self.assertIsNone(LOOP.search(code((ROOT / "dev" / "tools" / "pre_ci.py").read_text(encoding="utf-8").split('"""', 2)[2])))
        self.assertIsNone(LOOP.search(code((ROOT / "dev" / "tools" / "pre_ci_smoke.txt").read_text(encoding="utf-8"))))


class WorkflowsStartNoLoop(unittest.TestCase):
    def test_no_workflow_run_line_starts_a_repeat_or_stress_loop(self):
        files = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
        self.assertTrue(files)
        for f in files:
            for n, ln in enumerate(code(f.read_text(encoding="utf-8")).splitlines(), 1):
                if "run_tests.py" in ln or "pre_ci" in ln:
                    self.assertIsNone(LOOP.search(ln), "%s line %d starts a loop: %s" % (f.name, n, ln.strip()))

    def test_the_only_loop_word_left_in_workflow_code_is_the_option_value_skipper(self):
        found = []
        for f in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
            for ln in code(f.read_text(encoding="utf-8")).splitlines():
                if LOOP.search(ln):
                    found.append((f.name, ln.strip()))
        self.assertEqual([n for n, _ in found], ["tests.yml"], "found: %s" % found)
        self.assertRegex(found[0][1], r"^-j\|.*\|--max-fail\) PREV=")


if __name__ == "__main__":
    unittest.main()
