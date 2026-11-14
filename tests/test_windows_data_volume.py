"""Issue 635: the Windows default data location is a named volume (docker/compose.windows.yaml), and the Docker check says so.

Run: python3 tests/test_windows_data_volume.py
Docker is never run: the override file is read as text, and the checks run on fake environments.
"""
import re
import sys
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from clark import doctor, platform as pl  # noqa: E402

OVERRIDE = (ROOT / "docker" / "compose.windows.yaml").read_text(encoding="utf-8")
BASE = (ROOT / "docker" / "compose.yaml").read_text(encoding="utf-8")
CODE = "\n".join(line for line in OVERRIDE.splitlines() if not line.lstrip().startswith("#"))
VOLUME_ENV = {"CLARK_CONTAINER": "1", "CLARK_DATA_SOURCE": "docker-volume:clark-data"}


class Override(unittest.TestCase):
    def test_data_is_a_named_volume_at_the_same_target(self):
        self.assertIn("type: volume", CODE)
        self.assertIn("source: clark-data", CODE)
        self.assertIn("target: /data", CODE)
        self.assertIn("target: /data", BASE)
        self.assertRegex(CODE, r"(?m)^volumes:\n  clark-data:")

    def test_no_mac_path_and_no_bind_mount(self):
        self.assertNotIn("Library", CODE)
        self.assertNotIn("type: bind", CODE)
        self.assertNotIn("HOME", CODE)

    def test_data_source_matches_what_the_check_reads(self):
        found = re.search(r'CLARK_DATA_SOURCE: "([^"]+)"', CODE)
        self.assertEqual(found.group(1), VOLUME_ENV["CLARK_DATA_SOURCE"])
        self.assertTrue(found.group(1).startswith(pl.DOCKER_VOLUME_PREFIX))

    def test_base_file_is_unchanged_in_meaning(self):
        self.assertIn("${HOME}/Library/Application Support/clark", BASE)


class DockerCheck(unittest.TestCase):
    def seen(self, environ):
        return doctor.Seen(data="/data", environ=environ, home="/tmp/h", on=pl.MAC)

    def test_volume_is_ready_and_names_the_volume(self):
        line = doctor.check_docker(self.seen(VOLUME_ENV))
        self.assertEqual(line.kind, doctor.READY)
        self.assertIn("Docker volume clark-data", line.words)
        self.assertNotIn("Traceback", line.words)

    def test_volume_is_never_taken_for_onedrive_or_a_synced_folder(self):
        with mock.patch.object(pl, "container_mode", lambda: True):
            self.assertIsNone(pl.container_host_in_onedrive(VOLUME_ENV))
            self.assertIsNone(pl.container_host_in_synced(VOLUME_ENV))

    def test_an_onedrive_windows_folder_still_needs_fixing(self):
        env = {"CLARK_DATA_SOURCE": "C:\\Users\\a\\OneDrive - X\\clark"}
        self.assertEqual(doctor.check_docker(self.seen(env)).kind, doctor.FIX)

    def test_nothing_named_is_not_checked(self):
        self.assertEqual(doctor.check_docker(self.seen({})).kind, doctor.NOT_CHECKED)


if __name__ == "__main__":
    unittest.main()
