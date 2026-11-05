"""Issue 742: the daily log follows --data. With a data folder other than clark's own default, the log is <data>/logs and
nothing is written under the home's Library/Logs; with no --data (or the default folder) it stays Library/Logs/clark. The
Settings card reads the folder from the same log, so both are checked together. Linux-runnable: the system is faked as a Mac."""
import logging
import os
import shutil
import stat
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401
from clark import __main__ as launcher, platform as pl


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-742-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.data = self.tmp / "elsewhere" / "data"
        self.data.mkdir(parents=True)
        patch = mock.patch.object(pl, "system", return_value=pl.MAC)
        patch.start()
        self.addCleanup(patch.stop)

    def started(self, data):
        log, handler, logs = launcher.start_log(data, lambda: [], home=self.home)
        self.addCleanup(logging.getLogger("clark").removeHandler, handler)
        return log, logs


class Helper(Base):
    def test_no_data_is_the_library_logs_folder(self):
        self.assertEqual(pl.log_folder(None, self.home), self.home / "Library" / "Logs" / "clark")

    def test_the_default_data_folder_is_not_an_explicit_one(self):
        default = pl.data_dir(self.home)
        default.mkdir(parents=True)
        want = self.home / "Library" / "Logs" / "clark"
        self.assertEqual(pl.log_folder(default, self.home), want)
        self.assertEqual(pl.log_folder(default / ".." / "clark", self.home), want)

    def test_an_explicit_data_folder_holds_the_logs(self):
        self.assertEqual(pl.log_folder(self.data, self.home), self.data / "logs")

    def test_dots_are_resolved_and_the_answer_stays_inside(self):
        (self.data / "a").mkdir()
        odd = self.data / "a" / ".." / ".."
        got = pl.log_folder(odd, self.home)
        self.assertEqual(got, self.data.parent / "logs")
        self.assertEqual(got.parent, odd.resolve())

    def test_a_linked_data_folder_is_followed_to_its_real_place(self):
        link = self.tmp / "link"
        os.symlink(str(self.data), str(link))
        self.assertEqual(pl.log_folder(link, self.home), self.data / "logs")

    def test_a_logs_link_leading_out_is_refused(self):
        outside = self.tmp / "outside"
        outside.mkdir()
        os.symlink(str(outside), str(self.data / "logs"))
        with self.assertRaises(pl.PlatformError):
            pl.log_folder(self.data, self.home)

    def test_without_a_mac_a_data_folder_still_works_and_none_does_not(self):
        with mock.patch.object(pl, "system", return_value="linux"):
            self.assertEqual(pl.log_folder(self.data, self.home), self.data / "logs")
            with self.assertRaises(pl.NotBuiltYet):
                pl.log_folder(None, self.home)


class Started(Base):
    def test_data_given_writes_inside_it_and_nothing_under_the_home(self):
        log, logs = self.started(self.data)
        logging.getLogger("clark.server").info("started on port %d", 8123)
        self.assertEqual(log.folder, self.data / "logs")
        self.assertTrue(list((self.data / "logs").glob("clark-*.log")))
        self.assertEqual(list(self.home.iterdir()), [])

    def test_the_folder_is_private(self):
        log, logs = self.started(self.data)
        logging.getLogger("clark.server").info("started on port %d", 8123)
        self.assertEqual(stat.S_IMODE((self.data / "logs").stat().st_mode) & 0o077, 0)

    def test_no_data_given_is_exactly_the_library_folder(self):
        default = pl.data_dir(self.home)
        default.mkdir(parents=True)
        log, logs = self.started(default)
        logging.getLogger("clark.server").info("started on port %d", 8123)
        self.assertEqual(log.folder, self.home / "Library" / "Logs" / "clark")
        self.assertTrue(list(log.folder.glob("clark-*.log")))
        self.assertFalse((default / "logs").exists())

    def test_the_settings_card_opens_the_same_folder_in_both_cases(self):
        default = pl.data_dir(self.home)
        default.mkdir(parents=True)
        for data, want in ((self.data, self.data / "logs"), (default, self.home / "Library" / "Logs" / "clark")):
            opened = []
            log, logs = self.started(data)
            logs.opener = opened.append
            self.assertEqual(log.folder, want)
            logs.open_folder()
            self.assertEqual(opened, [want])

    def test_the_level_stays_in_the_data_folder(self):
        log, logs = self.started(self.data)
        self.assertEqual(log.level_file, self.data / "diagnostics.json")

    def test_pruning_works_in_the_data_folder(self):
        log, logs = self.started(self.data)
        today = datetime.now().date()
        folder = self.data / "logs"
        folder.mkdir(exist_ok=True)
        old = folder / f"clark-{(today - timedelta(days=30)):%Y-%m-%d}.log"
        recent = folder / f"clark-{(today - timedelta(days=2)):%Y-%m-%d}.log"
        other = folder / "notes.txt"
        for p in (old, recent, other):
            p.write_text("x\n", encoding="utf-8")
        log.prune(today)
        self.assertFalse(old.exists())
        self.assertTrue(recent.exists())
        self.assertTrue(other.exists())

    def test_a_demo_still_logs_in_its_scratch_folder(self):
        scratch = self.tmp / "scratch"
        scratch.mkdir()
        log, handler, logs = launcher.start_log(self.data, lambda: [], home=self.home, scratch=scratch)
        self.addCleanup(logging.getLogger("clark").removeHandler, handler)
        self.assertEqual(log.folder, scratch / "logs")


if __name__ == "__main__":
    unittest.main()
