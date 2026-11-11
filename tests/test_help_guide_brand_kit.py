"""Row 1089: the Help guide for a brand kit (what a kit holds, the limits, the steps in Settings > Brands).

Run: python3 dev/run_tests.py test_help_guide_brand_kit
Quick tier: no browser beyond node for the page's pure functions (skips with no node), as in test_help_guides_more.py.
"""
import json
import re
import unittest

from _help_shown import LATER, RAW, shown_content
from test_help_guides import check_guides, run_node
from test_help_navigation import BANNED
from test_help_shown import AgainstThePage

GID = "the-brand-kit-guide"
GUIDE = next((g for g in shown_content()["guides"] if g["id"] == GID), None)


def words(g):
    return [g["t"], g["job"], g["result"]] + [s["d"] for s in g["steps"]]


class TheBrandKitGuide(unittest.TestCase):
    def test_it_is_shown_with_the_guide_shape(self):
        self.assertIsNotNone(GUIDE, "the guide is shipped and not held")
        self.assertEqual(check_guides(RAW), [])
        self.assertTrue(5 <= len(GUIDE["steps"]) <= 8)
        self.assertTrue(all("pic" not in s for s in GUIDE["steps"]))
        held = {"howto-" + i for i in LATER["howto"]} | {"ref-" + i for i in LATER["reference"]}
        self.assertEqual(set(GUIDE["next"]) & held, set())

    def test_it_says_what_a_kit_holds(self):
        text = " ".join(words(GUIDE))
        for part in ("clark-brand.json", "name, id and version", "file list", "colours and fonts", "logo", "cover pictures", "no other kinds of file"):
            self.assertIn(part, text, part)
        self.assertIn("Your own file names are fine", text)

    def test_it_gives_the_limits_the_server_enforces(self):
        from clark import brands
        text = " ".join(words(GUIDE))
        for part in ("50 files", "16 MB the zip", "24 MB unpacked", "5 MB a file", "o links or paths outside"):
            self.assertIn(part, text, part)
        self.assertEqual((brands.FILE_CAP, brands.ZIP_CAP >> 20, brands.TOTAL_CAP >> 20, brands.MEMBER_CAP >> 20), (50, 16, 24, 5))

    def test_the_steps_use_the_controls_the_page_has(self):
        text = " ".join(s["d"] for s in GUIDE["steps"])
        for name in ("**Settings**", "**Brands**", "**Choose zip…**", "**Review the brand in Downloads**", "**Install**", "**Replace**", "**Undo**", "**Remove**"):
            self.assertIn(name, text, name)
        norm = lambda t: re.sub(r"[‘’]", "'", t)
        code = norm(AgainstThePage.HELPCODE)
        for b in {b for t in words(GUIDE) for b in re.findall(r"\*\*(.+?)\*\*", t)}:
            self.assertIn(norm(b).strip(" .,:;…"), code, b)

    def test_banned_words_slash_dates_and_digit_dates_are_absent(self):
        for t in words(GUIDE):
            self.assertIsNone(re.search(BANNED, t))
            self.assertNotRegex(t, r"(?<!\d)\d{1,2}/\d{1,2}/\d{2,4}")
            self.assertNotRegex(t, r"\b\d{4}-\d{2}-\d{2}\b")
            self.assertNotRegex(t, r"(?i)\b(delete|deleted)\b")

    def test_search_finds_it_by_title_and_by_the_minimum_requirements_question(self):
        for q in ("brand kit", "minimum requirements"):
            r = run_node(RAW, "(() => { const idx = HL.buildIndex(); return HL.search(idx, %s).map((x) => x.id); })()" % json.dumps(q))
            self.assertIn("guide-" + GID, r, q)


if __name__ == "__main__":
    unittest.main()
