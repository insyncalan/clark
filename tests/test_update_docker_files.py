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
        self.assertIn("check-data --data /data && exec python3 -m clark --data /data", line, "&& so exit 2 stops the container")

    def test_update_txt_gives_typed_commands_for_the_new_folder_route(self):
        for words in ("Unzip the new download into a new folder", "docker compose -f docker/compose.yaml down",
                      "docker compose -f docker/compose.yaml up -d", "start from the newer clark folder", "SHA-256",
                      "The last 3 of these copies are kept", "Update from file in Settings does not work under Docker"):
            self.assertIn(words, UPDATE)
        self.assertNotIn("docker load", UPDATE)
        self.assertNotIn("!", UPDATE)
        self.assertNotIn("\t", UPDATE)

    def test_update_txt_ships_in_the_docker_folder_of_the_download(self):
        self.assertTrue(release_files.covers("mac", "docker/UPDATE.txt"))
        self.assertTrue(release_files.at_top("docker/UPDATE.txt"))


if __name__ == "__main__":
    unittest.main()
