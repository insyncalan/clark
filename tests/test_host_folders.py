"""v1.1 item 625: Windows typed-path folders shared into the container (src/clark/host_folders.py), with fake host paths.

Run: python3 dev/run_tests.py test_host_folders
Nothing here needs Docker or a disk: the container and the environment are faked.
"""
import re
import unittest
from unittest import mock

from _paths import ROOT, SRC  # noqa: F401

from clark import host_folders as hf

ENV = {"CLARK_HOST": "windows",
       "CLARK_SHARE_CLIENT": "C:\\Users\\User\\OneDrive - Acme\\Clients",
       "CLARK_SHARE_BACKUP": "D:\\Backups",
       "CLARK_SHARE_FILES": "C:\\Users\\User\\Documents\\clark files"}


def container():
    return mock.patch("clark.platform.container_mode", lambda: True)


class Typed(unittest.TestCase):
    def test_a_typed_windows_path_maps_and_is_shown_back_in_windows_form(self):
        with container():
            path, shown = hf.to_container("client", "c:/users/user/onedrive - acme/clients/ABC/", ENV)
        self.assertEqual(path, "/shares/client/ABC")
        self.assertEqual(shown, "C:\\users\\user\\onedrive - acme\\clients\\ABC")
        self.assertNotIn("/", shown)

    def test_a_name_typed_in_the_wrong_case_is_spelled_as_the_share_lists_it(self):
        listing = {"/shares/client": ["Abc Ltd", "other"], "/shares/client/Abc Ltd": ["Week 43"]}
        with container(), mock.patch("clark.host_folders.os.listdir", lambda p: listing[p]):
            path, shown = hf.to_container("client", "c:\\users\\user\\onedrive - acme\\clients\\ABC LTD\\week 43", ENV)
        self.assertEqual(path, "/shares/client/Abc Ltd/Week 43")
        self.assertTrue(shown.endswith("ABC LTD\\week 43"), "the Windows form stays as typed")

    def test_a_name_the_share_does_not_list_or_lists_twice_keeps_the_typed_form(self):
        listing = {"/shares/client": ["Abc", "ABC"]}
        with container(), mock.patch("clark.host_folders.os.listdir", lambda p: listing[p]):
            self.assertEqual(hf.to_container("client", "C:\\Users\\User\\OneDrive - Acme\\Clients\\aBc", ENV)[0], "/shares/client/aBc")
        with container(), mock.patch("clark.host_folders.os.listdir", side_effect=OSError):
            self.assertEqual(hf.to_container("client", "C:\\Users\\User\\OneDrive - Acme\\Clients\\New\\x", ENV)[0], "/shares/client/New/x")

    def test_the_shared_folder_itself_maps_to_its_mount(self):
        with container():
            self.assertEqual(hf.to_container("backup", "d:\\backups", ENV)[0], "/shares/backup")

    def test_a_path_that_is_not_shared_in_is_refused_in_plain_words(self):
        with container():
            for typed in ("C:\\Other", "E:\\Backups", "C:\\Users\\User\\OneDrive - Acme\\Clientsold", "C:\\Users\\User"):
                with self.assertRaises(ValueError) as cm:
                    hf.to_container("client", typed, ENV)
                self.assertTrue(str(cm.exception).endswith("Nothing was changed."), typed)
                self.assertIn("shared", str(cm.exception))

    def test_a_folder_shared_for_another_use_is_not_taken(self):
        with container(), self.assertRaises(ValueError):
            hf.to_container("backup", "C:\\Users\\User\\OneDrive - Acme\\Clients", ENV)

    def test_text_that_is_not_a_full_windows_path_is_refused(self):
        bad = ("", "Clients", "/shares/client", "\\\\server\\share\\x", "\\\\?\\C:\\x", "C:", "C:x", "1:\\x", "C:\\a\\..\\b",
               "C:\\a\\.\\b", "C:\\a?\\b", "C:\\a\\b.", "C:\\a:b", None, 5)
        with container():
            for typed in bad:
                with self.assertRaises(ValueError, msg=repr(typed)):
                    hf.to_container("client", typed, ENV)

    def test_a_dot_dot_cannot_climb_out(self):
        with container(), self.assertRaises(ValueError):
            hf.to_container("client", "C:\\Users\\User\\OneDrive - Acme\\Clients\\..\\..\\Secret", ENV)

    def test_a_slot_with_nothing_shared_says_so(self):
        env = {"CLARK_HOST": "windows"}
        with container(), self.assertRaises(ValueError) as cm:
            hf.to_container("client", "C:\\x", env)
        self.assertEqual(str(cm.exception), hf.NOT_SHARED_AT_ALL)


class CheckInside(unittest.TestCase):
    """item 625: check_inside called directly, with a real folder as the share root (no paste route)."""

    def setUp(self):
        import os, shutil, tempfile
        self.base = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.base, True)
        self.share = os.path.join(self.base, "share")
        os.makedirs(os.path.join(self.share, "ABC"))
        os.makedirs(os.path.join(self.base, "share-other"))

    def check(self, real):
        with mock.patch.object(hf, "share_root", return_value=self.share):
            hf.check_inside("client", real, "C:\\Shared\\x")

    def test_the_share_itself_and_a_folder_below_it_pass(self):
        self.check(self.share)
        self.check(self.share + "/ABC")

    def test_a_folder_outside_the_share_is_refused_with_the_not_shared_sentence(self):
        with self.assertRaises(ValueError) as cm:
            self.check(self.base)
        self.assertEqual(str(cm.exception), hf.NOT_SHARED.format(folder=hf.platform.host_shown("C:\\Shared\\x")))

    def test_a_sibling_whose_name_starts_with_the_share_name_is_refused(self):
        with self.assertRaises(ValueError):
            self.check(self.base + "/share-other")


class WithinDriveLetter(unittest.TestCase):
    """item 625: the same folder names on another drive are not inside the shared folder (the drive letter is compared, its case is not)."""

    def test_the_same_path_on_another_drive_is_not_inside(self):
        self.assertIsNone(hf._within(hf._parse("C:\\Share\\x"), hf._parse("D:\\Share\\x")))

    def test_the_same_drive_in_another_letter_case_is_inside(self):
        self.assertEqual(hf._within(hf._parse("C:\\Share"), hf._parse("c:\\share\\x")), ["x"])


class Setting(unittest.TestCase):
    def test_nothing_is_on_without_the_setting_or_outside_a_container(self):
        with container():
            self.assertEqual(hf.shares({k: v for k, v in ENV.items() if k != "CLARK_HOST"}), {})
            self.assertEqual(hf.shares(dict(ENV, CLARK_HOST="mac")), {})
        self.assertFalse(hf.windows_host(ENV))
        self.assertEqual(hf.shares(ENV), {})

    def test_a_share_that_is_not_a_full_path_is_ignored(self):
        with container():
            self.assertEqual(list(hf.shares(dict(ENV, CLARK_SHARE_CLIENT="Clients", CLARK_SHARE_BACKUP="//srv/x"))), ["files"])


class Saved(unittest.TestCase):
    def test_a_saved_file_is_named_in_windows_form_without_the_user_name(self):
        with container():
            said = hf.saved_words("/shares/files/ABC/report.html", ENV)
        self.assertEqual(said, "Saved as ~\\Documents\\clark files\\ABC\\report.html.")
        self.assertNotIn("User", said)
        self.assertNotIn("/", said)

    def test_the_client_copy_is_named_in_the_client_folder_and_never_a_data_folder(self):
        with container():
            self.assertIn("\\Clients\\ABC\\r.html", hf.windows_form("/shares/client/ABC/r.html", ENV))
            for path in ("/data/r.html", "/data/backups/r.html", "/clark/r.html", "/shares/clientx/r.html", "/shares/client/../../data/r.html"):
                self.assertIsNone(hf.windows_form(path, ENV), path)
                self.assertIsNone(hf.saved_words(path, ENV), path)

    def test_nothing_is_said_off_the_windows_route(self):
        self.assertIsNone(hf.saved_words("/shares/files/a.html", {}))

    def test_a_mount_point_is_never_the_data_folder(self):
        targets = [t for _n, t in hf.SLOTS.values()]
        self.assertEqual(len(set(targets)), len(targets))
        for t in targets:
            self.assertTrue(t.startswith("/shares/"))


class Words(unittest.TestCase):
    def test_the_new_sentences_are_plain(self):
        for text in (hf.NOT_SHARED, hf.NOT_A_PATH, hf.NOT_SHARED_AT_ALL, hf.SAVED):
            self.assertFalse(text.lower().startswith("clark"))
            self.assertNotRegex(text, r"(?i)docker|container|mount|volume|compose|/shares")

    def test_nothing_mac_only_is_in_the_module(self):
        src = (SRC / "clark" / "host_folders.py").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"Library/|\.command|Terminal|Finder", src))


if __name__ == "__main__":
    unittest.main()
