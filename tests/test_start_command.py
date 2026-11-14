"""Row 1161: docker/start.command, the double-click start. Docker first, then Python, then Chrome.

Quick tier: docker, python3, curl and open are stubs first on PATH that record what they were given. No Docker, no browser, no waiting
(the stubs answer at once; the script's own retry is curl's, which the stub replaces).
Run: python3 dev/run_tests.py test_start_command"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class StartCommand(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = Path(self.tmp) / "repo"
        for f in ("src/clark/starter_check.py", "docker/start.command", "docker/compose.yaml"):
            (self.repo / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / f, self.repo / f)
        self.bin = Path(self.tmp) / "bin"
        self.bin.mkdir()
        self.log = Path(self.tmp) / "calls.log"
        self.real_python = shutil.which("python3")
        # python3 stub: the version test passes through to the real python; the starter check too; `-m clark.launch` is only recorded.
        self.stub("python3", f'case "$1" in -m) echo "python3 $*" >> "$LOG"; exit "${{PY_RC:-0}}" ;; esac\nexec {self.real_python} "$@"')
        self.stub("docker", 'if [ "$1" = info ]; then echo "docker info" >> "$LOG"; exit "${DOCKER_INFO_RC:-0}"; fi\n'
                            'echo "docker $*" >> "$LOG"; [ "$1" = compose ] && exit "${COMPOSE_RC:-0}"; exit 0')
        self.stub("curl", 'echo "curl $*" >> "$LOG"; exit "${CURL_RC:-0}"')
        self.stub("open", 'echo "open $*" >> "$LOG"; exit "${OPEN_RC:-0}"')

    def stub(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
        path.chmod(0o755)

    def run_script(self, *args, **extra):
        # A PATH of the stubs and the system folders only, so no real docker, Chrome or clark is found.
        env = {"PATH": f"{self.bin}:/usr/bin:/bin", "HOME": self.tmp, "LOG": str(self.log), "CLARK_DATA_DIR": f"{self.tmp}/data", **extra}
        return subprocess.run(["bash", str(self.repo / "docker" / "start.command"), *args], env=env, capture_output=True, text=True, cwd=self.tmp, timeout=60)

    def calls(self):
        return self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []

    def test_docker_running_starts_docker_and_opens_chrome(self):
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = self.calls()
        self.assertEqual(calls[0], "docker info")
        self.assertEqual(calls[1], f"docker compose -f {self.repo}/docker/compose.yaml up -d")
        self.assertIn('open -a Google Chrome http://localhost:8766', calls)
        self.assertFalse([c for c in calls if c.startswith("python3")], "Python must not start when Docker works")
        self.assertIn("clark is running in Docker.", r.stdout)
        self.assertIn("Opened clark in Chrome.", r.stdout)

    def test_docker_running_but_chrome_missing_gives_the_address(self):
        r = self.run_script(OPEN_RC="1", CLARK_PORT="9000")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Chrome was not found. To use clark, open this address in your browser: http://localhost:9000", r.stdout)
        self.assertNotIn("Opened clark in Chrome.", r.stdout)

    def test_docker_not_running_falls_back_to_python(self):
        r = self.run_script(DOCKER_INFO_RC="1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.calls(), ["docker info", "python3 -m clark.launch"])
        self.assertIn("Docker is not running, so clark is starting without it.", r.stdout)

    def test_docker_missing_falls_back_to_python(self):
        (self.bin / "docker").unlink()
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.calls(), ["python3 -m clark.launch"])

    def test_a_health_check_that_never_answers_says_so_and_still_opens_chrome(self):
        r = self.run_script(CURL_RC="1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("clark is still starting in Docker. If the page does not open, wait a minute and open http://localhost:8766 again.", r.stdout)
        self.assertIn("open -a Google Chrome http://localhost:8766", self.calls())

    def test_an_empty_port_setting_means_the_usual_port(self):
        r = self.run_script(CLARK_PORT="")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("open -a Google Chrome http://localhost:8766", self.calls())

    def test_compose_failing_falls_back_to_python(self):
        r = self.run_script(COMPOSE_RC="1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.calls()[-1], "python3 -m clark.launch")
        self.assertIn("Docker could not start clark, so clark is starting without it.", r.stdout)
        self.assertFalse([c for c in self.calls() if c.startswith("open")])

    def test_python_route_hands_on_the_exit_code(self):
        r = self.run_script(DOCKER_INFO_RC="1", PY_RC="1")
        self.assertEqual(r.returncode, 1)

    def test_a_synced_data_folder_stops_before_compose_and_before_python(self):
        r = self.run_script(CLARK_DATA_DIR=f"{self.tmp}/OneDrive - Test/clark")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("inside OneDrive", r.stderr)
        self.assertEqual(self.calls(), [], "docker is not run at all before the refusal")

    def test_old_python_says_how_to_install_it_and_starts_nothing(self):
        self.stub("python3", 'exit 1')
        r = self.run_script()
        self.assertEqual(r.returncode, 1)
        self.assertIn("clark needs Python 3.9 or newer", r.stdout)
        self.assertEqual(self.calls(), [])

    def test_extra_words_go_on_to_compose(self):
        self.run_script("--pull", "always")
        self.assertTrue(self.calls()[1].endswith("up -d --pull always"))

    def test_the_script_asks_for_no_key_and_has_no_sleep(self):
        text = (ROOT / "docker" / "start.command").read_text(encoding="utf-8")
        self.assertNotIn("read ", text)
        self.assertNotIn("sleep", text)


if __name__ == "__main__":
    unittest.main()
