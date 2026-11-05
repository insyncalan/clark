"""#97, the right-click menu on a work item: in the table, on the board and in full screen, by mouse and by keys, each entry doing
what its button elsewhere does (the cells' own words and requests, the board's cards, clark's archive step), with Undo.

Run: python3 dev/run_tests.py test_row_menu
Part 1 runs the menu's rules (src/clark/page/src/logic/rowMenu.js, bundled by the pinned esbuild) in headless Chrome. Part 2 drives
the committed page against the real server, whose change and undo routes are changes.make_change and make_undo over a demo
database, with real mouse and key events, and checks each step in the database. Desktop (1400) and 900 px. The browser parts are
required: they fail, never skip, without Chrome (set CLARK_CHROME to its path).
"""
import contextlib
import json
import time
import unittest
from datetime import date

from _paths import ROOT, SRC

from _demo import USER
from clark import draft_email_feed, publish

from test_server import chrome, wait  # noqa: E402
from test_work_filters import click, need_chrome  # noqa: E402
from test_work_items import bundled, page_target  # noqa: E402
import test_work_board_page as board  # noqa: E402
import test_multi_select as ms  # noqa: E402
import _testpage as testpage  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
NOT_OFFERED = "This item cannot go in an email: it is hidden from the report, marked sensitive or restricted, or no longer open."
TODAY = board.TODAY                        # Thursday 29-10-2026

KEYS = {"Enter": (13, "\r"), " ": (32, " "), "Escape": (27, ""), "ArrowDown": (40, ""), "ArrowUp": (38, ""), "ArrowLeft": (37, ""),
        "ArrowRight": (39, ""), "Home": (36, ""), "End": (35, ""), "Tab": (9, ""), "F10": (121, ""), "ContextMenu": (93, "")}


def key(cdp, sid, name, shift=False):
    vk, text = KEYS[name]
    common = {"key": name, "code": {" ": "Space"}.get(name, name), "windowsVirtualKeyCode": vk, **({"modifiers": 8} if shift else {})}
    cdp.call("Input.dispatchKeyEvent", {"type": "rawKeyDown" if not text else "keyDown", **common, **({"text": text} if text else {})}, sid)
    cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", **common}, sid)


def right_click(cdp, sid, selector):
    cdp.js(f"document.querySelector({json.dumps(selector)}).scrollIntoView({{block: 'center'}})", sid)
    x, y = cdp.js(f"(() => {{ const b = document.querySelector({json.dumps(selector)}).getBoundingClientRect(); return [b.x + Math.min(b.width / 2, 120), b.y + b.height / 2]; }})()", sid)
    cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, sid)
    cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "right", "buttons": 2, "clickCount": 1}, sid)
    cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "right", "buttons": 0, "clickCount": 1}, sid)


# ---- part 1: the rules ----
class Rules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        need_chrome()
        cls.stack = contextlib.ExitStack()
        cls.cdp = cls.stack.enter_context(chrome())
        cls.sid = page_target(cls.cdp)
        res = cls.cdp.call("Runtime.evaluate", {"expression": bundled(PAGE_SRC / "logic" / "rowMenu.js", "RM") + "; true", "returnByValue": True}, cls.sid)
        assert "exceptionDetails" not in res, res

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def js(self, expr):
        res = self.cdp.call("Runtime.evaluate", {"expression": expr, "returnByValue": True}, self.sid)
        self.assertNotIn("exceptionDetails", res, (expr, res))
        return res["result"].get("value")

    ACTION = {"id": "ABC-A-001", "kind": "action", "owner": "Ada Quillfeather", "status": "Open", "priority": "High", "due_date": "2026-11-02"}

    def test_draft_email_opens_with_the_to_line_empty_and_finds_an_address_by_owner_id_never_the_name(self):
        row = json.dumps(self.ACTION)
        self.assertEqual(self.js(f"RM.draftEntry({row}, {{}})"),
                         {"name": "Draft email to Ada Quillfeather", "disabled": False, "to": "",
                          "reason": "The To line is left empty: there is no People list to take the address from yet."})
        # Today's rows have no id link: a person with the same name is never used (two people can share a name).
        same_name = json.dumps({"people": [{"id": "P-001", "name": "Ada Quillfeather", "email": "ada@example.com"}]})
        self.assertEqual(self.js(f"RM.draftEntry({row}, {same_name})"),
                         {"name": "Draft email to Ada Quillfeather", "disabled": False, "to": "",
                          "reason": "Ada Quillfeather has no email on the People list, so the To line is left empty."})
        self.assertEqual(self.js(f"RM.emailOf({same_name}, 'Ada Quillfeather')"), "")
        self.assertEqual(self.js(f"RM.emailOf({same_name}, '')"), "")
        self.assertEqual(self.js(f"RM.emailOf({same_name}, 'P-001')"), "ada@example.com")
        self.assertEqual(self.js("RM.emailOf({}, 'P-001')"), "")
        linked = json.dumps({**self.ACTION, "owner_id": "P-002"})
        two = json.dumps({"people": [{"id": "P-001", "name": "Ada Quillfeather", "email": "one@example.com"},
                                     {"id": "P-002", "name": "Ada Quillfeather", "email": " two@example.com "}]})
        got = self.js(f"RM.draftEntry({linked}, {two})")
        self.assertEqual(got["to"], "two@example.com", "the id picks the person")
        self.assertEqual((got["reason"], got["disabled"]), ("", False), "nothing to explain once the address is known")
        for owner in ("TBC", None, ""):
            none = json.dumps({**self.ACTION, "owner": owner})
            got = self.js(f"RM.draftEntry({none}, {same_name})")
            self.assertEqual((got["name"], got["to"], got["disabled"]), ("Draft email to the owner", "", True))
            self.assertIn("no owner", got["reason"])

    def test_the_eye_is_one_change_to_the_items_own_flag_and_the_name_and_words_follow_the_item(self):
        shown = json.dumps({**self.ACTION, "client": True})
        self.assertEqual(self.js(f"RM.eyeChange({shown})"),
                         {"name": "Hide from the client", "table": "actions", "id": "ABC-A-001", "changes": {"client_visible": 0},
                          "words": "ABC-A-001 is hidden from the client.", "back": "ABC-A-001 is shown to the client again."})
        hidden = json.dumps({**self.ACTION, "kind": "risk", "id": "ABC-002", "client": False})
        got = self.js(f"RM.eyeChange({hidden})")
        self.assertEqual((got["name"], got["table"], got["changes"], got["words"], got["back"]),
                         ("Show to the client", "raid", {"client_visible": 1}, "ABC-002 is shown to the client.", "ABC-002 is hidden from the client again."))

    def test_the_draft_is_asked_for_by_the_item_and_then_with_the_dialogs_own_state(self):
        self.assertEqual(self.js("RM.draftRequest('ABC-A-001')"), {"item": "ABC-A-001", "picked": ["ABC-A-001"]},
                         "the first ask names the item and ticks it; the kind is left to the server")
        st = {"mode": "chase", "picked": ["ABC-A-001"], "replyBy": "2026-11-20", "unblocks": " the go-live ", "includeUpdate": True}
        self.assertEqual(self.js(f"RM.draftRequest('ABC-A-001', {json.dumps(st)})"),
                         {"item": "ABC-A-001", "mode": "chase", "picked": ["ABC-A-001"], "include_update": True, "reply_by": "2026-11-20", "unblocks": "the go-live"})
        none = {"mode": "update_request", "picked": [], "replyBy": "", "unblocks": "", "includeUpdate": False}
        self.assertEqual(self.js(f"RM.draftRequest('ABC-A-001', {json.dumps(none)})"),
                         {"item": "ABC-A-001", "mode": "update_request", "picked": [], "include_update": False})
        reply = {"mode": "decision", "picked": ["ABC-D-001"]}
        self.assertEqual(self.js(f"RM.draftState({json.dumps(reply)})"),
                         {"mode": "decision", "picked": ["ABC-D-001"], "replyBy": "", "unblocks": "", "includeUpdate": False})
        self.assertEqual(self.js(f"RM.draftState({json.dumps(reply)}, {json.dumps(st)})"),
                         {"mode": "decision", "picked": ["ABC-D-001"], "replyBy": "2026-11-20", "unblocks": " the go-live ", "includeUpdate": True})

    def test_the_lists_offer_what_the_cells_offer_without_what_the_item_has(self):
        row = json.dumps(self.ACTION)
        self.assertEqual(self.js(f"RM.statusList({row})"), ["Delayed", "Closed", "Cancelled"])
        made = json.dumps({"id": "ABC-D-002", "kind": "decision", "owner": "X Y", "status": "Made"})
        self.assertEqual(self.js(f"RM.statusList({made})"), ["Withdrawn"], "a made decision never goes back to Pending")
        self.assertEqual(self.js(f"RM.ownerList(['Ada Quillfeather', 'Zelda Quince'], {row})"), ["Zelda Quince"])
        self.assertEqual(self.js(f"RM.dueList({json.dumps(TODAY)})"),
                         [{"id": "friday", "name": "Friday", "day": "2026-10-30", "line": "30-10-2026"},
                          {"id": "week", "name": "A week on", "day": "2026-11-05", "line": "05-11-2026"}])

    def test_a_pick_is_the_cells_own_change_and_an_unchanged_value_is_nothing(self):
        row = json.dumps(self.ACTION)
        got = self.js(f"RM.pickChange({row}, 'status', 'Closed', {json.dumps(TODAY)})")
        self.assertEqual(got, {"table": "actions", "id": "ABC-A-001", "changes": {"status": "Closed"}, "words": "Status of ABC-A-001 changed to Closed.",
                               "back": "Status of ABC-A-001 is back to Open."})
        self.assertIsNone(self.js(f"RM.pickChange({row}, 'status', 'Open', {json.dumps(TODAY)})"))
        self.assertIn("error", self.js(f"RM.pickChange({row}, 'status', 'Made', {json.dumps(TODAY)})"))

    def test_duplicate_sends_the_id_and_a_title_that_says_it_is_a_copy_the_server_copies_the_rest(self):
        """#442: the request carries the item's id and its title with " (copy)"; status, latest update, use case and the rest are
        copied by the server from the STORED item (tests/test_changes_item_eye.py), so the request carries none of them."""
        raw = json.dumps({"id": "ABC-A-001", "description": "Order the laptops", "owner": "Ada Quillfeather", "priority": "High", "due_date": None,
                          "workstream": "Data", "milestone": None, "status": "Closed", "closed": "2026-10-10", "client_visible": 0, "latest_update": "x"})
        self.assertEqual(self.js(f"RM.duplicateRequest({raw}, 'actions')"),
                         {"kind": "actions", "op": "new", "place": "menu", "copy_of": "ABC-A-001", "values": {"description": "Order the laptops (copy)"}})
        risk = json.dumps({"id": "ABC-001", "description": "Supplier slips", "type": "Issue", "impact": "High"})
        self.assertEqual(self.js(f"RM.duplicateRequest({risk}, 'raid')")["values"], {"description": "Supplier slips (copy)", "type": "Issue"})
        long = json.dumps({"id": "ABC-D-001", "decision": "x" * 300, "made_by": "A B", "needed_by": "2026-11-20", "status": "Made"})
        got = self.js(f"RM.duplicateRequest({long}, 'decisions')")
        self.assertEqual((len(got["values"]["decision"]), got["values"]["decision"].endswith(" (copy)"), sorted(got["values"])), (200, True, ["decision"]))

    def test_duplicate_says_the_new_id_and_undo_says_the_copy_is_taken_back(self):
        self.assertEqual(self.js(f"RM.duplicateWords({json.dumps(self.ACTION)}, 'ABC-A-009')"),
                         {"text": "ABC-A-009 added, a copy of ABC-A-001.", "back": "ABC-A-009 is taken back. ABC-A-001 is as it was."})

    def test_the_link_is_the_items_peek_address(self):
        row = json.dumps(self.ACTION)
        self.assertEqual(self.js(f"RM.linkFor({row}, 'ABC', 'http://127.0.0.1:1/', (s) => '#' + s.view + '&p=' + s.project + '&item=' + s.item)"),
                         "http://127.0.0.1:1/#work&p=ABC&item=ABC-A-001")


# ---- part 2: the real page ----
class Menu(board.Base):
    TABLE = "tr[data-id='%s']"
    CARD = "article[data-id='%s'] .bc-main"

    def setUp(self):
        super().setUp()
        # PR 68's own seam for POST /api/draft-email (#50), as __main__ gives it; every request it gets is kept to be read back.
        self.drafts = []
        real = draft_email_feed.make(self.store.data_for, profile=lambda: {"name": "Sam Example", "own_domains": []},
                                     clock=lambda: f"{TODAY} 09:00",
                                     rules_for=lambda c: draft_email_feed.rules_from_inputs(publish.read_inputs(self.store, c)))

        def draft_seam(req):
            self.drafts.append(req)
            return real(req)
        self.s.httpd.draft_email = draft_seam
        real_sent = draft_email_feed.make_sent(self.store.path, [], by_user=lambda: "Sam Example", today=date.fromisoformat(TODAY))
        self.sent_calls = []

        def sent_seam(req):
            self.sent_calls.append(req)
            time.sleep(0.4)                           # slow enough for a second press to arrive while the first is in flight
            return real_sent(req)
        self.s.httpd.draft_email_sent = sent_seam

    def open_menu(self, cdp, sid, selector):
        right_click(cdp, sid, selector)
        self.until(cdp, sid, "!!document.querySelector('.rowmenu [role=menu]')", "the menu")

    def entries(self, cdp, sid):
        return cdp.js("[...document.querySelectorAll('.rowmenu [role=menuitem]')].map(b => [b.dataset.rm, b.querySelector('b').textContent, b.getAttribute('aria-disabled') === 'true', (b.querySelector('small') || {}).textContent || ''])", sid)

    def fly(self, cdp, sid):
        """The short list open beside its entry (row 848): [id, name, small line] of each of its entries."""
        return cdp.js("[...document.querySelectorAll('.rowmenu .rm-fly [role=menuitem]')].map(b => [b.dataset.rm, b.querySelector('b').textContent, (b.querySelector('small') || {}).textContent || ''])", sid)

    def shut(self, cdp, sid):
        self.until(cdp, sid, "!document.querySelector('.rowmenu')", "the menu to close")

    def test_a_right_click_on_a_row_opens_the_menu_with_every_entry(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            a, before = self.id_of("Order the laptops"), self.steps()
            self.open_menu(cdp, sid, self.TABLE % a)
            self.assertEqual(cdp.js("document.querySelector('.rowmenu [role=menu]').getAttribute('aria-label')", sid), f"Actions for {a}")
            got = self.entries(cdp, sid)
            self.assertEqual([e[1] for e in got], ["Draft email to Sara Khan", "Open the peek", "Change status", "Move due date", "Change owner",
                                                   "Hide from the client", "Copy link to this item", "Copy ID", "Duplicate", "Archive"])
            by = {e[0]: e for e in got}
            self.assertEqual(by["draft"][2:], [False, "The To line is left empty: there is no People list to take the address from yet."],
                             "open, with the To line's reason in words")
            self.assertFalse(any(by[k][2] for k in ("draft", "eye", "peek", "status", "due", "owner", "link", "copyid", "dup", "archive")))
            self.assertEqual(by["eye"][3], "", "the eye has nothing to explain in Edit")
            self.assertEqual(cdp.js("document.activeElement.dataset.rm", sid), "draft", "focus is on the first entry that can be used")
            box = cdp.js("(() => { const b = document.querySelector('.rowmenu').getBoundingClientRect(); return [b.left, b.top, b.right, b.bottom]; })()", sid)
            self.assertTrue(box[0] >= 0 and box[1] >= 0 and box[2] <= 1400 and box[3] <= 900, box)
            self.assertFalse(cdp.js("!!document.querySelector('.cpop')", sid))
            self.assertEqual(self.steps(), before)
            # The Draft email's line is read with it, so a screen reader hears that the To line is empty.
            why = cdp.js("(() => { const b = document.querySelector('.rowmenu [data-rm=draft]'); const d = document.getElementById(b.getAttribute('aria-describedby')); return d ? d.textContent : null; })()", sid)
            self.assertEqual(why, "The To line is left empty: there is no People list to take the address from yet.")
            # The menu items have a real focus ring: 2 px, a colour, not none.
            key(cdp, sid, "ArrowDown")                       # a key moved focus, so :focus-visible applies
            ring = cdp.js("(() => { const c = getComputedStyle(document.activeElement); return [c.outlineStyle, c.outlineWidth, c.outlineColor]; })()", sid)
            self.assertEqual(ring[:2], ["solid", "2px"], ring)
            self.assertNotEqual(ring[2], "rgba(0, 0, 0, 0)")

    def test_while_rows_are_selected_the_menu_stands_down_and_leaves_the_event_alone(self):
        """The Head's ruling: the selection wins. The multi-select menu (#196) owns the right click, Shift+F10 and the Menu key."""
        self.s.httpd.page_html = lambda: testpage.html()          # the test page has window.clarkPage.selected()
        with chrome() as cdp:
            sid = self.visit(cdp)
            rows = cdp.js("[...document.querySelectorAll('#work-list tr[data-id]')].map(r => r.dataset.id)", sid)
            a, b = rows[0], rows[1]
            # Records, for each event at the document's capture phase (after the menu's own listener, before Bulk's), whether the menu had prevented it.
            cdp.js("window.__seen = []; for (const t of ['contextmenu', 'keydown']) document.addEventListener(t, (e) => { if (t === 'contextmenu' || e.key === 'ContextMenu' || e.key === 'F10') window.__seen.push([t, e.defaultPrevented]); }, true);", sid)
            seen = lambda: cdp.js("window.__seen.splice(0)", sid)
            for picks in ([a], [a, b]):
                ms.tap(cdp, sid, f"#work-list tr[data-id='{picks[0]}'] .c-item .t")
                if len(picks) == 2:
                    ms.tap(cdp, sid, f"#work-list tr[data-id='{b}'] .c-item .t", mods=ms.MOD)
                self.until(cdp, sid, f"clarkPage.selected().length === {len(picks)}", "the selection")
                seen()
                right_click(cdp, sid, self.TABLE % a)
                self.until(cdp, sid, "window.__seen.length > 0", "the right click arrived")
                self.assertEqual(seen(), [["contextmenu", False]], "left for the multi-select menu")
                cdp.js(f"document.querySelector(\"{self.TABLE % a}\").focus()", sid)
                key(cdp, sid, "F10", shift=True)
                key(cdp, sid, "ContextMenu")
                self.until(cdp, sid, "window.__seen.length >= 2", "the keys arrived")
                got = seen()                                # the browser may add a contextmenu of its own after a key
                self.assertEqual([g for g in got if g[0] == "keydown"], [["keydown", False], ["keydown", False]])
                self.assertFalse(any(g[1] for g in got), got)
                self.assertFalse(cdp.js("!!document.querySelector('.rowmenu')", sid), f"{len(picks)} selected: no row menu")
            # Nothing selected: it opens as before.
            cdp.js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))", sid)
            key(cdp, sid, "Escape")                    # closes the multi-select menu, if one is open
            # #650: wait for the button the click below needs, instead of a fixed pause. (A wait for the multi-select menu to be gone cannot
            # work: the menu the key above opened stays open here, and the click is a script click, so the menu cannot swallow it.)
            self.until(cdp, sid, "!!document.getElementById('sel-clear')", "the clear button of the selection bar")
            cdp.js("document.getElementById('sel-clear').click()", sid)
            self.until(cdp, sid, "clarkPage.selected().length === 0", "the selection cleared")
            self.open_menu(cdp, sid, self.TABLE % a)
            self.assertTrue(cdp.js("!!document.querySelector('.rowmenu [role=menu]')", sid))
            self.assertEqual(seen()[-1], ["contextmenu", True])

    def test_a_right_click_on_a_row_opens_exactly_one_menu_with_a_selection_and_without(self):
        """#196's Bulk handler once opened its menu over this one (no defaultPrevented check). One owner: the row menu with no
        selection, the "N items" menu while rows are selected."""
        self.s.httpd.page_html = lambda: testpage.html()
        menus = "document.querySelectorAll('.rowmenu [role=menu], .bmenu').length"
        with chrome() as cdp:
            sid = self.visit(cdp)
            rows = cdp.js("[...document.querySelectorAll('#work-list tr[data-id]')].map(r => r.dataset.id)", sid)
            a, b = rows[0], rows[1]
            right_click(cdp, sid, self.TABLE % a)               # nothing selected: the row menu, and Bulk leaves it be
            self.until(cdp, sid, "!!document.querySelector('.rowmenu [role=menu]')", "the row menu")
            time.sleep(0.4)
            self.assertEqual(cdp.js(menus, sid), 1)
            self.assertFalse(cdp.js("!!document.querySelector('.bmenu')", sid))
            self.assertEqual(cdp.js("clarkPage.selected().length", sid), 0, "the right click selected nothing")
            key(cdp, sid, "Escape")
            self.shut(cdp, sid)
            for picks in ([a], [a, b]):                         # selected: Bulk's menu, and no row menu
                ms.tap(cdp, sid, f"#work-list tr[data-id='{a}'] .c-item .t")
                if len(picks) == 2:
                    ms.tap(cdp, sid, f"#work-list tr[data-id='{b}'] .c-item .t", mods=ms.MOD)
                self.until(cdp, sid, f"clarkPage.selected().length === {len(picks)}", "the selection")
                right_click(cdp, sid, self.TABLE % a)
                self.until(cdp, sid, "!!document.querySelector('.bmenu')", "the multi-select menu")
                time.sleep(0.4)
                self.assertEqual(cdp.js(menus, sid), 1, f"{len(picks)} selected")
                self.assertFalse(cdp.js("!!document.querySelector('.rowmenu')", sid))
                key(cdp, sid, "Escape")
                self.until(cdp, sid, "!document.querySelector('.bmenu')", "the menu to close")

    def test_the_eye_entry_follows_the_item_and_a_menu_closes_with_escape_and_a_click_away(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            shown, hidden = self.id_of("Send the invitations"), self.id_of("Book the training room")
            self.open_menu(cdp, sid, self.TABLE % shown)
            self.assertIn("Hide from the client", [e[1] for e in self.entries(cdp, sid)])
            key(cdp, sid, "Escape")
            self.shut(cdp, sid)
            self.until(cdp, sid, f"document.activeElement.dataset.id === {json.dumps(shown)}", "focus back on the row")
            self.open_menu(cdp, sid, self.TABLE % hidden)
            self.assertIn("Show to the client", [e[1] for e in self.entries(cdp, sid)])
            cdp.js("document.body.insertAdjacentHTML('beforeend', '<div id=away style=\"position:fixed;left:0;top:0;width:30px;height:30px;z-index:60\"></div>')", sid)
            hit = cdp.js("(() => { const a = document.querySelector('#away').getBoundingClientRect(); const e = document.elementFromPoint(a.x + 15, a.y + 15); return e && (e.id || e.outerHTML.slice(0, 60)); })()", sid)
            self.assertEqual(hit, "away", f"the click-away spot is covered by {hit}")      # say so, instead of waiting out a timeout
            click(cdp, sid, "#away")
            self.shut(cdp, sid)
            right_click(cdp, sid, ".head h1")
            self.assertFalse(cdp.js("!!document.querySelector('.rowmenu')", sid), "off a row the menu stays out of the way")

    def test_change_status_from_the_menu_is_one_step_with_undo(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            a = self.id_of("Order the laptops")
            before = self.steps()
            self.open_menu(cdp, sid, self.TABLE % a)
            click(cdp, sid, "[data-rm=status]")
            self.until(cdp, sid, "!!document.querySelector('.rowmenu .rm-fly')", "the list")
            self.assertEqual([e[1] for e in self.fly(cdp, sid)], ["Delayed", "Closed", "Cancelled"])
            click(cdp, sid, "[data-rm='s:Closed']")
            t = self.wait_toast(cdp, sid, "done")
            self.assertEqual((t["text"], t["undo"]), (f"Status of {a} changed to Closed.", True), "the cell's own words")
            self.assertEqual((self.row(a)["status"], self.steps()), ("Closed", before + 1))
            self.shut(cdp, sid)
            click(cdp, sid, "[data-undo]")
            self.until(cdp, sid, f"document.querySelector('.toast-text').textContent === 'Status of {a} is back to Open.'")
            self.assertEqual(self.row(a)["status"], "Open")

    def test_the_keys_open_the_menu_walk_it_and_run_an_entry(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            a = self.id_of("Order the laptops")
            cdp.js(f"document.querySelector(\"{self.TABLE % a}\").focus()", sid)
            key(cdp, sid, "F10", shift=True)
            self.until(cdp, sid, "!!document.querySelector('.rowmenu [role=menu]')", "Shift+F10 opens it")
            key(cdp, sid, "Escape")
            self.shut(cdp, sid)
            self.assertEqual(cdp.js("document.activeElement.dataset.id", sid), a)
            key(cdp, sid, "ContextMenu")
            self.until(cdp, sid, "!!document.querySelector('.rowmenu [role=menu]')", "the menu key opens it")
            first = cdp.js("document.activeElement.dataset.rm", sid)
            key(cdp, sid, "ArrowDown")
            self.assertEqual((first, cdp.js("document.activeElement.dataset.rm", sid)), ("draft", "peek"))
            key(cdp, sid, "End")
            self.assertEqual(cdp.js("document.activeElement.dataset.rm", sid), "archive")
            key(cdp, sid, "Home")
            self.assertEqual(cdp.js("document.activeElement.dataset.rm", sid), "draft")
            key(cdp, sid, "ArrowDown")                                  # Open the peek
            key(cdp, sid, "ArrowDown")                                  # Change status
            key(cdp, sid, "ArrowRight")                                 # opens its list
            self.until(cdp, sid, "!!document.querySelector('.rowmenu .rm-fly')")
            self.assertEqual(cdp.js("document.activeElement.dataset.rm", sid), "s:Delayed")
            self.assertTrue(cdp.js("!!document.querySelector('.rowmenu [data-rm=draft]')", sid), "the menu stays whole beside the list")
            key(cdp, sid, "ArrowLeft")                                  # back to the entry, the list shut
            self.until(cdp, sid, "!document.querySelector('.rowmenu .rm-fly')")
            self.assertEqual(cdp.js("document.activeElement.dataset.rm", sid), "status")
            key(cdp, sid, "ArrowRight")
            self.until(cdp, sid, "!!document.querySelector('.rowmenu .rm-fly')")
            key(cdp, sid, "End")
            self.assertEqual(cdp.js("document.activeElement.dataset.rm", sid), "s:Cancelled")
            key(cdp, sid, "Escape")                                     # Esc leaves the list first, the menu stays
            self.until(cdp, sid, "!document.querySelector('.rowmenu .rm-fly')")
            self.assertTrue(cdp.js("!!document.querySelector('.rowmenu [role=menu]')", sid))
            key(cdp, sid, "Home")
            key(cdp, sid, "ArrowDown")
            key(cdp, sid, "Enter")                                      # Open the peek
            self.until(cdp, sid, f"location.hash.includes('item={a}')", "Enter on Open the peek")
            self.shut(cdp, sid)

    def test_move_due_date_offers_friday_and_a_week_on_and_a_date_to_pick(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            a = self.id_of("Order the laptops")
            self.open_menu(cdp, sid, self.TABLE % a)
            click(cdp, sid, "[data-rm=due]")
            self.until(cdp, sid, "!!document.querySelector('.rm-fly [data-rm=pick]')", "the list")
            self.assertEqual([e[1:] for e in self.fly(cdp, sid)], [["Friday", "30-10-2026"], ["A week on", "05-11-2026"], ["Pick a date", ""], ["No date", ""]])
            click(cdp, sid, "[data-rm='d:2026-10-30']")
            self.wait_toast(cdp, sid, "done")
            self.assertEqual(self.row(a)["due_date"], "2026-10-30")
            self.open_menu(cdp, sid, self.TABLE % a)
            click(cdp, sid, "[data-rm=due]")
            click(cdp, sid, "[data-rm=pick]")
            self.until(cdp, sid, "!!document.querySelector('.cpop.cdate')", "the date picker")
            self.assertFalse(cdp.js("!!document.querySelector('.rowmenu [role=menu]')", sid), "the picker replaces the list")
            key(cdp, sid, "Escape")
            self.until(cdp, sid, "!document.querySelector('.cpop')")
            self.assertEqual(cdp.js("document.activeElement.dataset.id", sid), a)
            self.assertEqual(self.row(a)["due_date"], "2026-10-30")

    def test_change_owner_lists_the_people_of_the_project(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            a = self.id_of("Order the laptops")
            self.open_menu(cdp, sid, self.TABLE % a)
            click(cdp, sid, "[data-rm=owner]")
            self.until(cdp, sid, "!!document.querySelector('.rm-fly')", "the list")
            names = [e[1] for e in self.fly(cdp, sid)]
            self.assertNotIn("Sara Khan", names, "not the current owner")
            self.assertIn("Priya Nair", names)
            click(cdp, sid, "[data-rm='o:Priya Nair']")
            self.assertEqual(self.wait_toast(cdp, sid, "done")["text"], f"Owner of {a} changed to Priya Nair.")
            self.assertEqual(self.row(a)["owner"], "Priya Nair")
            self.open_menu(cdp, sid, self.TABLE % a)
            self.assertEqual(self.entries(cdp, sid)[0][1], "Draft email to Priya Nair", "the draft entry follows the owner")

    def test_archive_hides_the_item_and_undo_brings_it_back_nothing_is_deleted(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            a = self.id_of("Order the laptops")
            before = self.steps()
            self.open_menu(cdp, sid, self.TABLE % a)
            click(cdp, sid, "[data-rm=archive]")
            t = self.wait_toast(cdp, sid, "done")
            self.assertEqual((t["text"], t["undo"]), (f"{a} archived. It is out of the lists and the published page.", True))
            self.until(cdp, sid, f"!document.querySelector(\"{self.TABLE % a}\")", "the row to leave the list")
            self.assertEqual((self.row(a)["archived"], self.steps()), (1, before + 1))
            self.assertEqual(len(self.query("SELECT 1 FROM actions WHERE id = ?", a)), 1, "the record is still in the database")
            click(cdp, sid, "[data-undo]")
            self.until(cdp, sid, f"!!document.querySelector(\"{self.TABLE % a}\")", "the row to come back")
            self.assertEqual(self.row(a)["archived"], 0)
            self.assertEqual(cdp.js("document.querySelector('.toast-text').textContent", sid), f"{a} is back.")

    def test_duplicate_adds_a_copy_in_one_step_opens_it_and_undo_says_so(self):
        """#442: the copy is the item again (status, latest update, use case and the rest), titled " (copy)"; its peek opens; the
        toast names it and carries Undo, and Undo says the copy is taken back."""
        with chrome() as cdp:
            a = self.id_of("Order the laptops")
            with self.store.step("dashboard", USER) as st:
                st.update("actions", a, {"status": "Delayed", "latest_update": "Waiting on the supplier"})
            sid = self.visit(cdp)
            old = self.row(a)
            n, before = len(self.query("SELECT id FROM actions")), self.steps()
            self.open_menu(cdp, sid, self.TABLE % a)
            click(cdp, sid, "[data-rm=dup]")
            t = self.wait_toast(cdp, sid, "done")
            now = self.query("SELECT * FROM actions WHERE description = 'Order the laptops (copy)'")
            self.assertEqual((len(now), len(self.query("SELECT id FROM actions")), self.steps()), (1, n + 1, before + 1))
            copy = now[0]
            self.assertEqual((t["text"], t["undo"]), (f"{copy['id']} added, a copy of {a}.", True))
            for f in ("owner", "priority", "due_date", "workstream", "milestone", "status", "latest_update", "use_case", "client_visible"):
                self.assertEqual(copy[f], old[f], f)
            self.assertEqual((copy["status"], copy["latest_update"], copy["source"]), ("Delayed", "Waiting on the supplier", "Duplicated from " + a))
            self.until(cdp, sid, f"location.hash.includes('item={copy['id']}')", "the copy's peek to open")
            self.until(cdp, sid, f"!!document.querySelector(\"{self.TABLE % copy['id']}\")", "the copy in the list")
            click(cdp, sid, "[data-undo]")
            self.until(cdp, sid, f"!document.querySelector(\"{self.TABLE % copy['id']}\")", "the copy to go again")
            want = json.dumps(copy['id'] + ' is taken back. ' + a + ' is as it was.')
            self.until(cdp, sid, f"(document.querySelector('.toast-text') || {{}}).textContent === {want}", "the Undo words")
            self.assertEqual(self.query("SELECT id FROM actions WHERE id = ?", copy["id"]), [])

    def test_a_copy_keeps_the_eye_of_its_original_for_every_kind(self):
        """A copy of a hidden item stays hidden (its title would otherwise reach the client); a copy of a shown item stays shown."""
        with chrome() as cdp:
            made = []
            for text, table, col in (("Order the laptops", "actions", "description"), ("Supplier slips", "raid", "description"),
                                     ("Use the new tool", "decisions", "decision")):
                ref = self.id_of(text)
                for eye in (0, 1):
                    with self.store.step("dashboard", USER) as st:
                        st.update(table, ref, {"client_visible": eye})
                    sid = self.visit(cdp)                    # the page reads the item as it is now
                    self.open_menu(cdp, sid, self.TABLE % ref)
                    click(cdp, sid, "[data-rm=dup]")
                    self.assertTrue(wait(lambda: len([r for r in self.query(f"SELECT id FROM {table} WHERE {col} = ?", text + " (copy)")
                                                      if r["id"] not in made]) == 1), (table, eye))
                    new = [r["id"] for r in self.query(f"SELECT id FROM {table} WHERE {col} = ?", text + " (copy)") if r["id"] not in made][0]
                    made.append(new)
                    self.assertEqual(self.row(new)["client_visible"], eye, (table, eye))
                    self.until(cdp, sid, f"!!document.querySelector(\"{self.TABLE % new}\")", "the copy in the list")

    def go_dark(self, cdp, sid, where):
        cdp.js("document.documentElement.dataset.theme = 'dark'", sid)
        self.until(cdp, sid, "getComputedStyle(document.body).backgroundColor !== 'rgb(255, 255, 255)'", f"{where}: the page went dark")
        self.assertLess(ms._lum(cdp.js("getComputedStyle(document.body).backgroundColor", sid)), 0.2, f"{where}: the page is dark")

    def readable(self, cdp, sid, selector, where):
        """Each element's words against the first solid background behind it, at least 4.5:1."""
        got = cdp.js("[...document.querySelectorAll(" + json.dumps(selector) + ")].filter(e => e.offsetWidth > 1).map(e => {"
                     " let b = e, bg = 'rgba(0, 0, 0, 0)';"
                     " while (b && /rgba\\(.*, 0\\)$|transparent/.test(bg = getComputedStyle(b).backgroundColor)) b = b.parentElement;"
                     " return [e.textContent.trim(), getComputedStyle(e).color, bg]; })", sid)
        self.assertTrue(got, f"{where}: {selector} is on screen")
        for text, fg, bg in got:
            self.assertGreaterEqual(ms.contrast(fg, bg), 4.5, f"{where}: {text!r} is {fg} on {bg}")

    def test_in_dark_at_1400_and_900_duplicate_opens_the_copy_and_its_toast_with_undo_reads(self):
        """Item 442, Done-when 4: in dark, Duplicate adds the copy in one step, opens its peek, and the toast names it with an
        Undo that can be read and sits in the window; Undo takes the copy back."""
        a = self.id_of("Order the laptops")
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                where = f"dark {width}"
                sid = self.visit(cdp, width=width)
                self.go_dark(cdp, sid, where)
                n, before = len(self.query("SELECT id FROM actions")), self.steps()
                self.open_menu(cdp, sid, self.TABLE % a)
                self.readable(cdp, sid, ".rowmenu [role=menuitem] b", where + " menu")
                click(cdp, sid, "[data-rm=dup]")
                t = self.wait_toast(cdp, sid, "done")
                now = self.query("SELECT id FROM actions WHERE description = 'Order the laptops (copy)'")
                self.assertEqual((len(now), len(self.query("SELECT id FROM actions")), self.steps()), (1, n + 1, before + 1), where)
                copy = now[0]["id"]
                self.assertEqual((t["text"], t["undo"]), (f"{copy} added, a copy of {a}.", True), where)
                self.readable(cdp, sid, ".toast .toast-text, .toast [data-undo]", where + " toast")
                box = cdp.js("(() => { const b = document.querySelector('.toast').getBoundingClientRect(), u = document.querySelector('.toast [data-undo]').getBoundingClientRect();"
                             " return [b.left >= 0 && b.right <= innerWidth && b.bottom <= innerHeight, u.width > 0 && u.right <= b.right]; })()", sid)
                self.assertEqual(box, [True, True], f"{where}: the toast and its Undo are whole in the window")
                self.until(cdp, sid, f"location.hash.includes('item={copy}')", f"{where}: the copy's peek to open")
                self.until(cdp, sid, f"(document.querySelector('#peek') || {{}}).dataset && document.querySelector('#peek').dataset.peek === '{copy}'", f"{where}: the peek is the copy's")
                self.assertEqual(cdp.js("document.querySelector('#peek .pk-title').textContent", sid), "Order the laptops (copy)", where)
                self.readable(cdp, sid, "#peek .pk-title, #peek .pk-id", where + " peek")
                click(cdp, sid, "[data-undo]")
                self.until(cdp, sid, f"!document.querySelector(\"{self.TABLE % copy}\")", f"{where}: the copy to go again")
                want = json.dumps(copy + ' is taken back. ' + a + ' is as it was.')
                self.until(cdp, sid, f"(document.querySelector('.toast-text') || {{}}).textContent === {want}", f"{where}: the Undo words")
                self.readable(cdp, sid, ".toast .toast-text", where + " undo toast")
                self.assertEqual(self.query("SELECT id FROM actions WHERE id = ?", copy), [], where)
                self.assertTrue(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), f"{where}: no sideways scroll")

    def test_in_dark_at_1400_and_900_a_copy_keeps_the_eye_and_its_menu_says_so(self):
        """Item 442, Done-when 4: in dark, a copy of a hidden item is hidden and a copy of a shown one is shown, in the store and
        in the copy's own menu, whose eye entry can be read."""
        a = self.id_of("Order the laptops")
        made = []
        for width in (1400, 900):
            for eye in (0, 1):
                with self.subTest(width=width, eye=eye), chrome() as cdp:
                    where = f"dark {width} eye {eye}"
                    with self.store.step("dashboard", USER) as st:
                        st.update("actions", a, {"client_visible": eye})
                    sid = self.visit(cdp, width=width)
                    self.go_dark(cdp, sid, where)
                    self.open_menu(cdp, sid, self.TABLE % a)
                    click(cdp, sid, "[data-rm=dup]")
                    fresh = lambda: [r["id"] for r in self.query("SELECT id FROM actions WHERE description = 'Order the laptops (copy)'") if r["id"] not in made]
                    self.assertTrue(wait(lambda: len(fresh()) == 1), where)
                    new = fresh()[0]
                    made.append(new)
                    self.assertEqual(self.row(new)["client_visible"], eye, where)
                    self.until(cdp, sid, f"location.hash.includes('item={new}')", f"{where}: the copy's peek to open")
                    click(cdp, sid, "#peek [data-pk-close]")
                    self.until(cdp, sid, "!location.hash.includes('item=')", f"{where}: the peek closed")
                    self.until(cdp, sid, f"!!document.querySelector(\"{self.TABLE % new}\")", f"{where}: the copy in the list")
                    self.open_menu(cdp, sid, self.TABLE % new)
                    self.assertIn("Hide from the client" if eye else "Show to the client", [e[1] for e in self.entries(cdp, sid)], where)
                    self.readable(cdp, sid, ".rowmenu [data-rm=eye] b", where + " eye entry")
                    key(cdp, sid, "Escape")
                    self.shut(cdp, sid)

    def test_in_view_arrow_right_opens_the_list_for_status_due_and_owner(self):
        with chrome() as cdp:
            sid = self.visit(cdp, edit=False)
            a, before = self.id_of("Order the laptops"), self.steps()
            for rm in ("status", "due", "owner"):
                self.open_menu(cdp, sid, self.TABLE % a)
                cdp.js(f"document.querySelector('.rowmenu [data-rm={rm}]').focus()", sid)
                key(cdp, sid, "ArrowRight")
                self.until(cdp, sid, "!!document.querySelector('.rowmenu .rm-fly')", "the list for " + rm)
                self.assertTrue(cdp.js("!!document.querySelector('.rowmenu [data-rm=draft]')", sid), rm)
                key(cdp, sid, "Escape")                                 # the list first
                self.until(cdp, sid, "!document.querySelector('.rowmenu .rm-fly')")
                key(cdp, sid, "Escape")
                self.until(cdp, sid, "!document.querySelector('.rowmenu')", "the menu to close")
            self.assertEqual(self.steps(), before)

    def test_duplicate_works_for_a_risk_and_a_decision_too(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            for text, table, col in (("Supplier slips", "raid", "description"), ("Use the new tool", "decisions", "decision")):
                ref = self.id_of(text)
                self.open_menu(cdp, sid, self.TABLE % ref)
                click(cdp, sid, "[data-rm=dup]")
                self.assertTrue(wait(lambda: len(self.query(f"SELECT id FROM {table} WHERE {col} = ?", text + " (copy)")) == 1), table)

    def test_copy_id_and_copy_link_put_text_on_the_clipboard_and_say_so(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            before = self.steps()
            cdp.js("window.__clip = []; Object.defineProperty(navigator, 'clipboard', {value: {writeText: (t) => { window.__clip.push(t); return Promise.resolve(); }}, configurable: true})", sid)
            a = self.id_of("Order the laptops")
            self.open_menu(cdp, sid, self.TABLE % a)
            click(cdp, sid, "[data-rm=copyid]")
            self.until(cdp, sid, "window.__clip.length === 1")
            self.assertEqual(cdp.js("window.__clip[0]", sid), a)
            self.assertEqual(self.wait_toast(cdp, sid)["text"], f"{a} copied.")
            self.assertEqual(cdp.js("document.querySelector('#work-live').textContent", sid), f"{a} copied.")
            self.open_menu(cdp, sid, self.TABLE % a)
            click(cdp, sid, "[data-rm=link]")
            self.until(cdp, sid, "window.__clip.length === 2")
            self.assertTrue(cdp.js("window.__clip[1]", sid).endswith(f"#work&p=ABC&item={a}"), cdp.js("window.__clip[1]", sid))
            self.assertEqual(self.steps(), before)

    def test_when_the_browser_does_not_copy_the_cmd_c_hint_shows_only_with_a_selection(self):
        """Item 612: the note says to select the text and press the keys only when there is a selection to copy."""
        plain, hint = "The browser did not copy it.", "The browser did not copy it. Select the text and press ⌘C instead."
        toast = "(() => { const t = document.querySelector('.toast[data-kind=note] .toast-text'); return t ? t.textContent : ''; })()"
        with chrome() as cdp:
            sid = self.visit(cdp)
            a = self.id_of("Order the laptops")
            cdp.js("window.__select = false; Object.defineProperty(navigator, 'clipboard', {value: {writeText: () => { getSelection().removeAllRanges();"
                   " if (window.__select) getSelection().selectAllChildren(document.querySelector('main') || document.body);"
                   " return Promise.reject(new Error('no')); }}, configurable: true})", sid)
            self.open_menu(cdp, sid, self.TABLE % a)
            click(cdp, sid, "[data-rm=copyid]")
            self.until(cdp, sid, f"{toast} === {plain!r}", "the plain note")
            self.assertEqual(cdp.js("document.querySelector('#work-live').textContent", sid), plain)
            cdp.js("window.__select = true", sid)
            self.open_menu(cdp, sid, self.TABLE % a)
            click(cdp, sid, "[data-rm=link]")
            self.until(cdp, sid, f"{toast} === {hint!r}", "the note with the hint")

    def test_in_view_every_entry_is_enabled_and_a_choice_writes_one_step_with_its_undo(self):
        # Work items are always editable (View and Edit exist only on the Dashboard, ruled 02-11-2026)
        with chrome() as cdp:
            sid = self.visit(cdp, edit=False)
            a, before = self.id_of("Order the laptops"), self.steps()
            self.open_menu(cdp, sid, self.TABLE % a)
            by = {e[0]: e for e in self.entries(cdp, sid)}
            for k in ("status", "due", "owner", "eye", "dup", "archive", "draft", "peek", "link", "copyid"):
                self.assertFalse(by[k][2], k)
            self.assertNotIn("Switch to Edit to change this.", cdp.js("document.querySelector('.rowmenu').textContent", sid))
            click(cdp, sid, "[data-rm=archive]")
            t = self.wait_toast(cdp, sid, "done")
            self.assertEqual((t["text"], t["undo"]), (f"{a} archived. It is out of the lists and the published page.", True))
            self.assertEqual((self.row(a)["archived"], self.steps()), (1, before + 1), "one step")
            click(cdp, sid, "[data-undo]")
            self.until(cdp, sid, f"!!document.querySelector(\"{self.TABLE % a}\")", "the row to come back")
            self.assertEqual(self.row(a)["archived"], 0)

    def test_show_and_hide_flip_the_items_flag_in_one_step_with_one_undo_and_the_label_follows(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            a, before = self.id_of("Send the invitations"), self.steps()
            self.assertEqual(self.row(a)["client_visible"], 1)
            self.open_menu(cdp, sid, self.TABLE % a)
            self.assertIn("Hide from the client", [e[1] for e in self.entries(cdp, sid)])
            click(cdp, sid, "[data-rm=eye]")
            t = self.wait_toast(cdp, sid, "done")
            self.assertEqual((t["text"], t["undo"]), (f"{a} is hidden from the client.", True))
            self.assertEqual((self.row(a)["client_visible"], self.steps()), (0, before + 1), "one step")
            self.assertEqual(self.sent[-1][1]["changes"], {"client_visible": 0})
            self.assertEqual(self.sent[-1][1]["kind"], "actions")
            self.shut(cdp, sid)
            self.open_menu(cdp, sid, self.TABLE % a)
            self.assertIn("Show to the client", [e[1] for e in self.entries(cdp, sid)], "the label follows the item")
            key(cdp, sid, "Escape")
            self.shut(cdp, sid)
            click(cdp, sid, "[data-undo]")
            self.until(cdp, sid, "/shown to the client again/.test(document.querySelector('.toast').textContent)", "the Undo's words")
            self.assertEqual(self.row(a)["client_visible"], 1)
            self.open_menu(cdp, sid, self.TABLE % a)
            self.assertIn("Hide from the client", [e[1] for e in self.entries(cdp, sid)])
            key(cdp, sid, "Escape")
            self.shut(cdp, sid)
            hidden = self.id_of("Book the training room")                  # a hidden one is shown by the same entry
            self.open_menu(cdp, sid, self.TABLE % hidden)
            click(cdp, sid, "[data-rm=eye]")
            self.until(cdp, sid, f"document.querySelector('.toast') && document.querySelector('.toast').textContent.includes('{hidden} is shown to the client.')", "the toast")
            self.assertEqual(self.row(hidden)["client_visible"], 1)

    def test_draft_email_opens_the_dialog_with_the_items_subject_and_sends_and_saves_nothing(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            a, before, sent = self.id_of("Order the laptops"), self.steps(), len(self.sent)
            self.open_menu(cdp, sid, self.TABLE % a)
            click(cdp, sid, "[data-rm=draft]")
            self.until(cdp, sid, "!!document.querySelector('[data-draft-email] .de')", "the Draft email")
            self.shut(cdp, sid)
            self.assertEqual(self.drafts, [{"project": "ABC", "item": a, "picked": [a]}], "one ask, PR 68's POST /api/draft-email, for this item, ticked")
            self.assertEqual(cdp.js("[...document.querySelectorAll('.de .pick input')].map(i => [i.value, i.checked])", sid), [[a, True]], "its tick is pre-picked")
            self.assertEqual(cdp.js("document.querySelector('.de').getAttribute('role')", sid), "dialog")
            meta = cdp.js("[...document.querySelectorAll('.de-meta dt, .de-meta dd')].map(e => e.textContent)", sid)
            self.assertEqual(meta[0:2], ["To", "No address yet. Add one in your mail app."], "the To line is empty, for the person to type")
            self.assertEqual(meta[2], "Subject")
            self.assertIn(a, meta[3])
            self.assertIn("Example Programme", meta[3])
            self.assertIn("Order the laptops", cdp.js("document.querySelector('.de-preview').textContent", sid))
            self.assertTrue(cdp.js("document.querySelector('.de').contains(document.activeElement)", sid), "focus is in the dialog")
            self.assertEqual(cdp.js("[...document.querySelectorAll('.de-kinds input')].map(i => i.value)", sid), ["update_request", "chase", "decision"])
            # a change in the dialog asks for a new draft; it is still only a draft
            click(cdp, sid, ".de-kinds input[value=decision]")
            self.until(cdp, sid, "/Decision/.test(document.querySelector('.de-meta').textContent)", "the other kind of email")
            self.assertEqual(self.drafts[-1], {"project": "ABC", "item": a, "mode": "decision", "picked": [a], "include_update": False})
            self.assertTrue(cdp.js("/^mailto:\\?subject=/.test(document.querySelector('.de a.pk-btn').getAttribute('href'))", sid), "a plain mail link with no address")
            key(cdp, sid, "Escape")
            self.until(cdp, sid, "!document.querySelector('[data-draft-email]')", "the dialog to close")
            self.until(cdp, sid, f"document.activeElement.dataset.id === {json.dumps(a)}", "focus back on the row")      # given back one tick after the dialog goes
            self.assertEqual((self.steps(), len(self.sent)), (before, sent), "nothing was changed, saved or sent")
            self.assertFalse(cdp.js("document.querySelector('#main, .top').hasAttribute('inert')", sid))

    def test_the_draft_dialog_is_modal_and_everything_outside_it_is_inert_even_what_mounts_later(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            a = self.id_of("Order the laptops")
            self.open_menu(cdp, sid, self.TABLE % a)
            click(cdp, sid, "[data-rm=draft]")
            self.until(cdp, sid, "!!document.querySelector('[data-draft-email] .de')", "the Draft email")
            self.assertEqual(cdp.js("document.querySelector('[data-draft-email] .de').getAttribute('aria-modal')", sid), "true")
            outside = """(() => { const out = []; for (let n = document.querySelector('[data-draft-email]'); n && n !== document.body; n = n.parentNode)
                for (const s of n.parentNode.children) if (s !== n && !/^(SCRIPT|STYLE|LINK)$/.test(s.tagName)) out.push(s.hasAttribute('inert')); return out; })()"""
            got = cdp.js(outside, sid)
            self.assertTrue(got and all(got), got)
            # A panel that mounts after the dialog opened (the palette, Help, the peek) is held as it appears.
            cdp.js("(() => { const d = document.createElement('div'); d.id = 'late-panel'; document.querySelector('[data-draft-email]').parentNode.appendChild(d); })()", sid)
            self.until(cdp, sid, "document.getElementById('late-panel').hasAttribute('inert')", "the late panel to be held")
            key(cdp, sid, "Escape")
            self.until(cdp, sid, "!document.querySelector('[data-draft-email]')", "the dialog to close")
            self.assertFalse(cdp.js("!!document.querySelector('[inert]')", sid), "all released again")

    def test_draft_email_for_an_item_with_no_owner_stays_greyed_with_its_reason(self):
        with chrome() as cdp:
            a = self.id_of("Order the laptops")
            with self.store.step("dashboard", USER) as st:
                st.update("actions", a, {"owner": "TBC"})
            sid = self.visit(cdp)
            self.open_menu(cdp, sid, self.TABLE % a)
            by = {e[0]: e for e in self.entries(cdp, sid)}
            self.assertEqual(by["draft"][1:3], ["Draft email to the owner", True])
            self.assertIn("no owner", by["draft"][3])

    def test_draft_email_in_view_still_opens(self):
        with chrome() as cdp:
            sid = self.visit(cdp, edit=False)
            a = self.id_of("Order the laptops")
            self.open_menu(cdp, sid, self.TABLE % a)
            click(cdp, sid, "[data-rm=draft]")
            self.until(cdp, sid, "!!document.querySelector('[data-draft-email] .de')", "the Draft email, which changes nothing")

    def test_in_view_i_sent_it_is_greyed_with_the_house_line_and_records_nothing(self):
        with chrome() as cdp:
            sid = self.visit(cdp, edit=False)
            a = self.id_of("Order the laptops")
            self.open_menu(cdp, sid, self.TABLE % a)
            click(cdp, sid, "[data-rm=draft]")
            self.until(cdp, sid, "!!document.querySelector('[data-draft-email] .de')", "the Draft email")
            find = "[...document.querySelectorAll('.de .pk-btn')].find(b => /sent/.test(b.textContent))"
            self.assertTrue(cdp.js(find + ".disabled", sid), "I sent it is greyed in View")
            self.assertIn("Switch to Edit to change this.", cdp.js("document.querySelector('.de').textContent", sid))
            self.assertFalse(cdp.js("[...document.querySelectorAll('.de .pk-btn')].find(b => /Copy as text/.test(b.textContent)).disabled", sid), "copy stays")
            cdp.js(find + ".click()", sid)
            time.sleep(0.8)
            self.assertEqual(self.sent_calls, [], "no POST /api/draft-email/sent")
            self.assertEqual(self.store.email_sent_for("ABC"), [], "no email_sent record")

    def test_after_i_sent_it_focus_stays_in_the_dialog_and_escape_closes_it_and_returns_to_the_row(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            a = self.id_of("Order the laptops")
            self.open_menu(cdp, sid, self.TABLE % a)
            click(cdp, sid, "[data-rm=draft]")
            self.until(cdp, sid, "!!document.querySelector('[data-draft-email] .de')", "the Draft email")
            cdp.js("(() => { const b = [...document.querySelectorAll('.de .pk-btn')].find(x => /sent/.test(x.textContent)); b.focus(); b.click(); })()", sid)
            self.until(cdp, sid, "/sent/i.test(document.querySelector('.de-note').textContent)", "the note")
            self.until(cdp, sid, "document.querySelector('.de').contains(document.activeElement) && document.activeElement !== document.body", "focus back in the dialog")
            key(cdp, sid, "Escape")
            self.until(cdp, sid, "!document.querySelector('[data-draft-email]')", "the dialog to close")
            self.until(cdp, sid, f"document.activeElement.dataset.id === {json.dumps(a)}", "focus back on the row")

    def test_the_dialog_closes_when_the_page_changes(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            a = self.id_of("Order the laptops")
            self.open_menu(cdp, sid, self.TABLE % a)
            click(cdp, sid, "[data-rm=draft]")
            self.until(cdp, sid, "!!document.querySelector('[data-draft-email] .de')", "the Draft email")
            cdp.js("location.hash = '#settings&p=ABC'", sid)
            self.until(cdp, sid, "!document.querySelector('[data-draft-email]')", "the dialog to close on another page")
            self.assertFalse(cdp.js("document.querySelector('#main, .top').hasAttribute('inert')", sid))

    def test_a_missing_item_says_so_in_words(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            a = self.id_of("Order the laptops")
            with self.store.step("dashboard", USER) as st:
                st.archive("actions", a)                                  # gone from the database, still on the page until it reads again
            self.open_menu(cdp, sid, self.TABLE % a)
            click(cdp, sid, "[data-rm=draft]")
            t = self.wait_toast(cdp, sid, "note")
            self.assertEqual(t["text"], draft_email_feed.BAD_ITEM)
            self.assertFalse(cdp.js("!!document.querySelector('[data-draft-email]')", sid))

    def test_a_hidden_or_sensitive_item_is_not_offered_and_the_dialog_says_so_instead_of_an_empty_draft(self):
        with chrome() as cdp:
            hid, sens = self.id_of("Order the laptops"), self.id_of("Send the invitations")
            with self.store.step("dashboard", USER) as st:
                st.create("report_hidden", {"project": "ABC", "item_id": hid})
                st.create("item_labels", {"item_id": sens, "label": "Sensitive"})
                st.update("actions", sens, {"owner": "Sara Khan"})
            sid = self.visit(cdp)
            for item in (hid, sens):
                self.open_menu(cdp, sid, self.TABLE % item)
                click(cdp, sid, "[data-rm=draft]")
                if item == sens:                      # main's route refuses a Sensitive item for anyone: a plain note, no dialog, nothing to copy
                    note = self.wait_toast(cdp, sid, "note")
                    self.assertEqual(note["text"], "One of those items can't go in an email. Reload the page and choose again.")
                    self.assertEqual(self.drafts[-1], {"project": "ABC", "item": item, "picked": [item]})
                    self.assertFalse(cdp.js("!!document.querySelector('[data-draft-email]')", sid))
                    continue
                self.until(cdp, sid, "!!document.querySelector('[data-draft-email] .de')", "the Draft email")
                self.assertEqual(self.drafts[-1], {"project": "ABC", "item": item, "picked": [item]})
                self.assertEqual(cdp.js("document.querySelector('.de-problem').textContent", sid), NOT_OFFERED, "said plainly")
                self.assertEqual(cdp.js("document.querySelectorAll('.de .pick input').length", sid), 0, "nothing to tick")
                self.assertTrue(cdp.js("[...document.querySelectorAll('.de .pk-btn.pri, .de .pk-btn')].filter(b => /Copy|sent/.test(b.textContent)).every(b => b.disabled)", sid), "nothing to copy or record")
                self.assertFalse(cdp.js("/Share|Order|Book|laptops|training/.test(document.querySelector('.de-preview').textContent)", sid), "no words of the item in the draft")
                key(cdp, sid, "Escape")
                self.until(cdp, sid, "!document.querySelector('[data-draft-email]')", "the dialog to close")

    def test_i_sent_it_saves_the_ids_through_pr_68s_own_route(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            a = self.id_of("Order the laptops")
            self.open_menu(cdp, sid, self.TABLE % a)
            click(cdp, sid, "[data-rm=draft]")
            self.until(cdp, sid, "!!document.querySelector('[data-draft-email] .de')", "the Draft email")
            self.assertEqual(self.store.email_sent_for("ABC"), [])
            cdp.js("[...document.querySelectorAll('.de .pk-btn')].find(b => /sent/.test(b.textContent)).click()", sid)
            self.until(cdp, sid, "/sent/i.test(document.querySelector('.de-note').textContent)", "the note")
            rows = self.store.email_sent_for("ABC")
            self.assertEqual([r["ids"] for r in rows], [[a]])

    def test_a_double_press_of_i_sent_it_makes_one_post_and_one_record(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            a = self.id_of("Order the laptops")
            self.open_menu(cdp, sid, self.TABLE % a)
            click(cdp, sid, "[data-rm=draft]")
            self.until(cdp, sid, "!!document.querySelector('[data-draft-email] .de')", "the Draft email")
            cdp.js("(() => { const b = [...document.querySelectorAll('.de .pk-btn')].find(x => /sent/.test(x.textContent)); b.click(); b.click(); })()", sid)
            self.until(cdp, sid, "/sent/i.test(document.querySelector('.de-note').textContent)", "the note")
            self.until(cdp, sid, "[...document.querySelectorAll('.de .pk-btn')].every(x => !/sent/.test(x.textContent) || !x.disabled)", "the button ready again after the save")
            # #650: the button is usually ready already once the note shows, so give a second POST a short time to arrive
            # (a bounded wait for something that must NOT happen, as tests/test_report_editor.py does)
            time.sleep(0.3)
            self.assertEqual(len(self.sent_calls), 1, "one POST /api/draft-email/sent for two presses")
            self.assertEqual([r["ids"] for r in self.store.email_sent_for("ABC")], [[a]], "one record")
            self.assertFalse(cdp.js("[...document.querySelectorAll('.de .pk-btn')].find(x => /sent/.test(x.textContent)).disabled", sid), "ready again after the save")

    def test_on_the_board_and_in_full_screen(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            self.board(cdp, sid, "status")
            a, b = self.id_of("Order the laptops"), self.id_of("Send the invitations")
            self.open_menu(cdp, sid, self.CARD % a)
            self.assertEqual(cdp.js("document.querySelector('.rowmenu [role=menu]').getAttribute('aria-label')", sid), f"Actions for {a}")
            self.assertEqual(self.entries(cdp, sid)[0][1], "Draft email to Sara Khan")
            key(cdp, sid, "Escape")
            self.shut(cdp, sid)
            self.until(cdp, sid, f"(document.activeElement.closest('article') || {{dataset: {{}}}}).dataset.id === {json.dumps(a)}", "focus back on the card")
            before = self.steps()
            click(cdp, sid, "#board-full")
            self.until(cdp, sid, "document.body.classList.contains('board-full')")
            self.open_menu(cdp, sid, self.CARD % b)
            click(cdp, sid, "[data-rm=status]")
            click(cdp, sid, "[data-rm='s:Closed']")
            self.wait_toast(cdp, sid, "done")
            self.assertEqual((self.row(b)["status"], self.steps()), ("Closed", before + 1))
            self.assertTrue(cdp.js("document.body.classList.contains('board-full')", sid), "full screen stays")
            self.until(cdp, sid, f"!document.querySelector(\"{self.CARD % b}\") || document.querySelector(\"{self.CARD % b}\").closest('section').dataset.col === 'Closed'", "the card in its new column")
            cdp.js(f"document.querySelector(\"article[data-id='{a}'] .bc-main\").focus()", sid)
            key(cdp, sid, "F10", shift=True)
            self.until(cdp, sid, "!!document.querySelector('.rowmenu [role=menu]')", "the keys open it on a card too")
            key(cdp, sid, "Escape")
            self.shut(cdp, sid)
            self.assertTrue(cdp.js("document.body.classList.contains('board-full')", sid), "Esc closed the menu only, not full screen")

    # ---- row 848: where it opens, hover, no jump, Duplicate of a Sensitive item ----
    def box(self, cdp, sid):
        return cdp.js("(() => { const b = document.querySelector('.rowmenu > [role=menu]').getBoundingClientRect(); return [b.left, b.top, b.width, b.height]; })()", sid)

    def hover(self, cdp, sid, selector):
        x, y = cdp.js(f"(() => {{ const b = document.querySelector({json.dumps(selector)}).getBoundingClientRect(); return [b.x + b.width / 2, b.y + b.height / 2]; }})()", sid)
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, sid)

    def test_the_menu_opens_at_the_pointer(self):
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width=width)
                a = self.id_of("Order the laptops")
                cdp.js(f"document.querySelector(\"{self.TABLE % a}\").scrollIntoView({{block: 'start'}})", sid)
                px, py = 200, cdp.js(f"Math.round(document.querySelector(\"{self.TABLE % a}\").getBoundingClientRect().top + 10)", sid)
                for t, b, bs in (("mouseMoved", "none", 0), ("mousePressed", "right", 2), ("mouseReleased", "right", 0)):
                    cdp.call("Input.dispatchMouseEvent", {"type": t, "x": px, "y": py, "button": b, "buttons": bs, "clickCount": 1}, sid)
                self.until(cdp, sid, "!!document.querySelector('.rowmenu [role=menu]')", "the menu")
                left, top = self.box(cdp, sid)[:2]
                self.assertLessEqual(abs(left - px), 2, (width, left, px))
                self.assertLessEqual(abs(top - py), 2, (width, top, py))

    def test_a_list_opens_on_hover_stays_while_the_pointer_travels_and_the_menu_does_not_move(self):
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width=width)
                a, before = self.id_of("Order the laptops"), self.steps()
                self.open_menu(cdp, sid, self.TABLE % a)
                still = self.box(cdp, sid)
                for rm, first in (("status", "s:Delayed"), ("due", "d:2026-10-30"), ("owner", None)):
                    self.hover(cdp, sid, f".rowmenu > [role=menu] [data-rm={rm}]")
                    self.until(cdp, sid, f"!!document.querySelector('.rowmenu .rm-fly [role=menuitem]')", f"the {rm} list on hover")
                    if first:
                        self.assertEqual(self.fly(cdp, sid)[0][0], first)
                    self.assertEqual(self.box(cdp, sid), still, f"{rm}: the menu did not move or resize")
                    self.hover(cdp, sid, ".rowmenu .rm-fly [role=menuitem]")         # on to the list: it stays open
                    time.sleep(0.5)
                    self.assertTrue(cdp.js("!!document.querySelector('.rowmenu .rm-fly')", sid), f"{rm}: the list stays while the pointer is on it")
                    fl = cdp.js("(() => { const f = document.querySelector('.rm-fly').getBoundingClientRect(), m = document.querySelector('.rowmenu > [role=menu]').getBoundingClientRect(); return [f.left >= m.right - 4 || f.right <= m.left + 4, f.left >= 0, f.right <= window.innerWidth]; })()", sid)
                    self.assertEqual(fl, [True, True, True], (width, rm, "beside the menu, inside the window"))
                    self.hover(cdp, sid, ".rowmenu > [role=menu] [data-rm=link]")      # to a plain entry: it shuts
                    self.until(cdp, sid, "!document.querySelector('.rowmenu .rm-fly')", f"the {rm} list to shut")
                self.assertEqual(self.steps(), before, "hovering writes nothing")

    def test_a_click_acts_once_and_the_menu_does_not_jump_or_resize_on_the_way(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            a, before = self.id_of("Order the laptops"), self.steps()
            self.open_menu(cdp, sid, self.TABLE % a)
            still = self.box(cdp, sid)
            click(cdp, sid, ".rowmenu > [role=menu] [data-rm=status]")                 # a click on the entry the hover opened
            self.until(cdp, sid, "!!document.querySelector('.rowmenu .rm-fly')", "the list")
            self.assertEqual(self.box(cdp, sid), still, "the click did not move or resize the menu")
            self.assertEqual(self.steps(), before, "the click on the entry changes nothing")
            click(cdp, sid, "[data-rm='s:Delayed']")
            self.wait_toast(cdp, sid, "done")
            self.assertEqual((self.row(a)["status"], self.steps()), ("Delayed", before + 1), "one step")
            self.shut(cdp, sid)
            self.until(cdp, sid, f"document.activeElement.dataset.id === {json.dumps(a)}", "focus back on the row")

    def test_duplicate_of_a_sensitive_item_stays_hidden_from_the_report(self):
        with chrome() as cdp:
            a = self.id_of("Order the laptops")
            with self.store.step("dashboard", USER) as st:
                st.create("item_labels", {"item_id": a, "label": "Sensitive"})
                st.create("report_hidden", {"project": "ABC", "item_id": a})
            sid = self.visit(cdp)
            self.open_menu(cdp, sid, self.TABLE % a)
            click(cdp, sid, "[data-rm=dup]")
            ref = self.wait_toast(cdp, sid, "done")["text"].split(" ")[0]
            self.assertNotEqual(ref, a)
            self.assertEqual([r[0] for r in self.query("SELECT label FROM item_labels WHERE item_id = ?", ref)], ["Sensitive"], "the copy carries the label")
            self.assertEqual(len(self.query("SELECT item_id FROM report_hidden WHERE item_id = ?", ref)), 1, "and stays hidden from the report")

    def test_at_900_px_the_menu_stays_inside_the_window(self):
        with chrome() as cdp:
            sid = self.visit(cdp, width=900, height=500)
            rows = cdp.js("[...document.querySelectorAll('tr[data-id]')].map(r => r.dataset.id)", sid)
            self.open_menu(cdp, sid, self.TABLE % rows[-1])
            box = cdp.js("(() => { const b = document.querySelector('.rowmenu').getBoundingClientRect(); return [b.left, b.top, b.right, b.bottom]; })()", sid)
            self.assertTrue(box[0] >= 0 and box[1] >= 0 and box[2] <= 900 and box[3] <= 500, box)

    def test_no_dead_draft_email_event_is_left(self):
        for f in ("edit/RowMenu.jsx", "logic/rowMenu.js"):
            self.assertNotIn("clark:draft-email", (ROOT / "src" / "clark" / "page" / "src" / f).read_text(encoding="utf-8"))
        self.assertNotIn("clark:draft-email", (ROOT / "src" / "clark" / "page" / "page.html").read_text(encoding="utf-8"))

    def test_the_published_page_has_no_menu(self):
        view = (ROOT / "src" / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for word in ("data-rowmenu", "clark:draft-email", "Copy link to this item"):
            self.assertNotIn(word, view)


if __name__ == "__main__":
    unittest.main()
