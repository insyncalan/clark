"""#633: the Docker route's update words and the compose start that runs the data check first.

Run: python3 dev/run_tests.py test_update_docker_files
Reads files only. No server, no Docker.
"""
import re
import unittest
from pathlib import Path

from _paths import SRC  # noqa: F401  (puts src/ on the path)

from clark import release_files

ROOT = Path(__file__).resolve().parent.parent
COMPOSE = (ROOT / "docker" / "compose.yaml").read_text(encoding="utf-8")
UPDATE = (ROOT / "docker" / "UPDATE.txt").read_text(encoding="utf-8")


class DockerUpdate(unittest.TestCase):
    def test_the_check_runs_before_the_server_and_a_refusal_stops_the_start(self):
        m = re.search(r'^\s*command: \["sh", "-c", "(.+)"\]$', COMPOSE, re.M)
        self.assertIsNotNone(m, "the start is one sh -c line")
        line = m.group(1)
        self.assertLess(line.index("check-data --data /data"), line.index("--port 8766"))
        self.assertIn("rc=$$?", line, "the check's own code is kept, not hidden")
        self.assertIn("exec python3 -m clark --data /data", line)

    def run_start(self, code):
        import os, subprocess, tempfile
        line = re.search(r'^\s*command: \["sh", "-c", "(.+)"\]$', COMPOSE, re.M).group(1).replace("\\\"", '"').replace("$$", "$")
        with tempfile.TemporaryDirectory() as d:
            fake = Path(d) / "python3"
            log = Path(d) / "calls.log"
            fake.write_text('#!/bin/sh\necho "python3 $*" >> "%s"\ncase "$*" in *check-data*) exit %d;; *) echo SERVER; exit 0;; esac\n' % (log, code), encoding="utf-8")
            fake.chmod(0o755)
            idle = Path(d) / "sleep"
            idle.write_text('#!/bin/sh\necho "sleep $*" >> "%s"\necho HELD\nexit 0\n' % log, encoding="utf-8")
            idle.chmod(0o755)
            env = dict(os.environ, PATH=d + os.pathsep + os.environ["PATH"])
            done = subprocess.run(["sh", "-c", line], capture_output=True, text=True, env=env)
            done.calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
            return done

    def test_a_refused_check_says_its_words_once_then_holds_the_container_and_never_starts_the_server(self):
        for code in (1, 2):
          with self.subTest(code=code):
            done = self.run_start(code)
            self.assertEqual(done.calls[0].split()[:4], ["python3", "-m", "clark", "check-data"], "the check ran first")
            self.assertIn("--data /data", done.calls[0])
            self.assertEqual(len(done.calls), 2, done.calls)
            self.assertEqual(done.calls[1], "sleep 2147483647")
            self.assertIn("HELD", done.stdout, "unless-stopped restarts any exit, 0 included, so a refusal must not exit")
            self.assertNotIn("SERVER", done.stdout)
            self.assertEqual(done.stderr.count("clark did not start"), 1)

    def test_any_other_check_code_is_passed_on_so_docker_restarts_it(self):
        for code in (137, 3):
          with self.subTest(code=code):
            done = self.run_start(code)
            self.assertEqual(done.returncode, code)
            self.assertEqual(len(done.calls), 1, "only the check ran")
            self.assertNotIn("HELD", done.stdout)
            self.assertNotIn("SERVER", done.stdout)

    def test_a_passing_check_starts_the_server(self):
        done = self.run_start(0)
        self.assertIn("SERVER", done.stdout)
        self.assertIn("check-data", done.calls[0])
        self.assertIn("--data /data", done.calls[1])

    def test_compose_restarts_unless_stopped_so_a_reboot_brings_clark_back(self):
        self.assertRegex(COMPOSE, r"(?m)^    restart: unless-stopped$")
        self.assertNotRegex(COMPOSE, r"(?m)^    restart: on-failure$")

    def test_update_txt_names_the_backups_folder_for_the_copy(self):
        self.assertIn("The copy is in the backups folder,\ninside your data folder", UPDATE)
        self.assertNotIn("in your data folder)", UPDATE)

    def test_update_txt_gives_typed_commands_for_the_new_folder_route(self):
        for words in ("Unzip the new download into a new folder", "docker compose -f docker/compose.yaml down",
                      "docker compose -f docker/compose.yaml up -d", "start from the newer clark folder", "SHA-256",
                      "clark keeps the 14 newest of these copies", "never fewer than 3", "Get-FileHash -Algorithm SHA256", "Update from file in Settings does not work under Docker"):
            self.assertIn(words, UPDATE)
        self.assertNotIn("docker load", UPDATE)
        self.assertNotIn("!", UPDATE)
        self.assertNotIn("\t", UPDATE)

    def test_update_txt_ships_in_the_docker_folder_of_the_download(self):
        self.assertTrue(release_files.covers("mac", "docker/UPDATE.txt"))
        self.assertTrue(release_files.at_top("docker/UPDATE.txt"))


if __name__ == "__main__":
    unittest.main()
