"""One clark to a data folder: the lock in the data folder (platform.hold_data_lock) and what refuses or reports with it.

Run: python3 dev/run_tests.py test_data_lock
The holders are real clark processes (python3 -m clark on a free port, a temporary data folder), so a second clark, a stopped
one and a killed one are the real thing. The lock file must stay empty. Nothing is opened in a browser.
"""
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

from _paths import SRC

from clark import launch, platform as pl
from clark import __main__ as launcher

SENTENCE = "clark is already open on this folder. Use that window, or close it first."


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

    def stop_all(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
            p.wait()
            for f in (p.stdout, p.stderr):
                f and f.close()

    def start(self, port=None):
        port = port or free_port()
        env = {**os.environ, "PYTHONPATH": str(SRC), "HOME": self._tmp.name}
        env.pop("CLARK_LAUNCHED", None)
        p = subprocess.Popen([sys.executable, "-m", "clark", "--data", str(self.data), "--port", str(port)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=self._tmp.name)
        self.procs.append(p)
        return p, port

    def wait_up(self, port, p):
        end = time.monotonic() + 20
        while time.monotonic() < end and p.poll() is None:
            if answers(port):
                return True
            time.sleep(0.1)
        return False


class TheLock(Base):
    def test_a_second_clark_on_the_same_folder_is_refused_and_the_first_keeps_working(self):
        first, port1 = self.start()
        self.assertTrue(self.wait_up(port1, first))
        second, port2 = self.start()
        out, err = second.communicate(timeout=20)
        self.assertEqual(second.returncode, 1)
        self.assertIn(SENTENCE, err.decode())
        self.assertFalse(answers(port2), "the second started nothing")
        self.assertIsNone(first.poll())
        self.assertTrue(answers(port1), "the first keeps answering")

    def test_the_lock_file_holds_nothing(self):
        first, port1 = self.start()
        self.assertTrue(self.wait_up(port1, first))
        self.assertEqual((self.data / pl.LOCK_NAME).read_bytes(), b"")

    def test_after_a_clean_stop_the_next_clark_starts(self):
        first, port1 = self.start()
        self.assertTrue(self.wait_up(port1, first))
        first.send_signal(signal.SIGTERM)
        first.wait(timeout=20)
        second, port2 = self.start()
        self.assertTrue(self.wait_up(port2, second), "no lock was left behind")

    def test_after_a_kill_the_next_clark_starts(self):
        first, port1 = self.start()
        self.assertTrue(self.wait_up(port1, first))
        first.kill()
        first.wait(timeout=20)
        self.assertTrue((self.data / pl.LOCK_NAME).exists(), "the file stays; the lock does not")
        second, port2 = self.start()
        self.assertTrue(self.wait_up(port2, second), "a crash leaves no stale lock")

    def test_in_one_process_a_second_hold_is_refused_until_it_is_released(self):
        self.data.mkdir()
        pl.hold_data_lock(self.data)
        self.addCleanup(pl.release_data_lock, self.data)
        with self.assertRaises(pl.PlatformError) as ctx:
            pl.hold_data_lock(self.data)
        self.assertEqual(str(ctx.exception), SENTENCE)
        pl.release_data_lock(self.data)
        pl.hold_data_lock(self.data)

    def test_a_start_that_fails_after_the_lock_lets_it_go(self):
        self.data.mkdir()
        (self.data / "clark.db").write_bytes(b"not a database at all, just text")
        err = io.StringIO()
        self.assertEqual(launcher.main(["--data", str(self.data), "--port", str(free_port())], out=io.StringIO(), err=err,
                                       serve=lambda **k: 0), 1)
        self.assertFalse(pl.data_lock_held(self.data))
        pl.hold_data_lock(self.data)
        pl.release_data_lock(self.data)


class TheLauncher(Base):
    def test_it_reports_a_clark_on_another_port_and_starts_nothing(self):
        first, port1 = self.start()
        self.assertTrue(self.wait_up(port1, first))
        said, started = [], []
        code = launch.launch(free_port(), self.data, say=said.append, start=lambda *a, **k: started.append(a),
                             health=lambda port, mark: launch.NOTHING)
        self.assertEqual(code, 1)
        self.assertEqual(said, [SENTENCE])
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


if __name__ == "__main__":
    unittest.main()
