"""#635: the first-run checks for clark on Windows in Docker (src/clark/doctor.py --docker, src/clark/platform.py).

Run: python3 dev/run_tests.py test_windows_checks
Nothing here runs Docker, netsh or Windows: the system's answers are fakes. Covered: every output of the Docker check, the
Windows forms of a OneDrive path, the port Windows keeps for itself, and the 127.0.0.1 wording. The data move is in
test_data_move.py. What only a real Windows laptop can show is the hand check in #623.
"""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import _paths  # noqa: F401
from clark import doctor, launch, platform as pl

NETSH = """
Protocol tcp Port Exclusion Ranges

Start Port    End Port
----------    --------
      5357        5357
      8700        8799
     50000       50059     *

* - Administered port exclusions.
"""


def done(stdout="", returncode=0):
    return SimpleNamespace(stdout=stdout, returncode=returncode)


def runner(result=None, error=None):
    calls = []

    def run(args, **kw):
        calls.append((list(args), kw))
        if error is not None:
            raise error
        return result
    run.calls = calls
    return run


def seen(**over):
    return doctor.Seen(**{"on": pl.WINDOWS, "environ": {}, **over})


class DockerAnswer(unittest.TestCase):
    """platform.docker_os_type: the typed command of START-HERE step 1, never through a shell, with a time limit."""

    def test_linux(self):
        run = runner(done("linux\n"))
        self.assertEqual(pl.docker_os_type(run), "linux")
        args, kw = run.calls[0]
        self.assertEqual(args, ["docker", "info", "--format", "{{.OSType}}"])
        self.assertNotIn("shell", kw)
        self.assertEqual(kw["timeout"], pl.DOCKER_WAIT)

    def test_windows(self):
        self.assertEqual(pl.docker_os_type(runner(done("Windows\r\n"))), "windows")

    def test_docker_not_started_is_none(self):
        self.assertIsNone(pl.docker_os_type(runner(done("", 1))))

    def test_docker_not_installed_is_none(self):
        self.assertIsNone(pl.docker_os_type(runner(error=FileNotFoundError(2, "no docker"))))

    def test_docker_not_answering_is_none(self):
        self.assertIsNone(pl.docker_os_type(runner(error=subprocess.TimeoutExpired("docker", 30))))


class DockerCheck(unittest.TestCase):
    """doctor.check_docker_mode: each answer's line."""

    def line(self, answer):
        return doctor.run_check(doctor.DOCKER_CHECKS[0], seen(docker_os_type=lambda: answer))

    def test_linux_is_ready(self):
        self.assertEqual(self.line("linux"), doctor.Line(doctor.READY, "Docker Desktop is running and set to Linux containers, "
                                                                     "as clark needs."))

    def test_windows_containers_says_switch(self):
        line = self.line("windows")
        self.assertEqual(line.kind, doctor.FIX)
        self.assertIn("Right-click the Docker icon, choose Switch to Linux containers", line.words)
        self.assertIn("python3 -m clark.doctor --docker again", line.words)

    def test_error_says_start_docker_desktop(self):
        line = self.line(None)
        self.assertEqual(line.kind, doctor.FIX)
        self.assertTrue(line.words.startswith("Docker Desktop isn't running. Start Docker Desktop"), line.words)

    def test_a_check_that_stops_is_said_without_a_traceback(self):
        def broken():
            raise RuntimeError("Traceback: something inside")
        line = doctor.run_check(doctor.DOCKER_CHECKS[0], seen(docker_os_type=broken))
        self.assertEqual(line, doctor.Line(doctor.NOT_CHECKED, "The Docker check couldn't finish. Run python3 -m clark.doctor again."))


class OneDriveWindowsForms(unittest.TestCase):
    """platform.onedrive_in_path reads a Windows path as Windows wherever clark runs (in the container it is Linux)."""

    def test_backslashes_and_a_business_name(self):
        self.assertEqual(str(pl.onedrive_in_path(r"C:\Users\a\OneDrive - X\clark")), r"C:\Users\a\OneDrive - X")

    def test_forward_slashes_with_a_drive_letter(self):
        self.assertEqual(str(pl.onedrive_in_path("C:/Users/a/OneDrive/clark")), r"C:\Users\a\OneDrive")

    def test_case_and_the_mac_form(self):
        self.assertEqual(str(pl.onedrive_in_path(r"d:\data\onedrive-Corp\x")), r"d:\data\onedrive-Corp")
        self.assertEqual(str(pl.onedrive_in_path("/Users/a/Library/CloudStorage/OneDrive-Corp/clark")),
                         "/Users/a/Library/CloudStorage/OneDrive-Corp")

    def test_not_in_onedrive(self):
        for path in (r"C:\Users\a\Documents\clark", "C:/clark-data", "/Users/a/clark", r"\\server\share\clark"):
            self.assertIsNone(pl.onedrive_in_path(path), path)

    def test_the_form_is_read_from_the_text(self):
        self.assertIsInstance(pl.pure_path(r"C:\Users\a"), pl.PureWindowsPath)
        self.assertIsInstance(pl.pure_path("C:/Users/a"), pl.PureWindowsPath)
        self.assertIsInstance(pl.pure_path("/Users/a"), pl.PurePosixPath)
        self.assertEqual(pl.pure_path(r"C:\Users\a\OneDrive - X\clark").name, "clark")


class ReservedPorts(unittest.TestCase):
    def test_netsh_ranges_are_read(self):
        run = runner(done(NETSH))
        self.assertEqual(pl.reserved_port_ranges(run, on=pl.WINDOWS), [(5357, 5357), (8700, 8799), (50000, 50059)])
        self.assertEqual(run.calls[0][0], ["netsh", "interface", "ipv4", "show", "excludedportrange", "protocol=tcp"])

    def test_only_windows_keeps_ports(self):
        run = runner(done(NETSH))
        self.assertEqual(pl.reserved_port_ranges(run, on=pl.MAC), [])
        self.assertEqual(run.calls, [])

    def test_netsh_failing_is_none(self):
        self.assertIsNone(pl.reserved_port_ranges(runner(done("", 1)), on=pl.WINDOWS))
        self.assertIsNone(pl.reserved_port_ranges(runner(error=FileNotFoundError(2, "no netsh")), on=pl.WINDOWS))

    def line(self, ranges, **over):
        return doctor.run_check(doctor.DOCKER_CHECKS[1], seen(reserved_ports=lambda: ranges, **over))

    def test_8766_kept_by_windows_is_to_fix(self):
        line = self.line([(8700, 8799)])
        self.assertEqual(line.kind, doctor.FIX)
        self.assertTrue(line.words.startswith("Windows keeps port 8766 for itself, so clark can't use it. Restart the computer"),
                        line.words)

    def test_8766_free_says_127_0_0_1_not_localhost(self):
        self.assertEqual(self.line([(5357, 5357), (50000, 50059)]),
                         doctor.Line(doctor.READY, "Port 8766 is free for clark. Open clark at http://127.0.0.1:8766, not "
                                                   "localhost, which can lead to a different address."))

    def test_the_port_given_is_the_one_checked(self):
        self.assertEqual(self.line([(8700, 8799)], port="9100").kind, doctor.READY)
        self.assertEqual(self.line([(8700, 8799)], environ={"CLARK_PORT": "8701"}).kind, doctor.FIX)
        self.assertEqual(self.line([], port="0").kind, doctor.FIX)

    def test_windows_not_saying_is_not_checked(self):
        line = self.line(None)
        self.assertEqual(line.kind, doctor.NOT_CHECKED)
        self.assertIn("port 8766 wasn't checked", line.words)


class DockerFlag(unittest.TestCase):
    """--docker adds the two checks; without it the doctor is as it was."""

    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="clark-home-"))
        self.addCleanup(shutil.rmtree, self.home, True)

    def run_doctor(self, argv, **over):
        lines = []
        seams = dict(on=pl.MAC, environ={}, home=self.home, app=self.home, version=(3, 9, 6), sqlite_version="3.37.0",
                     data_dir=lambda: self.home / "clark-data",
                     onedrive_roots=lambda: [], find_chrome=lambda: "/fictional/chrome", find_claude=lambda: "/fictional/bin/claude",
                     health=lambda port, mark: launch.NOTHING, free=lambda port: False,
                     docker_os_type=lambda: "linux", reserved_ports=lambda: [])
        seams.update(over)
        code = doctor.main(argv, say=lines.append, **seams)
        return code, lines

    def test_without_the_flag_docker_is_not_asked(self):
        def never():
            raise AssertionError("Docker was asked")
        code, lines = self.run_doctor([], docker_os_type=never)
        self.assertEqual(len(lines), 2 + len(doctor.CHECKS))
        self.assertNotIn("Docker", "\n".join(lines))

    def test_with_the_flag_both_checks_run(self):
        code, lines = self.run_doctor(["--docker"])
        self.assertEqual(len(lines), 2 + len(doctor.CHECKS) + len(doctor.DOCKER_CHECKS))
        self.assertIn("Ready: Docker Desktop is running and set to Linux containers, as clark needs.", lines)
        self.assertEqual(code, 0, lines)

    def test_windows_containers_fails_the_run(self):
        code, lines = self.run_doctor(["--docker"], docker_os_type=lambda: "windows")
        self.assertEqual(code, 1)
        self.assertEqual(lines[-1], "1 thing to fix before clark can start. Fix it, then run python3 -m clark.doctor again.")


if __name__ == "__main__":
    unittest.main()
