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
                    "files while they are being written, which damages the database. Nothing has been changed. Move your "
                    f"clark data folder to a folder on this computer that {service} doesn't sync, then start clark again.")
                shutil.rmtree(self.home / place.split("/")[0])

    def test_a_docker_host_folder_in_each_service_is_refused_in_the_same_words(self):
        for service, path in (("Dropbox", "/Users/sam/Dropbox/clark"), ("Dropbox", "/Users/sam/Library/CloudStorage/Dropbox-Work/clark"),
                              ("Google Drive", "/Users/sam/Google Drive/clark"), ("Google Drive", "/Users/sam/My Drive/clark"),
                              ("Google Drive", "/Users/sam/Library/CloudStorage/GoogleDrive-a@b.c/My Drive/clark"),
                              ("iCloud Drive", "/Users/sam/Library/Mobile Documents/com~apple~CloudDocs/clark"),
                              ("Dropbox", "/Users/sam/dropbox (Personal)/clark")):
            with self.subTest(path=path):
                with mock.patch.dict("os.environ", {"CLARK_CONTAINER": "1", "CLARK_DATA_SOURCE": path}), \
                        mock.patch.object(pl.os.path, "exists", side_effect=lambda p: p == "/.dockerenv"):
                    with self.assertRaises(pl.PlatformError) as caught:
                        pl.check_data_dir("/data")
                self.assertEqual(
                    str(caught.exception),
                    f"Your data can't be kept in {path} because it is inside {service}. {service} copies "
                    "files while they are being written, which damages the database. Nothing has been changed. Move your "
                    f"clark data folder to a folder on this computer that {service} doesn't sync, then start clark again.")

    def test_a_docker_host_folder_with_only_a_similar_name_is_let_through(self):
        for path in ("/Users/sam/Dropbox-old/clark", "/Users/sam/Documents/my-dropbox-notes/clark", "/Users/sam/clark"):
            with self.subTest(path=path):
                with mock.patch.dict("os.environ", {"CLARK_CONTAINER": "1", "CLARK_DATA_SOURCE": path}), \
                        mock.patch.object(pl.os.path, "exists", side_effect=lambda p: p == "/.dockerenv"):
                    self.assertEqual(pl.check_data_dir("/data"), Path("/data").resolve())

    def test_the_home_folder_is_not_spelled_out_in_it(self):
        self.assertNotIn(str(self.home), self.refuse("Dropbox"))


if __name__ == "__main__":
    unittest.main()
