"""Row 1185: the peek source draws the Latest update box for every kind that has the column (a source-level check; the box itself is
covered in test_peek_latest). Run: python3 dev/run_tests.py test_peek_latest_1185
"""
import re
import unittest

from _paths import SRC
from test_milestone_peek_828 import Fields
from test_movement_page import GO_LIVE, Base
from test_server import chrome

PAGE = SRC / "clark" / "page" / "src"


class PeekSource(unittest.TestCase):
    def read(self, rel):
        return (PAGE / rel).read_text(encoding="utf-8")

    def test_the_box_is_not_gated_on_an_action(self):
        src = self.read("edit/PeekLatest.jsx")
        self.assertNotRegex(src, r"action\s*\?")
        self.assertNotIn('"actions"', src)          # the table comes from the row, not a fixed word

    def test_a_risk_row_carries_the_field_to_the_peek(self):
        src = self.read("workItems.js")
        raid = [l for l in src.splitlines() if "latest_update" in l]
        self.assertGreaterEqual(len(raid), 2, "actions and risks/issues both read latest_update")

    def test_a_decision_is_still_skipped_and_the_milestone_and_published_rows_are_not_action_only(self):
        self.assertIn('"decision"', self.read("edit/PeekLatest.jsx"))
        ms = self.read("edit/MilestonePeek.jsx")
        self.assertIn('<Row name="Latest update" k="latest_update">', ms)
        self.assertIn("PeekLatestHistory", ms)
        peek = self.read("components/Peek.jsx")
        shown = [l for l in peek.splitlines() if 'name="Latest update"' in l]
        self.assertEqual(len(shown), 2, "a published work item and a published milestone each show it")
        self.assertFalse([l for l in shown if "action" in l], "the work item row is not gated on an action")


class MilestoneBox(Base):
    """The milestone peek in a real browser (1400 and 900): the box saves the editor's HTML, one Undo puts it back, the history lists it."""
    visit_peek, click, undo, until_store, saved, toast_text = (Fields.visit_peek, Fields.click, Fields.undo, Fields.until_store,
                                                                Fields.saved, Fields.toast_text)
    cur = GO_LIVE

    def test_the_milestone_latest_update_saves_undoes_and_is_listed(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit_peek(cdp, width=width)
                was = self.row(GO_LIVE)["latest_update"]
                self.click(p, "#peek [data-rich=latest_update]")
                p.until("!!document.querySelector('#peek .ProseMirror') && document.activeElement.classList.contains('ProseMirror')", "the editor opened")
                p.js("document.querySelector('#peek .ProseMirror').cxed.editor.commands.insertContent('Venue booked'); true")
                p.key("Enter", modifiers=4 if p.js("/Mac/.test(navigator.platform)") else 2, code="Enter", vk=13)
                self.saved(p, "latest_update", "<p>Venue booked</p>")
                self.assertEqual(len(self.sent), 1, "one request")
                self.assertIn("Latest update of", self.toast_text(p))
                self.click(p, "#peek [data-ms-row=latest_update] [data-pk-lh-btn]")
                p.until("(e => !!e && e.innerText.includes('Venue booked'))(document.querySelector('#peek [data-pk-lh-panel]'))", "the history lists the change")
                self.undo(p)
                self.saved(p, "latest_update", was)


if __name__ == "__main__":
    unittest.main()
