"""Hostile tests for PR 950 (synced folders: Dropbox, iCloud Drive, Google Drive). Guarded: platform.py. Fictional data only.

Run: python3 dev/run_tests.py test_hostile_h950
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401
from clark import platform as pl
from test_platform_container import markers


def host(path):
    return mock.patch.dict("os.environ", {"CLARK_CONTAINER": "1", "CLARK_DATA_SOURCE": path}), markers("/.dockerenv")


class Tmp(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="clark-h950-")).resolve()
        self.addCleanup(shutil.rmtree, self.home, True)


class DropboxName(unittest.TestCase):
    def test_exact_forms(self):
        for name in ("Dropbox", "dropbox", "DROPBOX", "Dropbox (Personal)", "DROPBOX (x)", "Dropbox - Company", "dropbox -x", "Dropbox (", "Dropbox -"):
            with self.subTest(name):
                self.assertTrue(pl._dropbox_name(name))

    def test_lookalikes_and_empty(self):
        for name in ("", " ", "Dropbox-old", "Dropbox2", "Dropbox ", "Dropbox(x)", "My Dropbox", "Dropboxx", "Dropbo", "Dropbox​", "Dрopbox"):
            with self.subTest(name):
                self.assertFalse(pl._dropbox_name(name))


class ContainerHost(unittest.TestCase):
    def ask(self, path, container=True):
        env = {"CLARK_CONTAINER": "1" if container else "0", "CLARK_DATA_SOURCE": path}
        with mock.patch.dict("os.environ", env), markers("/.dockerenv"):
            return pl.container_host_in_synced()

    def test_each_service_is_named_and_the_root_returned(self):
        cases = {
            "/Users/sam/Dropbox/clark": ("Dropbox", "/Users/sam/Dropbox"),
            "/Users/sam/DROPBOX (Work)/a/b": ("Dropbox", "/Users/sam/DROPBOX (Work)"),
            "/Users/sam/Library/CloudStorage/Dropbox-Fictional/x": ("Dropbox", "/Users/sam/Library/CloudStorage/Dropbox-Fictional"),
            "/Users/sam/Library/CloudStorage/GoogleDrive-a@example.org/My Drive/x": ("Google Drive", "/Users/sam/Library/CloudStorage/GoogleDrive-a@example.org"),
            "/Users/sam/Google Drive/x": ("Google Drive", "/Users/sam/Google Drive"),
            "/Users/sam/GOOGLE DRIVE": ("Google Drive", "/Users/sam/GOOGLE DRIVE"),
            "/Users/sam/My Drive/x": ("Google Drive", "/Users/sam/My Drive"),
            "/Users/sam/Library/Mobile Documents/com~apple~CloudDocs/x": ("iCloud Drive", "/Users/sam/Library/Mobile Documents"),
            "/Users/sam/library/MOBILE DOCUMENTS": ("iCloud Drive", "/Users/sam/library/MOBILE DOCUMENTS"),
        }
        for path, (service, root) in cases.items():
            with self.subTest(path):
                self.assertEqual(self.ask(path), (service, Path(root)))

    def test_lookalikes_are_let_through(self):
        for path in ("/Users/sam/Dropbox-old/x", "/Users/sam/Dropboxes/x", "/Users/sam/Library/Application Support/Dropbox2", "/Users/sam/GoogleDrive/x",
                     "/Users/sam/Library/CloudStorage/Box/x", "/Users/sam/Mobile Documents2/x", "/Users/sam/not-Google Drive/x", "/data", "/"):
            with self.subTest(path):
                self.assertIsNone(self.ask(path))

    def test_dropbox_under_cloudstorage_only_by_prefix(self):
        self.assertEqual(self.ask("/Users/sam/Library/CloudStorage/dropboxanything/x")[0], "Dropbox")
        self.assertIsNone(self.ask("/Users/sam/other/dropboxanything/x"), "the prefix form needs CloudStorage as the parent")
        self.assertIsNone(self.ask("/dropboxanything/x"), "i == 0 must not read parts[-1]")
        self.assertIsNone(self.ask("CloudStorage/x/dropboxfoo"))
        self.assertIsNone(self.ask("dropboxfoo/CloudStorage"), "i == 0 must not wrap round to the last part")

    def test_cloudstorage_must_be_the_direct_parent(self):
        self.assertIsNone(self.ask("/Users/sam/Library/CloudStorage/x/dropbox-y"))

    def test_the_first_service_along_the_path_wins(self):
        self.assertEqual(self.ask("/Users/sam/Dropbox/My Drive/x")[0], "Dropbox")
        self.assertEqual(self.ask("/Users/sam/My Drive/Dropbox/x"), ("Google Drive", Path("/Users/sam/My Drive")))

    def test_not_in_a_container_or_without_the_variable_nothing_is_known(self):
        self.assertIsNone(self.ask("/Users/sam/Dropbox/x", container=False))
        with mock.patch.dict("os.environ", {"CLARK_CONTAINER": "1"}, clear=False), markers("/.dockerenv"):
            for value in ("", None):
                env = {"CLARK_DATA_SOURCE": value} if value is not None else {}
                self.assertIsNone(pl.container_host_in_synced(env))
        with markers():
            with mock.patch.dict("os.environ", {"CLARK_CONTAINER": "1", "CLARK_DATA_SOURCE": "/Users/sam/Dropbox"}):
                self.assertIsNone(pl.container_host_in_synced(), "the setting alone is not a container")

    def test_an_environ_argument_beats_the_process_environment(self):
        with mock.patch.dict("os.environ", {"CLARK_CONTAINER": "1", "CLARK_DATA_SOURCE": "/Users/sam/Dropbox"}), markers("/.dockerenv"):
            self.assertIsNone(pl.container_host_in_synced({"CLARK_DATA_SOURCE": "/Users/sam/clark"}))

    def test_odd_values_do_not_crash(self):
        for path in ("relative/Dropbox/x", "~/Dropbox", "//Dropbox//x", "/Users/sam/Dropbox/../x", "/üser/Dröpbox", "/" + "a/" * 5000 + "Dropbox", "\x01", " "):
            with self.subTest(path[:30]):
                self.ask(path)

    def test_check_data_dir_names_the_mac_folder_and_service(self):
        a, b = host("/Users/sam/Library/CloudStorage/GoogleDrive-a@example.org/clark")
        with a, b:
            with self.assertRaises(pl.PlatformError) as e:
                pl.check_data_dir("/data")
        self.assertIn("Google Drive", str(e.exception))
        self.assertIn("GoogleDrive-a@example.org", str(e.exception))
        self.assertNotIn("/data", str(e.exception))

    def test_onedrive_wins_over_synced_when_both_are_named(self):
        a, b = host("/Users/sam/Dropbox/OneDrive/clark")
        with a, b:
            with self.assertRaises(pl.PlatformError) as e:
                pl.check_data_dir("/data")
        self.assertIn("OneDrive", str(e.exception))

    def test_explicit_synced_argument_skips_the_container_name_check(self):
        a, b = host("/Users/sam/Dropbox/clark")
        with a, b:
            self.assertEqual(pl.check_data_dir("/data", roots=[], synced=[]), Path("/data").resolve())

    def test_unreadable_path_in_the_synced_check_fails_open(self):
        with mock.patch.object(pl, "inside_synced", side_effect=PermissionError("denied")):
            self.assertEqual(pl.check_data_dir("/data", roots=[], synced=[("Dropbox", Path("/x"))]), Path("/data").resolve())

    def test_backups_are_never_refused_by_a_synced_name(self):
        a, b = host("/Users/sam/Dropbox/clark")
        with a, b:
            self.assertEqual(pl.check_data_dir("/data", roots=[], what="backups"), Path("/data").resolve())


class InsideSynced(Tmp):
    def test_the_root_itself_is_inside_but_a_sibling_prefix_is_not(self):
        root = self.home / "Dropbox"
        root.mkdir()
        (self.home / "Dropbox2").mkdir()
        (self.home / "Drop").mkdir()
        roots = [("Dropbox", root)]
        self.assertEqual(pl.inside_synced(root, roots), ("Dropbox", root))
        self.assertIsNone(pl.inside_synced(self.home / "Dropbox2", roots))
        self.assertIsNone(pl.inside_synced(self.home / "Drop", roots))
        self.assertIsNone(pl.inside_synced(self.home, roots), "the parent of a root is not inside it")

    def test_empty_roots_none_and_unicode(self):
        self.assertIsNone(pl.inside_synced(self.home, []))
        self.assertIsNone(pl.inside_synced(self.home, ()))
        odd = self.home / "Dropbox" / "däta ☃ \U0001f600"
        odd.mkdir(parents=True)
        self.assertEqual(pl.inside_synced(odd, [("Dropbox", self.home / "Dropbox")])[0], "Dropbox")

    def test_a_nonexistent_root_does_not_crash(self):
        self.assertIsNone(pl.inside_synced(self.home, [("Dropbox", self.home / "no" / "such")]))

    def test_the_first_matching_root_is_returned(self):
        (self.home / "A").mkdir()
        roots = [("Dropbox", self.home / "A"), ("Google Drive", self.home)]
        self.assertEqual(pl.inside_synced(self.home / "A", roots)[0], "Dropbox")

    def test_bad_paths_give_none(self):
        roots = [("Dropbox", self.home)]
        for bad in ("\x00", "~nosuchuser_h950/x"):
            with self.subTest(bad):
                self.assertIsNone(pl.inside_synced(bad, roots))

    def test_a_link_out_of_dropbox_to_elsewhere_is_not_inside(self):
        (self.home / "Dropbox").mkdir()
        (self.home / "local").mkdir()
        (self.home / "Dropbox" / "out").symlink_to(self.home / "local")
        self.assertIsNone(pl.inside_synced(self.home / "Dropbox" / "out", [("Dropbox", self.home / "Dropbox")]))


class WindowsInfoJson(Tmp):
    def env(self, info, var="APPDATA", raw=None):
        d = self.home / "appdata" / "Dropbox"
        d.mkdir(parents=True, exist_ok=True)
        (d / "info.json").write_text(raw if raw is not None else json.dumps(info), encoding="utf-8")
        return {var: str(self.home / "appdata")}

    def roots(self, environ):
        return pl._windows_dropbox_roots(environ)

    def test_crafted_json_shapes_refuse_nothing_and_do_not_crash(self):
        real = self.home / "real"
        real.mkdir()
        for info in ([], [1, 2], "x", 5, None, {}, {"personal": None}, {"personal": []}, {"personal": {}}, {"personal": {"path": ""}},
                     {"personal": {"path": 5}}, {"personal": {"path": None}}, {"personal": {"path": ["x"]}}, {"personal": "path"},
                     {"personal": {"path": str(self.home / "missing")}}, {"personal": {"path": "\x00"}}):
            with self.subTest(info=repr(info)[:50]):
                self.assertEqual(self.roots(self.env(info)), [])
        self.assertEqual(self.roots(self.env({"personal": {"path": str(real)}})), [("Dropbox", real)])

    def test_bad_bytes_and_huge_files(self):
        for raw in ("", "{", "﻿{}", "nan"):
            with self.subTest(raw[:10]):
                self.assertEqual(self.roots(self.env(None, raw=raw)), [])
        d = self.home / "appdata" / "Dropbox"
        (d / "info.json").write_bytes(b"\xff\xfe\x00bad")
        self.assertEqual(self.roots({"APPDATA": str(self.home / "appdata")}), [])

    def test_deeply_nested_json_refuses_nothing(self):
        # On some Python versions json.loads raises RecursionError for this file; it must not crash the doctor or the data folder check.
        self.assertEqual(self.roots(self.env(None, raw='{"a": ' * 20000)), [])

    def test_recursion_error_from_the_parser_is_caught(self):
        # The parser's behaviour differs between Python versions, so force the error to keep this covered on all of them.
        with mock.patch("json.loads", side_effect=RecursionError):
            self.assertEqual(self.roots(self.env(None, raw="{}")), [])

    def test_info_json_a_directory_does_not_crash(self):
        d = self.home / "appdata" / "Dropbox" / "info.json"
        d.mkdir(parents=True)
        self.assertEqual(self.roots({"APPDATA": str(self.home / "appdata")}), [])

    def test_both_variables_and_duplicates_are_listed_once(self):
        real = self.home / "real"
        real.mkdir()
        env = self.env({"personal": {"path": str(real)}, "business": {"path": str(real)}})
        env["LOCALAPPDATA"] = env["APPDATA"]
        self.assertEqual(self.roots(env), [("Dropbox", real)])

    def test_empty_variables_and_userprofile_lookalikes(self):
        self.assertEqual(self.roots({}), [])
        self.assertEqual(self.roots({"APPDATA": "", "LOCALAPPDATA": "", "USERPROFILE": ""}), [])
        for name in ("Dropbox-old", "Dropbox2", "MyDropbox"):
            (self.home / name).mkdir()
        self.assertEqual(self.roots({"USERPROFILE": str(self.home)}), [])
        (self.home / "Dropbox (Team)").mkdir()
        self.assertEqual(self.roots({"USERPROFILE": str(self.home)}), [("Dropbox", self.home / "Dropbox (Team)")])

    def test_a_missing_userprofile_dir_is_fine(self):
        self.assertEqual(self.roots({"USERPROFILE": str(self.home / "nope")}), [])


class MacRoots(Tmp):
    def test_dropbox_files_and_lookalike_folders_in_the_home(self):
        (self.home / "Dropbox").write_text("a file, not a folder")
        (self.home / "Dropbox-old").mkdir()
        (self.home / "Dropboxes").mkdir()
        self.assertEqual(pl.synced_roots(self.home, on=pl.MAC), [])

    def test_cloudstorage_globs_pick_only_the_named_prefixes(self):
        s = self.home / "Library" / "CloudStorage"
        for name in ("GoogleDrive", "googledrive-x", "Box-x", "Dropbox", "Dropbox-A"):
            (s / name).mkdir(parents=True)
        got = [(svc, p.name) for svc, p in pl.synced_roots(self.home, on=pl.MAC)]
        self.assertEqual(sorted(got), [("Dropbox", "Dropbox"), ("Dropbox", "Dropbox-A")])

    def test_unicode_and_odd_home(self):
        home = self.home / "höme ☃"
        (home / "Dropbox").mkdir(parents=True)
        self.assertEqual(pl.synced_roots(home, on=pl.MAC), [("Dropbox", home / "Dropbox")])
        self.assertEqual(pl.synced_roots(str(home), on=pl.MAC), [("Dropbox", home / "Dropbox")])

    def test_a_dangling_icloud_desktop_link_does_not_crash(self):
        cloud = self.home / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
        cloud.mkdir(parents=True)
        (self.home / "Desktop").symlink_to(self.home / "gone")
        (cloud / "Documents").mkdir()
        (self.home / "Documents").mkdir()
        self.assertEqual([s for s, _ in pl.synced_roots(self.home, on=pl.MAC)], ["iCloud Drive"])

    def test_the_same_inode_desktop_is_refused_and_a_copy_is_not(self):
        cloud = self.home / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
        (cloud / "Desktop").mkdir(parents=True)
        (cloud / "Documents").mkdir()
        (self.home / "Documents").mkdir()
        self.assertIsNone(pl.inside_synced(self.home / "Documents" / "x", [("iCloud Drive", self.home / "nonexistent")]))
        (self.home / "Desktop").symlink_to(cloud / "Desktop")
        self.assertIsNotNone(pl.inside_synced(self.home / "Desktop", pl.synced_roots(self.home, on=pl.MAC)))

    def test_unknown_system_raises_and_windows_never_reads_a_mac_home(self):
        with self.assertRaises(pl.NotBuiltYet):
            pl.synced_roots(self.home, on="plan9")
        (self.home / "Library" / "CloudStorage" / "Dropbox").mkdir(parents=True)
        self.assertEqual(pl.synced_roots(self.home, on=pl.WINDOWS, environ={}), [])


class OneDriveCaseFold(Tmp):
    def test_prefix_part_boundaries_and_case(self):
        root = self.home / "OneDrive"
        (self.home / "OneDrive2").mkdir()
        (root / "x").mkdir(parents=True)
        self.assertEqual(pl.inside_onedrive(self.home / "ONEDRIVE" / "x", [root]), root)
        self.assertIsNone(pl.inside_onedrive(self.home / "OneDrive2", [root]))
        self.assertEqual(pl.inside_onedrive(root, [root]), root)
        self.assertIsNone(pl.inside_onedrive(self.home, [root]))
        self.assertIsNone(pl.inside_onedrive(self.home / "x", []))


if __name__ == "__main__":
    unittest.main()
