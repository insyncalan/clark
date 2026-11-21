"""Item 635: the Windows default data location is a bind mount of the data folder beside the clark files (docker/compose.windows.yaml).

Run: python3 tests/test_windows_data_volume.py
Docker is never run: the override file is read as text.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERRIDE = (ROOT / "docker" / "compose.windows.yaml").read_text(encoding="utf-8")
BASE = (ROOT / "docker" / "compose.yaml").read_text(encoding="utf-8")
CODE = "\n".join(line for line in OVERRIDE.splitlines() if not line.lstrip().startswith("#"))


class Override(unittest.TestCase):
    def test_data_is_a_bind_mount_at_the_same_target(self):
        self.assertIn("type: bind", CODE)
        self.assertIn("target: /data", CODE)
        self.assertIn("target: /data", BASE)

    def test_default_is_beside_the_clark_folder(self):
        found = re.search(r"source: \$\{CLARK_DATA_DIR:-([^}]+)\}", CODE)
        self.assertEqual(found.group(1), "../../clark-data")

    def test_not_a_named_volume_and_no_mac_path(self):
        self.assertNotIn("type: volume", CODE)
        self.assertNotRegex(CODE, r"(?m)^volumes:")
        self.assertNotIn("Library", CODE)
        self.assertNotIn("HOME", CODE)

    def test_data_source_is_the_same_folder_as_the_mount(self):
        found = re.search(r'CLARK_DATA_SOURCE: "\$\{CLARK_DATA_DIR:-([^}]+)\}"', CODE)
        self.assertEqual(found.group(1), "../../clark-data")

    def test_base_file_is_unchanged_in_meaning(self):
        self.assertIn("${HOME}/Library/Application Support/clark", BASE)


if __name__ == "__main__":
    unittest.main()
