"""Row 1568 AP1: the ask-index folder is kept out of Time Machine at every creation, on a Mac only. tmutil and osascript are stubbed: nothing real runs.
Run: python3 dev/run_tests.py test_ask_index_time_machine_1568"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

from clark import ask_index, platform as pl


class TimeMachine(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.run_ = mock.Mock()
        env = mock.patch.dict(os.environ)                        # these tests exercise the real code path: the CLARK_TEST guard is off here
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("CLARK_TEST", None)
        for p in (mock.patch.object(pl.subprocess, "run", self.run_), mock.patch.object(pl, "system", return_value=pl.MAC)):
            p.start()
            self.addCleanup(p.stop)

    def make(self):
        ask_index._open(self.d, "P1").close()

    def calls(self):
        return [c.args[0] for c in self.run_.call_args_list]

    def test_called_on_create_with_the_folder(self):
        self.make()
        self.assertEqual(self.calls(), [["tmutil", "addexclusion", str(self.d / "ask-index")]])

    def test_the_call_is_pinned_to_its_10_second_timeout(self):
        self.make()
        self.assertEqual(self.run_.call_args.kwargs["timeout"], 10)

    def test_called_again_when_the_folder_is_recreated_but_not_for_a_new_file(self):
        self.make()
        ask_index._open(self.d, "P2").close()                    # a new file in the same folder: the mark is still there
        self.assertEqual(len(self.calls()), 1)
        shutil.rmtree(self.d / "ask-index")
        self.make()
        self.assertEqual(len(self.calls()), 2)

    def test_not_called_off_a_mac(self):
        with mock.patch.object(pl, "system", return_value="linux"):
            self.make()
        self.run_.assert_not_called()

    def test_failure_is_swallowed_and_the_index_still_opens(self):
        for err in (FileNotFoundError("tmutil"), OSError("boom"), pl.subprocess.TimeoutExpired("tmutil", 10)):
            shutil.rmtree(self.d / "ask-index", ignore_errors=True)
            self.run_.side_effect = err
            self.make()
            self.assertTrue(ask_index.path_for(self.d, "P1").exists())

    def test_under_clark_test_nothing_runs_tmutil(self):
        os.environ["CLARK_TEST"] = "1"
        self.run_.side_effect = AssertionError("the real tmutil must never run under CLARK_TEST=1")
        self.make()
        pl.exclude_from_backup(self.d)
        self.run_.assert_not_called()

    def test_a_missing_folder_is_not_created_for_a_read(self):
        self.assertIsNone(ask_index._open(self.d, "P1", create=False))
        self.run_.assert_not_called()


if __name__ == "__main__":
    unittest.main()
