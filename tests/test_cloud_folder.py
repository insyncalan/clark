"""Row 836 step 6: is a chosen data folder inside a synced cloud folder (Dropbox, iCloud Drive, Google Drive)?

Run: python3 tests/test_cloud_folder.py
The answer is a pure function of the path's text: nothing is read from the disk, so Mac and Windows paths are tested on any system.
Every name below is made up.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from clark import cloud_folder as cf  # noqa: E402

FOUND = (
    ("/Users/sam/Dropbox/clark", "Dropbox"),
    ("/Users/sam/Dropbox (Personal)/clark", "Dropbox"),
    ("/Users/sam/Library/CloudStorage/Dropbox/clark", "Dropbox"),
    ("/Users/sam/DROPBOX/clark", "Dropbox"),
    ("/Users/sam/Library/Mobile Documents/com~apple~CloudDocs/clark", "iCloud Drive"),
    ("/Users/sam/library/mobile documents/com~apple~clouddocs/clark", "iCloud Drive"),
    ("/Users/sam/Library/CloudStorage/GoogleDrive-a@b.test/My Drive/clark", "Google Drive"),
    ("/Users/sam/Google Drive/clark", "Google Drive"),
    ("/Users/sam/GOOGLE DRIVE/clark", "Google Drive"),
    ("/Users/sam/Dropbox-Team/clark", "Dropbox"),
    ("/Volumes/Work/Dropbox/clark", "Dropbox"),
    ("C:\\Users\\sam\\Dropbox\\clark", "Dropbox"),
    ("c:\\users\\sam\\dropbox (work)\\clark", "Dropbox"),
    ("C:/Users/sam/Dropbox/clark", "Dropbox"),
    ("C:\\Users\\sam\\iCloudDrive\\clark", "iCloud Drive"),
    ("C:\\Users\\sam\\ICLOUD DRIVE\\clark", "iCloud Drive"),
    ("G:\\My Drive\\clark", "Google Drive"),
    ("D:\\Google Drive\\Notes\\clark", "Google Drive"),
    ("\\\\server\\share\\Dropbox\\clark", "Dropbox"),
    ("C:\\Users\\sam\\Dropbox\\", "Dropbox"),
)
CLEAR = (
    "/Users/sam/Library/Application Support/clark", "/Users/sam/clark-data", "/Users/sam/Documents/dropboxing/clark",
    "/Users/sam/My Drives/clark", "/Users/sam/Documents/not-Google Drive-really/clark",
    "C:\\Users\\sam\\AppData\\Local\\clark", "C:\\Users\\sam\\Documents\\clark", "D:\\clark", "C:\\GoogleDriveFS\\clark",
    "/Users/sam/Library/Mobile Documents2/clark", "", "clark", "/",
)
WORDS = ("Your data can't be kept in {path} because it is inside {s}. {s} copies files while they are being written, "
         "which damages the database. Choose a folder on this computer that {s} doesn't sync.")


class Detect(unittest.TestCase):
    def test_a_folder_inside_a_synced_folder_names_the_service(self):
        for path, service in FOUND:
            with self.subTest(path):
                self.assertEqual(cf.cloud_service(path), service)

    def test_other_folders_are_clear(self):
        for path in CLEAR:
            with self.subTest(path):
                self.assertIsNone(cf.cloud_service(path))

    def test_onedrive_is_not_this_check(self):
        for path in ("/Users/sam/OneDrive/clark", "C:\\Users\\sam\\OneDrive - Fictional Ltd\\clark"):
            self.assertIsNone(cf.cloud_service(path))

    def test_nothing_is_read_from_the_disk(self):
        import os
        calls = []
        real = os.stat
        os.stat = lambda *a, **k: calls.append(a) or real(*a, **k)
        try:
            cf.cloud_service("/Users/sam/Dropbox/clark")
            cf.cloud_warning("C:\\Users\\sam\\Dropbox\\clark")
        finally:
            os.stat = real
        self.assertEqual(calls, [])

    def test_not_text_is_clear_not_a_crash(self):
        for bad in (None, 5, b"/Users/sam/Dropbox"):
            self.assertIsNone(cf.cloud_service(bad))
            self.assertIsNone(cf.cloud_warning(bad))

    def test_a_path_object_is_read_as_text(self):
        self.assertEqual(cf.cloud_service(Path("/Users/sam/Dropbox/clark")), "Dropbox")


class Sentence(unittest.TestCase):
    def test_the_words_are_the_existing_refusal_words(self):
        for path, service in FOUND:
            with self.subTest(path):
                self.assertEqual(cf.cloud_warning(path), WORDS.format(path=path, s=service))

    def test_the_shown_path_is_what_the_person_reads(self):
        self.assertEqual(cf.cloud_warning("/Users/sam/Dropbox/clark", shown="~/Dropbox/clark"), WORDS.format(path="~/Dropbox/clark", s="Dropbox"))

    def test_no_warning_for_a_clear_folder(self):
        self.assertIsNone(cf.cloud_warning("/Users/sam/clark-data"))

    def test_the_words_are_those_of_the_starter_check(self):
        from clark import starter_check as sc
        path = "/Users/sam/Dropbox/clark"
        self.assertEqual(cf.cloud_warning(path), sc.refusal(path))


if __name__ == "__main__":
    unittest.main()
