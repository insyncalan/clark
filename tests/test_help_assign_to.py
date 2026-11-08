"""Row 987: Help says how Assign to works (Recent names, search, add a new person, "TBC (no one yet)").

Run: python3 dev/run_tests.py test_help_assign_to
Quick tier: reads files, starts no browser. The words Help uses for the picker must be the words the picker draws
(src/clark/page/src/edit/cells/OwnerPick.jsx, itemEdit.js), and the entry must be shown (not held in helpLater.json).
"""
import unittest

from _help_shown import LATER, shown_content
from _paths import ROOT

PAGE = ROOT / "src" / "clark" / "page" / "src"
PICK = (PAGE / "edit" / "cells" / "OwnerPick.jsx").read_text(encoding="utf-8")
EDIT = (PAGE / "edit" / "itemEdit.js").read_text(encoding="utf-8")


def work_items(content):
    return [s for s in content["reference"]["sections"] if s["id"] == "work-items"][0]


class AssignToHelp(unittest.TestCase):
    def setUp(self):
        blocks = [b[1] for b in work_items(shown_content())["b"] if b[0] == "p"]
        self.text = " ".join(x for x in blocks if x.startswith("Assign to:"))

    def test_the_words_are_in_the_shown_work_items_reference(self):
        self.assertTrue(self.text, "no Assign to paragraph in the shown Work items section")
        self.assertNotIn("work-items", str(LATER.get("reference") or ""))

    def test_help_uses_the_words_the_picker_draws(self):
        for w in ("Recent", "as a new person", "Keep the name only", "TBC (no one yet)"):
            self.assertIn(w, self.text, w)
        pick = PICK + EDIT
        self.assertIn(">Recent<", pick)
        self.assertIn("as a new person", pick)
        self.assertIn("Keep the name only", pick)
        self.assertIn("TBC (no one yet)", pick)

    def test_help_says_each_way_to_assign(self):
        for w in ("click the owner", "Type to search", "one step", "puts them on the list of people"):
            self.assertIn(w, self.text, w)

    def test_help_says_where_recents_live_and_what_storage_refused_does(self):
        self.assertIn("this browser only, not in Excel or a published file", self.text)
        self.assertIn("If the browser will not keep them, there is no Recent list", self.text)

    def test_help_says_tbc_stays_the_stored_value(self):
        self.assertIn("the owner stays as TBC", self.text)

    def test_no_new_bold_name_is_needed(self):
        self.assertNotIn("**", self.text)


if __name__ == "__main__":
    unittest.main()
