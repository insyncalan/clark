"""The nightly's shard times (dev/tools/shard_refresh.py): the real per-file times of a full run become the new
dev/tools/shard_times.txt, so the shards stay balanced. A file the run did not time keeps its old line, a test file that is
gone loses its line, and the result still reads as the runner reads it.

Run: python3 dev/run_tests.py test_shard_refresh   (quick tier)
"""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT  # noqa: F401  (puts dev/tools on the path)

import shard_refresh as sr

OLD = "# header line one\n# header line two\ntest_a.py 10.0\ntest_b.py 20.0\ntest_gone.py 5.0\n"


class MergeTest(unittest.TestCase):
    def test_times_are_read_and_bad_lines_dropped(self):
        self.assertEqual(sr.read_times("test_a.py 1.25\n# note\n\ntest_b.py x\ntest_c.py 0\nnot a line\ntest_d.py 3\n"),
                         {"test_a.py": 1.25, "test_d.py": 3.0})

    def test_a_measured_file_takes_the_new_time_and_an_unmeasured_one_keeps_the_old(self):
        merged = sr.merge({"test_a.py": 10.0, "test_b.py": 20.0}, {"test_a.py": 14.44}, {"test_a.py", "test_b.py"})
        self.assertEqual(merged, {"test_a.py": 14.4, "test_b.py": 20.0})

    def test_a_test_file_that_is_gone_loses_its_line_and_a_new_one_gets_one(self):
        merged = sr.merge({"test_a.py": 10.0, "test_gone.py": 5.0}, {"test_new.py": 2.0, "test_stray.py": 9.0}, {"test_a.py", "test_new.py"})
        self.assertEqual(merged, {"test_a.py": 10.0, "test_new.py": 2.0})

    def test_the_slowest_time_wins_when_two_shards_timed_one_file(self):
        self.assertEqual(sr.combine([{"test_a.py": 3.0}, {"test_a.py": 7.0, "test_b.py": 1.0}]), {"test_a.py": 7.0, "test_b.py": 1.0})

    def test_the_header_is_kept_and_the_lines_are_in_name_order(self):
        text = sr.render(OLD, {"test_b.py": 21.0, "test_a.py": 9.5})
        self.assertEqual(text, "# header line one\n# header line two\ntest_a.py 9.5\ntest_b.py 21.0\n")


class CommandTest(unittest.TestCase):
    def test_the_file_is_rewritten_from_every_durations_file_in_the_folder(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "tests").mkdir()
            for name in ("test_a.py", "test_b.py", "test_c.py"):
                (d / "tests" / name).write_text("", encoding="utf-8")
            (d / "times").mkdir()
            (d / "times" / "shard-1.durations").write_text("test_a.py 12.34\n", encoding="utf-8")
            (d / "times" / "shard-2.durations").write_text("test_c.py 0.52\n", encoding="utf-8")
            out = d / "shard_times.txt"
            out.write_text(OLD, encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = sr.main(["--durations", str(d / "times"), "--tests", str(d / "tests"), "--out", str(out)])
            self.assertEqual(code, 0)
            self.assertEqual(out.read_text(encoding="utf-8"),
                             "# header line one\n# header line two\ntest_a.py 12.3\ntest_b.py 20.0\ntest_c.py 0.5\n")
            self.assertIn("2 measured, 1 kept, 1 removed", buf.getvalue())

    def test_no_measured_time_changes_nothing_and_is_not_a_pass(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "tests").mkdir()
            (d / "times").mkdir()
            out = d / "shard_times.txt"
            out.write_text(OLD, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                code = sr.main(["--durations", str(d / "times"), "--tests", str(d / "tests"), "--out", str(out)])
            self.assertEqual(code, 2)
            self.assertEqual(out.read_text(encoding="utf-8"), OLD)

    def test_the_real_file_survives_a_round_trip(self):
        real = (ROOT / "dev" / "tools" / "shard_times.txt").read_text(encoding="utf-8")
        self.assertEqual(sr.render(real, sr.read_times(real)).count("\n"), real.count("\n"))


if __name__ == "__main__":
    unittest.main()
