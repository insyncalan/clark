"""One clark to a data folder: the lock in the data folder (platform.hold_data_lock) and what refuses or reports with it.

Run: python3 dev/run_tests.py test_data_lock
The holders are real clark processes (`-m clark` on a free port, a temporary data folder, started through test_main's AS_THE_MAC
so they run as the Mac does on any system), so a second clark, a stopped one and a killed one are the real thing. The lock file
must stay empty. Nothing is opened in a browser. When a clark fails to come up, the failure carries what it wrote to stderr.
"""
import errno
import http.client
import io
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC

from clark import launch, platform as pl
from clark import __main__ as launcher
from test_main import AS_THE_MAC

RESTORE_SENTENCE = ("Nothing was restored: clark is open with this data. Close its window, wait a minute for clark to stop, "
                    "then run the restore again.")


def already_open(folder, home=None):
    return (f"Nothing was started: clark is already open with the data in {pl.with_tilde(folder, home)}. Switch to its window. If you can't "
            "find it, wait a minute and try again: clark stops by itself a minute after its last window closes.")


def cant_check(folder, nothing="Nothing was started", home=None):
    return (f"{nothing}: clark can't check whether it is already open with the data in {pl.with_tilde(folder, home)}. "
            "Check that you can save files there, then try again.")


def lock_unreadable(case):
    """The lock file exists but nobody may open it (skipped as root, who may open anything)."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        case.skipTest("root can open a file whatever its mode")
    case.data.mkdir()
    lock = case.data / pl.LOCK_NAME
    lock.write_bytes(b"")
    lock.chmod(0)
    case.addCleanup(lock.chmod, 0o600)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def answers(port):
    try:
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
        c.request("GET", "/health")
        return c.getresponse().status == 200
    except OSError:
        return False


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.data = Path(self._tmp.name) / "data"
        self.procs = []
        self.addCleanup(self.stop_all)
        patch = mock.patch.object(pl, "system", return_value=pl.MAC)      # the in-process calls run as the Mac too (see AS_THE_MAC)
        patch.start()
        self.addCleanup(patch.stop)

    def stop_all(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
            p.wait()
            p.stderr_file.close()

    def start(self, port=None):
        port = port or free_port()
        env = {**os.environ, "PYTHONPATH": str(SRC), "HOME": self._tmp.name}
        env.pop("CLARK_LAUNCHED", None)
        errors = open(Path(self._tmp.name) / f"stderr-{len(self.procs)}.txt", "w+b")     # a file, not a pipe: a full pipe stops the child
        p = subprocess.Popen([sys.executable, "-c", AS_THE_MAC, "--data", str(self.data), "--port", str(port)],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=errors, env=env, cwd=self._tmp.name)
        p.stderr_file = errors
        self.procs.append(p)
        return p, port

    def stderr_of(self, p):
        p.stderr_file.flush()
        p.stderr_file.seek(0)
        return p.stderr_file.read().decode("utf-8", "replace")

    def wait_up(self, port, p):
        end = time.monotonic() + 20
        while time.monotonic() < end and p.poll() is None:
            if answers(port):
                return True
            time.sleep(0.1)
        return False

    def assert_up(self, port, p):
        self.assertTrue(self.wait_up(port, p), f"clark did not answer /health (exit {p.poll()}); its stderr:\n{self.stderr_of(p)}")


class TheLock(Base):
    def test_a_second_clark_on_the_same_folder_is_refused_and_the_first_keeps_working(self):
        first, port1 = self.start()
        self.assert_up(port1, first)
        second, port2 = self.start()
        second.wait(timeout=20)
        self.assertEqual(second.returncode, 1, self.stderr_of(second))
        self.assertIn(already_open(self.data, self._tmp.name), self.stderr_of(second))   # the clark started here has HOME in the temporary folder
        self.assertFalse(answers(port2), "the second started nothing")
        self.assertIsNone(first.poll())
        self.assertTrue(answers(port1), "the first keeps answering")

    def test_the_lock_file_holds_nothing(self):
        first, port1 = self.start()
        self.assert_up(port1, first)
        self.assertEqual((self.data / pl.LOCK_NAME).read_bytes(), b"")

    def test_after_a_clean_stop_the_next_clark_starts(self):
        first, port1 = self.start()
        self.assert_up(port1, first)
        first.send_signal(signal.SIGTERM)
        first.wait(timeout=20)
        second, port2 = self.start()
        self.assert_up(port2, second)

    def test_after_a_kill_the_next_clark_starts(self):
        first, port1 = self.start()
        self.assert_up(port1, first)
        first.kill()
        first.wait(timeout=20)
        self.assertTrue((self.data / pl.LOCK_NAME).exists(), "the file stays; the lock does not")
        second, port2 = self.start()
        self.assert_up(port2, second)

    def test_in_one_process_a_second_hold_is_refused_until_it_is_released(self):
        self.data.mkdir()
        pl.hold_data_lock(self.data)
        self.addCleanup(pl.release_data_lock, self.data)
        with self.assertRaises(pl.PlatformError) as ctx:
            pl.hold_data_lock(self.data)
        self.assertEqual(str(ctx.exception), already_open(self.data))
        pl.release_data_lock(self.data)
        pl.hold_data_lock(self.data)

    def test_a_lock_that_can_not_be_looked_at_is_not_reported_as_already_open(self):
        lock_unreadable(self)
        with self.assertRaises(pl.PlatformError) as ctx:
            pl.hold_data_lock(self.data)
        self.assertEqual(str(ctx.exception), cant_check(self.data))
        with self.assertRaises(pl.PlatformError) as ctx:
            pl.data_lock_held(self.data)
        self.assertEqual(str(ctx.exception), cant_check(self.data))

    def test_any_other_error_on_the_lock_is_can_not_check_and_a_busy_one_is_already_open(self):
        self.data.mkdir()
        for error, said in ((OSError(errno.EIO, "io"), cant_check(self.data)), (OSError(errno.EACCES, "no"), cant_check(self.data)),
                            (BlockingIOError(errno.EAGAIN, "busy"), already_open(self.data)),
                            (OSError(errno.EAGAIN, "busy"), already_open(self.data))):
            with mock.patch.object(pl, "_lock_file", side_effect=error):
                with self.assertRaises(pl.PlatformError) as ctx:
                    pl.hold_data_lock(self.data)
            self.assertEqual(str(ctx.exception), said, error)

    def test_clark_does_not_start_when_the_lock_can_not_be_looked_at(self):
        lock_unreadable(self)
        p, port = self.start()
        p.wait(timeout=20)
        self.assertEqual(p.returncode, 1, self.stderr_of(p))
        self.assertIn(cant_check(self.data, home=self._tmp.name), self.stderr_of(p))
        self.assertFalse(answers(port), "nothing started")

    def test_a_start_that_fails_after_the_lock_lets_it_go(self):
        self.data.mkdir()
        (self.data / "clark.db").write_bytes(b"not a database at all, just text")
        err = io.StringIO()
        self.assertEqual(launcher.main(["--data", str(self.data), "--port", str(free_port())], out=io.StringIO(), err=err,
                                       home=Path(self._tmp.name), onedrive_roots=[], serve=lambda **k: 0), 1)
        self.assertIn("can't be read", err.getvalue(), "it stopped at the database, after the lock was taken")
        self.assertFalse(pl.data_lock_held(self.data))
        pl.hold_data_lock(self.data)
        pl.release_data_lock(self.data)


class TheLauncher(Base):
    def test_it_reports_a_clark_on_another_port_and_starts_nothing(self):
        first, port1 = self.start()
        self.assert_up(port1, first)
        said, started = [], []
        code = launch.launch(free_port(), self.data, say=said.append, start=lambda *a, **k: started.append(a),
                             health=lambda port, mark: launch.NOTHING)
        self.assertEqual(code, 1)
        self.assertEqual(said, [already_open(self.data)])
        self.assertEqual(started, [])

    def test_it_says_it_can_not_check_and_starts_nothing_when_the_lock_can_not_be_looked_at(self):
        lock_unreadable(self)
        said, started = [], []
        code = launch.launch(free_port(), self.data, say=said.append, start=lambda *a, **k: started.append(a),
                             health=lambda port, mark: launch.NOTHING)
        self.assertEqual(code, 1)
        self.assertEqual(said, [cant_check(self.data)])
        self.assertEqual(started, [])

    def test_with_no_clark_open_it_starts_one_as_before(self):
        self.data.mkdir()
        (self.data / pl.LOCK_NAME).write_bytes(b"")
        started = []
        seen = iter([launch.NOTHING])
        launch.launch(free_port(), self.data, say=lambda t: None, start=lambda *a, **k: started.append(a) or object(),
                      health=lambda p, m: next(seen), wait=lambda *a, **k: launch.NOT_CLARK,
                      find_chrome=lambda e: None, open_window=None, open_browser=None)
        self.assertEqual(len(started), 1)


class TheRestoreCommand(Base):
    """#418: `clark restore NAME` swaps clark.db, so a clark open on the folder refuses it."""

    def restore(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        code = launcher.main(["restore", *argv, "--data", str(self.data)], out=out, err=err, home=Path(self._tmp.name),
                             onedrive_roots=[])
        return code, out.getvalue(), err.getvalue()

    def test_it_is_refused_while_a_clark_is_open_and_changes_nothing(self):
        first, port1 = self.start()
        self.assert_up(port1, first)
        code, out, err = self.restore("clark-20260101T000000Z-daily.db")
        self.assertEqual((code, out, err.strip()), (1, "", RESTORE_SENTENCE))
        self.assertEqual([p.name for p in self.data.rglob("*") if "replaced-" in p.name or p.name.endswith(("-restore.db", ".restoring"))], [])
        self.assertTrue(answers(port1), "the clark that was open keeps answering")

    def test_it_says_it_can_not_check_when_the_lock_can_not_be_looked_at(self):
        lock_unreadable(self)
        code, out, err = self.restore("clark-20260101T000000Z-daily.db")
        self.assertEqual((code, out, err.strip()), (1, "", cant_check(self.data, "Nothing was restored")))

    def test_listing_the_backups_is_still_allowed_while_a_clark_is_open(self):
        first, port1 = self.start()
        self.assert_up(port1, first)
        code, out, err = self.restore()
        self.assertEqual((code, err), (0, ""))

    def test_with_no_clark_open_it_goes_on_to_the_backup_and_lets_the_lock_go(self):
        self.data.mkdir()
        code, out, err = self.restore("clark-20260101T000000Z-daily.db")
        self.assertEqual(code, 1)
        self.assertNotIn(RESTORE_SENTENCE, err, "it got as far as looking for the backup")
        self.assertFalse(pl.data_lock_held(self.data), "and let the lock go")


if __name__ == "__main__":
    unittest.main()
