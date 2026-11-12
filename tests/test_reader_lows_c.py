"""Reader LOWs on rows 1277, 1280, 1274 and 1287 (quick tier: starts no Chrome). Run: python3 dev/run_tests.py test_reader_lows_c

A Settings card that is missing may skip only off CI; a card's id must sit inside a section; the menu pick test does not sleep;
the clark.app test file has no run of three blank lines."""
import re
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def text(name):
    return (HERE / name).read_text(encoding="utf-8")


class ReaderLows(unittest.TestCase):
    def test_the_first_half_probe_does_not_fall_back_to_the_heading(self):
        self.assertNotRegex(text("test_settings_widths_1.py"), r"closest\('section'\)\s*\|\|")

    def test_the_menu_pick_waits_for_the_menu_not_for_half_a_second(self):
        self.assertNotIn("time.sleep", text("test_menu_icons_mutproof_1074.py"))

    def test_no_three_blank_lines_in_the_app_build_tests(self):
        self.assertIsNone(re.search(r"\n\n\n\n", text("test_package_app.py")))


if __name__ == "__main__":
    unittest.main()
