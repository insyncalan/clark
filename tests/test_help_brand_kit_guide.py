"""Row 1089: the Help guide for the brand kit (what a kit holds, the limits, how to bring one in).

Run: python3 dev/run_tests.py test_help_brand_kit_guide
Quick tier: no browser. The limits the guide states are the ones src/clark/brands.py enforces; the control names are the ones Brands.jsx shows.
"""
import re
import unittest

from _help_shown import RAW, shown_content
from _paths import ROOT
from test_help_navigation import BANNED

ID = "bring-in-a-brand-kit"
SRC = ROOT / "src" / "clark"


def guide():
    return next((g for g in shown_content()["guides"] if g["id"] == ID), None)


def text(g):
    return " ".join([g["t"], g["job"], g["result"]] + [s["d"] for s in g["steps"]])


class TheBrandKitGuide(unittest.TestCase):
    def test_it_is_a_shown_guide_with_five_to_eight_steps_and_known_links(self):
        g = guide()
        self.assertIsNotNone(g)
        self.assertEqual(RAW["guides"][-1]["id"], ID)
        self.assertTrue(5 <= len(g["steps"]) <= 8)
        self.assertTrue(g["job"].strip() and g["result"].strip() and g["next"])
        self.assertTrue(all("pic" not in s for s in g["steps"]))

    def test_it_says_what_a_kit_holds(self):
        t = text(guide())
        for w in ("clark-brand.json", "name, id and version", "lists its files", "colours and fonts", "logo", "cover pictures", "no other files"):
            self.assertIn(w, t.lower() if w.islower() else t, w)

    def test_the_limits_are_the_ones_the_code_enforces(self):
        t = text(guide())
        code = (SRC / "brands.py").read_text(encoding="utf-8")
        self.assertIn("FILE_CAP = 50", code)
        self.assertIn("ZIP_CAP = 16 * 1024 * 1024", code)
        self.assertIn("TOTAL_CAP = 24 * 1024 * 1024", code)
        self.assertIn("MEMBER_CAP = 5 * 1024 * 1024", code)
        for w in ("50 files", "16 MB", "24 MB", "5 MB"):
            self.assertIn(w, t, w)
        self.assertRegex(t, r"(?i)no links")
        self.assertRegex(t, r"(?i)outside")

    def test_it_says_the_layout_and_the_checks_the_code_makes(self):
        t = text(guide())
        code = (SRC / "brands.py").read_text(encoding="utf-8")
        self.assertIn("the manifest's id is not the folder's", code)
        self.assertIn("size, sha, mode = rows[rel]", code)
        self.assertIn("one folder named by the brand id", t)
        for w in ("size", "sha256", "mode", "must match"):
            self.assertIn(w, t, w)

    def test_it_says_no_file_name_is_required(self):
        self.assertRegex(text(guide()), r"(?i)no (particular )?file name is required|needs no particular file name|any file name")

    def test_it_walks_the_steps_in_settings_brands(self):
        t = " ".join(s["d"] for s in guide()["steps"])
        for name in ("**Settings**", "**Brands**", "**Choose zip…**", "**Install**", "**Replace**", "**Cancel**", "**Undo**", "**Remove**"):
            self.assertIn(name, t, name)
        self.assertIn("Review the brand in Downloads", t)

    def test_every_bold_name_is_a_string_in_the_page_source(self):
        src = " ".join(p.read_text(encoding="utf-8") for p in (SRC / "page" / "src").rglob("*") if p.suffix in (".js", ".jsx") and "help" not in p.parts)
        norm = lambda s: re.sub(r"[‘’]", "'", s)
        names = {b for s in guide()["steps"] for b in re.findall(r"\*\*(.+?)\*\*", s["d"])}
        self.assertTrue(names)
        self.assertEqual(sorted(b for b in names if norm(b).strip(" .,:;") not in norm(src)), [])

    def test_no_banned_word_and_no_date_with_slashes(self):
        t = text(guide())
        self.assertIsNone(re.search(BANNED, t), re.search(BANNED, t))
        self.assertNotRegex(t, r"(?<!\d)\d{1,2}/\d{1,2}/\d{2,4}")


class AfterTheBrandsFixes(unittest.TestCase):
    def test_remove_is_for_a_brand_that_was_added_and_downloads_means_a_kit(self):
        t = " ".join(s["d"] for s in guide()["steps"])
        code = (SRC / "brands.py").read_text(encoding="utf-8")
        self.assertIn("def _own_folder", code)
        self.assertIn("To take away a brand you added, press **Remove** on its row and confirm.", t)
        self.assertIn("To use the newest brand kit in your Downloads folder", t)
