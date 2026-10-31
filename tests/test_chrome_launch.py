"""#104: no headless Chrome in clark's tests asks for the macOS login Keychain, and none outlives its test.

A headless Chrome with a throwaway profile asks the Keychain for its "Chrome Safe Storage" key unless it is started with
--use-mock-keychain and --password-store=basic: a "Keychain Not Found" dialog then appears on the person's screen. Every
launch goes through run_support.chrome_command(), and run_support stops what it started (on exit, on SIGTERM, and in the
runner's group kill). Run: python3 dev/run_tests.py test_chrome_launch
"""
import ast
import contextlib
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from _paths import ROOT

import run_support as support

LAUNCH_FLAGS = ("--headless", "--remote-debugging")
HELPER = ROOT / "dev" / "tools" / "run_support.py"
THIS = Path(__file__).resolve()
# The prototype's own self-test starts Chrome itself (outside the shared helper); it must carry both keychain flags.
OWN_LAUNCH = {Path("system") / "prototype" / "run_selftest.py"}


def python_files():
    for base in ("tests", "dev", "system"):
        for path in sorted((ROOT / base).rglob("*.py")):
            if {"vendor", "node_modules", "__pycache__"} & set(path.parts):
                continue
            yield path


def launch_strings(path):
    """The string constants in `path` that are Chrome launch flags, and all string constants (for the flag check)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    every = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    return [s for s in every if s.startswith(LAUNCH_FLAGS)], every


class EveryLaunchGoesThroughTheHelper(unittest.TestCase):
    def test_no_file_builds_its_own_chrome_command(self):
        offenders, own = [], []
        for path in python_files():
            if path in (HELPER, THIS):
                continue
            flags, every = launch_strings(path)
            if not flags:
                continue
            rel = path.relative_to(ROOT)
            if rel in OWN_LAUNCH:
                missing = [f for f in support.KEYCHAIN_FLAGS if f not in every]
                if missing:
                    own.append(f"{rel} starts Chrome itself without {', '.join(missing)}")
            else:
                offenders.append(f"{rel} starts Chrome without run_support.chrome_command()")
        self.assertEqual(offenders + own, [], "build the command with run_support.chrome_command() (#104)")

    def test_the_checker_finds_a_launch_that_skips_the_helper(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.py"
            bad.write_text('import subprocess\nsubprocess.Popen(["chrome", "--headless=new", "--remote-debugging-pipe"])\n',
                           encoding="utf-8")
            ok = Path(tmp) / "ok.py"
            ok.write_text("import run_support\ncmd = run_support.chrome_command('c', 'p')\n", encoding="utf-8")
            self.assertTrue(launch_strings(bad)[0])
            self.assertFalse(launch_strings(ok)[0])

    def test_the_browser_harness_uses_the_helper(self):
        text = (ROOT / "tests" / "test_server.py").read_text(encoding="utf-8")
        self.assertIn("start_chrome(chrome_command(", text)
        self.assertIn("stop_chrome(", text)


class TheCommand(unittest.TestCase):
    def test_both_keychain_flags_are_always_there(self):
        cmd = support.chrome_command("/x/chrome", "/tmp/profile")
        for flag in ("--use-mock-keychain", "--password-store=basic", "--headless=new", "--remote-debugging-pipe",
                     "--user-data-dir=/tmp/profile", "--no-first-run"):
            self.assertIn(flag, cmd)
        self.assertEqual(support.KEYCHAIN_FLAGS, ("--use-mock-keychain", "--password-store=basic"))
        extra = support.chrome_command("/x/chrome", "/tmp/p", "--allow-file-access-from-files")
        self.assertLess(extra.index("--allow-file-access-from-files"), extra.index("--remote-debugging-pipe"))
        self.assertTrue(set(support.KEYCHAIN_FLAGS) <= set(extra))

    def test_it_tells_chrome_there_is_a_mouse(self):
        # headless Chrome on Linux reports (hover: none) and (pointer: none) without it; faint-at-rest checks then fail
        mouse = "--blink-settings=primaryHoverType=2,availableHoverTypes=2,primaryPointerType=4,availablePointerTypes=4"
        self.assertEqual(support.MOUSE_FLAG, mouse)
        for cmd in (support.chrome_command("/x/chrome", "/tmp/p"),
                    support.chrome_command("/x/chrome", "/tmp/p", "--allow-file-access-from-files")):
            self.assertEqual(cmd.count(mouse), 1, cmd)
            self.assertEqual(len([f for f in cmd if f.startswith("--blink-settings")]), 1, cmd)

    def test_the_test_harness_starts_chrome_with_them(self):
        import test_server
        seen = []

        class Gone:
            def poll(self):
                return 0

            def wait(self, *a):
                return 0

        def fake_start(command, to_r, from_w):
            seen.append(command)
            return Gone()

        with mock.patch.object(test_server, "start_chrome", fake_start), \
                mock.patch.object(test_server, "stop_chrome", lambda proc: None):
            with test_server.chrome():
                pass
        self.assertEqual(len(seen), 1)
        self.assertTrue(set(support.KEYCHAIN_FLAGS) <= set(seen[0]), seen[0])
        self.assertIn(support.MOUSE_FLAG, seen[0])


FAKE_CHROME = 'echo $$ > "$1"; exec sleep 120'


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def wait_gone(pid, seconds=60):
    end = time.time() + seconds
    while time.time() < end:
        if not alive(pid):
            return True
        time.sleep(0.1)
    return not alive(pid)


def fake_command(pidfile):
    return ["/bin/sh", "-c", FAKE_CHROME, "fake-chrome", str(pidfile)]


class NoOrphans(unittest.TestCase):
    """The Chrome child dies with the test: stop_chrome, a normal exit, and SIGTERM (a fake Chrome is a sleeping shell)."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-chrome-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.dir, True))

    def pid_of(self, pidfile):
        end = time.time() + 60
        while time.time() < end:
            if pidfile.exists() and pidfile.read_text(encoding="utf-8").strip():
                return int(pidfile.read_text(encoding="utf-8").strip())
            time.sleep(0.05)
        self.fail("the fake Chrome did not start")

    def start(self, pidfile):
        r1, w1 = os.pipe()
        r2, w2 = os.pipe()
        proc = support.start_chrome(fake_command(pidfile), r1, w2)
        for fd in (r1, w1, r2, w2):
            os.close(fd)
        return proc

    def test_stop_chrome_stops_it_and_forgets_it(self):
        pidfile = self.dir / "pid"
        proc = self.start(pidfile)
        pid = self.pid_of(pidfile)
        self.assertIn(proc, support._LIVE)
        support.stop_chrome(proc)
        self.assertTrue(wait_gone(pid))
        self.assertNotIn(proc, support._LIVE)

    def test_stop_all_chrome_stops_what_is_left(self):
        pidfile = self.dir / "pid"
        self.start(pidfile)
        pid = self.pid_of(pidfile)
        support.stop_all_chrome()
        self.assertTrue(wait_gone(pid))

    def run_child(self, tail):
        """A separate Python starts the fake Chrome through run_support, then `tail`; returns (its process, the fake's pid)."""
        pidfile = self.dir / "pid"
        code = ("import os, sys, time\nsys.path.insert(0, sys.argv[1])\nimport run_support as s\n"
                "r1, w1 = os.pipe(); r2, w2 = os.pipe()\n"
                f"s.start_chrome({fake_command(pidfile)!r}, r1, w2)\n"
                f"while not os.path.exists({str(pidfile)!r}):\n    time.sleep(0.05)\n"       # the fake has written its pid
                f"print('started', flush=True)\n{tail}")
        proc = subprocess.Popen([sys.executable, "-c", code, str(HELPER.parent)], stdout=subprocess.PIPE, text=True)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        self.assertEqual(proc.stdout.readline().strip(), "started")
        return proc, self.pid_of(pidfile)

    def test_a_normal_exit_without_stopping_it_does_not_leave_it(self):
        proc, pid = self.run_child("")
        proc.wait(60)
        self.assertTrue(wait_gone(pid), "the Chrome outlived its test process")

    def test_sigterm_to_the_test_process_stops_it_too(self):
        proc, pid = self.run_child("import time\ntime.sleep(60)\n")
        proc.send_signal(signal.SIGTERM)
        proc.wait(60)
        self.assertTrue(wait_gone(pid), "the Chrome outlived a SIGTERM to its test process")
        self.assertEqual(proc.returncode, -signal.SIGTERM, "the signal still ends the process")


if __name__ == "__main__":
    unittest.main()
