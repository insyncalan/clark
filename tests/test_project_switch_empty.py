"""Row 1092 read fix: the project button's menu is never empty. With no project listed and none open it has one row that opens Settings (source pins, no browser)."""
import re
import unittest
from pathlib import Path

SRC = (Path(__file__).resolve().parent.parent / "src" / "clark" / "page" / "src" / "edit" / "ProjectSwitch.jsx").read_text(encoding="utf-8")


class EmptyMenu(unittest.TestCase):
    def test_an_empty_list_gets_one_row_that_says_where_a_project_is_added(self):
        self.assertRegex(SRC, r'none \? \[\{ id: "__settings", name: "No project yet\. Open Settings to add one\." \}\]')

    def test_that_row_opens_settings_and_never_calls_setProject(self):
        m = re.search(r"const pick = \(id\) => \{(.*?)\n  \};", SRC, re.S)
        self.assertIsNotNone(m)
        body = m.group(1)
        self.assertLess(body.index('"__settings"'), body.index("setProject(id)"))
        self.assertIn('location.hash = "#settings"', body)
        self.assertIn("return;", body.split("setProject(id)")[0])


if __name__ == "__main__":
    unittest.main()
