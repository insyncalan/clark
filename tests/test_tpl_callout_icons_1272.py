"""Row 1272 AP3: the callout icon set is 27 entries (No icon plus 26 named icons), pinned by count and by name.

Reads the lists from source (callout.py, notes.js, Icon.jsx); no browser. A failure lists the missing and the extra names.
Run: python3 dev/run_tests.py test_tpl_callout_icons_1272
"""
import re
import unittest

from _paths import ROOT

from clark.section_kinds import callout

PAGE = ROOT / "src" / "clark" / "page" / "src"
WANT = ["No icon", "Information", "Question", "Warning triangle", "Alert", "Tick", "Clock", "Calendar", "Flag", "Lock", "Key",
        "Light bulb", "Star", "Bell", "Megaphone", "Document", "Link", "People", "Money", "Chart", "Shield",
        "Lightning", "Eye", "Table", "Gear", "Sparkle", "Two ways"]


def diff(got, want=WANT):
    return f"count {len(got)} (want {len(want)}); missing: {sorted(set(want) - set(got))}; extra: {sorted(set(got) - set(want))}"


class CalloutIcons27(unittest.TestCase):
    def test_store_list_is_27_names(self):
        got = list(callout.ICONS.values())
        self.assertTrue(len(got) == 27 and sorted(got) == sorted(WANT), diff(got))

    def test_page_list_has_the_same_27_names(self):
        src = (PAGE / "templates" / "notes.js").read_text(encoding="utf-8")
        block = src[src.index("export const ICONS"):src.index("export const TONE_LOOK")]
        got = [n for _, n in re.findall(r'(\w+): "([^"]+)"', block)]
        self.assertTrue(len(got) == 27 and sorted(got) == sorted(WANT), diff(got))

    def test_every_named_icon_has_a_drawing(self):
        src = (PAGE / "components" / "Icon.jsx").read_text(encoding="utf-8")
        gone = [k for k in callout.ICONS if k != "none" and not re.search(rf"^\s+{k}: '<", src, re.M)]
        self.assertEqual(gone, [], f"icons with no drawing in Icon.jsx: {gone}")


if __name__ == "__main__":
    unittest.main()
