"""Rows 1077 and 1078: the Help text for the work item peek and the milestone peek says only what the peek does (no browser).

Run: python3 dev/run_tests.py test_help_peek_words_true
Each wrong claim found in review is pinned as absent, and the true replacement as present, against the code it describes.
"""
import json
import unittest

from _paths import SRC

HELP = SRC / "clark" / "page" / "src" / "help"
PAGE = SRC / "clark" / "page" / "src"
DOC = json.loads((HELP / "helpContent.json").read_text(encoding="utf-8"))


def lines(section, key, ident):
    for s in DOC[section][key]:
        if s["id"] == ident:
            return [x for b in s.get("b", []) if b[0] == "ul" for x in b[1]] if "b" in s else s["s"]
    raise AssertionError(ident)


ITEM = lines("reference", "sections", "peek")
MS = lines("reference", "sections", "milestone-peek")
HOWTO = lines("howto", "tasks", "change-an-item-in-the-peek")
MSHOW = lines("howto", "tasks", "update-a-milestone")


def find(rows, start):
    got = [r for r in rows if r.startswith(start)]
    assert len(got) == 1, (start, got)
    return got[0]


class ItemPeek(unittest.TestCase):
    def test_top_bar_is_the_real_bar(self):
        bar = find(ITEM, "At the top:")          # merged with main: the buttons are named as the page names them (Peek.jsx aria-labels)
        for word in ("Previous item", "Next item", "ID", "Duplicate", "Archive", "Make this panel fill the screen", "Close this panel"):
            self.assertIn(word, bar)
        for gone in ("eye", "Copy link", "⋯"):
            self.assertNotIn(gone, bar)
        code = (PAGE / "components" / "Peek.jsx").read_text(encoding="utf-8")
        self.assertNotIn("Copy link", code.split('class="pk-bar"')[1].split("</div>")[0])

    def test_source_is_in_view_and_published_too(self):
        src = find(ITEM, "**Source**")
        self.assertNotIn("(in Edit)", src)
        self.assertIn("View", src)
        self.assertIn("published", src)

    def test_details_is_a_tab_and_has_no_description(self):
        det = find(ITEM, "**Details**")
        self.assertNotIn("Description", det)
        self.assertIn("tab", det)
        how = find(HOWTO, "In Edit, **Details**")
        self.assertNotIn("description", how)
        self.assertNotIn("open or closed", how)
        self.assertIn("tab", how)
        self.assertIn("In Edit", how)          # Peek.jsx: Tabs = editing && tools.PeekTabs; View shows the fields with no tab
        self.assertIn("in Edit", det)

    def test_arrows_are_previous_and_next_buttons(self):
        step = find(HOWTO, "With the peek open")
        self.assertNotIn("up and down arrows at the top", step)
        self.assertIn("**Previous item** and **Next item**", step)
        self.assertIn("[[Up]] and [[Down]]", step)
        self.assertIn("only when focus is on one of the peek’s own buttons", step)      # Peek.jsx peekOwnsArrow: BUTTON inside #peek only
        code = (PAGE / "components" / "Peek.jsx").read_text(encoding="utf-8")
        self.assertIn('t.tagName !== "BUTTON" || !t.closest("#peek")', code)


class MilestonePeek(unittest.TestCase):
    def test_top_bar_has_no_eye(self):
        bar = find(MS, "**The top bar**")
        self.assertNotIn("eye", bar)
        self.assertIn("Archive", bar)          # PeekArchive.jsx: the button is named Archive
        self.assertIn("Previous item", bar)

    def test_dates_have_no_rebaseline(self):
        d = find(MS, "**Dates**")
        for gone in ("Rebaseline", "original", "later than agreed"):
            self.assertNotIn(gone, d)
        self.assertIn("Agreed", d)
        self.assertIn("Forecast", d)
        self.assertIn("in Edit", d)            # the Forecast picker and the Achieved on row are the editor's alone (MilestonePeek.jsx; View's MilestoneFields shows the date as text)
        self.assertIn("Achieved on", d)
        code = (PAGE / "edit" / "MilestonePeek.jsx").read_text(encoding="utf-8")
        self.assertNotIn("Rebaseline", code)

    def test_no_linked_items_or_history(self):
        self.assertEqual([r for r in MS if r.startswith("**Linked work items**")], [])
        self.assertEqual([r for r in MS if "history" in r], [r for r in MS if r.startswith("**Tabs**")])      # the only history is the Activity tab the peek has in Edit (PeekTabs)

    def test_state_has_no_why(self):
        st = find(MS, "**State**")
        self.assertNotIn("why", st)
        self.assertIn("Overdue", st)

    def test_howto_says_nothing_false(self):
        text = "\n".join(MSHOW)
        for gone in ("says why", "Rebaseline", "keeps the original", "Linked work items", "lists the items tied"):
            self.assertNotIn(gone, text)
        st = find(MSHOW, "**State**")
        self.assertIn("buttons", st)
        dates = find(MSHOW, "**Dates**")
        self.assertIn("does not change it", dates)
        code = (PAGE / "edit" / "MilestonePeek.jsx").read_text(encoding="utf-8")
        self.assertIn('<Row name="Agreed date" k="baseline">{showDate(', code)


if __name__ == "__main__":
    unittest.main()
