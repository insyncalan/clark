"""Row 1280 (source check, no browser): from 900 to 1099 px the Settings list adds no gap of its own between rows or groups,
so the space above a group heading is the heading's own margin. Reads shell.css; the browser test
test_C_the_list_has_no_gap_between_groups_at_900 in test_settings_menu_1280 measures the same thing in a real window.

Run: python3 dev/run_tests.py test_settings_menu_1280_source
"""
import re
import unittest

from _paths import ROOT

CSS = ROOT / "src" / "clark" / "page" / "shell.css"


class Source(unittest.TestCase):
    def test_the_list_gap_is_zero_from_900_to_1099(self):
        with open(CSS, encoding="utf-8") as f:
            text = f.read()
        blocks = re.findall(r"@media \(min-width: 900px\) and \(max-width: 1099px\) \{(.*)\}", text)
        self.assertEqual(len(blocks), 1, "one 900 to 1099 block holds the list rules")
        self.assertRegex(blocks[0], r"\.set-nav \{[^}]*\bgap: 0;", "from 900 to 1099 the list has gap 0")


if __name__ == "__main__":
    unittest.main()
