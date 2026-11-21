"""Row 1470 (v1.3): the Dashboard peek draws the editable Latest update box in View and in Edit (Classic), above Details, with the mock-up's stamp and Created entry.
Row 1185: the Latest update box on a risk, an issue and a milestone peek in a real browser (1400 and 900: save, one Undo, the history link), the
milestone Latest update in the published file, and the few source checks that remain (the box itself is covered in test_peek_latest). Run: python3 dev/run_tests.py test_peek_latest_1185
"""
import json
import sys
import unittest

from _paths import ROOT, SRC
from test_milestone_peek_828 import Fields
from test_movement_page import GO_LIVE, Base
from _demo import USER, DemoStore
from clark import activity_read, changes, publish
import test_peek_latest
from test_server import chrome, wait

PAGE = SRC / "clark" / "page" / "src"


class PeekSource(unittest.TestCase):
    def read(self, rel):
        return (PAGE / rel).read_text(encoding="utf-8")

    def test_a_decision_has_the_box_since_row_1195_and_the_milestone_and_published_rows_are_not_action_only(self):
        self.assertNotIn('"decision"', self.read("edit/PeekLatest.jsx").split("export function PeekLatest")[1], "row 1195: the box is drawn for a decision too")
        ms = self.read("edit/MilestonePeek.jsx")
        self.assertNotIn('<Row name="Latest update"', ms, "row 1184: the milestone's box is above Details, not a row")
        self.assertIn("<LatestBox", ms, "the milestone uses the work item peek's box")
        self.assertIn("PeekLatestHistory", self.read("edit/PeekLatest.jsx"), "with its history")
        peek = self.read("components/Peek.jsx")
        shown = [l for l in peek.splitlines() if 'name="Latest update"' in l]
        self.assertEqual(len(shown), 3, "a published work item, a published action (row 1181: its own file rows above the Details) and a published milestone each show it")
        self.assertFalse([l for l in shown if "action" in l], "the work item row is not gated on an action")


_B = test_peek_latest.Browser


class RaidBox(unittest.TestCase):
    """A risk peek and an issue peek (they were once action-only): the box saves the editor's HTML, one Undo puts the old text back, the history link shows."""
    load, open_box, type_in, save_key, toast, fresh, refused = (_B.load, _B.open_box, _B.type_in, _B.save_key, _B.toast,
                                                                _B.fresh, _B.refused)
    HOLD, SHOWN, BOX = _B.HOLD, _B.SHOWN, _B.BOX

    def shown(self, cdp, sid):
        return cdp.js(f"(document.querySelector({json.dumps(self.SHOWN)}) || {{textContent: ''}}).textContent", sid)

    def test_a_risk_and_an_issue_save_a_latest_update_undo_it_and_show_the_history_link(self):
        for ref, kind in (("TUL-007", "Risk"), ("TUL-010", "Issue")):
            for width in (1400, 900):
                with self.subTest(kind=kind, width=width), chrome() as cdp:
                    sent, sid = self.load(cdp, width, ref, edit=True)
                    row = lambda: self.store.read("raid", ref=ref)["latest_update"]
                    self.assertEqual(cdp.js("(e => e ? e.textContent : '')(document.querySelector('#peek [data-pk-lh-btn]'))", sid), "Show history", "the link is there before any change")
                    was = row()
                    self.open_box(cdp, sid)
                    self.type_in(cdp, sid, f"{kind} words")
                    self.save_key(cdp, sid)
                    self.assertTrue(wait(lambda: f"{kind} words" in self.shown(cdp, sid)), "the peek shows the saved update")
                    self.assertEqual((len(sent), sent[0]["kind"], sent[0]["id"]), (1, "raid", ref), "one request")
                    self.assertEqual(row(), f"<p>{kind} words</p>")
                    self.assertIn("Latest update of", self.toast(cdp, sid))
                    self.assertEqual(cdp.js("document.querySelector('#peek [data-pk-lh-btn]').textContent", sid), "Show history", "the link stays after the save")
                    cdp.js("document.querySelector('.toast [data-undo]').click()", sid)
                    self.assertTrue(wait(lambda: f"{kind} words" not in self.shown(cdp, sid)), "one Undo takes the text off the peek")
                    self.assertEqual(row(), was)
                    self.assertTrue(cdp.js("!!document.querySelector('#peek [data-pk-lh-btn]')", sid), "the link is there after the Undo")


DASH_ITEMS = (("TUL-007", "risk", "item"), ("TUL-010", "issue", "item"), ("TUL-A-001", "action", "item"), ("TUL-D-013", "decision", "item"), ("TUL-M-001", "milestone", "milestone"))
PANEL = "#peek [data-pk-latest]"


class DashPeek(unittest.TestCase):
    """Row 1470: the peek opened from the Dashboard (Classic page), in View and in Edit, at 1400 and 900."""
    load, open_box, type_in, save_key, toast, fresh, refused = (_B.load, _B.open_box, _B.type_in, _B.save_key, _B.toast, _B.fresh, _B.refused)
    HOLD, SHOWN, BOX = _B.HOLD, _B.SHOWN, _B.BOX
    setUp = _B.setUp

    def each(self, check, items=DASH_ITEMS, modes=("view", "edit"), dark=False):
        """`check(cdp, sid, sent, ref, label, mode)` for every item, mode and width, each in its own browser and subTest."""
        for width in (1400, 900):
            for mode in modes:
                for ref, label, kind in items:
                    with self.subTest(width=width, mode=mode, kind=label), chrome() as cdp:
                        sent, sid = self.load(cdp, width, ref, edit=False, dash=mode, kind=kind, classic=True, dark=dark)
                        check(cdp, sid, sent, ref, label, mode)

    def test_dash_view_peek_has_editable_latest_box(self):
        def check(cdp, sid, sent, ref, label, mode):
            self.assertTrue(cdp.js(f"!!document.querySelector({json.dumps(PANEL + ' [data-pk-lbox] [data-rich=latest_update]')})", sid), "the box is drawn")
            self.assertTrue(cdp.js(f"/Draft with AI/.test(document.querySelector({json.dumps(PANEL)}).textContent)", sid), "with Draft with AI")
            self.open_box(cdp, sid)
            self.type_in(cdp, sid, f"{label} dash words")
            self.save_key(cdp, sid)
            self.assertTrue(wait(lambda: f"{label} dash words" in cdp.js(f"(document.querySelector({json.dumps(self.SHOWN)}) || {{textContent: ''}}).textContent", sid)), "it is editable: the saved words are shown")
            self.assertEqual(len(sent), 1, "one request")
            self.assertIn(f"{label} dash words", sent[0]["changes"]["latest_update"])
        self.each(check)

    def test_latest_panel_above_details_1400_900(self):
        def check(cdp, sid, sent, ref, label, mode):
            r = cdp.js("(() => { const p = document.querySelector('#peek [data-pk-latest]'), b = p.querySelector('[data-pk-lbox]'), v = b.querySelector('.rt-view'), c = getComputedStyle(b), t = getComputedStyle(v),"
                       " dl = document.querySelector('#peek dl'); return { top: b.getBoundingClientRect().top, dl: dl ? dl.getBoundingClientRect().top : null, bt: c.borderTopWidth, rad: c.borderTopLeftRadius, pt: t.paddingTop, pl: t.paddingLeft, fs: t.fontSize, lh: t.lineHeight, minh: v.getBoundingClientRect().height }; })()", sid)
            self.assertIsNotNone(r["dl"], "the Details are drawn")
            self.assertLess(r["top"], r["dl"], "the Latest panel sits above Details")
            self.assertEqual((r["bt"], r["rad"], r["pt"], r["pl"], r["fs"], r["lh"]), ("1px", "12px", "12px", "14px", "15px", "23.25px"), r)
            self.assertGreaterEqual(r["minh"], 84, "min-height 84")
        self.each(check)

    def test_client_visible_keeps_eye_in_dashboard_peek(self):
        def check(cdp, sid, sent, ref, label, mode):
            t = cdp.js("(() => { const e = document.querySelector('#peek [data-pk-client], #peek [data-pk-client-read]'); return e ? [e.textContent.trim(), e.querySelectorAll('svg').length, e.hasAttribute('data-pk-client-read')] : null; })()", sid)
            self.assertIsNotNone(t, "the Client visible line is drawn")
            self.assertEqual(t[2], mode == "view", "the read-only line in View, the clickable one in Edit")
            self.assertRegex(t[0], r"Client visible|Client not visible|Shown to the client|Hidden from the client")
            self.assertGreaterEqual(t[1], 1, "its eye icon is kept")
        self.each(check, items=DASH_ITEMS[:3])
        self.each(check, items=DASH_ITEMS[3:4], modes=("edit",))      # a decision's View peek has no Client visible line (it never had one)

    def test_latest_panel_dark_1400_900(self):
        def check(cdp, sid, sent, ref, label, mode):
            r = cdp.js("(() => { const p = document.querySelector('#peek [data-pk-latest]'), b = p.querySelector('[data-pk-lbox]'), c = getComputedStyle(b), l = p.querySelector('[data-pk-last]'); return { bg: c.backgroundColor, bc: c.borderTopColor, st: l ? getComputedStyle(l).color : null }; })()", sid)
            self.assertEqual(r["bg"], "rgb(25, 36, 64)", "--soft 192440")
            self.assertEqual(r["bc"], "rgb(37, 50, 77)", "--line 25324D")
            if r["st"] is not None:
                self.assertEqual(r["st"], "rgb(154, 169, 189)", "--muted 9AA9BD")
        self.each(check, items=DASH_ITEMS[:3], dark=True)

    def test_never_updated_item_shows_created_entry_and_first_save_replaces_it(self):
        def check(cdp, sid, sent, ref, label, mode):
            shown = lambda: cdp.js(f"(document.querySelector({json.dumps(self.SHOWN)}) || {{textContent: ''}}).textContent", sid)
            self.assertTrue(wait(lambda: shown().startswith("Created by Demo Author, ")), shown())
            self.assertRegex(shown(), r"^Created by Demo Author, \d{2}-\d{2}-\d{4} \d{2}:\d{2} · Source: Demo data \(fictional\)$")
            self.assertFalse(cdp.js("!!document.querySelector('#peek [data-pk-last]')", sid), "no stamp: nothing has been updated")
            self.open_box(cdp, sid)
            self.type_in(cdp, sid, "First update")
            self.save_key(cdp, sid)
            self.assertTrue(wait(lambda: shown() == "First update"), "the first saved update replaces the Created entry: " + shown())
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek [data-pk-last]')", sid)), "and the stamp appears")
            rows = activity_read.make_read(self.store.path, self.store.data_for)(self.code, ref)["rows"]
            self.assertTrue([r for r in rows if r["kind"] == "Created"], "the Created entry stays in the Activity")
        self.each(check, items=(DASH_ITEMS[0], DASH_ITEMS[3], DASH_ITEMS[4]))

    def test_old_item_history_carries_user_and_source_1470(self):
        """An item with no recorded user and no Source (an older clark's row) shows "Last updated <date> <time>" alone: no migration, no invented name; one with both shows them."""
        import sqlite3

        def old(store):
            con = sqlite3.connect(str(store.path))
            con.execute("UPDATE applies SET by_user = ''")
            con.execute("UPDATE actions SET source = '' WHERE id = 'TUL-A-001'")
            con.commit()
            con.close()
        for width in (1400, 900):
            for prep, want in ((old, r"^Last updated \d{2}-\d{2}-\d{4} \d{2}:\d{2}$"), (None, r"^Last updated \d{2}-\d{2}-\d{4} \d{2}:\d{2} by Demo Author · Source: Demo data \(fictional\)$")):
                with self.subTest(width=width, old=prep is not None), chrome() as cdp:
                    sent, sid = self.load(cdp, width, "TUL-A-001", edit=False, dash="view", classic=True, prep=prep)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek [data-pk-last]')", sid)))
                    self.assertRegex(cdp.js("document.querySelector('#peek [data-pk-last]').textContent.trim()", sid), want)


class MilestonePublished(unittest.TestCase):
    def test_a_published_file_peek_has_no_editable_box_and_the_dashboard_view_box_never_reaches_it_1470(self):
        """AP7: the file's page carries no box, no editor field and no new stamp wording, and the View box is gated on a live (not file) peek."""
        sys.path.insert(0, str(ROOT / "dev" / "tools"))
        import build_page
        page = build_page.build(build_page.ENTRY_VIEW)
        for needle in ("data-pk-latest", "contenteditable", "Last updated", "Created by"):
            self.assertNotIn(needle, page, needle)
        peek = (PAGE / "components/Peek.jsx").read_text(encoding="utf-8")
        self.assertIn("const dashView = !!tools && !fromFile.value && classicTheme();", peek, "the View box needs live tools and no file")
        self.assertIn("(editing || dashView) && forItem && tools.PeekLatest", peek)

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
    visit_peek, click, undo, until_store, saved, toast_text = (Fields.visit_peek, Fields.click, Fields.undo, Fields.until_store,
                                                                Fields.saved, Fields.toast_text)
    cur = GO_LIVE

    def test_the_milestone_latest_update_saves_undoes_and_is_listed(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit_peek(cdp, width=width)
                was, before = self.row(GO_LIVE)["latest_update"], len(self.sent)
                self.click(p, "#peek [data-rich=latest_update]")
                p.until("!!document.querySelector('#peek .ProseMirror') && document.activeElement.classList.contains('ProseMirror')", "the editor opened")
                p.js("document.querySelector('#peek .ProseMirror').cxed.editor.commands.insertContent('Venue booked'); true")
                p.key("Enter", modifiers=4 if p.js("/Mac/.test(navigator.platform)") else 2, code="Enter", vk=13)
                self.saved(p, "latest_update", "<p>Venue booked</p>")
                self.assertEqual(len(self.sent) - before, 1, "one request")
                p.until("(document.querySelector('.toast .toast-text') || {}).textContent?.includes('Latest update of') === true", "the toast named the saved update")
                self.assertIn("Latest update of", self.toast_text(p))
                self.click(p, "#peek [data-pk-latest] [data-pk-lh-btn]")
                p.until("(e => !!e && e.innerText.includes('Venue booked'))(document.querySelector('#peek [data-pk-lh-panel]'))", "the history lists the change")
                self.undo(p)
                self.saved(p, "latest_update", was)


if __name__ == "__main__":
    unittest.main()
