"""v1.1 item 625: the backup copy folder takes a typed Windows path that was shared in (settings.set_backup_copy_folder), with fake host
paths and the host environment injected. Off Windows the call is the same as before.

Run: python3 dev/run_tests.py test_set_backup_copy_folder_windows
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401
from clark import host_folders as hf, settings

ENV = {"CLARK_HOST": "windows", "CLARK_SHARE_BACKUP": "C:\\Users\\User\\OneDrive - Acme\\Backups"}


class Typed(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.data = self.root / "data"
        self.data.mkdir()
        self.mount = self.root / "mount"
        self.mount.mkdir()

    def run_on(self, text, env=ENV):
        slots = dict(hf.SLOTS, backup=(hf.SLOTS["backup"][0], str(self.mount)))
        with mock.patch.dict("os.environ", env, clear=False), mock.patch("clark.platform.container_mode", lambda: True), \
                mock.patch.dict(hf.SLOTS, slots):
            return settings.set_backup_copy_folder(self.data, text)

    def saved(self):
        f = self.data / settings.FILE
        return json.loads(f.read_text(encoding="utf-8")).get(settings.BACKUP_COPY_FOLDER) if f.exists() else None

    def test_a_typed_path_inside_the_share_saves_the_container_path(self):
        got = self.run_on("c:/users/user/onedrive - acme/backups/Copies")
        self.assertEqual(got, self.mount / "Copies")
        self.assertEqual(self.saved(), str(self.mount / "Copies"))
        self.assertTrue((self.mount / "Copies").is_dir())

    def test_a_path_outside_the_share_is_refused_and_nothing_is_written(self):
        with self.assertRaises(ValueError) as cm:
            self.run_on("C:\\Other")
        self.assertIn("Nothing was changed.", str(cm.exception))
        self.assertIsNone(self.saved())

    def test_flag_off_a_drive_path_is_refused_as_before(self):
        with self.assertRaises(ValueError) as cm:
            self.run_on("C:\\Users\\User\\OneDrive - Acme\\Backups", env={"CLARK_HOST": ""})
        self.assertEqual(str(cm.exception), settings.COPY_BAD)


if __name__ == "__main__":
    unittest.main()
