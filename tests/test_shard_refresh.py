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

    def test_a_pinned_heavy_file_never_drops_below_its_pin_and_stays_within_ten_percent_above_it(self):
        """Found on the first real nightly (27-11): test_publish_scan_time.py measured 184.7 s against a pin of 450.4, and
        test_run_tests holds the five heavy files within 10 percent of their pins. The pin is the floor; a slower night counts
        up to 10 percent over it."""
        existing = set(sr.PINNED) | {"test_other.py"}
        low = sr.merge({}, dict({n: 1.0 for n in sr.PINNED}, **{"test_other.py": 1.0}), existing)
        self.assertEqual({n: low[n] for n in sr.PINNED}, sr.PINNED)
        self.assertEqual(low["test_other.py"], 1.0)
        high = sr.merge({}, {n: 9999.0 for n in existing}, existing)
        self.assertEqual({n: high[n] for n in sr.PINNED}, {n: sr.cap(v) for n, v in sr.PINNED.items()})
        self.assertEqual(high["test_other.py"], 9999.0)
        self.assertEqual(sr.PINNED["test_publish_scan_time.py"], 450.4)

    def test_the_cap_of_a_pinned_file_is_itself_inside_the_ten_percent_band(self):
        """Found in the read of ec39c4bb: the cap was rounded to the nearest tenth, so 277.8 gave 305.6, which is 10.007 percent
        over its pin and fails the band test in test_run_tests on the next run. The cap rounds down."""
        existing = set(sr.PINNED)
        high = sr.merge({}, {n: 9999.0 for n in existing}, existing)
        for name, pin in sr.PINNED.items():
            with self.subTest(name=name):
                self.assertAlmostEqual(high[name] / pin, 1.0, delta=0.10, msg=name)      # the same check test_run_tests makes
                self.assertGreater(high[name], pin * 1.09, name)                          # and still the highest value that fits

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


if __name__ == "__main__":
    unittest.main()
