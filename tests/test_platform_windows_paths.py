"""#836 slice 4: where clark keeps its data on Windows, and which typed or chosen folders it takes there.

Run: python3 tests/test_platform_windows_paths.py
Pure functions over text: no Windows, no disk, no program. Every path below is a made-up string. Nothing here changes
platform.data_dir, which still says "not built yet" on Windows; these are the rules the later Windows branch will use.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from clark import platform as pl  # noqa: E402

ENV = {"LOCALAPPDATA": "C:\\Users\\Someone\\AppData\\Local", "USERPROFILE": "C:\\Users\\Someone"}


class Default(unittest.TestCase):
    def test_the_default_is_clark_in_local_app_data(self):
        self.assertEqual(pl.windows_data_default(ENV), "C:\\Users\\Someone\\AppData\\Local\\clark")

    def test_without_local_app_data_the_profile_is_used(self):
        self.assertEqual(pl.windows_data_default({"USERPROFILE": "C:\\Users\\Someone"}),
                         "C:\\Users\\Someone\\AppData\\Local\\clark")

    def test_local_app_data_wins_over_the_profile(self):
        env = {"LOCALAPPDATA": "D:\\Local", "USERPROFILE": "C:\\Users\\Someone"}
        self.assertEqual(pl.windows_data_default(env), "D:\\Local\\clark")

    def test_a_local_app_data_that_is_not_a_usable_path_falls_to_the_profile(self):
        profile = "C:\\Users\\Someone"
        for bad in ("Local", "\\\\server\\share", "", None, 7):
            with self.subTest(bad=bad):
                self.assertEqual(pl.windows_data_default({"LOCALAPPDATA": bad, "USERPROFILE": profile}),
                                 "C:\\Users\\Someone\\AppData\\Local\\clark")

    def test_a_trailing_separator_is_not_doubled(self):
        self.assertEqual(pl.windows_data_default({"LOCALAPPDATA": "D:\\Local\\"}), "D:\\Local\\clark")

    def test_nothing_known_is_none(self):
        for env in ({}, {"LOCALAPPDATA": ""}, {"LOCALAPPDATA": "Local"}, {"LOCALAPPDATA": "\\\\server\\share"},
                    {"USERPROFILE": "relative\\path"}, {"LOCALAPPDATA": None}):
            self.assertIsNone(pl.windows_data_default(env), env)

    def test_a_default_that_is_itself_refused_is_none(self):
        self.assertIsNone(pl.windows_data_default({"LOCALAPPDATA": "C:\\Users\\Someone\\OneDrive\\Local"}))

    def test_the_default_passes_the_rules(self):
        self.assertIsNone(pl.windows_folder_problem(pl.windows_data_default(ENV)))

    def test_it_never_reads_the_real_environment(self):
        with mock.patch.dict(os.environ, {"LOCALAPPDATA": "C:\\Real\\Local", "USERPROFILE": "C:\\Users\\Real"}):
            self.assertIsNone(pl.windows_data_default({}))


class Allowed(unittest.TestCase):
    def test_ordinary_folders(self):
        for text in ("C:\\clark-data", "D:\\Work\\clark data", "c:/Users/Someone/clark", "E:\\a\\b\\c\\d",
                     "C:\\Users\\Someone\\AppData\\Local\\clark", "C:\\Data.v2\\x", "C:\\caf\u00e9"):
            self.assertIsNone(pl.windows_folder_problem(text), text)

    def test_a_dot_inside_a_name_is_fine(self):
        self.assertIsNone(pl.windows_folder_problem("C:\\a.b\\c.d"))


class Refused(unittest.TestCase):
    def check(self, code, *texts):
        for text in texts:
            self.assertEqual(pl.windows_folder_problem(text), code, repr(text))

    def test_not_text_or_empty(self):
        self.check("not_absolute", None, 5, b"C:\\x", "", "   ")

    def test_not_a_full_path(self):
        self.check("not_absolute", "clark", "data\\clark", ".\\clark", "\\clark", "/clark", "C:clark", "C:", "~\\clark",
                   "%LOCALAPPDATA%\\clark")

    def test_a_network_share(self):
        self.check("network", "\\\\server\\share\\clark", "//server/share/clark", "\\\\server\\share")

    def test_a_device_or_long_path_prefix(self):
        self.check("device", "\\\\?\\C:\\clark", "\\\\.\\C:\\clark", "//?/C:/clark", "\\\\?\\UNC\\server\\share")

    def test_a_drive_on_its_own(self):
        self.check("drive_root", "C:\\", "C:/", "D:\\\\")

    def test_a_character_windows_does_not_allow(self):
        self.check("bad_character", "C:\\a<b", "C:\\a>b", "C:\\a\"b", "C:\\a|b", "C:\\a?b", "C:\\a*b", "C:\\a:b",
                   "C:\\a\x01b", "C:\\a\tb", "C:\\a\x00b", "C:\\a\x7fb")

    def test_a_device_name_in_any_part(self):
        self.check("reserved_name", "C:\\CON", "C:\\a\\nul", "C:\\Aux.txt", "C:\\com1", "C:\\LPT9\\x", "C:\\COM\u00b9",
                   "C:\\con .x", "C:\\a\\PRN.data\\b", "C:\\CONIN$", "C:\\conout$")

    def test_names_that_only_look_like_device_names(self):
        for text in ("C:\\console", "C:\\COM0", "C:\\COM10", "C:\\LPT", "C:\\nullable", "C:\\auxiliary"):
            self.assertIsNone(pl.windows_folder_problem(text), text)

    def test_a_part_ending_in_a_dot_or_space(self):
        self.check("trailing", "C:\\a.", "C:\\a \\b", "C:\\a\\b.", "C:\\a \\", "C:\\a. \\b")

    def test_a_part_that_is_all_dots_goes_up_or_stays(self):
        self.check("dot_part", "C:\\a\\..\\b", "C:\\.\\b", "C:\\a\\..", "C:\\..\\x", "C:\\a\\.")

    def test_a_part_that_is_empty_in_the_middle_is_refused(self):
        self.check("empty_part", "C:\\a\\\\b", "C:\\a//b")

    def test_one_trailing_separator_is_fine(self):
        self.assertIsNone(pl.windows_folder_problem("C:\\clark\\"))
        self.assertIsNone(pl.windows_folder_problem("C:/clark/"))

    def test_inside_onedrive_by_name(self):
        self.check("onedrive", "C:\\Users\\Someone\\OneDrive\\clark", "C:\\Users\\Someone\\OneDrive - Fictional Co\\x",
                   "C:\\Users\\Someone\\OneDrive-Fictional\\x", "C:\\Users\\Someone\\onedrive\\clark", "D:\\OneDrive")

    def test_a_name_that_only_contains_onedrive_is_fine(self):
        self.assertIsNone(pl.windows_folder_problem("C:\\notes about onedrive\\clark"))

    def test_too_long(self):
        edge = pl.WINDOWS_DATA_MAX
        ok = "C:\\" + "a" * (edge - 3)
        self.assertEqual(len(ok), edge)
        self.assertIsNone(pl.windows_folder_problem(ok))
        self.check("too_long", ok + "a", "C:\\" + "a\\" * 200)

    def test_room_is_left_for_the_files_inside(self):
        self.assertLessEqual(pl.WINDOWS_DATA_MAX + pl.WINDOWS_ROOM_BELOW, pl.MAX_PATH - 1)
        self.assertGreaterEqual(pl.WINDOWS_ROOM_BELOW, 40)

    def test_the_first_problem_found_is_the_one_given(self):
        self.check("network", "\\\\server\\share\\CON\\a<b")
        self.check("bad_character", "C:\\CON\\a<b")


class OnlyWhatItSays(unittest.TestCase):
    def test_the_data_folder_is_still_not_built_on_windows(self):
        with self.assertRaises(pl.NotBuiltYet):
            pl.data_dir(on=pl.WINDOWS)

    def test_the_codes_are_the_whole_vocabulary(self):
        self.assertEqual(set(pl.WINDOWS_FOLDER_PROBLEMS), {"not_absolute", "network", "device", "drive_root", "bad_character",
                                                          "reserved_name", "trailing", "dot_part", "empty_part", "onedrive",
                                                          "too_long"})


if __name__ == "__main__":
    unittest.main()
