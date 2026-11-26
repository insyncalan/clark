"""#1666 hardening: a test run never reaches the Mac's real picture reader (osascript) by accident. On a Mac ask_index registers the
real reader at import; a test that does not stub the reader would start osascript (CI run 45523455732, macOS shard 3/6). Under the
tests (tests/_paths.py sets CLARK_TEST=1) the reader, given no stand-in `run`, raises PictureUnreadable and starts nothing.
Run: python3 dev/run_tests.py test_ask_vision_guard_1366"""
import os
import subprocess
import unittest
from unittest import mock

from _paths import ROOT  # noqa: F401
from clark import ask_picture, ask_vision_mac as vm, platform as pl

PNG = b"\x89PNG\r\n\x1a\n not really a picture"


class NoRealReaderUnderTests(unittest.TestCase):
    def setUp(self):
        for p in (mock.patch.object(pl, "system", return_value=pl.MAC), mock.patch.object(ask_picture, "_READER", None)):
            p.start()
            self.addCleanup(p.stop)

    def test_the_paths_helper_marks_the_run_as_a_test(self):
        self.assertEqual(os.environ.get("CLARK_TEST"), "1")

    def test_the_registered_reader_without_a_stand_in_never_calls_run_jxa_or_starts_a_program(self):
        with mock.patch.object(pl, "run_jxa") as jxa, mock.patch.object(subprocess, "run") as started:
            vm.register()
            with self.assertRaises(ask_picture.PictureUnreadable):
                ask_picture._READER(PNG)
            self.assertEqual(jxa.call_count, 0)
            self.assertEqual(started.call_count, 0)

    def test_the_refusal_is_observable_and_leaves_no_temporary_file(self):
        with mock.patch.object(pl, "run_jxa"), mock.patch("tempfile.mkstemp") as made:
            with self.assertRaises(ask_picture.PictureUnreadable) as got:
                vm.read(PNG)
            self.assertIn("not run under the tests", str(got.exception))
            self.assertEqual(made.call_count, 0)

    def test_a_test_stand_in_still_reads_as_before(self):
        class Done:
            returncode, stdout = 0, "hello\n"
        with mock.patch.object(subprocess, "run") as started:
            self.assertEqual(vm.read(PNG, run=lambda *a, **k: Done()), "hello")
            self.assertEqual(started.call_count, 0)

    def test_outside_the_tests_the_real_path_is_taken(self):
        with mock.patch.dict(os.environ), mock.patch.object(pl, "run_jxa", return_value="seen") as jxa:
            os.environ.pop("CLARK_TEST", None)
            self.assertEqual(vm.read(PNG), "seen")
            self.assertEqual(jxa.call_count, 1)


if __name__ == "__main__":
    unittest.main()
