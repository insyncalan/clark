"""Item 632 (v1.1, Windows Docker route): how the container starts, stops and logs.

Run: python3 dev/run_tests.py test_container_lifecycle_632
Headless: the container check is patched (no Docker, no marker file), nothing is written outside a temporary folder.
"""
import contextlib
import io
import logging
import re
import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401
from clark import __main__ as launcher, appfiles as af, idle, log as clog, log_routes, platform as pl

COMPOSE = Path(__file__).resolve().parents[1] / "docker" / "compose.yaml"
CONTAINER_ENV = {"CLARK_CONTAINER": "1", "CLARK_PORT": "8766"}     # the image's environment: CLARK_LAUNCHED is never set


def in_container(on=True):
    return mock.patch.object(pl, "container_mode", lambda: on)


class NoIdleStop(unittest.TestCase):
    """(1) The container never stops by itself, and nothing in the compose file sets the launcher's mark."""

    def test_idle_launched_is_false_under_the_images_environment(self):
        with in_container():
            self.assertFalse(idle.launched(dict(CONTAINER_ENV)))

    def test_even_with_the_launchers_mark_it_is_false_in_the_container(self):
        with in_container():
            self.assertFalse(idle.launched(dict(CONTAINER_ENV, CLARK_LAUNCHED="1")))

    def test_the_compose_file_does_not_set_the_launchers_mark(self):
        text = COMPOSE.read_text(encoding="utf-8")
        self.assertNotIn("CLARK_LAUNCHED", re.sub(r"(?m)^\s*#.*$", "", text))

    def test_the_compose_file_restarts_unless_stopped(self):
        self.assertRegex(COMPOSE.read_text(encoding="utf-8"), r"(?m)^\s+restart: unless-stopped\s*$")


class OfflinePageInContainer(unittest.TestCase):
    def page(self, container):
        return af.offline_page(container=container).decode("utf-8")

    def test_it_names_docker_compose_and_not_the_launcher(self):
        page = self.page(True)
        self.assertIn("docker compose -f docker/compose.yaml up -d", page)
        self.assertIn("Start it from Docker Desktop", page)
        self.assertIn("Your data is safe.", page)
        self.assertNotIn("clark.command", page)
        self.assertNotIn("stops clark", page)
        self.assertNotIn("after two minutes", page)
        self.assertNotIn("docker compose -f docker/compose.yaml down", page)
        self.assertIn('"Still not running. Start it from Docker Desktop, then check again."', page)

    def test_outside_the_container_the_page_is_the_one_it_was(self):
        page = self.page(False)
        self.assertIn("double-click <b>clark.command</b>", page)
        self.assertIn("Closing the last clark window stops clark.command after two minutes.", page)
        self.assertIn('"Still not running. Double-click clark.command, then check again."', page)

    def test_neither_page_keeps_a_marker_and_both_keep_check_again(self):
        for inside in (True, False):
            page = self.page(inside)
            self.assertNotRegex(page, r"@[A-Z_]+@|<!--")
            self.assertIn('<button type="button" id="again">Check again</button>', page)

    def test_the_default_follows_the_container_check(self):
        with in_container():
            self.assertNotIn("clark.command", af.offline_page().decode("utf-8"))
        with in_container(False):
            self.assertIn("clark.command", af.offline_page().decode("utf-8"))

    def test_the_container_page_is_still_hashed_once_each_for_style_and_script(self):
        from clark import server as sv
        h = sv.csp_hashes(self.page(True))
        self.assertEqual((len(h["style"]), len(h["script"])), (1, 1))


class LogsInContainer(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-632-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.data = self.tmp / "data"
        self.data.mkdir()

    def started(self, out=None):
        """start_log in the container; what it echoes goes to `out` (a throw-away stream when not given)."""
        with in_container(), mock.patch.object(pl, "system", return_value="linux"), contextlib.redirect_stdout(out or io.StringIO()):
            log, handler, logs = launcher.start_log(self.data, lambda: [], home=self.tmp / "home")
        self.addCleanup(logging.getLogger("clark").removeHandler, handler)
        return log, logs

    def test_start_log_writes_the_daily_file_under_the_data_folder(self):
        log, _ = self.started()
        self.assertEqual(log.folder, self.data / "logs")
        logging.getLogger("clark.test").info("started on port %d", 8766)
        (written,) = (self.data / "logs").glob("clark-*.log")
        self.assertRegex(written.name, r"^clark-\d{4}-\d{2}-\d{2}\.log$")
        self.assertIn("started on port 8766", written.read_text(encoding="utf-8"))

    def test_the_same_lines_go_to_standard_output_through_the_same_scrub(self):
        out = io.StringIO()
        log, _ = self.started(out)
        logging.getLogger("clark.test").info("opened %s", "/Users/someone/private-name.xlsx")
        printed, filed = out.getvalue(), next((self.data / "logs").glob("clark-*.log")).read_text(encoding="utf-8")
        self.assertEqual(printed, filed)
        self.assertNotIn("private-name", printed)
        self.assertIn("INFO", printed)

    def test_outside_the_container_nothing_goes_to_standard_output(self):
        out = io.StringIO()
        with in_container(False), contextlib.redirect_stdout(out), mock.patch.object(pl, "system", return_value=pl.MAC):
            log, handler, _ = launcher.start_log(self.data, lambda: [], home=self.tmp / "home")
            self.addCleanup(logging.getLogger("clark").removeHandler, handler)
            logging.getLogger("clark.test").info("started on port %d", 1)
        self.assertEqual((out.getvalue(), log.echo), ("", None))

    def test_a_line_that_is_not_written_for_size_still_does_not_break_the_stream(self):
        log, _ = self.started()
        log.echo = mock.Mock(write=mock.Mock(side_effect=OSError("closed")), flush=mock.Mock())
        log.info("server", "still here")                 # never raises
        self.assertIn("still here", next((self.data / "logs").glob("clark-*.log")).read_text(encoding="utf-8"))

    def test_diagnostics_answers_200(self):
        _, logs = self.started()
        with in_container():
            status, body = logs.diagnostics()
        self.assertEqual((status, body["ok"]), (200, True))

    def test_open_folder_shows_the_path_instead_of_failing(self):
        _, logs = self.started()
        opened = []
        logs.opener = opened.append
        env = {"CLARK_DATA_SOURCE": "C:\\Users\\Someone\\clark-data"}
        with in_container(), mock.patch.dict("os.environ", env):
            status, body = logs.open_folder()
        self.assertEqual((status, body["ok"], opened), (200, True, []))
        self.assertTrue(body["shown"].startswith("The log files are in this folder: "))
        self.assertTrue(body["shown"].endswith("\\logs"), body["shown"])
        self.assertNotIn("Someone", body["shown"])

    def test_open_folder_without_the_data_source_names_the_folder_inside_the_data_folder(self):
        _, logs = self.started()
        with in_container(), mock.patch.dict("os.environ", {}, clear=True):
            status, body = logs.open_folder()
        self.assertEqual((status, body["shown"]), (200, "The log files are in the logs folder inside your clark data folder."))

    def test_open_folder_outside_the_container_still_opens_the_folder(self):
        _, logs = self.started()
        opened = []
        logs.opener = opened.append
        with in_container(False):
            status, body = logs.open_folder()
        self.assertEqual((status, body, opened), (200, {"ok": True}, [self.data / "logs"]))


class BackupsSkipLogs(unittest.TestCase):
    def test_a_backup_copy_and_its_tidy_up_leave_the_logs_folder_alone(self):
        from clark import backup
        tmp = Path(tempfile.mkdtemp(prefix="clark-632-")).resolve()
        self.addCleanup(shutil.rmtree, tmp, True)
        data, copy = tmp / "data", tmp / "copy"
        (data / "logs").mkdir(parents=True)
        (copy).mkdir()
        log = data / "logs" / "clark-2026-11-14.log"
        log.write_text("2026-11-14 00:00:00 INFO  test         started\n", encoding="utf-8")
        backup._copy_kept(data, copy)
        self.assertEqual(sorted(p.name for p in copy.iterdir()), [])         # nothing of logs/ is copied out
        self.assertEqual(backup.entries(data), [])                           # and logs/ holds no backup
        backup.prune(data, keep=1)
        self.assertEqual(log.read_text(encoding="utf-8"), "2026-11-14 00:00:00 INFO  test         started\n")


if __name__ == "__main__":
    unittest.main()
