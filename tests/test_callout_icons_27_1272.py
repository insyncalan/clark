"""Row 1272 (owner ruling 20-11): the callout icon set is 26 icons and No icon; each new one is named, drawn, checked, and written as words.

Run: python3 dev/run_tests.py test_callout_icons_27_1272
"""
import re
import unittest

from _paths import ROOT

from clark import docx_build
from clark.excel_callout_lines import callout_lines
from clark.section_kinds import callout
from clark.section_kinds.base import Bad

NEW = {"flash": "Lightning", "eye": "Eye", "table": "Table", "gear": "Gear", "sparkle": "Sparkle", "fork": "Two ways"}
PAGE = ROOT / "src" / "clark" / "page" / "src"


class Icons27(unittest.TestCase):
    def test_count_is_27_and_no_icon(self):
        self.assertEqual(len(callout.ICONS), 27)
        self.assertEqual(callout.ICONS["none"], "No icon")
        self.assertEqual(len([k for k in callout.ICONS if k != "none"]), 26)

    def test_one_warning_triangle_only(self):
        self.assertEqual([k for k, n in callout.ICONS.items() if n == "Warning triangle"], ["warning"])
        self.assertNotIn("warn", callout.ICONS)
        self.assertNotIn("Warning", callout.ICONS.values())
        src = (PAGE / "components" / "Icon.jsx").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"^\s+warn: '<", src, re.M))
        tri = [k for k in callout.ICONS if k != "none" and re.search(rf"^\s+{k}: '<path d=\"M12 3\.5 22 20H2z", src, re.M)]
        self.assertEqual(tri, ["warning"])

    def test_new_names_spelled_as_ruled_and_no_magnifier_or_person(self):
        for k, n in NEW.items():
            self.assertEqual(callout.ICONS[k], n)
        self.assertNotIn("Magnifier", callout.ICONS.values())
        self.assertNotIn("Person", callout.ICONS.values())

    def test_page_list_matches_the_store_list(self):
        src = (PAGE / "templates" / "notes.js").read_text(encoding="utf-8")
        block = src[src.index("export const ICONS"):src.index("export const TONE_LOOK")]
        got = dict(re.findall(r'(\w+): "([^"]+)"', block))
        self.assertEqual(got, callout.ICONS)

    def test_each_new_icon_has_a_drawing(self):
        src = (PAGE / "components" / "Icon.jsx").read_text(encoding="utf-8")
        for k in NEW:
            self.assertIsNotNone(re.search(rf"^\s+{k}: '<", src, re.M), k)

    def test_round_trip_and_unknown_still_refused(self):
        for k in NEW:
            out = callout.check({"v": 1, "tone": "info", "title": "t", "icon": k}, None)
            self.assertEqual(out["icon"], k)
            self.assertEqual(callout.check(out, None)["icon"], k)
        for bad in ("search", "user", "magnifier", "person"):
            with self.assertRaises(Bad):
                callout.check({"v": 1, "tone": "info", "icon": bad}, None)

    def test_excel_line_names_each_new_icon(self):
        for k, n in NEW.items():
            got = callout_lines({"type": "callout", "content": {"v": 1, "tone": "info", "title": "ZQ", "colour": "amber", "icon": k}})
            self.assertEqual(got[1], (f"Colour: Amber. Icon: {n}.", False))

    def test_word_line_names_each_new_icon(self):
        from test_docx_callout import texts, with_callout
        for k, n in NEW.items():
            got = texts(docx_build.build(with_callout({"colour": "amber", "icon": k, "title": "ZQ", "html": "<p>w</p>"})))
            self.assertIn(f"Colour: Amber. Icon: {n}.", got)


if __name__ == "__main__":
    unittest.main()
