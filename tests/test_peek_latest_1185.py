"""Row 1185: the Latest update box on a risk, an issue and a milestone peek in a real browser (1400 and 900: save, one Undo, the Updates tab), the
milestone Latest update in the published file, and the few source checks that remain (the box itself is covered in test_peek_latest). Run: python3 dev/run_tests.py test_peek_latest_1185
"""
import json
import unittest

from _new_page import reload_to_new_page_cdp
from _paths import SRC
from test_milestone_peek_828 import Fields
from test_movement_page import GO_LIVE, Base
from _demo import USER, DemoStore
from clark import changes, publish
import test_peek_latest
from test_server import chrome, wait

PAGE = SRC / "clark" / "page" / "src"
LAYER_DOC = "(function(){var add=function(){if(!document.head||document.getElementById('theme'))return !!document.head; var s=document.createElement('style'); s.id='theme'; document.head.appendChild(s); return true;}; if(!add()) new MutationObserver(function(m,o){if(add()) o.disconnect();}).observe(document,{childList:true,subtree:true});})()"      # the Classic layer (classicTheme() reads it), added before the page's script runs


class PeekSource(unittest.TestCase):
    def read(self, rel):
        return (PAGE / rel).read_text(encoding="utf-8")

    def test_a_decision_has_the_box_since_row_1195_and_the_milestone_and_published_rows_are_not_action_only(self):
        self.assertNotIn('"decision"', self.read("edit/PeekLatest.jsx").split("export function PeekLatest")[1], "row 1195: the box is drawn for a decision too")
        ms = self.read("edit/MilestonePeek.jsx")
        self.assertNotIn('<Row name="Latest update"', ms, "row 1184: the milestone's box is above Details, not a row")
        self.assertIn("<LatestBox", ms, "the milestone uses the work item peek's box")
        self.assertNotIn("<PeekLatestHistory", self.read("edit/PeekLatest.jsx"), "row 1258: no Show history link in any theme; the Updates tab is the history")
        self.assertNotIn("classicTheme", self.read("edit/PeekLatest.jsx"), "no theme branch")
        peek = self.read("components/Peek.jsx")
        shown = [l for l in peek.splitlines() if 'name="Latest update"' in l]
        self.assertEqual(len(shown), 3, "a published work item, a published action (row 1181: its own file rows above the Details) and a published milestone each show it")
        self.assertFalse([l for l in shown if "action" in l], "the work item row is not gated on an action")


_B = test_peek_latest.Browser


class RaidBox(unittest.TestCase):
    """A risk peek and an issue peek (they were once action-only): the box saves the editor's HTML, one Undo puts the old text back, there is no Show history link (row 1258)."""
    load, open_box, type_in, save_key, toast, fresh, refused = (_B.load, _B.open_box, _B.type_in, _B.save_key, _B.toast,
                                                                _B.fresh, _B.refused)
    HOLD, SHOWN, BOX = _B.HOLD, _B.SHOWN, _B.BOX

    def shown(self, cdp, sid):
        return cdp.js(f"(document.querySelector({json.dumps(self.SHOWN)}) || {{textContent: ''}}).textContent", sid)

    def test_a_risk_and_an_issue_save_a_latest_update_undo_it_and_show_no_history_link(self):
        for ref, kind in (("TUL-007", "Risk"), ("TUL-010", "Issue")):
            for width in (1400, 900):
                with self.subTest(kind=kind, width=width), chrome() as cdp:
                    sent, sid = self.load(cdp, width, ref, edit=True, classic=True)
                    row = lambda: self.store.read("raid", ref=ref)["latest_update"]
                    self.assertFalse(cdp.js("!!document.querySelector('#peek [data-pk-lh-btn]')", sid), "row 1258: no Show history link before any change")
                    was = row()
                    self.open_box(cdp, sid)
                    self.type_in(cdp, sid, f"{kind} words")
                    self.save_key(cdp, sid)
                    self.assertTrue(wait(lambda: f"{kind} words" in self.shown(cdp, sid)), "the peek shows the saved update")
                    self.assertEqual((len(sent), sent[0]["kind"], sent[0]["id"]), (1, "raid", ref), "one request")
                    self.assertEqual(row(), f"<p>{kind} words</p>")
                    self.assertIn("Latest update of", self.toast(cdp, sid))
                    self.assertFalse(cdp.js("!!document.querySelector('#peek [data-pk-lh-btn]')", sid), "no link after the save")
                    cdp.js("document.querySelector('.toast [data-undo]').click()", sid)
                    self.assertTrue(wait(lambda: f"{kind} words" not in self.shown(cdp, sid)), "one Undo takes the text off the peek")
                    self.assertEqual(row(), was)
                    self.assertFalse(cdp.js("!!document.querySelector('#peek [data-pk-lh-btn]')", sid), "no link after the Undo")


class MilestonePublished(unittest.TestCase):
    """The milestone Latest update in the published (client) file, through the real change route and the real build."""
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)

    def body(self):
        return publish.build(self.s, "ABC", now="2026-10-29")["body"].decode("utf-8")

    def set(self, ref, **fields):
        status, body = self.change({"project": "ABC", "kind": "milestones", "op": "update", "id": ref, "changes": fields, "place": "peek"})
        self.assertEqual(status, 200, body)

    def test_it_is_in_the_client_file_with_client_wording_and_gone_without(self):
        ref = self.demo.milestone
        with self.s.step("dashboard", USER) as st:
            st.update("milestones", ref, {"client_visible": 1})
        self.set(ref, latest_update="zz-ms-latest-token")
        self.assertNotIn("zz-ms-latest-token", self.body(), "no client wording: the Latest update is dropped, the milestone stays")
        self.assertIn("Pilot live", self.body())
        self.set(ref, client_message="Client wording for the pilot")
        self.assertIn("zz-ms-latest-token", self.body(), "with client wording it is published")
        self.assertEqual(self.s.read("milestones", ref=ref)["latest_update"], "<p>zz-ms-latest-token</p>")
        self.set(ref, client_message="")
        self.assertNotIn("zz-ms-latest-token", self.body(), "the wording removed: it is dropped again")
        self.assertEqual(self.s.read("milestones", ref=ref)["latest_update"], "<p>zz-ms-latest-token</p>", "dropped from the file only, kept in the store")


class MilestoneBox(Base):
    """The milestone peek in a real browser (1400 and 900): the box saves the editor's HTML, one Undo puts it back, the history lists it."""
    def visit_classic(self, cdp, width):
        """The milestone peek on the Classic page: the layer is added before the page's script runs, then the page loads again."""
        p = self.visit_peek(cdp, width=width)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": LAYER_DOC}, p.sid)
        reload_to_new_page_cdp(cdp, p.sid, ready="!!document.querySelector('#peek [data-rich=latest_update]') && !!document.getElementById('theme')", what="the Classic peek drew")
        return p

    visit_peek, click, undo, until_store, saved, toast_text = (Fields.visit_peek, Fields.click, Fields.undo, Fields.until_store,
                                                                Fields.saved, Fields.toast_text)
    cur = GO_LIVE

    def test_the_milestone_latest_update_saves_undoes_and_is_listed(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit_classic(cdp, width)
                was, before = self.row(GO_LIVE)["latest_update"], len(self.sent)
                self.click(p, "#peek [data-rich=latest_update]")
                p.until("!!document.querySelector('#peek .ProseMirror') && document.activeElement.classList.contains('ProseMirror')", "the editor opened")
                p.js("document.querySelector('#peek .ProseMirror').cxed.editor.commands.insertContent('Venue booked'); true")
                p.key("Enter", modifiers=4 if p.js("/Mac/.test(navigator.platform)") else 2, code="Enter", vk=13)
                self.saved(p, "latest_update", "<p>Venue booked</p>")
                self.assertEqual(len(self.sent) - before, 1, "one request")
                p.until("(document.querySelector('.toast .toast-text') || {}).textContent?.includes('Latest update of') === true", "the toast named the saved update")
                self.assertIn("Latest update of", self.toast_text(p))
                self.assertFalse(p.js("!!document.querySelector('#peek [data-pk-lh-btn]')"), "row 1258: no Show history link")
                self.click(p, "#peek [data-pk-htab=updates]")
                p.until("(e => !!e && e.innerText.includes('Venue booked'))(document.querySelector('#peek [data-pk-history]'))", "the Updates tab lists the change")
                self.undo(p)
                self.saved(p, "latest_update", was)


if __name__ == "__main__":
    unittest.main()
