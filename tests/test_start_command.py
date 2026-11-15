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
BROWSER = "Google " + "Chrome"      # built from pieces so the runner does not take this plain-stub file for a browser test


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
        # A PATH of the stub folder only, so no docker, curl, Chrome or clark of this computer is ever found (a CI image has docker in /usr/bin).
        # CLARK_BROWSER names a program that does not exist, so the starter's own search (the Chrome or Edge of the computer the test runs on,
        # on a Mac runner the real /Applications one) is never reached and the stubbed `open -a` line is what the script falls back to.
        env = {"PATH": str(self.bin), "HOME": self.tmp, "LOG": str(self.log), "CLARK_DATA_DIR": f"{self.tmp}/data",
               "CLARK_BROWSER": f"{self.tmp}/no-such-browser", **extra}
        return subprocess.run([shutil.which("bash"), str(self.repo / "docker" / "start.command"), *args], env=env, capture_output=True, text=True, cwd=self.tmp, timeout=60)

    def calls(self):
        return self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []

    def test_docker_running_starts_docker_and_opens_chrome(self):
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = self.calls()
        self.assertEqual(calls[0], "docker info")
        self.assertEqual(calls[1], f"docker compose -f {self.repo}/docker/compose.yaml up -d")
        self.assertIn(f'open -a {BROWSER} http://localhost:8766', calls)
        self.assertFalse([c for c in calls if c.startswith("python3")], "Python must not start when Docker works")
        self.assertIn("clark is running in Docker.", r.stdout)
        self.assertIn("Opened clark in Chrome.", r.stdout)

    def test_a_chrome_installed_on_the_computer_does_not_change_the_stubbed_runs(self):
        """The macOS runner has a real Chrome in /Applications (here: one under HOME, which the starter also searches): the stubbed
        `open -a` line must still be what these runs log, because CLARK_BROWSER is set to a program that is not there."""
        real = Path(self.tmp) / "Applications" / "Google Chrome.app" / "Contents" / "MacOS" / "Google Chrome"
        real.parent.mkdir(parents=True)
        real.write_text("#!/bin/sh\necho real-chrome-started >> \"$LOG\"\n", encoding="utf-8")
        real.chmod(0o755)
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(f"open -a {BROWSER} http://localhost:8766", self.calls())
        self.assertNotIn("real-chrome-started", self.calls())

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
        # A docker that is installed on the computer outside the stub folder must not be found either.
        system = Path(self.tmp) / "system"
        system.mkdir()
        (system / "docker").write_text('#!/bin/sh\necho "system docker $*" >> "$LOG"\nexit 0\n', encoding="utf-8")
        (system / "docker").chmod(0o755)
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.calls(), ["python3 -m clark.launch"])

    def test_a_health_check_that_never_answers_says_so_and_still_opens_chrome(self):
        r = self.run_script(CURL_RC="1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("clark is still starting in Docker. If the page does not open, wait a minute and open http://localhost:8766 again.", r.stdout)
        self.assertIn(f"open -a {BROWSER} http://localhost:8766", self.calls())

    def test_an_empty_port_setting_means_the_usual_port(self):
        r = self.run_script(CLARK_PORT="")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(f"open -a {BROWSER} http://localhost:8766", self.calls())

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

    def old_python(self):
        # Only the 3.9 version test says "too old"; the starter check and `-m clark.launch` behave as before.
        self.stub("python3", f'case "$1" in -c) exit 1 ;; -m) echo "python3 $*" >> "$LOG"; exit 0 ;; esac\nexec {self.real_python} "$@"')

    def test_old_python_with_docker_working_still_starts_docker(self):
        self.old_python()
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("Python 3.9", r.stdout)
        self.assertEqual(self.calls()[:2], ["docker info", f"docker compose -f {self.repo}/docker/compose.yaml up -d"])

    def test_old_python_without_docker_says_how_to_install_it_and_starts_nothing(self):
        self.old_python()
        r = self.run_script(DOCKER_INFO_RC="1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("clark needs Python 3.9 or newer", r.stdout)
        self.assertEqual(self.calls(), ["docker info"], "no python start after the refusal")

    def test_a_port_set_only_in_docker_env_is_the_one_opened_and_checked(self):
        """Compose reads CLARK_PORT from docker/.env, so the window and the health check use it when the shell has none."""
        (self.repo / "docker" / ".env").write_text('CLARK_DATA_DIR=' + self.tmp + '/data\nCLARK_PORT="9123"\n', encoding="utf-8")
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = self.calls()
        self.assertIn(f"open -a {BROWSER} http://localhost:9123", calls)
        self.assertTrue([c for c in calls if c.startswith("curl") and "127.0.0.1:9123/health" in c], calls)

    def test_the_shell_port_wins_over_docker_env_and_a_bad_value_is_the_usual_port(self):
        (self.repo / "docker" / ".env").write_text("CLARK_PORT=9123\n", encoding="utf-8")
        self.run_script(CLARK_PORT="9200")
        self.assertIn(f"open -a {BROWSER} http://localhost:9200", self.calls())
        self.log.unlink()
        (self.repo / "docker" / ".env").write_text("CLARK_PORT=abc\n", encoding="utf-8")
        self.run_script()
        self.assertIn(f"open -a {BROWSER} http://localhost:8766", self.calls())

    def test_extra_words_go_on_to_compose(self):
        self.run_script("--pull", "always")
        self.assertTrue(self.calls()[1].endswith("up -d --pull always"))

    def test_the_script_asks_for_no_key_and_has_no_sleep(self):
        text = (ROOT / "docker" / "start.command").read_text(encoding="utf-8")
        self.assertNotIn("read ", text)
        self.assertNotIn("sleep", text)

    def test_a_shell_port_that_is_set_but_empty_means_the_usual_port_not_the_env_file(self):
        """Compose takes ${CLARK_PORT:-8766}: an exported empty value is the default and docker/.env is not asked."""
        (self.repo / "docker" / ".env").write_text("CLARK_PORT=9123\n", encoding="utf-8")
        self.run_script(CLARK_PORT="")
        self.assertIn(f"open -a {BROWSER} http://localhost:8766", self.calls())

    def test_the_forms_compose_accepts_for_the_port_line_are_all_taken(self):
        forms = {"export": "export CLARK_PORT=9124\n", "blanks": "  CLARK_PORT=9125\n", "comment": "CLARK_PORT=9126 # my port\n",
                 "crlf": "A=1\r\nCLARK_PORT=9127\r\nB=2\r\n", "quoted comment": "CLARK_PORT='9128' # x\n",
                 "last wins": "CLARK_PORT=9129\nCLARK_PORT=9130\n", "commented out": "# CLARK_PORT=9131\n"}
        for name, text in forms.items():
            with self.subTest(name):
                (self.repo / "docker" / ".env").write_bytes(text.encode())
                if self.log.exists():
                    self.log.unlink()
                self.run_script()
                want = {"commented out": 8766, "last wins": 9130}.get(name, int(text.split("CLARK_PORT=")[1].strip("'\"")[:4]))
                self.assertIn(f"open -a {BROWSER} http://localhost:{want}", self.calls())

    def test_reading_docker_env_leaves_globbing_and_word_splitting_as_they_were(self):
        """The .env loop turns globbing off and sets IFS to a newline; a command after it must get both back. The test puts a probe line
        into a copy of the script right after the port is settled and reads what the probe saw from the log."""
        anchor = "case \"$port\" in ''|*[!0-9]*) port=8766 ;; esac\n"
        script = self.repo / "docker" / "start.command"
        text = script.read_text(encoding="utf-8")
        self.assertEqual(text.count(anchor), 1)
        probe = ('words="one two"; { printf \'split'
                 '<%s>\' $words; echo; printf \'glob<%s>\' docker/compose.y*; echo; } >> "$LOG"\n')
        script.write_text(text.replace(anchor, anchor + probe), encoding="utf-8")
        (self.repo / "docker" / ".env").write_text("CLARK_PORT=9123\n", encoding="utf-8")
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("split<one>split<two>", self.calls())
        self.assertIn("glob<docker/compose.yaml>", self.calls())


if __name__ == "__main__":
    unittest.main()
