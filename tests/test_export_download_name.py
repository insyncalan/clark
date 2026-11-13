"""Row 1143: the Excel export is downloaded as "<project name>(<code>) YYYY.MM.DD HH.MM.SS.xlsx" (excel.download_name), in the
computer's local time, and the browser receives that name (Content-Disposition, read by publishApi.js). The import reads the
workbook's own export record, never its file name.

Run: python3 dev/run_tests.py test_export_download_name
"""
import datetime
import re
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401
from clark import excel, excel_import, platform
import test_preview_export_route as pre

WHEN = datetime.datetime(2026, 11, 13, 18, 52, 7)


class Name(unittest.TestCase):
    def test_the_format_is_name_bracketed_code_then_date_and_time_with_dots(self):
        self.assertEqual(excel.download_name("ENERGYai", "EAI", WHEN), "ENERGYai(EAI) 2026.11.13 18.52.07.xlsx")

    def test_the_time_is_zero_padded(self):
        self.assertEqual(excel.download_name("A", "B", datetime.datetime(2026, 1, 2, 3, 4, 5)), "A(B) 2026.01.02 03.04.05.xlsx")

    def test_characters_a_file_name_cannot_hold_become_a_dash(self):
        got = excel.download_name('Plan: "A/B" <v2>?', "E|I", WHEN)
        self.assertEqual(got, "Plan- -A-B- -v2--(E-I) 2026.11.13 18.52.07.xlsx")
        self.assertFalse(platform.RESERVED_CHARS.search(got))

    def test_a_long_name_is_cut_at_sixty_characters(self):
        got = excel.download_name("N" * 100, "EAI", WHEN)
        self.assertEqual(got, "N" * 60 + "(EAI) 2026.11.13 18.52.07.xlsx")

    def test_sixty_emoji_are_cut_by_bytes_so_the_file_name_fits_255(self):
        got = excel.download_name("\U0001F600" * 60, "EAI", WHEN)
        self.assertLessEqual(len(got.encode("utf-8")), 255)
        self.assertEqual(got, "\U0001F600" * 30 + "(EAI) 2026.11.13 18.52.07.xlsx")

    def test_a_byte_cut_never_splits_a_character(self):
        got = excel.download_name("a" + "\u00e9" * 100, "", WHEN)
        got.encode("utf-8")
        self.assertEqual(got, "a" + "\u00e9" * 59 + " 2026.11.13 18.52.07.xlsx")

    def test_leading_dots_are_dropped_so_the_file_is_not_hidden(self):
        self.assertEqual(excel.download_name("..hidden", "EAI", WHEN), "hidden(EAI) 2026.11.13 18.52.07.xlsx")
        self.assertEqual(excel.download_name(". .", "EAI", WHEN), "EAI 2026.11.13 18.52.07.xlsx")

    def test_a_300_character_code_is_cut_and_the_name_keeps_its_date_and_extension(self):
        got = excel.download_name("Plan", "C" * 300, WHEN)
        self.assertEqual(got, "Plan(" + "C" * 40 + ") 2026.11.13 18.52.07.xlsx")

    def test_fifty_emoji_in_the_code_and_a_long_name_still_fit_255_bytes(self):
        got = excel.download_name("\U0001F600" * 60, "\U0001F680" * 50, WHEN)
        self.assertLessEqual(len(got.encode("utf-8")), 255)
        self.assertTrue(got.endswith(") 2026.11.13 18.52.07.xlsx"))
        self.assertEqual(got.count("\U0001F680"), 40)
        got = excel.download_name("", "\U0001F680" * 50, WHEN)
        self.assertEqual(got, "\U0001F680" * 40 + " 2026.11.13 18.52.07.xlsx")

    def test_a_dotted_code_never_gives_a_hidden_file(self):
        self.assertEqual(excel.download_name("..", "..code", WHEN), "code 2026.11.13 18.52.07.xlsx")
        self.assertEqual(excel.download_name("Plan", "..code", WHEN), "Plan(code) 2026.11.13 18.52.07.xlsx")
        self.assertEqual(excel.download_name("..", ". .", WHEN), "work items 2026.11.13 18.52.07.xlsx")
        self.assertEqual(excel.download_name("", "..", WHEN), "work items 2026.11.13 18.52.07.xlsx")

    def test_invisible_and_direction_characters_are_removed(self):
        for ch in "\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\u200b\u200c\u200d\u200e\u200f\ufeff\x7f\x85\u2028\u2029":
            got = excel.download_name(f"Pl{ch}an", "EAI", WHEN)
            self.assertEqual(got, "Plan(EAI) 2026.11.13 18.52.07.xlsx", repr(ch))

    def test_a_name_of_only_invisible_characters_falls_back(self):
        self.assertEqual(excel.download_name("\u202e\u200b", "EAI", WHEN), "EAI 2026.11.13 18.52.07.xlsx")
        self.assertEqual(excel.download_name("\u202e", "", WHEN), "work items 2026.11.13 18.52.07.xlsx")

    def test_safe_name_itself_is_unchanged_for_others(self):
        self.assertEqual(platform.safe_name("a\u202eb"), "a\u202eb")

    def test_without_a_code_there_are_no_brackets(self):
        self.assertEqual(excel.download_name("ENERGYai", "", WHEN), "ENERGYai 2026.11.13 18.52.07.xlsx")
        self.assertEqual(excel.download_name("ENERGYai", None, WHEN), "ENERGYai 2026.11.13 18.52.07.xlsx")

    def test_without_a_name_the_code_stands_in_for_it(self):
        self.assertEqual(excel.download_name("", "EAI", WHEN), "EAI 2026.11.13 18.52.07.xlsx")
        self.assertEqual(excel.download_name("  ", "", WHEN), "work items 2026.11.13 18.52.07.xlsx")


class Download(pre.Case):
    def got(self):
        with mock.patch.object(self.rig.publisher, "now", lambda: WHEN):
            return pre.get(self.rig, "/api/export?project=PUB")

    def test_the_browser_is_given_the_new_name(self):
        status, r, raw = self.got()
        self.assertEqual(status, 200)
        name = self.rig.store.read("projects", ref="PUB")["name"]
        self.assertEqual(r.getheader("Content-Disposition"), f'attachment; filename="{excel.download_name(name, "PUB", WHEN)}"')
        self.assertRegex(r.getheader("Content-Disposition"), r'filename="[^"]+\(PUB\) 2026\.11\.13 18\.52\.07\.xlsx"')

    def test_a_name_outside_ascii_reaches_the_client_whole(self):
        with self.rig.store.step("dashboard", "tester") as st:
            st.update("projects", "PUB", {"name": "Énergie ☀ Plan"})
        status, r, raw = self.got()
        head = r.getheader("Content-Disposition")
        self.assertEqual(status, 200)
        head.encode("latin-1")                                       # a header is latin-1 at most
        want = excel.download_name("Énergie ☀ Plan", "PUB", WHEN)
        self.assertIn("filename*=UTF-8''" + urllib.parse.quote(want, safe=""), head)

    def test_a_workbook_with_the_old_name_and_one_with_the_new_name_both_import(self):
        _, _, raw = self.got()
        state = self.rig.data_dir / excel.STATE_FILE
        for name in ("PUB-2026-10-28.xlsx", "Bridge & -Harbour- -Programme-(PUB) 2026.11.13 18.52.07.xlsx"):
            mine = Path(self.rig.root) / name
            mine.write_bytes(raw)
            plan = excel_import.read_workbook(self.rig.store, mine, "PUB", state_path=state)
            self.assertFalse(plan.unrecorded, name)


if __name__ == "__main__":
    unittest.main()
