"""Row 836 step 6, hardening: the whole refusal for a data folder inside Dropbox, iCloud Drive or Google Drive, word for word.

Run: python3 dev/run_tests.py test_synced_refusal_words
The refusal says the service by name twice (where it is, and which one will not sync) and shows the folder from "~" so a
person's name is not in the message. Temporary folders only.
"""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import ROOT  # noqa: F401

from clark import platform as pl


class RefusalWords(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="clark-home-")).resolve()
        self.addCleanup(shutil.rmtree, self.home, True)

    def refuse(self, place):
        inside = self.home / place / "clark"
        inside.mkdir(parents=True)
        roots = pl.synced_roots(self.home, on=pl.MAC)
        with mock.patch.object(pl.Path, "home", return_value=self.home):
            with self.assertRaises(pl.PlatformError) as caught:
                pl.check_data_dir(inside, roots=[], synced=roots)
        return str(caught.exception)

    def test_the_whole_refusal_for_each_service(self):
        for service, place in (("Dropbox", "Dropbox"), ("iCloud Drive", "Library/Mobile Documents"),
                               ("Google Drive", "Google Drive")):
            with self.subTest(service=service):
                self.assertEqual(
                    self.refuse(place),
                    f"Your data can't be kept in ~/{place}/clark because it is inside {service}. {service} copies "
                    "files while they are being written, which damages the database. Choose a folder on this "
                    f"computer that {service} doesn't sync.")
                shutil.rmtree(self.home / place.split("/")[0])

    def test_the_home_folder_is_not_spelled_out_in_it(self):
        self.assertNotIn(str(self.home), self.refuse("Dropbox"))


if __name__ == "__main__":
    unittest.main()
