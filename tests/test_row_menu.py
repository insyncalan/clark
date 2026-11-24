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

    def test_the_chosen_chase_tone_is_sent_and_kept_in_the_dialogs_state(self):
        st = {"mode": "chase", "picked": ["ABC-A-001"], "replyBy": "", "unblocks": "", "includeUpdate": False, "tone": 2}
        got = self.js(f"RM.draftRequest('ABC-A-001', {json.dumps(st)})")
        self.assertEqual(got.get("tone"), 2, "the tone the person pressed goes to the server")
        reply = {"mode": "chase", "picked": ["ABC-A-001"]}
        self.assertEqual(self.js(f"RM.draftState({json.dumps(reply)}, {json.dumps(st)})").get("tone"), 2,
                         "the pressed tone stays in the state for the next ask")
        st1 = dict(st, mode="update_request")
        self.assertNotIn("tone", self.js(f"RM.draftRequest('ABC-A-001', {json.dumps(st1)})"), "only a chase carries a tone")

    def test_the_owners_address_and_name_come_from_their_people_row_and_ride_on_both_asks(self):
        ppl = json.dumps([{"id": "P-001", "name": "Ada Quillfeather", "email": " ada@example.com "},
                          {"id": "P-002", "name": "Bo Bad", "email": "a@b.co,c@d.co"}, {"id": "P-003", "name": "Cy None", "email": ""},
                          {"id": "P-004", "name": "Di Line", "email": "a@b.co\nBcc: x@y.co"}, {"id": "P-005", "name": "Ed Long", "email": "x" * 250 + "@a.co"}])
        self.assertEqual(self.js(f"RM.recipientOf({ppl}, 'P-001')"), {"email": "ada@example.com", "name": "Ada Quillfeather"})
        for owner in ("P-002", "P-003", "P-004", "P-005", "P-404", "", None):
            self.assertIsNone(self.js(f"RM.recipientOf({ppl}, {json.dumps(owner)})"), owner)       # never invented, never a bad address
        self.assertIsNone(self.js("RM.recipientOf(null, 'P-001')"))
        who = {"email": "ada@example.com", "name": "Ada Quillfeather"}
        self.assertEqual(self.js(f"RM.draftRequest('ABC-A-001', null, {json.dumps(who)})"),
                         {"item": "ABC-A-001", "picked": ["ABC-A-001"], "email": "ada@example.com", "name": "Ada Quillfeather"})
        st = {"mode": "chase", "picked": ["ABC-A-001"], "replyBy": "", "unblocks": "", "includeUpdate": False}
        self.assertEqual(self.js(f"RM.draftRequest('ABC-A-001', {json.dumps(st)}, {json.dumps(who)})"),
                         {"item": "ABC-A-001", "mode": "chase", "picked": ["ABC-A-001"], "include_update": False, "email": "ada@example.com", "name": "Ada Quillfeather"})
        self.assertEqual(self.js("RM.draftRequest('ABC-A-001', null, null)"), {"item": "ABC-A-001", "picked": ["ABC-A-001"]})

    def test_the_name_sent_with_the_address_is_trimmed_and_left_out_when_the_server_would_refuse_it(self):
        def name_for(name):
            ppl = json.dumps([{"id": "P-001", "name": name, "email": "ada@example.com"}])
            return self.js(f"RM.recipientOf({ppl}, 'P-001')")["name"]
        self.assertEqual(name_for("  Ada Q  "), "Ada Q")
        self.assertEqual(name_for("n" * 100), "n" * 100)
        self.assertEqual(name_for("n" * 101), "")                 # over 100 characters: no name, the address still goes
        self.assertEqual(name_for("Ada\nBcc: x@y.co"), "")        # a line break in a name never reaches the server
        self.assertEqual(name_for("Ada\rQ"), "")

    def test_the_page_refuses_every_address_the_server_refuses(self):
        """The page rule (recipientOf) mirrors draft_email_feed: ADDRESS, then no Cf, Co or Cs character, and a control character or
        a space inside makes one_line leave a gap the ADDRESS rule refuses. The same table is run against the server's own rule below."""
        bad = ["a\u200b@b.co", "a\u202e@b.co", "a\x1c@b.co", "a @b.co", "a\ud800@b.co", "a\x00@b.co", "a\x7f@b.co", "a\x85@b.co",
               "a\ufeff@b.co", "a\ue000@b.co", "a\u2028@b.co", "a\u00a0@b.co", "a@b\u200d.co", "a@b.co\u202c", "a\tb@b.co"]
        for addr in bad:
            ppl = json.dumps([{"id": "P-001", "name": "Ada", "email": addr}])
            self.assertIsNone(self.js(f"RM.recipientOf({ppl}, 'P-001')"), repr(addr))
            self.assertFalse(self.server_takes(addr), repr(addr))
        good = json.dumps([{"id": "P-001", "name": "Ada", "email": "ada@example.com"}])
        self.assertEqual(self.js(f"RM.recipientOf({good}, 'P-001')")["email"], "ada@example.com")

    def test_the_address_length_limit_is_the_servers_exactly_254_in_255_out(self):
        """Both sides of the limit: the page must not drop an address the server takes, nor send one it refuses."""
        for n, want in ((254, True), (255, False)):
            addr = "x" * (n - 5) + "@a.co"
            ppl = json.dumps([{"id": "P-001", "name": "Ada", "email": addr}])
            got = self.js(f"RM.recipientOf({ppl}, 'P-001')")
            self.assertEqual(got is not None, want, n)
            self.assertEqual(len(addr) <= draft_email_feed.MAX_EMAIL, want, n)

    @staticmethod
    def server_takes(addr):
        """True when draft_email_feed's address rule lets the address through (the rule in make(): one_line, ADDRESS, no Cf, Co, Cs)."""
        import unicodedata
        from clark import draft_email
        email = draft_email.one_line(addr)
        return bool(email) and bool(draft_email_feed.ADDRESS.fullmatch(email)) and not any(unicodedata.category(c) in draft_email_feed.HIDDEN_IN_TEXT for c in email)

    def test_the_draft_entrys_reason_line_follows_the_same_rule_as_the_address_that_is_sent(self):
        row = json.dumps({**self.ACTION, "owner_id": "P-001"})
        for addr in ("a\u200b@b.co", "x" * 250 + "@a.co", "a@b.co,c@d.co"):
            ppl = json.dumps({"people": [{"id": "P-001", "name": "Ada", "email": addr}]})
            got = self.js(f"RM.draftEntry({row}, {ppl})")
            self.assertEqual((got["to"], got["reason"]), ("", "Ada Quillfeather has no email on the People list, so the To line is left empty."), repr(addr))
        ok = json.dumps({"people": [{"id": "P-001", "name": "Ada", "email": "ada@example.com"}]})
        self.assertEqual(self.js(f"RM.draftEntry({row}, {ok})")["to"], "ada@example.com")

    def test_the_lists_offer_what_the_cells_offer_without_what_the_item_has(self):
        row = json.dumps(self.ACTION)
        self.assertEqual(self.js(f"RM.statusList({row})"), ["Delayed", "Closed", "Cancelled"])
        made = json.dumps({"id": "ABC-D-002", "kind": "decision", "owner": "X Y", "status": "Made"})
        self.assertEqual(self.js(f"RM.statusList({made})"), ["Withdrawn"], "a made decision never goes back to Pending")
        self.assertEqual(self.js(f"RM.ownerList(['Ada Quillfeather', 'Zelda Quince'], {row})"), ["Zelda Quince"])
        self.assertEqual(self.js(f"RM.dueList({json.dumps(TODAY)})"),
                         [{"id": "friday", "name": "Friday", "day": "2026-10-30", "line": "30-10-2026"},
                          {"id": "week", "name": "A week on", "day": "2026-11-05", "line": "05-11-2026"}])

    def test_item_1070_hostile_text_in_the_change_owner_search_never_throws_and_markup_is_only_text(self):
        """Hostile pass: control characters, markup, quotes, a huge string, unicode and odd register rows (null, numbers) are only text to the search."""
        row = json.dumps(self.ACTION)
        reg = json.dumps([{"name": "Ada Quillfeather"}, None, {"name": None}, {"name": 42, "aliases": 7}, {"name": "\u00dcn\u00ef \u540d\u524d"}])
        names = json.dumps(["Zelda Quince"])
        typed = ["<script>alert(1)</script>", "\u0000\u0007bell", "'\"`\\", "x" * 100000, "\u00e9\u00e9", "%", "*", ".", "a;b", "\u202eevil"]
        got = self.js(f"{json.dumps(typed)}.map((t) => [RM.ownerChoices({reg}, {names}, {row}, t), RM.canAddPerson({reg}, {names}, {row}, t)])")
        for t, (found, can) in zip(typed, got):
            self.assertEqual(found, [], repr(t[:20]))
            self.assertEqual(can, True, repr(t[:20]) + ": an unknown name is offered as text; the save's own checks refuse hidden characters")
        self.assertEqual(self.js(f"RM.ownerChoices({reg}, {names}, {row}, '\u540d')"), ["\u00dcn\u00ef \u540d\u524d"])
        self.assertEqual(self.js(f"RM.canAddPerson({reg}, {names}, {row}, '  ADA   quillfeather ')"), False, "spacing and case do not make a known name new")

    def test_item_1070_typing_in_change_owner_searches_the_register_and_the_projects_names_and_offers_to_add_only_an_unknown_name(self):
        row = json.dumps(self.ACTION)
        reg = json.dumps([{"name": "Ada Quillfeather", "email": "ada@example.com"}, {"name": "Bryony Castellan", "aliases": "Bry C"},
                          {"name": "Cedric Dunmore", "role": "Supplier lead"}, {"name": "Old Hand", "archived": 1}])
        names = json.dumps(["Ada Quillfeather", "Zelda Quince"])
        self.assertEqual(self.js(f"RM.ownerChoices({reg}, {names}, {row}, '')"), ["Zelda Quince"], "no text: the list as it was, without the owner")
        self.assertEqual(self.js(f"RM.ownerChoices({reg}, {names}, {row}, 'bry')"), ["Bryony Castellan"], "the register is searched, an alias too")
        self.assertEqual(self.js(f"RM.ownerChoices({reg}, {names}, {row}, 'SUPPLIER')"), ["Cedric Dunmore"], "role")
        self.assertEqual(self.js(f"RM.ownerChoices({reg}, {names}, {row}, 'quil')"), [], "the current owner is never offered")
        self.assertEqual(self.js(f"RM.ownerChoices({reg}, {names}, {row}, 'zel')"), ["Zelda Quince"], "a name in the project that is not on the register")
        self.assertEqual(self.js(f"RM.ownerChoices({reg}, {names}, {row}, 'old')"), [], "an archived person is not found")
        for typed, want in (("Wilhelmina Frost", True), ("  Wilhelmina   Frost ", True), ("", False), ("   ", False), ("tbc", False),
                            ("Bryony Castellan", False), ("bry c", False), ("Zelda Quince", False), ("Ada Quillfeather", False)):
            self.assertEqual(self.js(f"RM.canAddPerson({reg}, {names}, {row}, {json.dumps(typed)})"), want, typed)

    def test_item_1070_an_archived_persons_name_is_known_so_it_is_not_offered_as_new_and_the_current_owner_is_never_offered_even_when_the_project_lacks_them(self):
        row = json.dumps(self.ACTION)
        reg = json.dumps([{"name": "Old Hand", "aliases": "Oldie", "archived": 1}, {"name": "Bryony Castellan"}])
        names = json.dumps(["Zelda Quince"])
        for typed in ("Old Hand", "old   hand", "Oldie"):
            self.assertEqual(self.js(f"RM.canAddPerson({reg}, {names}, {row}, {json.dumps(typed)})"), False, typed + ": the picker counts an archived name as known")
        self.assertEqual(self.js(f"RM.canAddPerson({reg}, {names}, {row}, 'Old Hander')"), True, "a different name is still offered")
        self.assertEqual(self.js(f"RM.canAddPerson([], {names}, {row}, 'Ada Quillfeather')"), False, "the owner, though the project's names and the register lack them")

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

    def settled(self, cdp, sid):
        """Row 878: a menu drops in over --dur-instant; its place is measured and clicked only once that has finished."""
        self.until(cdp, sid, "document.querySelector('.rowmenu') && document.querySelector('.rowmenu').getAnimations({subtree: true}).length === 0", "the menu has settled")

    def open_menu(self, cdp, sid, selector):
        right_click(cdp, sid, selector)
        self.until(cdp, sid, "!!document.querySelector('.rowmenu [role=menu]')", "the menu")
        self.settled(cdp, sid)

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
                                                   "Hide from the client", "Copy link to this item", "Copy ID", "Duplicate", "Archive", "Delete"])
            by = {e[0]: e for e in got}
            self.assertEqual(by["draft"][2:], [False, "Sara Khan has no email on the People list, so the To line is left empty."],
                             "open, with the To line's reason in words (#1048: the People list is read when the menu opens)")
            self.assertFalse(any(by[k][2] for k in ("draft", "eye", "peek", "status", "due", "owner", "link", "copyid", "dup", "archive", "delete")))
            self.assertEqual(by["eye"][3], "", "the eye has nothing to explain in Edit")
            self.assertEqual(cdp.js("document.activeElement.dataset.rm", sid), "draft", "focus is on the first entry that can be used")
            box = cdp.js("(() => { const b = document.querySelector('.rowmenu').getBoundingClientRect(); return [b.left, b.top, b.right, b.bottom]; })()", sid)
            self.assertTrue(box[0] >= 0 and box[1] >= 0 and box[2] <= 1400 and box[3] <= 900, box)
            self.assertFalse(cdp.js("!!document.querySelector('.cpop')", sid))
            self.assertEqual(self.steps(), before)
            # The Draft email's line is read with it, so a screen reader hears that the To line is empty.
            why = cdp.js("(() => { const b = document.querySelector('.rowmenu [data-rm=draft]'); const d = document.getElementById(b.getAttribute('aria-describedby')); return d ? d.textContent : null; })()", sid)
            self.assertEqual(why, "Sara Khan has no email on the People list, so the To line is left empty.")
            # The menu items have a real focus ring: 2 px, a colour, not none.
            key(cdp, sid, "ArrowDown")                       # a key moved focus, so :focus-visible applies
            self.until(cdp, sid, "document.getAnimations().filter(a => !(a.effect && a.effect.target && a.effect.target.classList && a.effect.target.classList.contains('toast-bar'))).length === 0", "the focus ring to finish")
            ring = cdp.js("(() => { const c = getComputedStyle(document.activeElement); return [c.outlineStyle, c.outlineWidth, c.outlineColor]; })()", sid)
            self.assertEqual(ring[:2], ["solid", "2px"], ring)
            self.assertNotEqual(ring[2], "rgba(0, 0, 0, 0)")

    def test_item_977_the_entry_words_are_plain_not_the_browsers_bold_in_the_menu_and_in_the_list_beside_it(self):
        """Item 977: every entry's words (the <b> in each entry) draw at regular weight. The control is a <b> outside the menu, which the browser
        draws bold, so the test fails if the rule goes (the entries turn bold) and fails if the probe stops reading weights (the control is not bold)."""
        weights = "[...document.querySelectorAll('%s')].map(b => getComputedStyle(b).fontWeight)"
        with chrome() as cdp:
            sid = self.visit(cdp)
            a = self.id_of("Order the laptops")
            self.open_menu(cdp, sid, self.TABLE % a)
            control = cdp.js("(() => { const b = document.body.appendChild(document.createElement('b')); const w = getComputedStyle(b).fontWeight; b.remove(); return w; })()", sid)
            self.assertIn(control, ("700", "bold"), "the control: a plain <b> is bold, so a weight of 400 below is the rule's doing")
            got = cdp.js(weights % ".rowmenu [role=menuitem] .rm-t b", sid)
            self.assertEqual(len(got), 11, "every entry of the menu was read (Delete is the eleventh)")
            self.assertEqual(set(got), {"400"}, "the menu's entries are regular weight")
            cdp.js("document.querySelector('.rowmenu [data-rm=status]').click()", sid)
            self.until(cdp, sid, "!!document.querySelector('.rowmenu .rm-fly [role=menuitem]')", "the list beside Change status")
            listed = cdp.js(weights % ".rowmenu .rm-fly [role=menuitem] .rm-t b", sid)
            self.assertTrue(listed, "the list's entries were read")
            self.assertEqual(set(listed), {"400"}, "the list's entries are regular weight")

    def test_row_978_every_entry_has_an_icon_from_the_existing_set_before_its_words_16px_muted_and_taking_the_entry_colour_on_hover(self):
        """Row 978: each entry of the menu has an icon (the page's own set, named here) before its words, 16 px, in the muted text colour at rest,
        and in the entry's own colour under the pointer. The list beside an entry (statuses, dates, names) has none."""
        want = {"draft": "pencil", "peek": "expand", "status": "half", "due": "cal", "owner": "user", "link": "ext", "copyid": "doc", "dup": "plus", "archive": "archive"}
        with chrome() as cdp:
            sid = self.visit(cdp)
            a = self.id_of("Order the laptops")
            self.open_menu(cdp, sid, self.TABLE % a)
            got = cdp.js("Object.fromEntries([...document.querySelectorAll('.rowmenu > .ddmenu [role=menuitem]')].map(b => { const i = b.querySelector('svg.rm-ic'); "
                         "return [b.dataset.rm, i ? [i.dataset.icn, i.getBoundingClientRect().width, i.getBoundingClientRect().height, getComputedStyle(i).color, "
                         "!!(i.compareDocumentPosition(b.querySelector('.rm-t')) & Node.DOCUMENT_POSITION_FOLLOWING), i.getAttribute('aria-hidden'), b === document.activeElement || b.matches(':hover')] : null]; }))", sid)
            self.assertEqual(len(got), 11, "eleven entries")
            self.assertTrue(all(got.values()), "an icon for every entry")
            self.assertEqual({k: got[k][0] for k in want}, want, "the icons, by name")
            self.assertIn(got["eye"][0], ("eye", "eyeoff"))
            muted = cdp.js("(() => { const s = document.createElement('span'); s.style.color = 'var(--text-muted)'; document.body.appendChild(s); const c = getComputedStyle(s).color; s.remove(); return c; })()", sid)
            for k, v in got.items():
                self.assertEqual(v[1:3], [16, 16], f"{k}: 16 px")
                if not v[6]:      # the entry under focus or the pointer takes the entry's colour (checked below)
                    self.assertEqual(v[3], muted, f"{k}: muted at rest")
                self.assertTrue(v[4], f"{k}: before the words")
                self.assertEqual(v[5], "true", f"{k}: hidden from screen readers")
            x, y = cdp.js("(() => { const b = document.querySelector('.rowmenu [data-rm=archive]').getBoundingClientRect(); return [b.x + 60, b.y + b.height / 2]; })()", sid)
            cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, sid)
            self.until(cdp, sid, "(() => { const b = document.querySelector('.rowmenu [data-rm=archive]'); return b.matches(':hover') && getComputedStyle(b.querySelector('svg')).color === getComputedStyle(b).color; })()", "the icon takes the entry's colour under the pointer")
            self.assertNotEqual(cdp.js("getComputedStyle(document.querySelector('.rowmenu [data-rm=archive] svg')).color", sid), muted, "and that colour is not the muted one")
            cdp.js("document.querySelector('.rowmenu [data-rm=status]').click()", sid)
            self.until(cdp, sid, "!!document.querySelector('.rowmenu .rm-fly [role=menuitem]')", "the list beside Change status")
            self.assertEqual(cdp.js("document.querySelectorAll('.rowmenu .rm-fly svg').length", sid), 0, "the list has no icons")

    def test_row_979_a_mouse_open_shows_no_ring_on_the_first_entry_even_after_a_key_was_pressed_and_a_key_brings_it_back(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            a = self.id_of("Order the laptops")
            key(cdp, sid, "Home")                       # the page's last input was the keyboard: :focus-visible would show on the first entry
            self.open_menu(cdp, sid, self.TABLE % a)
            self.until(cdp, sid, "document.getAnimations().filter(a => !(a.effect && a.effect.target && a.effect.target.classList && a.effect.target.classList.contains('toast-bar'))).length === 0", "the menu to finish opening")
            self.assertEqual(cdp.js("document.querySelector('.rowmenu > .ddmenu').dataset.pointer", sid), "1", "marked as a mouse open")
            self.assertEqual(cdp.js("document.activeElement.dataset.rm", sid), "draft", "the first entry has the focus")
            cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 1390, "y": 5}, sid)      # the menu opens under the pointer: move off it, so the first entry is not the hovered one
            self.until(cdp, sid, "!document.activeElement.matches(':hover')", "the pointer is off the first entry")
            ring = cdp.js("(() => { const c = getComputedStyle(document.activeElement); return [c.outlineStyle, c.backgroundColor]; })()", sid)
            self.assertEqual(ring, ["none", "rgba(0, 0, 0, 0)"], "no ring and no tint on the first entry")
            key(cdp, sid, "ArrowDown")                  # a key is used: the ring is back, on the entry the key moved to
            self.until(cdp, sid, "document.getAnimations().filter(a => !(a.effect && a.effect.target && a.effect.target.classList && a.effect.target.classList.contains('toast-bar'))).length === 0", "the ring to finish")
            self.assertEqual(cdp.js("document.querySelector('.rowmenu > .ddmenu').dataset.pointer || ''", sid), "", "the mark goes with the first key")
            self.assertEqual(cdp.js("getComputedStyle(document.activeElement).outlineStyle", sid), "solid", "the key brought the ring back")

    def test_row_979_the_menu_and_its_list_fade_without_the_drop_and_are_still_when_reduced_and_a_pass_over_entries_mounts_one_list(self):
        for reduce in (False, True):
            with self.subTest(reduce=reduce), chrome() as cdp:
                sid = self.visit(cdp)
                cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce" if reduce else "no-preference"}]}, sid)
                a = self.id_of("Order the laptops")
                name = "(el => getComputedStyle(document.querySelector(el)).animationName)"
                self.open_menu(cdp, sid, self.TABLE % a)
                self.until(cdp, sid, "document.getAnimations().filter(a => !(a.effect && a.effect.target && a.effect.target.classList && a.effect.target.classList.contains('toast-bar'))).length === 0", "the menu to finish opening")
                want = "none" if reduce else "m-in"
                self.assertEqual(cdp.js(name + "('.rowmenu > .ddmenu')", sid), want, "the row menu: a fade, not the 4 px drop (m-drop)")
                cdp.js("window.mounted = []; new MutationObserver((ms) => ms.forEach((m) => m.addedNodes.forEach((n) => { if (n.classList && n.classList.contains('rm-fly')) window.mounted.push(n.getAttribute('aria-label')); }))).observe(document.querySelector('.rowmenu'), {childList: true, subtree: true});", sid)
                cdp.js("['status', 'due', 'owner'].forEach((rm) => document.querySelector('.rowmenu > .ddmenu [data-rm=' + rm + ']').dispatchEvent(new PointerEvent('pointerenter', {pointerType: 'mouse'})))", sid)
                self.assertEqual(cdp.js("document.querySelectorAll('.rowmenu .rm-fly').length", sid), 0, "no list while the pointer only passes over the entries")
                self.until(cdp, sid, "!!document.querySelector('.rowmenu .rm-fly [role=menuitem]')", "the list after the pointer rests")
                self.until(cdp, sid, "document.getAnimations().filter(a => !(a.effect && a.effect.target && a.effect.target.classList && a.effect.target.classList.contains('toast-bar'))).length === 0", "the list to finish opening")
                self.assertEqual(cdp.js("window.mounted", sid), ["Change owner"], "one list was mounted, for the entry the pointer rested on")
                self.assertEqual(cdp.js(name + "('.rowmenu .rm-fly')", sid), want, "the list: a fade, not the drop")

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

    def test_tab_leaves_the_menu_from_the_row_not_from_the_top_of_the_page(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            a = self.id_of("Order the laptops")
            for deep in (False, True):
                cdp.js(f"document.querySelector(\"{self.TABLE % a}\").focus()", sid)
                key(cdp, sid, "ContextMenu")
                self.until(cdp, sid, "!!document.querySelector('.rowmenu [role=menu]')", "the menu")
                self.settled(cdp, sid)
                if deep:
                    key(cdp, sid, "ArrowDown")
                    key(cdp, sid, "ArrowDown")
                    key(cdp, sid, "ArrowRight")
                    self.until(cdp, sid, "!!document.querySelector('.rm-fly')", "the list")
                key(cdp, sid, "Tab")
                self.shut(cdp, sid)
                time.sleep(0.3)
                self.assertNotEqual(cdp.js("document.activeElement.className", sid), "skip", "Tab from the menu must not throw focus to the top of the page")
                self.assertNotEqual(cdp.js("document.activeElement.tagName", sid), "BODY", "focus is still on the page")

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
            self.assertEqual(cdp.js("document.activeElement.dataset.rm", sid), "delete")
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

    def add_register(self, *people):
        from _demo import USER
        for name, email in people:
            with self.store.step("dashboard", USER) as w:
                w.add_person(name=name, source="test", **({"email": email} if email else {}))

    def search_box(self, cdp, sid):
        self.until(cdp, sid, "!!document.querySelector('.rowmenu .rm-fly input[data-rm-search]')", "the search box in the owner list")

    # The menu reads the people before it opens, so the first read fails here (the menu opens with no list); the owner list then reads again, and that read is held.
    HOLD_PEOPLE = """(() => { const real = window.fetch.bind(window); let go, first = true; const held = new Promise((r) => { go = r; }); window.__peopleGo = go;
        window.fetch = (u, ...a) => { const get = String(u).indexOf('/api/people') === 0 && !(a[0] && a[0].method && a[0].method !== 'GET');
          if (get && first) { first = false; return Promise.resolve(new Response('{}', { status: 500 })); }
          return get ? held.then(() => real(u, ...a)) : real(u, ...a); }; })()"""

    def people_loaded(self, cdp, sid):
        """Item 1070: the owner list has read the people (the list marks itself while it has not)."""
        self.until(cdp, sid, "!!document.querySelector('.rowmenu .rm-fly input[data-rm-search]') && !document.querySelector('.rowmenu .rm-fly[data-rm-loading]')", "the people list to load")

    def type_in(self, cdp, sid, text):
        cdp.js("document.querySelector('.rowmenu .rm-fly input[data-rm-search]').focus()", sid)
        cdp.call("Input.insertText", {"text": text}, sid)

    def test_item_1070_change_owner_has_a_search_box_that_finds_people_on_the_register(self):
        self.add_register(("Bryony Castellan", ""), ("Cedric Dunmore", "cedric@example.com"))
        with chrome() as cdp:
            sid = self.visit(cdp)
            a = self.id_of("Order the laptops")
            self.open_menu(cdp, sid, self.TABLE % a)
            click(cdp, sid, "[data-rm=owner]")
            self.search_box(cdp, sid)
            self.people_loaded(cdp, sid)
            self.assertEqual(cdp.js("document.querySelector('.rowmenu .rm-fly input[data-rm-search]').placeholder", sid), "Type a name")
            self.assertEqual(cdp.js("document.activeElement.matches('input[data-rm-search]')", sid), True, "a click opens it on the box")
            self.type_in(cdp, sid, "cedric dunmore")
            self.until(cdp, sid, "[...document.querySelectorAll('.rowmenu .rm-fly [role=menuitem]')].length === 1", "the list narrowed", why=lambda: cdp.js("JSON.stringify([...document.querySelectorAll('.rowmenu .rm-fly [role=menuitem]')].map(b=>b.textContent))", sid))
            self.assertEqual([e[1] for e in self.fly(cdp, sid)], ["Cedric Dunmore"])
            self.assertEqual(cdp.js("!!document.querySelector('.rm-fly [data-rm=addp]')", sid), False, "a name on the register offers no add, as the picker does not")
            key(cdp, sid, "ArrowDown")
            self.assertEqual(cdp.js("document.activeElement.dataset.rm", sid), "o:Cedric Dunmore")
            key(cdp, sid, "Enter")
            self.assertEqual(self.wait_toast(cdp, sid, "done")["text"], f"Owner of {a} changed to Cedric Dunmore.")
            self.assertEqual(self.row(a)["owner"], "Cedric Dunmore")

    def test_item_1070_a_name_typed_before_the_people_list_loads_never_offers_add_for_a_person_who_exists(self):
        self.add_register(("Bryony Castellan", ""), ("Cedric Dunmore", "cedric@example.com"))
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width=width)
                a = self.id_of("Order the laptops")
                cdp.js(self.HOLD_PEOPLE, sid)
                self.open_menu(cdp, sid, self.TABLE % a)
                click(cdp, sid, "[data-rm=owner]")
                self.search_box(cdp, sid)
                cdp.js("window.__addSeen = false; new MutationObserver(() => { if (document.querySelector('.rm-fly [data-rm=addp]')) window.__addSeen = true; })"
                       ".observe(document.body, {subtree: true, childList: true, characterData: true})", sid)
                self.type_in(cdp, sid, "cedric dunmore")
                self.until(cdp, sid, "document.querySelector('.rowmenu .rm-fly input[data-rm-search]').value === 'cedric dunmore'", "the typing")
                time.sleep(0.6)
                self.assertEqual(cdp.js("!!document.querySelector('.rm-fly [data-rm=addp]')", sid), False, "no add while the list loads")
                self.assertEqual(cdp.js("!!document.querySelector('.rm-fly[data-rm-loading]')", sid), True, "still loading")
                cdp.js("window.__peopleGo()", sid)
                self.people_loaded(cdp, sid)
                self.until(cdp, sid, "[...document.querySelectorAll('.rowmenu .rm-fly [role=menuitem]')].some(b => b.textContent.trim() === 'Cedric Dunmore')", "the person found after the load")
                self.assertEqual([e[1] for e in self.fly(cdp, sid)], ["Cedric Dunmore"])
                self.assertEqual(cdp.js("window.__addSeen", sid), False, "an add entry was never in the page, at any moment")

    def test_item_1070_a_name_that_is_not_known_can_be_added_as_a_person_and_assigned_in_one_step_with_one_undo(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            a, before = self.id_of("Order the laptops"), self.steps()
            self.open_menu(cdp, sid, self.TABLE % a)
            click(cdp, sid, "[data-rm=owner]")
            self.search_box(cdp, sid)
            self.type_in(cdp, sid, "Wilhelmina Frost")
            self.until(cdp, sid, "!!document.querySelector('.rm-fly [data-rm=addp]')", "the add entry")
            self.assertEqual(cdp.js("document.querySelector('.rm-fly [data-rm=addp]').textContent.trim()", sid), "Add Wilhelmina Frost as a new person")
            click(cdp, sid, ".rm-fly [data-rm=addp]")
            self.until(cdp, sid, "!!document.querySelector('[data-pop] [data-new-name]')", "the new person form")
            self.assertEqual(cdp.js("document.querySelector('[data-pop] [data-new-name]').value", sid), "Wilhelmina Frost")
            click(cdp, sid, "[data-pop] [data-new-email]")
            cdp.call("Input.insertText", {"text": "not an email"}, sid)
            click(cdp, sid, "[data-pop] [data-new-save]")
            self.until(cdp, sid, "!!document.querySelector('[data-pop] .cp-problem')", "the shared email rule refuses it")
            self.assertEqual(self.steps(), before, "nothing was saved")
            cdp.js("(() => { const i = document.querySelector('[data-pop] [data-new-email]'); i.value = 'wilhelmina@example.com'; i.dispatchEvent(new Event('input', {bubbles: true})); })()", sid)
            click(cdp, sid, "[data-pop] [data-new-save]")
            self.assertEqual(self.wait_toast(cdp, sid, "done")["text"], f"Owner of {a} changed to Wilhelmina Frost, added as a new person.")
            self.assertEqual(self.row(a)["owner"], "Wilhelmina Frost")
            self.assertEqual(self.steps() - before, 1, "one step")
            self.assertEqual([r[0] for r in self.query("SELECT email FROM people WHERE name = ?", "Wilhelmina Frost")], ["wilhelmina@example.com"])

    def test_item_1070_a_list_opened_by_hover_keeps_a_focused_or_typed_search_when_the_pointer_leaves_and_still_closes_on_escape(self):
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width=width)
                a = self.id_of("Order the laptops")
                self.open_menu(cdp, sid, self.TABLE % a)
                self.hover(cdp, sid, ".rowmenu > [role=menu] [data-rm=owner]")
                self.search_box(cdp, sid)
                self.until(cdp, sid, "document.getAnimations().length === 0", "the list to finish opening")
                self.hover(cdp, sid, ".rowmenu .rm-fly input[data-rm-search]")
                click(cdp, sid, ".rowmenu .rm-fly input[data-rm-search]")
                cdp.call("Input.insertText", {"text": "Wilh"}, sid)
                cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 3, "y": 3}, sid)      # off the menu and its list
                time.sleep(0.7)
                self.assertTrue(cdp.js("!!document.querySelector('.rowmenu .rm-fly')", sid), "the list stays: the box has focus and text")
                self.assertEqual(cdp.js("document.querySelector('.rowmenu .rm-fly input[data-rm-search]').value", sid), "Wilh")
                cdp.js("document.querySelector('.rowmenu .rm-fly input[data-rm-search]').blur()", sid)
                self.hover(cdp, sid, ".rowmenu > [role=menu] [data-rm=link]")
                time.sleep(0.7)
                self.assertTrue(cdp.js("!!document.querySelector('.rowmenu .rm-fly')", sid), "text typed and not yet used is kept even unfocused")
                cdp.js("document.querySelector('.rowmenu .rm-fly input[data-rm-search]').focus()", sid)
                key(cdp, sid, "Escape")
                self.until(cdp, sid, "!document.querySelector('.rowmenu .rm-fly')", "Escape closes the list")
                self.open_menu(cdp, sid, self.TABLE % self.id_of("Order the laptops")) if cdp.js("!document.querySelector('.rowmenu')", sid) else None
                self.hover(cdp, sid, ".rowmenu > [role=menu] [data-rm=owner]")
                self.search_box(cdp, sid)
                self.until(cdp, sid, "document.getAnimations().length === 0", "the list to finish opening")
                self.hover(cdp, sid, ".rowmenu .rm-fly input[data-rm-search]")
                cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 3, "y": 3}, sid)
                self.until(cdp, sid, "!document.querySelector('.rowmenu .rm-fly')", "an empty, unfocused search still closes on leaving")

    def hover_owner_list(self, cdp, sid):
        a = self.id_of("Order the laptops")
        self.open_menu(cdp, sid, self.TABLE % a)
        self.hover(cdp, sid, ".rowmenu > [role=menu] [data-rm=owner]")
        self.search_box(cdp, sid)
        self.until(cdp, sid, "document.getAnimations().length === 0", "the list to finish opening")
        self.hover(cdp, sid, ".rowmenu .rm-fly input[data-rm-search]")

    def test_item_1070_search_guard_edges_focus_alone_blank_text_swap_timing_and_a_list_opened_by_key(self):
        away = {"type": "mouseMoved", "x": 3, "y": 3}
        has_fly = "!!document.querySelector('.rowmenu .rm-fly')"
        for width in (1400, 900):
            with self.subTest(width=width, case="focused, empty"):
                with chrome() as cdp:
                    sid = self.visit(cdp, width=width)
                    self.hover_owner_list(cdp, sid)
                    cdp.js("document.querySelector('.rowmenu .rm-fly input[data-rm-search]').focus()", sid)
                    cdp.call("Input.dispatchMouseEvent", away, sid)
                    time.sleep(0.7)
                    self.assertTrue(cdp.js(has_fly, sid), "a focused search box keeps the list though it holds no text")
            with self.subTest(width=width, case="blank text, unfocused"):
                with chrome() as cdp:
                    sid = self.visit(cdp, width=width)
                    self.hover_owner_list(cdp, sid)
                    self.type_in(cdp, sid, "   ")
                    cdp.js("document.querySelector('.rowmenu .rm-fly input[data-rm-search]').blur()", sid)
                    cdp.call("Input.dispatchMouseEvent", away, sid)
                    time.sleep(0.7)
                    self.assertFalse(cdp.js(has_fly, sid), "spaces only are no text: the list closes about 250 ms after the pointer leaves")
            with self.subTest(width=width, case="swap held"):
                with chrome() as cdp:
                    sid = self.visit(cdp, width=width)
                    self.hover_owner_list(cdp, sid)
                    self.type_in(cdp, sid, "Wilh")
                    cdp.js("document.querySelector('.rowmenu .rm-fly input[data-rm-search]').blur()", sid)
                    self.hover(cdp, sid, ".rowmenu > [role=menu] [data-rm=status]")
                    time.sleep(0.7)
                    self.assertTrue(cdp.js("!!document.querySelector('.rowmenu .rm-fly input[data-rm-search]')", sid), "typed text is not swapped away by resting on another entry")
            with self.subTest(width=width, case="list opened by a click survives the pointer leaving"):
                with chrome() as cdp:
                    sid = self.visit(cdp, width=width)
                    a = self.id_of("Order the laptops")
                    self.open_menu(cdp, sid, self.TABLE % a)
                    click(cdp, sid, "[data-rm=status]")
                    self.until(cdp, sid, "!!document.querySelector('.rowmenu .rm-fly [role=menuitem]')", "the list")
                    cdp.call("Input.dispatchMouseEvent", away, sid)
                    time.sleep(0.7)
                    self.assertTrue(cdp.js(has_fly, sid), "a list taken by click or key stays when the pointer leaves")
            with self.subTest(width=width, case="Escape from an entry"):
                with chrome() as cdp:
                    sid = self.visit(cdp, width=width)
                    a = self.id_of("Order the laptops")
                    self.open_menu(cdp, sid, self.TABLE % a)
                    cdp.js("document.querySelector('.rowmenu > [role=menu] [data-rm=status]').focus()", sid)
                    key(cdp, sid, "ArrowRight")
                    self.until(cdp, sid, "!!document.querySelector('.rowmenu .rm-fly [role=menuitem]')", "the list")
                    self.until(cdp, sid, "!!document.activeElement.closest('.rm-fly')", "focus in the list")
                    key(cdp, sid, "Escape")
                    self.until(cdp, sid, "!document.querySelector('.rowmenu .rm-fly')", "Escape on a name closes the list")

    def test_item_1070_search_enter_and_add_form_edges_blank_enter_does_nothing_enter_adds_the_new_name_the_menu_gives_way_and_focus_returns(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            a, before = self.id_of("Order the laptops"), self.steps()
            self.open_menu(cdp, sid, self.TABLE % a)
            click(cdp, sid, "[data-rm=owner]")
            self.search_box(cdp, sid)
            self.until(cdp, sid, "document.activeElement.matches('input[data-rm-search]')", "focus on the box")
            key(cdp, sid, "Enter")
            time.sleep(0.5)
            self.assertEqual(self.steps(), before, "Enter on an empty box takes no name")
            self.assertTrue(cdp.js("!!document.querySelector('.rowmenu .rm-fly')", sid), "the list stays")
            self.type_in(cdp, sid, "Wilhelmina Frost")
            self.until(cdp, sid, "!!document.querySelector('.rm-fly [data-rm=addp]')", "the add entry")
            key(cdp, sid, "Enter")
            self.until(cdp, sid, "!!document.querySelector('[data-pop] [data-new-name]')", "Enter on the add entry opens the form")
            self.assertEqual(cdp.js("document.querySelector('[data-pop] [data-new-name]').value", sid), "Wilhelmina Frost")
            self.assertEqual(cdp.js("!!document.querySelector('.rowmenu > [role=menu]')", sid), False, "the menu gives way to the form")
            cdp.js("(() => { const i = document.querySelector('[data-pop] [data-new-name]'); i.value = 'Wilhelmina Frost'; i.dispatchEvent(new Event('input', {bubbles: true})); })()", sid)
            click(cdp, sid, "[data-pop] [data-new-save]")
            self.assertEqual(self.wait_toast(cdp, sid, "done")["text"], f"Owner of {a} changed to Wilhelmina Frost, added as a new person.")
            self.until(cdp, sid, f"document.activeElement && document.activeElement.matches('tr[data-id=\"{a}\"]')", "focus back on the row",
                       why=lambda: cdp.js("document.activeElement ? document.activeElement.outerHTML.slice(0, 80) : 'none'", sid))

    def test_item_1070_the_add_form_naming_the_current_owner_saves_nothing_and_closes(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            a, before = self.id_of("Order the laptops"), self.steps()
            owner = self.row(a)["owner"]
            self.open_menu(cdp, sid, self.TABLE % a)
            click(cdp, sid, "[data-rm=owner]")
            self.search_box(cdp, sid)
            self.type_in(cdp, sid, "Wilhelmina Frost")
            self.until(cdp, sid, "!!document.querySelector('.rm-fly [data-rm=addp]')", "the add entry")
            click(cdp, sid, ".rm-fly [data-rm=addp]")
            self.until(cdp, sid, "!!document.querySelector('[data-pop] [data-new-name]')", "the form")
            cdp.js("(() => { const i = document.querySelector('[data-pop] [data-new-name]'); i.value = %s; i.dispatchEvent(new Event('input', {bubbles: true})); })()" % json.dumps(owner), sid)
            click(cdp, sid, "[data-pop] [data-new-save]")
            self.until(cdp, sid, "!document.querySelector('[data-pop]') && !document.querySelector('.rowmenu > [role=menu]')", "the form and the menu closed",
                       why=lambda: cdp.js("document.body.innerHTML.length", sid))
            self.assertEqual(self.steps(), before)

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

    def test_row_865_archive_keeps_focus_on_a_row_and_undo_returns_it_to_the_archived_row(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            a = self.id_of("Order the laptops")
            self.open_menu(cdp, sid, self.TABLE % a)
            click(cdp, sid, "[data-rm=archive]")
            self.wait_toast(cdp, sid, "done")
            self.until(cdp, sid, "document.getAnimations().filter(a => !(a.effect && a.effect.target && a.effect.target.classList && a.effect.target.classList.contains('toast-bar'))).length === 0", "the toast to finish arriving")
            self.until(cdp, sid, f"!document.querySelector(\"{self.TABLE % a}\")", "the row to leave the list")
            self.until(cdp, sid, "!!document.activeElement && !!document.activeElement.closest('tr[data-id]')", "focus went to a neighbouring row, not the page")
            cdp.js("document.activeElement.blur()", sid)
            click(cdp, sid, "[data-undo]")
            self.until(cdp, sid, f"!!document.querySelector(\"{self.TABLE % a}\")", "the row to come back")
            self.until(cdp, sid, f"document.activeElement && document.activeElement.closest('tr[data-id]') && document.activeElement.closest('tr[data-id]').dataset.id === {json.dumps(a)}", "focus is on the archived row again")

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
        self.until(cdp, sid, "document.getAnimations().filter(a => !(a.effect && a.effect.target && a.effect.target.classList && a.effect.target.classList.contains('toast-bar'))).length === 0", f"{where}: the animations to end before the colours are read")
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
                self.until(cdp, sid, "document.getAnimations().filter(a => !(a.effect && a.effect.target && a.effect.target.classList && a.effect.target.classList.contains('toast-bar'))).length === 0", f"{where}: the toast to finish arriving")
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
                    # The peek slides in as a whole: where() only waits for animations inside the button, so the fast wait found the hash
                    # and clicked where the button was a moment before it settled. Wait for the page's animations to end, then click.
                    self.until(cdp, sid, "document.getAnimations().filter(a => !(a.effect && a.effect.target && a.effect.target.classList && a.effect.target.classList.contains('toast-bar'))).length === 0", f"{where}: the peek to finish sliding in")
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

    def gated_people(self):
        """Holds GET /api/people until the test lets it go; returns (gate, done): done is set once the read has been answered."""
        import threading
        gate, done, real = threading.Event(), threading.Event(), self.s.httpd.people_list

        def slow(*req):
            gate.wait(10)
            try:
                return real(*req)
            finally:
                done.set()
        self.s.httpd.people_list = slow
        return gate, done

    def test_row_1048_when_the_people_list_cannot_be_read_the_menu_still_opens_and_the_draft_entry_gives_no_reason(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                self.s.httpd.people_list = lambda *req: (500, {"ok": False})
                sid = self.visit(cdp, width=width)
                a = self.id_of("Order the laptops")
                self.open_menu(cdp, sid, self.TABLE % a)
                by = {e[0]: e for e in self.entries(cdp, sid)}
                self.assertFalse(by["draft"][2], f"{width}: the entry can still be used")
                self.assertEqual(by["draft"][3], "", f"{width}: no reason is given while there is no People list to judge by")

    def test_a_dismiss_before_the_people_read_resolves_cancels_the_open(self):
        for how in ("escape", "outside"):
            with self.subTest(how=how), chrome() as cdp:
                sid = self.visit(cdp)
                a = self.id_of("Order the laptops")
                gate, done = self.gated_people()
                try:
                    right_click(cdp, sid, self.TABLE % a)
                    time.sleep(0.3)
                    self.assertFalse(cdp.js("!!document.querySelector('.rowmenu')", sid), "nothing is drawn while the list is read")
                    if how == "escape":
                        key(cdp, sid, "Escape")
                    else:
                        cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": 5, "y": 5, "button": "left", "buttons": 1, "clickCount": 1}, sid)
                        cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": 5, "y": 5, "button": "left", "buttons": 0, "clickCount": 1}, sid)
                finally:
                    gate.set()
                self.assertTrue(done.wait(10))
                time.sleep(0.8)
                self.assertFalse(cdp.js("!!document.querySelector('.rowmenu')", sid), "the read came back after the dismiss: the menu stays shut")
                self.open_menu(cdp, sid, self.TABLE % a)            # a fresh open still works afterwards
                self.assertTrue(cdp.js("!!document.querySelector('.rowmenu [role=menu]')", sid))

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

    def test_row_1048_the_owners_address_and_name_ride_on_the_ask_show_in_the_to_line_and_stay_on_a_changed_option_at_1400_and_900(self):
        a = self.id_of("Order the laptops")
        with self.store.step("dashboard", USER) as st:
            pid = st.add_person(name="Ada Quillfeather", email="ada@example.com", source="test")
            st.update("actions", a, {"owner": "Ada Quillfeather", "owner_id": pid})
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                self.drafts.clear()
                sid = self.visit(cdp, width=width)
                self.open_menu(cdp, sid, self.TABLE % a)
                click(cdp, sid, "[data-rm=draft]")
                self.until(cdp, sid, "!!document.querySelector('[data-draft-email] .de')", f"{width}: the Draft email")
                who = {"email": "ada@example.com", "name": "Ada Quillfeather"}
                self.assertEqual(self.drafts, [{"project": "ABC", "item": a, "picked": [a], **who}], f"{width}: the first ask carries the owner's address and name")
                meta = cdp.js("[...document.querySelectorAll('.de-meta dt, .de-meta dd')].map(e => e.textContent)", sid)
                self.assertEqual(meta[0], "To")
                self.assertIn("ada@example.com", meta[1], f"{width}: the To line shows the address")
                click(cdp, sid, ".de-kinds input[value=decision]")
                self.until(cdp, sid, "/Decision/.test(document.querySelector('.de-meta').textContent)", f"{width}: the other kind of email")
                self.assertEqual(self.drafts[-1], {"project": "ABC", "item": a, "mode": "decision", "picked": [a], "include_update": False, **who}, f"{width}: the re-ask keeps them")
                self.assertIn("ada@example.com", cdp.js("document.querySelectorAll('.de-meta dd')[0].textContent", sid), f"{width}: the To line still shows it")

    def test_row_1048_a_risk_and_a_decision_find_their_owners_address_too_not_only_an_action(self):
        """Mutation audit: the owner link is looked up in actions, raid and decisions alike (withOwnerLink in RowMenu.jsx)."""
        risk, decision = self.id_of("Supplier slips"), self.id_of("Use the new tool")
        with self.store.step("dashboard", USER) as st:
            pid = st.add_person(name="Ada Quillfeather", email="ada@example.com", source="test")
            st.update("raid", risk, {"owner": "Ada Quillfeather", "owner_id": pid})
            st.update("decisions", decision, {"made_by": "Ada Quillfeather", "owner_id": pid})
        for width in (1400, 900):
            for ref in (risk, decision):
                with self.subTest(width=width, ref=ref), chrome() as cdp:
                    self.drafts.clear()
                    sid = self.visit(cdp, width=width)
                    self.open_menu(cdp, sid, self.TABLE % ref)
                    click(cdp, sid, "[data-rm=draft]")
                    self.until(cdp, sid, "!!document.querySelector('[data-draft-email] .de')", f"{width} {ref}: the Draft email")
                    self.assertEqual(self.drafts[0].get("email"), "ada@example.com", f"{width} {ref}: the ask carries the owner's address")
                    self.assertEqual(self.drafts[0].get("name"), "Ada Quillfeather")

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
            self.until(cdp, sid, "!document.querySelector('[inert]')", "all released again: no element may still be [inert] after the dialog closed",   # the release follows the close by a frame
                       why=lambda: cdp.js("[...document.querySelectorAll('[inert]')].map(e => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (e.className ? '.' + String(e.className).trim().split(/\\s+/).join('.') : ''))", sid))

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

    def test_in_view_on_work_items_i_sent_it_works_and_records_the_ids(self):
        # Row 824: Work items have no mode, so "I sent it" is live in View as in Edit (a Dashboard in View still writes nothing).
        with chrome() as cdp:
            sid = self.visit(cdp, edit=False)
            a = self.id_of("Order the laptops")
            self.open_menu(cdp, sid, self.TABLE % a)
            click(cdp, sid, "[data-rm=draft]")
            self.until(cdp, sid, "!!document.querySelector('[data-draft-email] .de')", "the Draft email")
            find = "[...document.querySelectorAll('.de .pk-btn')].find(b => /sent/.test(b.textContent))"
            self.assertFalse(cdp.js(find + ".disabled", sid), "I sent it is live in View on Work items")
            self.assertNotIn("Switch to Edit to change this.", cdp.js("document.querySelector('.de').textContent", sid))
            cdp.js(find + ".click()", sid)
            self.until(cdp, sid, "/sent/i.test(document.querySelector('.de-note').textContent)", "the note")
            self.assertEqual([r["ids"] for r in self.store.email_sent_for("ABC")], [[a]])

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
        self.settled(cdp, sid)
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
                    self.until(cdp, sid, "document.getAnimations().filter(a => !(a.effect && a.effect.target && a.effect.target.classList && a.effect.target.classList.contains('toast-bar'))).length === 0", f"{rm}: the list to finish opening")
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

    def test_item_1070_typing_in_the_owner_list_moves_nothing_and_a_hostile_text_stays_inside_the_window_at_1400_and_900(self):
        """Movement pass: while text is typed (the list narrows to nothing and to the add entry) the menu and the list's box keep their place
        and the list stays inside the window; markup typed is shown as text, never as elements."""
        self.add_register(("Bryony Castellan", ""), ("Cedric Dunmore", "cedric@example.com"))
        box = "(() => { const r = document.querySelector('.rowmenu .rm-fly').getBoundingClientRect(); const m = document.querySelector('.rowmenu .ddmenu').getBoundingClientRect(); return [r.left, r.top, r.width, m.left, m.top, m.width, m.height, r.right <= window.innerWidth, r.bottom <= window.innerHeight, r.left >= 0, r.top >= 0]; })()"
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width=width)
                a = self.id_of("Order the laptops")
                self.open_menu(cdp, sid, self.TABLE % a)
                click(cdp, sid, "[data-rm=owner]")
                self.search_box(cdp, sid)
                self.people_loaded(cdp, sid)
                before = cdp.js(box, sid)
                self.type_in(cdp, sid, "q" * 500)
                self.until(cdp, sid, "document.querySelector('.rowmenu .rm-fly input[data-rm-search]').value.length > 0", "the typing")
                self.assertEqual(cdp.js("document.querySelector('.rowmenu .rm-fly input[data-rm-search]').value.length", sid), 200, "a huge paste stops at 200 characters")
                cdp.js("document.querySelector('.rowmenu .rm-fly input[data-rm-search]').select()", sid)
                for text in ("ced", "<img src=x onerror=alert(1)>" + "w" * 150, "Zed Nobody"):
                    self.type_in(cdp, sid, text)
                    self.until(cdp, sid, f"document.querySelector('.rowmenu .rm-fly input[data-rm-search]').value === {json.dumps(text)}", "the typing")
                    time.sleep(0.3)
                    now = cdp.js(box, sid)
                    self.assertEqual((now[1], now[3:7]), (before[1], before[3:7]), f"{width}: the menu and the list's top do not move or resize while typing")
                    self.assertEqual(now[7:], [True] * 4, f"{width}: the list stays inside the window")
                    self.assertEqual(cdp.js("document.querySelectorAll('.rm-fly img, .rm-fly script').length", sid), 0, "markup is only text")
                    cdp.js("(() => { const i = document.querySelector('.rowmenu .rm-fly input[data-rm-search]'); i.select(); })()", sid)

    def test_no_dead_draft_email_event_is_left(self):
        for f in ("edit/RowMenu.jsx", "logic/rowMenu.js"):
            self.assertNotIn("clark:draft-email", (ROOT / "src" / "clark" / "page" / "src" / f).read_text(encoding="utf-8"))
        self.assertNotIn("clark:draft-email", (ROOT / "src" / "clark" / "page" / "page.html").read_text(encoding="utf-8"))

    def test_row_658_the_more_actions_button_opens_the_same_menu_beside_it_and_does_nothing_else_at_1400_and_900(self):
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width=width, height=900)
                a = self.id_of("Order the laptops")
                btn = f"tr[data-id='{a}'] button.rmore"
                self.assertEqual(cdp.js(f"[document.querySelectorAll('tr[data-id] button.rmore').length, document.querySelectorAll('tr[data-id]').length]", sid)[0],
                                 cdp.js("document.querySelectorAll('tr[data-id]').length", sid), "one on every row")
                self.assertEqual(cdp.js(f"(() => {{ const b = document.querySelector({json.dumps(btn)}); return [b.getAttribute('aria-label'), b.title, b.tabIndex]; }})()", sid), ["More actions", "More actions", -1])
                self.assertEqual(cdp.js(f"getComputedStyle(document.querySelector({json.dumps(btn)})).opacity", sid), "0", "hidden until the row is hovered or focused")
                before = self.steps()
                cdp.js(f"document.querySelector({json.dumps(btn)}).scrollIntoView({{block: 'center'}})", sid)
                cdp.js(f"document.querySelector({json.dumps(btn)}).focus()", sid)
                self.assertEqual(cdp.js(f"getComputedStyle(document.querySelector({json.dumps(btn)})).opacity", sid), "1", "shown on focus")
                cdp.js("document.activeElement.blur()", sid)
                click(cdp, sid, btn)
                self.until(cdp, sid, "!!document.querySelector('.rowmenu [role=menu]')", "the menu")
                self.settled(cdp, sid)
                self.assertEqual(cdp.js("document.querySelector('.rowmenu [role=menu]').getAttribute('aria-label')", sid), f"Actions for {a}")
                self.assertEqual([e[1] for e in self.entries(cdp, sid)][-1], "Delete")
                self.assertFalse(cdp.js("!!document.querySelector('.peek.on, #peek.on, [data-peek].on')", sid), "no peek")
                self.assertEqual(cdp.js("document.querySelectorAll('tr[data-id].picked').length", sid), 0, "no row selected")
                self.assertEqual(self.steps(), before)
                key(cdp, sid, "Escape")
                self.shut(cdp, sid)
                self.until(cdp, sid, f"document.activeElement && document.activeElement.matches({json.dumps(btn)})", "focus back on the button")

    def test_the_published_page_has_no_menu(self):
        view = (ROOT / "src" / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for word in ("data-rowmenu", "clark:draft-email", "Copy link to this item", "More actions"):
            self.assertNotIn(word, view)


if __name__ == "__main__":
    unittest.main()

