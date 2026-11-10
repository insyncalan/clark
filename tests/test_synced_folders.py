"""Step 6 of row 836: a data folder inside Dropbox, iCloud Drive or Google Drive is found like one inside OneDrive.

Run: python3 dev/run_tests.py test_synced_folders
Everything is a temporary folder standing in for the home folder: no real Dropbox, iCloud or Google Drive is read.
"""
import os
import tempfile
import shutil
import unittest
from pathlib import Path
from unittest import mock

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

    def test_letter_case_is_ignored(self):
        for service, place in PLACES:
            for spelled in (place.lower(), place.swapcase()):
                with self.subTest(place=spelled):
                    (self.home / place).mkdir(parents=True)
                    inside = self.home / spelled / "clark"
                    roots = [(service, self.home / place)]
                    self.assertEqual(pl.inside_synced(inside, roots), (service, self.home / place))
                    self.assertIsNone(pl.inside_synced(self.home / (spelled + "-not") / "clark", roots))
                    shutil.rmtree(self.home / place.split("/")[0])

    def test_a_link_into_one_is_followed(self):
        (self.home / "Dropbox").mkdir()
        link = self.home / "data"
        link.symlink_to(self.home / "Dropbox")
        self.assertEqual(pl.inside_synced(link, pl.synced_roots(self.home, on=pl.MAC))[0], "Dropbox")

    def test_not_the_mac_is_not_built_yet_and_a_container_finds_nothing(self):
        with self.assertRaises(pl.NotBuiltYet):
            pl.synced_roots(self.home, on=pl.WINDOWS)


class Lookalikes(Case):
    def test_names_that_only_start_with_dropbox_are_not_roots(self):
        for name in ("Dropbox-old", "Dropboxes-of-notes", "DropboxArchive"):
            with self.subTest(name=name):
                inside = self.home / name / "clark"
                inside.mkdir(parents=True)
                self.assertIsNone(pl.inside_synced(inside, pl.synced_roots(self.home, on=pl.MAC)))
                pl.check_data_dir(inside, roots=[], synced=pl.synced_roots(self.home, on=pl.MAC))

    def test_dropbox_and_its_named_forms_are_roots(self):
        for name in ("Dropbox", "Dropbox (Personal)", "Dropbox - Company"):
            with self.subTest(name=name):
                inside = self.home / name / "clark"
                inside.mkdir(parents=True)
                with self.assertRaises(pl.PlatformError) as caught:
                    pl.check_data_dir(inside, roots=[], synced=pl.synced_roots(self.home, on=pl.MAC))
                self.assertIn("inside Dropbox.", str(caught.exception))
                shutil.rmtree(self.home / name)


class Guards(Case):
    def test_a_container_finds_nothing_even_with_dropbox_there(self):
        (self.home / "Dropbox").mkdir()
        with mock.patch.dict("os.environ", {"CLARK_CONTAINER": "1"}), \
                mock.patch("os.path.exists", lambda p: p == "/.dockerenv" or os.path.lexists(p)):
            self.assertTrue(pl.container_mode())
            self.assertEqual(pl.synced_roots(self.home, on="linux"), [])

    def test_not_built_yet_while_checking_is_not_a_refusal(self):
        folder = self.home / "Documents" / "clark"
        folder.mkdir(parents=True)
        with mock.patch.object(pl, "inside_synced", side_effect=pl.NotBuiltYet("not built")):
            self.assertEqual(pl.check_data_dir(folder, roots=[]), folder)

    def test_no_home_folder_finds_nothing_and_the_doctor_does_not_crash(self):
        with mock.patch("pathlib.Path.home", side_effect=RuntimeError("Could not determine home directory.")):
            self.assertEqual(pl.synced_roots(None, on=pl.MAC), [])
            self.assertEqual(pl.synced_roots(on=pl.MAC), [])
            self.assertIsNone(pl.inside_synced(self.home, pl.synced_roots(on=pl.MAC)))


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


class OneDriveCase(Case):
    def test_letter_case_is_ignored(self):
        root = self.home / "Library" / "CloudStorage" / "OneDrive-Fictional Ltd"
        root.mkdir(parents=True)
        for spelled in (str(root).lower(), str(root).swapcase()):
            with self.subTest(place=spelled):
                self.assertEqual(pl.inside_onedrive(Path(spelled) / "clark", [root]), root)
                with self.assertRaises(pl.PlatformError):
                    pl.check_data_dir(Path(spelled) / "clark", roots=[root], synced=[])
        self.assertIsNone(pl.inside_onedrive(Path(str(root).lower() + "-not") / "clark", [root]))

    def test_the_onedrive_refusals_and_doctor_line_keep_their_exact_words(self):
        root = self.home / "OneDrive"
        root.mkdir()
        inside = root / "clark"
        with self.assertRaises(pl.PlatformError) as caught:
            pl.check_data_dir(inside, roots=[root], synced=[])
        self.assertEqual(str(caught.exception),
                         f"Your data can't be kept in {pl.shown(inside)} because it is inside OneDrive (OneDrive). OneDrive "
                         "copies files while they are being written, which damages the database. Choose a folder on "
                         "this computer that OneDrive doesn't sync, and choose a backup folder in OneDrive instead (Settings \u203a "
                         "Backups \u203a Copy my backups to): backups can still go to OneDrive.")
        with self.assertRaises(pl.PlatformError) as caught:
            pl.check_data_dir(inside, roots=[root], what="backups", synced=[])
        self.assertEqual(str(caught.exception),
                         f"Backups can't be kept in {pl.shown(inside)} because it is inside OneDrive (OneDrive). OneDrive "
                         "copies files while they are being written, which damages a database. Keep them beside the "
                         "database on this computer. To have a copy in OneDrive, choose it in Settings \u203a Backups \u203a Copy my "
                         "backups to.")
        seen = doctor.Seen(data=str(inside), on=pl.MAC, home=self.home, environ={}, app=self.home, version=(3, 9, 6),
                           sqlite_version="3.37.0", onedrive_roots=lambda: [root])
        line = doctor.check_data_not_in_onedrive(seen)
        self.assertEqual(line.kind, doctor.FIX)
        self.assertEqual(line.words, f"Your clark data is set to go in {seen.tilde(inside)}, which is inside OneDrive. OneDrive "
                         "copies files while they are being written, which damages the data. Choose a folder on this computer "
                         "that OneDrive doesn't sync. Then open Terminal, type cd and a space, drag clark's folder into the "
                         f"Terminal window and press Return. Type {doctor.typed.clark('--data')} and a space, drag the folder you "
                         "chose into the window, and press Return. Backups can still go to OneDrive.")


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
                self.assertEqual(line.words, f"Your clark data is in {pl.with_tilde(inside, self.home)}, which is inside "
                                             f"{service}. {service} copies files while they are being written, which damages the "
                                             "database. Move your clark data folder to a folder on this computer that "
                                             f"{service} doesn't sync, then start clark again.")
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
