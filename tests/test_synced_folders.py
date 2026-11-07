"""Step 6 of row 836: a data folder inside Dropbox, iCloud Drive or Google Drive is found like one inside OneDrive.

Run: python3 dev/run_tests.py test_synced_folders
Everything is a temporary folder standing in for the home folder: no real Dropbox, iCloud or Google Drive is read.
"""
import tempfile
import shutil
import unittest
from pathlib import Path

from _paths import ROOT  # noqa: F401

from clark import doctor, launch, platform as pl

PLACES = (
    ("Dropbox", "Dropbox"),
    ("Dropbox", "Dropbox (Fictional Ltd)"),
    ("Dropbox", "Library/CloudStorage/Dropbox"),
    ("iCloud Drive", "Library/Mobile Documents"),
    ("iCloud Drive", "Library/Mobile Documents/com~apple~CloudDocs"),
    ("Google Drive", "Library/CloudStorage/GoogleDrive-fictional@example.org"),
    ("Google Drive", "Library/CloudStorage/GoogleDrive-fictional@example.org/My Drive"),
    ("Google Drive", "Google Drive"),
    ("Google Drive", "My Drive"),
)


class Case(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="clark-home-")).resolve()
        self.addCleanup(shutil.rmtree, self.home, True)

    def seen(self, folder):
        return doctor.Seen(data=str(folder), on=pl.MAC, home=self.home, environ={}, app=self.home, version=(3, 9, 6),
                           sqlite_version="3.37.0")


class Roots(Case):
    def test_none_when_none_are_there(self):
        self.assertEqual(pl.synced_roots(self.home, on=pl.MAC), [])

    def test_each_usual_place_is_found_by_its_service(self):
        for service, place in PLACES:
            with self.subTest(place=place):
                inside = self.home / place / "clark"
                inside.mkdir(parents=True)
                self.assertEqual(pl.inside_synced(inside, pl.synced_roots(self.home, on=pl.MAC))[0], service)
                shutil.rmtree(self.home / place.split("/")[0])

    def test_a_folder_beside_them_is_not_inside(self):
        (self.home / "Dropbox").mkdir()
        (self.home / "Dropboxes-of-notes").mkdir()
        elsewhere = self.home / "Documents" / "clark"
        elsewhere.mkdir(parents=True)
        self.assertIsNone(pl.inside_synced(elsewhere, pl.synced_roots(self.home, on=pl.MAC)))
        self.assertIsNone(pl.inside_synced(self.home / "Dropbox-not", pl.synced_roots(self.home, on=pl.MAC)))

    def test_a_link_into_one_is_followed(self):
        (self.home / "Dropbox").mkdir()
        link = self.home / "data"
        link.symlink_to(self.home / "Dropbox")
        self.assertEqual(pl.inside_synced(link, pl.synced_roots(self.home, on=pl.MAC))[0], "Dropbox")

    def test_not_the_mac_is_not_built_yet_and_a_container_finds_nothing(self):
        with self.assertRaises(pl.NotBuiltYet):
            pl.synced_roots(self.home, on=pl.WINDOWS)


class Refusal(Case):
    def test_each_place_is_refused_by_name(self):
        for service, place in PLACES:
            with self.subTest(place=place):
                inside = self.home / place / "clark"
                inside.mkdir(parents=True)
                with self.assertRaises(pl.PlatformError) as caught:
                    pl.check_data_dir(inside, roots=[], synced=pl.synced_roots(self.home, on=pl.MAC))
                self.assertIn(f"because it is inside {service}.", str(caught.exception))
                shutil.rmtree(self.home / place.split("/")[0])

    def test_a_folder_elsewhere_is_fine(self):
        (self.home / "Dropbox").mkdir()
        folder = self.home / "Documents" / "clark"
        folder.mkdir(parents=True)
        self.assertEqual(pl.check_data_dir(folder, roots=[], synced=pl.synced_roots(self.home, on=pl.MAC)), folder)

    def test_backups_are_not_refused_here(self):
        (self.home / "Dropbox").mkdir()
        folder = self.home / "Dropbox" / "backups"
        folder.mkdir()
        self.assertEqual(pl.check_data_dir(folder, roots=[], what="backups", synced=pl.synced_roots(self.home, on=pl.MAC)), folder)

    def test_onedrive_is_still_said_as_before(self):
        root = self.home / "Library" / "CloudStorage" / "OneDrive-Fictional Ltd"
        root.mkdir(parents=True)
        with self.assertRaises(pl.PlatformError) as caught:
            pl.check_data_dir(root / "clark", roots=[root], synced=[])
        self.assertIn("because it is inside OneDrive (OneDrive-Fictional Ltd).", str(caught.exception))


class Doctor(Case):
    def test_ready_when_elsewhere(self):
        line = doctor.check_data_not_in_synced_folder(self.seen(self.home / "Documents" / "clark"))
        self.assertEqual(line, doctor.Line(doctor.READY, "Your clark data isn't inside Dropbox, iCloud Drive or Google Drive."))

    def test_fix_for_each_place_without_the_folders_own_name(self):
        for service, place in PLACES:
            with self.subTest(place=place):
                inside = self.home / place / "clark"
                inside.mkdir(parents=True)
                line = doctor.check_data_not_in_synced_folder(self.seen(inside))
                self.assertEqual(line.kind, doctor.FIX)
                self.assertEqual(line.words, f"Your clark data is set to go in {pl.with_tilde(inside, self.home)}, which is "
                                             f"inside {service}. It copies files while they are being written, which damages "
                                             "the data. Choose a folder on this computer that it doesn't sync.")
                shutil.rmtree(self.home / place.split("/")[0])

    def test_it_is_a_required_check_and_the_onedrive_one_is_unchanged(self):
        names = {check.run: check for check in doctor.CHECKS}
        self.assertTrue(names[doctor.check_data_not_in_synced_folder].required)
        self.assertIn(doctor.check_data_not_in_onedrive, names)

    def test_the_whole_doctor_fails_for_dropbox(self):
        inside = self.home / "Dropbox" / "clark"
        inside.mkdir(parents=True)
        lines = []
        code = doctor.main(["--data", str(inside)], say=lines.append, on=pl.MAC, home=self.home, environ={}, app=self.home,
                           version=(3, 9, 6), sqlite_version="3.37.0", find_chrome=lambda: "/fictional/chrome",
                           find_claude=lambda: "/fictional/bin/claude", health=lambda port, mark: launch.NOTHING,
                           free=lambda port: False)
        self.assertEqual(code, 1, lines)
        self.assertEqual(len([line for line in lines if "inside Dropbox" in line]), 1, lines)


if __name__ == "__main__":
    unittest.main()
