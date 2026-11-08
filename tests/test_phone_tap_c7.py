"""Sweep c7: at phone width (640 px and under) the People table, the edit rows, the Settings chips, the use case list and the menus fit and are 44 px to tap.

Run: python3 dev/run_tests.py test_phone_tap_c7

Reads the style sheets only. No new words.
"""
import re
import unittest

from _paths import ROOT

PAGE = ROOT / "src" / "clark" / "page"


def phone_css(path):
    """The text of every @media (max-width: 640px) block in the file."""
    text = path.read_text(encoding="utf-8")
    out = []
    for m in re.finditer(r"@media \(max-width: 640px\)\s*\{", text):
        depth, i = 1, m.end()
        while depth:
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        out.append(text[m.end():i - 1])
    return "\n".join(out)


def rule(css, selector):
    """The declarations of the rule whose selector list holds this selector."""
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        if selector in [s.strip() for s in m.group(1).split(",")]:
            return m.group(2)
    return ""


class PhoneWidth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shell = phone_css(PAGE / "shell.css")
        cls.edit = phone_css(PAGE / "src" / "edit" / "edit.css")

    def test_people_table_does_not_run_past_the_window(self):
        self.assertIn("table-layout: fixed", rule(self.shell, "table.pp-table"))

    def test_edit_row_meta_wraps_and_its_pieces_shrink(self):
        self.assertIn("flex-wrap: wrap", rule(self.edit, ".item-rows-edit .wl-meta .cell-val"))
        self.assertIn("min-width: 0", rule(self.edit, ".item-rows-edit .wl-meta .cell-val"))
        late = rule(self.edit, ".item-rows-edit .wl-meta .late")
        self.assertIn("min-width: 0", late)
        self.assertIn("overflow-wrap: anywhere", late)

    def test_settings_chips_are_44_px(self):
        self.assertIn("min-height: 44px", rule(self.shell, ".set-chip"))

    def test_use_case_link_and_eye_are_44_px(self):
        self.assertIn("min-height: 44px", rule(self.edit, ".ucl-go"))
        eye = rule(self.edit, ".ucl-eye")
        self.assertIn("width: 44px", eye)
        self.assertIn("height: 44px", eye)

    def test_profile_menu_items_are_44_px(self):
        for sel in ('.ddmenu [role="menuitem"]', '.ddmenu [role="menuitemradio"]'):
            self.assertIn("min-height: 44px", rule(self.shell, sel), sel)
        self.assertIn("min-height: 44px", rule(self.shell, '.ddmenu [role="menuitemradio"].hp'))


if __name__ == "__main__":
    unittest.main()
