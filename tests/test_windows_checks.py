"""Issue 635: the first-run checks for the Windows Docker route.

Run: python3 tests/test_windows_checks.py
Docker and netsh are never run: the system calls are replaced by fakes. Nothing is written outside the process.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from clark import doctor, platform as pl  # noqa: E402

NETSH = """
Protocol tcp Port Exclusion Ranges

Start Port    End Port
----------    --------
      1234        1333
      8700        8799     *

* - Administered port exclusions.
"""


def fake(out="", code=0, boom=None):
    def run(args, **kw):
        if boom:
            raise boom
        return SimpleNamespace(stdout=out, returncode=code)
    return run


def seen(**kw):
    return doctor.Seen(data="/tmp/x", environ=kw.pop("environ", {}), home="/tmp/h", on=kw.pop("on", pl.WINDOWS), **kw)


class DockerMode(unittest.TestCase):
    def test_docker_os_reads_the_answer(self):
        self.assertEqual(pl.docker_os(fake("linux\n")), "linux")
        self.assertEqual(pl.docker_os(fake("Windows\r\n")), "windows")

    def test_docker_os_is_none_when_docker_cannot_answer(self):
        self.assertIsNone(pl.docker_os(fake("", 1)))
        self.assertIsNone(pl.docker_os(fake("something else")))
        self.assertIsNone(pl.docker_os(fake(boom=FileNotFoundError())))

    def test_each_output_of_the_check(self):
        for answer, kind, words in (("linux", doctor.READY, "running Linux containers"),
                                    ("windows", doctor.FIX, "Switch to Linux containers"),
                                    (None, doctor.FIX, "Start Docker Desktop")):
            line = doctor.check_docker_mode(seen(docker_os=lambda a=answer: a))
            self.assertEqual(line.kind, kind)
            self.assertIn(words, line.words)
            self.assertNotIn("Traceback", line.words)


class AgainCommand(unittest.TestCase):
    """The "run ... again" words of the two Docker checks give the command with --docker, so the second run repeats them."""
    def test_every_again_in_the_docker_checks_names_docker(self):
        lines = [doctor.check_docker_mode(seen(docker_os=lambda a=a: a)) for a in ("windows", None)]
        lines.append(doctor.check_port_reserved(seen(reserved_ports=lambda: [(8700, 8799)])))
        for line in lines:
            self.assertEqual(line.kind, doctor.FIX)
            self.assertIn("python3 -m clark.doctor --docker again.", line.words)
        line = doctor.run_check(doctor.DOCKER_CHECKS[1], seen(port="abc"))      # a bad port: the port check says it, this one could not finish
        self.assertEqual(line.kind, doctor.NOT_CHECKED)
        self.assertIn("python3 -m clark.doctor --docker again.", line.words)

    def test_the_command_in_a_download(self):
        from unittest import mock
        from clark import typed
        with mock.patch.object(typed, "_set", return_value=True):
            self.assertEqual(typed.doctor(docker=True), "bash clark.command --check --docker")
            self.assertEqual(typed.doctor(), "bash clark.command --check")


class ProbeWait(unittest.TestCase):
    def test_both_probes_are_given_a_time_limit(self):
        got = []

        def run(args, **kw):
            got.append(kw.get("timeout"))
            return SimpleNamespace(stdout="linux" if args[0] == "docker" else NETSH, returncode=0)
        pl.docker_os(run)
        pl.reserved_ports(run)
        self.assertEqual(got, [pl.PROBE_WAIT, pl.PROBE_WAIT])
        self.assertGreater(pl.PROBE_WAIT, 0)

    def test_a_probe_that_hangs_is_no_answer_and_stops_nothing(self):
        hang = fake(boom=subprocess.TimeoutExpired("docker", 15))
        self.assertIsNone(pl.docker_os(hang))
        self.assertIsNone(pl.reserved_ports(hang))
        line = doctor.run_check(doctor.DOCKER_CHECKS[0], seen(docker_os=lambda: pl.docker_os(hang)))
        self.assertEqual(line.kind, doctor.FIX)


class ReservedPort(unittest.TestCase):
    def test_ranges_are_read(self):
        self.assertEqual(pl.reserved_ports(fake(NETSH)), [(1234, 1333), (8700, 8799)])
        self.assertIsNone(pl.reserved_ports(fake("", 1)))
        self.assertIsNone(pl.reserved_ports(fake("no ranges")))
        self.assertEqual(pl.reserved_ports(fake(NETSH.split("1234")[0])), [])       # the table and no row: nothing is set aside
        self.assertIsNone(pl.reserved_ports(fake(boom=OSError())))

    def test_the_check(self):
        inside = doctor.check_port_reserved(seen(reserved_ports=lambda: [(8700, 8799)]))
        self.assertEqual(inside.kind, doctor.FIX)
        self.assertIn("Windows has set port 8766 aside", inside.words)
        self.assertEqual(doctor.check_port_reserved(seen(reserved_ports=lambda: [(1, 100)])).kind, doctor.READY)
        self.assertEqual(doctor.check_port_reserved(seen(port="9000", reserved_ports=lambda: [(8700, 8799)])).kind, doctor.READY)
        self.assertEqual(doctor.check_port_reserved(seen(reserved_ports=lambda: [])).kind, doctor.READY)

    def test_the_first_and_last_port_of_a_range_are_set_aside(self):
        for port in ("8700", "8799"):
            line = doctor.check_port_reserved(seen(port=port, reserved_ports=lambda: [(8700, 8799)]))
            self.assertEqual(line.kind, doctor.FIX, port)
        for port in ("8699", "8800"):
            self.assertEqual(doctor.check_port_reserved(seen(port=port, reserved_ports=lambda: [(8700, 8799)])).kind, doctor.READY, port)

    def test_an_answer_with_a_failing_exit_code_is_no_answer(self):
        self.assertIsNone(pl.reserved_ports(fake(NETSH, 1)))
        self.assertIsNone(pl.docker_os(fake("linux", 1)))
        self.assertIsNone(pl.docker_os(fake("windows", 125)))

    def test_not_windows_is_not_asked(self):
        def boom():
            raise AssertionError("asked")
        self.assertEqual(doctor.check_port_reserved(seen(on=pl.MAC, reserved_ports=boom)).kind, doctor.READY)

    def test_unreadable_list_is_not_checked_without_a_traceback(self):
        line = doctor.run_check(doctor.DOCKER_CHECKS[1], seen(reserved_ports=lambda: None))
        self.assertEqual(line.kind, doctor.NOT_CHECKED)


class DockerFlag(unittest.TestCase):
    def test_a_bad_port_is_said_once_and_the_rerun_keeps_the_flag(self):
        lines = []
        kw = dict(environ={"CLARK_CONTAINER": "1"}, home="/tmp/h", on=pl.WINDOWS, docker_os=lambda: "windows", reserved_ports=lambda: [])
        doctor.main(["--data", "/tmp/x", "--docker", "--port", "99999"], say=lines.append, **kw)
        self.assertEqual(sum("must be a whole number" in l for l in lines), 1)
        self.assertTrue(lines[-1].endswith("run python3 -m clark.doctor --docker again."), lines[-1])
        lines.clear()
        doctor.main(["--data", "/tmp/x", "--port", "99999"], say=lines.append, **kw)
        self.assertTrue(lines[-1].endswith("run python3 -m clark.doctor again."), lines[-1])

    def test_flag_adds_the_two_checks_only_when_given(self):
        lines = []
        kw = dict(environ={"CLARK_CONTAINER": "1"}, home="/tmp/h", on=pl.WINDOWS, docker_os=lambda: "linux", reserved_ports=lambda: [])
        doctor.main(["--data", "/tmp/x", "--docker"], say=lines.append, **kw)
        self.assertTrue(any("Linux containers" in l for l in lines))
        lines.clear()
        doctor.main(["--data", "/tmp/x"], say=lines.append, **kw)
        self.assertFalse(any("Linux containers" in l for l in lines))


class WindowsOneDrive(unittest.TestCase):
    def host(self, path):
        return pl.container_host_in_onedrive({"CLARK_DATA_SOURCE": path}) if self._in else None

    def setUp(self):
        self._orig = pl.container_mode
        pl.container_mode = lambda: True
        self._in = True

    def tearDown(self):
        pl.container_mode = self._orig

    def test_windows_forms_are_found(self):
        for path in (r"C:\Users\a\OneDrive - X\clark", "C:/Users/a/OneDrive/clark", r"C:\Users\a\onedrive-personal\x\clark",
                     r"\\?\C:\Users\a\OneDrive\clark"):
            with self.subTest(path):
                self.assertIsNotNone(self.host(path))

    def test_windows_folders_not_in_onedrive_are_allowed(self):
        for path in (r"C:\Users\a\clark", "C:/Users/a/Documents/not-OneDrive-really/clark", r"C:\Users\a\AppData\Local\clark"):
            with self.subTest(path):
                self.assertIsNone(self.host(path))

    def test_mac_forms_still_found(self):
        self.assertEqual(self.host("/Users/sam/OneDrive - Y/clark"), Path("/Users/sam/OneDrive - Y"))

    def test_the_refusal_names_the_folder_without_the_tenant(self):
        import os
        old = os.environ.get("CLARK_DATA_SOURCE")
        os.environ["CLARK_DATA_SOURCE"] = r"C:\Users\a\OneDrive - Fictional Ltd\clark"
        try:
            with self.assertRaises(pl.PlatformError) as e:
                pl.check_data_dir("/data", roots=[])
        finally:
            if old is None:
                del os.environ["CLARK_DATA_SOURCE"]
            else:
                os.environ["CLARK_DATA_SOURCE"] = old
        text = str(e.exception)
        self.assertIn("inside OneDrive", text)
        self.assertNotIn("Fictional", text)
        self.assertNotIn("C:\\Users\\a", text)


if __name__ == "__main__":
    unittest.main()
