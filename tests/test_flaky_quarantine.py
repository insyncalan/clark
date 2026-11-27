"""Flaky tests are quarantined at two (dev/tools/flaky_quarantine.py, and the runner's part in dev/run_tests.py): a test file that
failed and then passed alone in two different runs goes on dev/tools/quarantine.txt, a "Tech Debt - Priority" ticket is written
out for filing, and the runner leaves a quarantined file out of an ordinary run (the nightly still runs it).

Run: python3 dev/run_tests.py test_flaky_quarantine   (quick tier)
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


class CommandTest(unittest.TestCase):
    def run_main(self, d, *more):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = fq.main(["--results", str(d / "results"), "--list", str(d / "quarantine.txt"),
                            "--tickets", str(d / "tickets.json"), *more])
        return code, buf.getvalue()

    def folder(self, d, docs):
        (d / "results").mkdir()
        for name, body in docs.items():
            (d / "results" / name).write_text(json.dumps(body), encoding="utf-8")
        (d / "quarantine.txt").write_text("# The quarantine list.\n", encoding="utf-8")

    def test_a_file_flaky_in_two_runs_is_listed_and_a_ticket_written(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            self.folder(d, {"100__s1.json": doc(["test_a.py"]), "101__s3.json": doc(["test_a.py", "test_b.py"])})
            code, out = self.run_main(d, "--write")
            self.assertEqual(code, 0)
            self.assertEqual(fq.read_list((d / "quarantine.txt").read_text(encoding="utf-8")), ["test_a.py"])
            self.assertTrue((d / "quarantine.txt").read_text(encoding="utf-8").startswith("# The quarantine list.\n"))
            tickets = json.loads((d / "tickets.json").read_text(encoding="utf-8"))
            self.assertEqual([t["file"] for t in tickets], ["test_a.py"])
            self.assertIn("quarantined: test_a.py (runs 100, 101)", out)
            # a second pass over the same results adds nothing and files nothing
            code, out = self.run_main(d, "--write")
            self.assertEqual(fq.read_list((d / "quarantine.txt").read_text(encoding="utf-8")), ["test_a.py"])
            self.assertEqual(json.loads((d / "tickets.json").read_text(encoding="utf-8")), [])

    def test_one_flaky_run_is_not_enough(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            self.folder(d, {"100__s1.json": doc(["test_a.py"]), "100__s2.json": doc(["test_a.py"])})
            self.run_main(d, "--write")
            self.assertEqual(fq.read_list((d / "quarantine.txt").read_text(encoding="utf-8")), [])

    def test_a_results_file_that_does_not_read_is_named_and_is_not_a_pass(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            self.folder(d, {"100__s1.json": doc(["test_a.py"])})
            (d / "results" / "101__s1.json").write_text("{not json", encoding="utf-8")
            code, out = self.run_main(d, "--write")
            self.assertEqual(code, 2)
            self.assertIn("not checked: 101__s1.json", out)


class RunnerTest(unittest.TestCase):
    """The runner's part, in a copy of the runner beside a tiny tests folder."""
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
        (d / "tests" / "test_steady.py").write_text(body, encoding="utf-8")
        (d / "tests" / "test_shaky.py").write_text(body, encoding="utf-8")
        (d / "dev" / "tools" / "quarantine.txt").write_text("# list\ntest_shaky.py  # runs 100, 101\n", encoding="utf-8")
        self.dir = d

    def tearDown(self):
        self.tmp.cleanup()

    def runner(self, *args):
        r = subprocess.run([sys.executable, "dev/run_tests.py", *args], cwd=self.dir, capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def test_an_ordinary_run_leaves_the_quarantined_file_out_and_says_so(self):
        code, out = self.runner()
        self.assertEqual(code, 0, out)
        self.assertIn("Quarantined, not run: test_shaky.py", out)
        self.assertIn("test_steady.py", out)
        self.assertNotIn("OK    test_shaky.py", out)
        self.assertIn("1 tests", out)

    def test_a_quarantined_file_named_on_the_command_line_still_runs(self):
        code, out = self.runner("test_shaky.py")        # a ticket's named test is never left out: only an unnamed run drops a quarantined file
        self.assertEqual(code, 0, out)
        self.assertIn("OK    test_shaky.py", out)
        self.assertNotIn("Quarantined, not run", out)

    def test_the_nightly_flag_runs_it(self):
        code, out = self.runner("--with-quarantined")
        self.assertEqual(code, 0, out)
        self.assertNotIn("Quarantined, not run", out)
        self.assertIn("2 tests", out)


if __name__ == "__main__":
    unittest.main()
