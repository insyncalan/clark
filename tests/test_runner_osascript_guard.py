"""RULE 14 in code: no test can open a real macOS dialog. Run: python3 dev/run_tests.py test_runner_osascript_guard  (quick tier)

Three guards, each proved here:
1. dev/run_tests.py puts a stub osascript FIRST on PATH for every test it starts (Runner.run), and tells it where to log
   (CLARK_TEST_OSASCRIPT_LOG).
2. A run in which any test called osascript FAILS (run_all prints the logged lines; exit status non-zero), though every test passed.
3. tests/_real_server.py never gives the Word export the system's folder window: a request that needs a folder answers
   "cancelled" (or asks the test's own `choose_folder`).
The runner is exercised on tiny test files made in a temporary folder, never on the real suite.
"""
import io
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from _paths import ROOT

sys.path.insert(0, str(ROOT / "dev"))
import run_support as support  # noqa: E402
import run_tests  # noqa: E402

BASE = Path(tempfile.mkdtemp(prefix="clark-guard-"))
support.RUN_BASE = BASE
WEB = Path("/tmp/clark-fictional/local/ABC-report-2026-10-23.html")

CLEAN = "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n"
PATHS = ("import os, unittest\nclass T(unittest.TestCase):\n    def test_path(self):\n"
         "        first = os.environ['PATH'].split(os.pathsep)[0]\n"
         "        log = os.environ['CLARK_TEST_OSASCRIPT_LOG']\n"
         "        self.assertEqual(first, os.path.dirname(log))\n"
         "        self.assertTrue(os.access(os.path.join(first, 'osascript'), os.X_OK))\n")
CALLS = ("import subprocess, unittest\nclass T(unittest.TestCase):\n    def test_calls(self):\n"
         "        subprocess.run(['osascript', '-e', 'beep'])\n")


def tiny(text, name="test_tiny"):
    d = Path(tempfile.mkdtemp(dir=BASE))
    f = d / (name + ".py")
    f.write_text(text, encoding="utf-8")
    return f


class TheRunnerStubsOsascript(unittest.TestCase):
    def setUp(self):
        self.runner = run_tests.Runner(timeout=60)
        self.addCleanup(self.runner.close)

    def test_the_stub_is_first_on_path_in_a_child_and_the_log_is_told(self):
        f, code, _, out = self.runner.run(tiny(PATHS))
        self.assertEqual(code, 0, out)
        self.assertEqual(self.runner.osascript_calls(), [])

    def test_a_child_that_calls_osascript_is_logged(self):
        _, code, _, out = self.runner.run(tiny(CALLS))
        self.assertEqual(code, 0, out)                  # the stub exits 1 but the test ignores that: the LOG is what fails the run
        lines = self.runner.osascript_calls()
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("osascript -e beep", lines[0])

    def test_a_clean_child_logs_nothing(self):
        self.runner.run(tiny(CLEAN))
        self.assertEqual(self.runner.osascript_calls(), [])


class ARunWithADialogCallFails(unittest.TestCase):
    def run_all(self, text):
        out = io.StringIO()
        with redirect_stdout(out), mock.patch.object(run_tests, "TIMES", BASE / "times.txt"), mock.patch.object(run_tests, "remember_failed"):
            code = run_tests.run_all([tiny(text)], 1)
        return code, out.getvalue()

    def test_every_test_passes_yet_the_run_fails_and_names_the_logged_line(self):
        code, out = self.run_all(CALLS)
        self.assertEqual(code, 1, out)
        self.assertIn("1 passed, 0 failed", out.replace("file passed", "passed").replace("files passed", "passed"))
        self.assertIn("osascript -e beep", out)
        self.assertIn("FAIL: 1 call(s) to osascript", out)

    def test_a_clean_run_passes(self):
        code, out = self.run_all(CLEAN)
        self.assertEqual(code, 0, out)
        self.assertNotIn("osascript", out)


class TheRealServerNeverOpensTheSystemFolderWindow(unittest.TestCase):
    def test_a_word_export_that_needs_a_folder_is_cancelled_not_asked_of_the_system(self):
        from _demo import DemoStore
        from _real_server import real_handlers
        from clark import platform
        demo = DemoStore()
        self.addCleanup(demo.close)
        demo.store.log_publication("ABC", WEB, "2026-10-23", "a" * 64, "Sam Carter")
        asked = []
        with mock.patch.object(platform, "choose_folder", side_effect=lambda *a, **k: asked.append(a) or None):
            handlers = real_handlers(demo.store.path, lambda *a, **k: None, roots=[])
            status, body = handlers["word_export"]({"project": "ABC"})
        self.assertEqual(asked, [], "the system's folder window was asked for")
        self.assertEqual((status, body.get("cancelled")), (200, True), body)

    def test_a_test_may_answer_the_folder_itself(self):
        from _demo import DemoStore
        from _real_server import real_handlers
        demo = DemoStore()
        self.addCleanup(demo.close)
        demo.store.log_publication("ABC", WEB, "2026-10-23", "a" * 64, "Sam Carter")
        prompts = []
        handlers = real_handlers(demo.store.path, lambda *a, **k: None, roots=[], choose_folder=lambda p: prompts.append(p))
        status, body = handlers["word_export"]({"project": "ABC"})
        self.assertEqual(len(prompts), 1)
        self.assertEqual((status, body.get("cancelled")), (200, True), body)


if __name__ == "__main__":
    unittest.main()
