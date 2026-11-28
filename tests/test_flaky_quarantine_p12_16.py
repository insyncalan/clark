"""P12-16 boundaries of the flake quarantine (dev/tools/flaky_quarantine.py, the runner's part in dev/run_tests.py): the pins the
first test file leaves open. A test file that was a FLAKE in two different runs is listed with one ticket (board Release
"Tech Debt - Priority", ledger release none); one run, a defect, or two different files are not.

LIMIT: the tool counts whole test files, not single test functions; it never takes a file off the list (a pull request does).
Run: python3 dev/run_tests.py test_flaky_quarantine_p12_16
"""
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT

import flaky_quarantine as fq


def doc(flakes=(), defects=()):
    return {"complete": True, "failed": bool(defects), "files": 10, "not_run": 0,
            "counts": {"DEFECT": len(defects), "FLAKE": len(flakes), "SIZING": 0},
            "defects": sorted(defects), "flakes": {f: 1 for f in flakes}, "sizing": [], "failed_first": []}


class FlakyQuarantineBoundaryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        (self.d / "results").mkdir()
        self.list = self.d / "quarantine.txt"
        self.tickets = self.d / "tickets.json"

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, docs, listed="# list\n"):
        for name, body in docs.items():
            (self.d / "results" / name).write_text(json.dumps(body), encoding="utf-8")
        self.list.write_text(listed, encoding="utf-8")

    def run_main(self, *more):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = fq.main(["--results", str(self.d / "results"), "--list", str(self.list),
                            "--tickets", str(self.tickets), *more])
        return code, buf.getvalue()

    def listed(self):
        return fq.read_list(self.list.read_text(encoding="utf-8"))

    def filed(self):
        return json.loads(self.tickets.read_text(encoding="utf-8"))

    def test_the_threshold_is_two_different_runs_and_the_label_is_pinned(self):
        self.assertEqual(fq.AT, 2)
        self.assertEqual(fq.RELEASE, "Tech Debt - Priority")
        self.assertEqual(fq.to_quarantine({"a.py": ["1"]}, set()), {})
        self.assertEqual(fq.to_quarantine({"a.py": ["1", "2"]}, set()), {"a.py": ["1", "2"]})
        self.assertEqual(fq.to_quarantine({"a.py": ["1", "2", "3"]}, set()), {"a.py": ["1", "2", "3"]})
        self.assertEqual(fq.to_quarantine({"a.py": ["1", "2"]}, {"a.py"}), {})

    def test_the_ticket_names_the_file_the_runs_and_the_tech_debt_release(self):
        self.put({"100__s1.json": doc(["test_a.py"]), "101__s2.json": doc(["test_a.py"])})
        self.run_main("--write")
        self.assertEqual(self.filed(), [{
            "file": "test_a.py", "runs": ["100", "101"], "release": "Tech Debt - Priority", "ledger_release": "none",
            "title": "Flaky test quarantined: test_a.py",
            "body": "test_a.py failed and then passed alone in 2 runs (100, 101), so it is on dev/tools/quarantine.txt and no longer "
                    "runs on a pull request. The nightly still runs it. Fix the test or the code, show it steady "
                    "(dev/run_tests.py --repeat), and take its line off the list in the same pull request."}])

    def test_two_flaky_files_get_one_ticket_each_and_only_the_file_with_two_runs_is_listed(self):
        self.put({"100__s1.json": doc(["test_a.py", "test_b.py"]), "101__s1.json": doc(["test_a.py"]),
                  "102__s1.json": doc(["test_c.py"])})
        self.run_main("--write")
        self.assertEqual(self.listed(), ["test_a.py"])
        self.assertEqual([t["file"] for t in self.filed()], ["test_a.py"])

    def test_two_files_each_flaky_once_are_not_added_together(self):
        self.put({"100__s1.json": doc(["test_a.py"]), "101__s1.json": doc(["test_b.py"])})
        code, out = self.run_main("--write")
        self.assertEqual((code, self.listed(), self.filed()), (0, [], []))
        self.assertIn("0 new on the list", out)

    def test_a_clean_run_between_two_flaky_runs_does_not_reset_the_count(self):
        self.put({"100__s1.json": doc(["test_a.py"]), "101__s1.json": doc(), "102__s1.json": doc(["test_a.py"])})
        _, out = self.run_main("--write")
        self.assertEqual(self.listed(), ["test_a.py"])
        self.assertIn("quarantined: test_a.py (runs 100, 102)", out)

    def test_a_file_that_failed_every_time_is_a_defect_and_is_never_quarantined(self):
        self.put({"100__s1.json": doc(defects=["test_a.py"]), "101__s1.json": doc(defects=["test_a.py"]),
                  "102__s1.json": doc(defects=["test_a.py"])})
        code, _ = self.run_main("--write")
        self.assertEqual((code, self.listed(), self.filed()), (0, [], []))

    def test_a_quarantined_file_that_passes_again_stays_listed_until_a_pull_request_takes_it_off(self):
        self.put({"200__s1.json": doc(), "201__s1.json": doc()}, listed="# list\ntest_a.py  # runs 100, 101\n")
        self.run_main("--write")
        self.assertEqual(self.listed(), ["test_a.py"])
        self.assertEqual(self.filed(), [])

    def test_a_further_flaky_run_of_a_listed_file_files_no_second_ticket(self):
        self.put({"100__s1.json": doc(["test_a.py"]), "101__s1.json": doc(["test_a.py"]), "102__s1.json": doc(["test_a.py"])},
                 listed="test_a.py  # runs 90, 91\n")
        code, out = self.run_main("--write")
        self.assertEqual((code, self.listed(), self.filed()), (0, ["test_a.py"], []))
        self.assertNotIn("quarantined: ", out)

    def test_without_write_it_reports_and_changes_nothing(self):
        self.put({"100__s1.json": doc(["test_a.py"]), "101__s1.json": doc(["test_a.py"])})
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("quarantined: test_a.py (runs 100, 101)", out)
        self.assertIn("1 new on the list (report only)", out)
        self.assertEqual(self.list.read_text(encoding="utf-8"), "# list\n")
        self.assertFalse(self.tickets.exists())

    def test_the_run_id_is_what_comes_before_the_double_underscore(self):
        self.assertEqual(fq.flaky_runs({"100__s1.json": doc(["a.py"]), "100__s2.json": doc(["a.py"]),
                                        "101__s1.json": doc(["a.py"])}), {"a.py": ["100", "101"]})

    def test_the_list_skips_comments_and_blank_lines_and_a_missing_list_is_empty(self):
        self.assertEqual(fq.read_list("# top\n\n  test_a.py  # runs 1, 2\n   \ntest_b.py\n"), ["test_a.py", "test_b.py"])
        self.put({"100__s1.json": doc(["test_a.py"]), "101__s1.json": doc(["test_a.py"])})
        self.list.unlink()
        self.run_main("--write")
        self.assertEqual(self.listed(), ["test_a.py"])
        self.assertIn("# runs 100, 101;", self.list.read_text(encoding="utf-8"))

    def test_a_line_added_to_a_list_without_a_final_newline_starts_on_its_own_line(self):
        self.put({"100__s1.json": doc(["test_b.py"]), "101__s1.json": doc(["test_b.py"])}, listed="test_a.py")
        self.run_main("--write")
        self.assertEqual(self.listed(), ["test_a.py", "test_b.py"])


class RunnerListBoundaryTest(unittest.TestCase):
    """The runner reads the list in a copy of itself beside a tiny tests folder."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        (d / "dev" / "tools").mkdir(parents=True)
        (d / "tests").mkdir()
        (d / "src" / "clark").mkdir(parents=True)
        for rel in ("dev/run_tests.py", "dev/tools/run_support.py"):
            (d / rel).write_text((ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
        (d / "src" / "clark" / "__init__.py").write_text("", encoding="utf-8")
        (d / "src" / "clark" / "page.py").write_text("class PageError(Exception):\n    pass\n\n\ndef ensure_built():\n    return None\n",
                                                     encoding="utf-8")
        body = "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n"
        for n in ("test_one.py", "test_two.py", "test_three.py"):
            (d / "tests" / n).write_text(body, encoding="utf-8")
        self.dir = d

    def tearDown(self):
        self.tmp.cleanup()

    def runner(self, listed, *args):
        if listed is not None:
            (self.dir / "dev" / "tools" / "quarantine.txt").write_text(listed, encoding="utf-8")
        r = subprocess.run([sys.executable, "dev/run_tests.py", *args], cwd=self.dir, capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def test_only_the_listed_file_is_left_out_and_a_comment_does_not_list_a_file(self):
        code, out = self.runner("# test_three.py is fine\ntest_one.py  # runs 1, 2\n")
        self.assertEqual(code, 0, out)
        self.assertIn("Quarantined, not run: test_one.py (dev/tools/quarantine.txt).", out)
        self.assertIn("OK    test_two.py", out)
        self.assertIn("OK    test_three.py", out)
        self.assertNotIn("OK    test_one.py", out)
        self.assertIn("2 tests", out)

    def test_a_missing_list_leaves_nothing_out(self):
        code, out = self.runner(None)
        self.assertEqual(code, 0, out)
        self.assertNotIn("Quarantined", out)
        self.assertIn("3 tests", out)

    def test_two_listed_files_are_both_left_out_in_one_line(self):
        code, out = self.runner("test_one.py\ntest_three.py\n")
        self.assertEqual(code, 0, out)
        self.assertIn("Quarantined, not run: test_one.py, test_three.py (dev/tools/quarantine.txt).", out)
        self.assertIn("1 tests", out)


if __name__ == "__main__":
    unittest.main()
