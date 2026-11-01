"""#80: the Work items table's Owner, Due, Priority and Status cells change in place, in Edit, each from its own picker.

Run: python3 dev/run_tests.py test_inline_edits
Part 1 runs the page's own rules (src/clark/page/src/edit/itemEdit.js, bundled by the pinned esbuild) in headless Chrome: what each
pick sends, the choices each kind of item has, and the date picker's days. Part 2 starts a real server whose `change` and `undo`
are the real clark.changes over a real demo store (fictional data, built at CLARK_NOW=2026-10-28) and drives the committed page
at 1400 and 900 px with real mouse and key events: each picker opens by a click and by the keyboard, a pick changes the row and
the store in one step with Undo, Esc leaves the value as it was (one panel, closed by one Esc), and a click on the row still opens
the item's peek. The table has no phone layout of its own (it is the 900 px one below that), so 390 px is not tested here.
The browser parts are required: they fail, never skip, without Chrome (set CLARK_CHROME to its path).
"""
import contextlib
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _demo import USER
from _paths import SRC
import _testpage as testpage

from clark import changes, page, server as sv  # noqa: E402
from clark.store import open_store, priority as store_priority  # noqa: E402
from test_server import CHROME, Running, chrome, wait  # noqa: E402
from test_work_items import FIXED_DATE, TODAY, bundled, load_demo, page_target  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")
KEYS = {"Enter": (13, "\r"), " ": (32, " "), "Escape": (27, ""), "ArrowDown": (40, ""), "ArrowUp": (38, ""), "ArrowLeft": (37, ""),
        "ArrowRight": (39, ""), "Home": (36, ""), "End": (35, ""), "Tab": (9, ""), "PageDown": (34, ""), "PageUp": (33, "")}


def tearDownModule():
    shutil.rmtree(EMPTY_BRANDING, ignore_errors=True)


def need_chrome():
    assert Path(CHROME).is_file(), f"Google Chrome is needed for the required browser tests ({CHROME}); set CLARK_CHROME"


# ---- part 1: the rules ----
class Rules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        need_chrome()
        cls.stack = contextlib.ExitStack()
        cls.cdp = cls.stack.enter_context(chrome())
        cls.sid = page_target(cls.cdp)
        res = cls.cdp.call("Runtime.evaluate", {"expression": bundled(PAGE_SRC / "edit" / "itemEdit.js", "E") + "; true", "returnByValue": True}, cls.sid)
        assert "exceptionDetails" not in res, res

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def js(self, expr):
        res = self.cdp.call("Runtime.evaluate", {"expression": expr, "returnByValue": True}, self.sid)
        self.assertNotIn("exceptionDetails", res, (expr, res))
        return res["result"].get("value")

    def change(self, row, field, value):
        return self.js(f"E.changeFor({json.dumps(row)}, {json.dumps(field)}, {json.dumps(value)}, {json.dumps(TODAY)})")

    ACTION = {"id": "ABC-A-001", "kind": "action", "owner": "Ada Quillfeather", "priority": "High", "status": "Open", "due_date": "2026-11-02"}
    RISK = {"id": "ABC-007", "kind": "risk", "owner": "TBC", "priority": "High", "status": "Open", "due_date": None}
    PENDING = {"id": "ABC-D-001", "kind": "decision", "owner": None, "priority": None, "status": "Pending", "needed_by": "2026-11-27", "date": None}
    MADE = {"id": "ABC-D-002", "kind": "decision", "owner": "Cressida Pennywhistle", "priority": None, "status": "Made", "needed_by": None, "date": "2026-10-20"}

    def test_each_pick_sends_only_the_field_clark_takes_for_that_kind(self):
        self.assertEqual(self.change(self.ACTION, "priority", "Low"), {"changes": {"priority": "Low"}, "words": "Priority of ABC-A-001 changed to Low.",
                                                                       "back": "Priority of ABC-A-001 is back to High."})
        self.assertEqual(self.change(self.ACTION, "status", "Closed"), {"changes": {"status": "Closed"}, "words": "Status of ABC-A-001 changed to Closed.",
                                                                        "back": "Status of ABC-A-001 is back to Open."})
        self.assertEqual(self.change(self.ACTION, "owner", "  Zelda   Quince "), {"changes": {"owner": "Zelda Quince"}, "words": "Owner of ABC-A-001 changed to Zelda Quince.",
                                                                                "back": "Owner of ABC-A-001 is back to Ada Quillfeather."})
        self.assertEqual(self.change(self.ACTION, "due", "2026-11-05"), {"changes": {"due_date": "2026-11-05"}, "words": "Due date of ABC-A-001 changed to 05-11-2026.",
                                                                         "back": "Due date of ABC-A-001 is back to 02-11-2026."})
        self.assertEqual(self.change(self.ACTION, "due", ""), {"changes": {"due_date": None}, "words": "Due date of ABC-A-001 cleared.",
                                                               "back": "Due date of ABC-A-001 is back to 02-11-2026."})
        self.assertEqual(self.change(self.RISK, "owner", "Edna Marblethorpe")["changes"], {"owner": "Edna Marblethorpe"})
        self.assertEqual(self.change(self.PENDING, "owner", "Ada Quillfeather")["changes"], {"made_by": "Ada Quillfeather"})
        self.assertEqual(self.change(self.PENDING, "due", "2026-12-01")["changes"], {"needed_by": "2026-12-01"})
        self.assertEqual(self.change(self.MADE, "due", "2026-10-21")["changes"], {"date": "2026-10-21"})
        self.assertEqual(self.change(self.MADE, "owner", "")["changes"], {"made_by": None}, "a decider may be cleared")

    def test_what_undo_says_is_the_value_the_cell_goes_back_to(self):
        self.assertEqual(self.change(self.RISK, "due", "2026-12-01")["back"], "Due date of ABC-007 is blank again.")
        self.assertEqual(self.change(self.PENDING, "owner", "Ada Quillfeather")["back"], "Decider of ABC-D-001 is blank again.")
        self.assertEqual(self.change(self.MADE, "owner", "")["back"], "Decider of ABC-D-002 is back to Cressida Pennywhistle.")
        self.assertEqual(self.change(self.MADE, "due", "2026-10-21")["back"], "Decision date of ABC-D-002 is back to 20-10-2026.")
        self.assertEqual(self.change(self.PENDING, "due", "2026-12-01")["back"], "Needed-by date of ABC-D-001 is back to 27-11-2026.")
        self.assertEqual(self.change(self.MADE, "status", "Withdrawn")["back"], "Status of ABC-D-002 is back to Made.")
        self.assertEqual(self.change({**self.ACTION, "priority": None}, "priority", "Low")["back"], "Priority of ABC-A-001 is blank again.")

    def test_a_pick_of_the_same_value_sends_nothing(self):
        for row, field, v in ((self.ACTION, "priority", "High"), (self.ACTION, "status", "Open"), (self.ACTION, "owner", " Ada Quillfeather "),
                              (self.ACTION, "due", "2026-11-02"), (self.RISK, "due", ""), (self.PENDING, "owner", "")):
            with self.subTest(field=field, v=v):
                self.assertIsNone(self.change(row, field, v))

    def test_what_is_refused_is_said_in_plain_words_and_sends_nothing(self):
        self.assertEqual(self.change(self.ACTION, "owner", "  "), {"error": "An owner can't be blank. Type a name, or TBC if no one is known yet."})
        self.assertEqual(self.change(self.MADE, "due", ""), {"error": "A made decision keeps the date it was made. Pick another date instead."})
        # each says why, that nothing was changed, and what to do next
        self.assertEqual(self.change(self.ACTION, "due", "2026-02-30"), {"error": "That date isn't a real day, so nothing was changed. Pick another date."})
        self.assertEqual(self.change(self.RISK, "priority", "Low"), {"error": "A risk's or issue's priority is set from its impact and likelihood, so nothing was changed."})
        self.assertEqual(self.change(self.PENDING, "priority", "Low"), {"error": "A decision has no priority, so nothing was changed."})
        self.assertEqual(self.change(self.ACTION, "priority", "Critical"), {"error": "That priority can't be used, so nothing was changed. Pick Urgent, High, Medium or Low."})
        status = {"error": "That status isn't one this item can have, so nothing was changed. Pick one from the list."}
        self.assertEqual(self.change(self.MADE, "status", "Pending"), status)
        self.assertEqual(self.change(self.RISK, "status", "Delayed"), status)
        self.assertEqual(self.change(self.ACTION, "title", "New"), {"error": "Only the owner, due date, priority and status can be changed here. Nothing was changed."})
        self.assertIn("error", self.change(self.ACTION, "owner", "x" * 201))

    def test_a_name_with_a_hidden_character_is_said_in_the_picker_and_sends_nothing(self):
        # the classes clark/changes.py refuses (ITEM_BAD_KINDS): a zero-width space, a right-to-left override, a soft hyphen,
        # a private-use character, a control character; the picker says so and keeps what was typed
        words = "That name has a hidden character in it, often from copying and pasting. Type the name again, then press Enter."
        for typed in ("Zelda\u200bQuince", "Zelda \u202eQuince", "Zel\u00adda", "Zelda \ue000", "Zelda\x07"):
            with self.subTest(typed=repr(typed)):
                self.assertEqual(self.change(self.ACTION, "owner", typed), {"error": words})
                self.assertEqual(self.change(self.PENDING, "owner", typed), {"error": words})
        self.assertEqual(sorted(changes.ITEM_BAD_KINDS), ["Cc", "Cf", "Co", "Cs", "Zl", "Zp"], "the page checks the same classes as clark")
        self.assertEqual(self.change(self.ACTION, "owner", "Zoë\u2028Quince")["changes"], {"owner": "Zoë Quince"}, "a line break is a space, as before")
        self.assertEqual(self.change(self.ACTION, "owner", "Zoë Quince-Smith")["changes"], {"owner": "Zoë Quince-Smith"}, "accents and hyphens are fine")

    def test_a_decision_made_gets_todays_date_and_says_it_has_no_undo(self):
        c = self.change(self.PENDING, "status", "Made")
        self.assertEqual(c["changes"], {"status": "Made", "date": TODAY})
        self.assertEqual(c["words"], "ABC-D-001 is now made, on 28-10-2026. This can't be undone. To change it, record a new decision.",
                         "the toast says the date it was made, short")
        # the warning comes before the pick: small print under Made in the picker, on a decision that isn't made yet
        got = self.js(f"[{json.dumps(self.PENDING)}, {json.dumps(self.MADE)}].map(r => ['Pending', 'Made', 'Withdrawn'].map(s => E.statusNote(r, s)))")
        self.assertEqual(got, [["", "Can't be undone", ""], ["", "", ""]])
        self.assertEqual(self.js(f"E.statusNote({json.dumps(self.ACTION)}, 'Closed')"), "")
        self.assertEqual(self.change(self.MADE, "status", "Withdrawn")["changes"], {"status": "Withdrawn"}, "a made decision keeps its date")
        self.assertEqual(self.change({**self.MADE, "status": "Withdrawn"}, "status", "Pending")["changes"], {"status": "Pending", "date": None})

    def test_the_status_cell_in_edit_shows_the_live_look_the_prototype_gives(self):
        """#448 (row 54, system/prototype/core.js C.look): Edit's Status cell reads as View's pill does, not the raw status word."""
        late = {**self.ACTION, "status": "Delayed", "due_date": "2026-10-01"}       # a late action reads Overdue
        soon = {**self.ACTION, "due_date": "2026-10-30"}                             # Due soon
        delayed = {**self.ACTION, "status": "Delayed", "due_date": "2026-11-20"}
        rows = [late, soon, delayed, self.RISK, {**self.RISK, "priority": "Medium"}, {**self.RISK, "priority": "Low"}, {**self.RISK, "kind": "issue", "priority": "Urgent"},
                {**self.RISK, "status": "Cancelled"}, {**self.RISK, "status": "Closed", "priority": "Low"},
                self.PENDING, self.MADE, {**self.MADE, "status": "Withdrawn"}, {**self.ACTION, "status": "Closed"}]
        got = self.js(f"{json.dumps(rows)}.map(r => E.statusPill(r, {json.dumps(TODAY)}))")
        self.assertEqual(got, [{"text": "Overdue", "class": "r"}, {"text": "Due soon", "class": "a"}, {"text": "Delayed", "class": "a"},
                               {"text": "Red", "class": "r"}, {"text": "Amber", "class": "a"}, {"text": "Green", "class": "g"}, {"text": "Red", "class": "r"},
                               {"text": "Cancelled", "class": "n"}, {"text": "Closed", "class": "n"},
                               {"text": "Pending", "class": "b"}, {"text": "Made", "class": "g"}, {"text": "Withdrawn", "class": "n"}, {"text": "Closed", "class": "n"}])

    def test_rating_rules(self):
        self.assertEqual(self.js(f"E.ratingChoices({json.dumps(self.RISK)})"), ["Red", "Amber", "Green"])
        self.assertEqual(self.js(f"[E.ratingChoices({json.dumps(self.ACTION)}), E.ratingChoices({json.dumps(self.PENDING)})]"), [[], []])
        self.assertEqual(self.change(self.RISK, "rating", "rating:Green"), {"changes": {"impact": "Low", "likelihood": "Low"}, "words": "ABC-007 rated Green.",
                                                                            "back": "ABC-007 is back to Red."})
        self.assertEqual(self.change(self.RISK, "rating", "rating:Amber")["changes"], {"impact": "Medium", "likelihood": "Medium"})
        self.assertIsNone(self.change(self.RISK, "rating", "rating:Red"), "the colour it already has sends nothing")
        self.assertNotIn("priority", self.change(self.RISK, "rating", "rating:Green")["changes"], "priority is worked out by the store, never sent")
        self.assertIn("error", self.change(self.ACTION, "rating", "rating:Red"))
        others = [{**self.RISK, "kind": "issue"}, {**self.RISK, "kind": "assumption"}, {**self.RISK, "kind": "dependency"}, {**self.RISK, "status": "Closed"}, {**self.RISK, "status": "Cancelled"},
                  {**self.RISK, "kind": "issue", "status": "Closed"}]
        self.assertEqual(self.js(f"{json.dumps(others)}.map(r => E.ratingChoices(r).length)"), [3, 0, 0, 3, 3, 3],
                         "a risk or issue whatever its status (#448, system/prototype/peek.js:260), as the server")
        self.assertIn("error", self.change(others[1], "rating", "rating:Red"))
        self.assertEqual(self.change(others[3], "rating", "rating:Green")["changes"], {"impact": "Low", "likelihood": "Low"}, "a closed risk is rated")
        self.assertEqual(self.change(others[4], "rating", "rating:Amber")["words"], "ABC-007 rated Amber.", "a cancelled one too")
        self.assertIsNone(self.change(others[3], "rating", "rating:Red"), "the colour it already has sends nothing")
        self.assertEqual(self.js("[E.pickField('status', 'rating:Red'), E.pickField('status', 'Open'), E.pickField('owner', 'x')]"), ["rating", "status", "owner"])

    def test_a_raid_items_priority_says_why_it_is_not_a_picker(self):
        got = self.js(f"[{json.dumps(self.RISK)}, {json.dumps({**self.RISK, 'kind': 'issue'})}, {json.dumps(self.ACTION)}, {json.dumps(self.PENDING)}].map(r => E.whyFixed(r, 'priority'))")
        self.assertEqual(got, ["Set from impact and likelihood", "Set from impact and likelihood", "", ""])
        self.assertEqual(self.js(f"E.whyFixed({json.dumps(self.RISK)}, 'status')"), "")

    def test_the_choices_and_which_cells_are_pickers(self):
        self.assertEqual(self.js(f"E.statusChoices({json.dumps(self.ACTION)})"), ["Open", "Delayed", "Closed", "Cancelled"])
        self.assertEqual(self.js(f"E.statusChoices({json.dumps(self.RISK)})"), ["Open", "Closed", "Cancelled"])
        self.assertEqual(self.js(f"E.statusChoices({json.dumps(self.PENDING)})"), ["Pending", "Made", "Withdrawn"])
        self.assertEqual(self.js(f"E.statusChoices({json.dumps(self.MADE)})"), ["Made", "Withdrawn"])
        self.assertEqual(self.js("E.PRIORITIES"), ["Urgent", "High", "Medium", "Low"])
        got = self.js(f"[{json.dumps(self.ACTION)}, {json.dumps(self.RISK)}, {json.dumps(self.PENDING)}].map(r => E.FIELDS.map(f => E.canPick(r, f)))")
        self.assertEqual(got, [[True] * 4, [True, True, False, True], [True, True, False, True]])
        self.assertEqual(self.js(f"[E.canClearDue({json.dumps(self.MADE)}), E.canClearDue({json.dumps(self.PENDING)})]"), [False, True])
        self.assertEqual(self.js(f"[E.fieldName({json.dumps(self.PENDING)}, 'due'), E.fieldName({json.dumps(self.MADE)}, 'due'), E.fieldName({json.dumps(self.MADE)}, 'owner')]"),
                         ["Needed-by date", "Decision date", "Decider"])

    def test_people_and_matching(self):
        d = {"actions": [{"owner": "Ada Quillfeather"}, {"owner": "TBC"}], "raid": [{"owner": " Edna Marblethorpe "}],
             "decisions": [{"made_by": None}, {"made_by": "Ada Quillfeather"}], "milestones": [{"owner": "Barnaby Tumblewick"}]}
        self.assertEqual(self.js(f"E.people({json.dumps(d)})"), ["Ada Quillfeather", "Barnaby Tumblewick", "Edna Marblethorpe"])
        names = ["Ada Quillfeather", "Barnaby Tumblewick", "Edna Marblethorpe"]
        self.assertEqual(self.js(f"E.matching({json.dumps(names)}, 'mar')"), ["Edna Marblethorpe"])
        self.assertEqual(self.js(f"E.matching({json.dumps(names)}, 'b')"), ["Barnaby Tumblewick", "Edna Marblethorpe"], "a word that starts with it first")
        self.assertEqual(self.js(f"E.matching({json.dumps(names)}, 'wick')"), ["Barnaby Tumblewick"], "inside a name")
        self.assertEqual(self.js(f"E.matching({json.dumps(names)}, '')"), names)

    def test_the_date_pickers_days(self):
        cells = self.js("E.monthCells('2026-11')")
        self.assertEqual(cells[:7], ["", "", "", "", "", "", "2026-11-01"], "1 November 2026 is a Sunday: the grid starts on Monday")
        self.assertEqual(len([c for c in cells if c]), 30)
        self.assertEqual(len([c for c in self.js("E.monthCells('2028-02')") if c]), 29)
        self.assertEqual(self.js("[E.addDays('2026-12-31', 1), E.addDays('2026-03-01', -1), E.addMonths('2026-12', 1), E.addMonths('2026-01', -1), E.monthTitle('2026-11')]"),
                         ["2027-01-01", "2026-02-28", "2027-01", "2025-12", "November 2026"])
        self.assertEqual(self.js("E.quickDates('2026-10-28')"), [["Today", "2026-10-28"], ["Tomorrow", "2026-10-29"], ["Friday", "2026-10-30"], ["Next week", "2026-11-04"]])
        self.assertEqual(self.js("E.quickDates('2026-10-30')")[2], ["Friday", "2026-11-06"], "on a Friday, the next one")


# ---- part 2: the real page, the real routes, a real store ----
def key(cdp, sid, name, alt=False):
    vk, text = KEYS[name]
    common = {"key": name, "code": {" ": "Space"}.get(name, name), "windowsVirtualKeyCode": vk, **({"modifiers": 1} if alt else {})}
    cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", **common, **({"text": text} if text else {})}, sid)
    cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", **common}, sid)


def click(cdp, sid, selector, mods=0):
    cdp.js(f"document.querySelector({json.dumps(selector)}).scrollIntoView({{block: 'center'}})", sid)
    box = cdp.js(f"(() => {{ const e = document.querySelector({json.dumps(selector)}); if (!e) return null; const b = e.getBoundingClientRect(); return [b.x + Math.min(b.width / 2, 20), b.y + b.height / 2]; }})()", sid)
    assert box, f"{selector} is not on the page"
    x, y = box
    cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, sid)
    cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "buttons": 1, "clickCount": 1, "modifiers": mods}, sid)
    cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "buttons": 0, "clickCount": 1, "modifiers": mods}, sid)


def dblclick(cdp, sid, selector):
    """Two presses on the same place, the second a double click (#195: one click on a row selects it, two open its peek)."""
    click(cdp, sid, selector)
    box = cdp.js(f"(() => {{ const b = document.querySelector({json.dumps(selector)}).getBoundingClientRect(); return [b.x + Math.min(b.width / 2, 20), b.y + b.height / 2]; }})()", sid)
    x, y = box
    cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "buttons": 1, "clickCount": 2}, sid)
    cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "buttons": 0, "clickCount": 2}, sid)


class Live(unittest.TestCase):
    def setUp(self):
        need_chrome()
        self.store, self.folder, _ = load_demo()
        self.addCleanup(shutil.rmtree, str(self.folder), True)
        self.addCleanup(self.store.close)
        self.path = self.folder / "clark.db"
        self.sent = []
        self.failure = None                  # a function (req) -> (status, body), to make clark refuse on purpose
        real_change, real_undo = changes.make_change(self.path, [], USER), changes.make_undo(self.path, [], USER)

        def seam(real, which):
            def call(req):
                self.sent.append((which, req))
                return self.failure(req) if self.failure else real(req)
            return call
        self.s = Running(data_for=self.read, projects=lambda: [{"code": "TUL", "name": "Tulip"}],
                         page_html=lambda: testpage.html(), change=seam(real_change, "change"), undo=seam(real_undo, "undo"))
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def read(self, code):
        """The project's data as the server would read it, from a connection of this thread (the server's own)."""
        st = open_store(self.path, onedrive_roots=[])
        try:
            return st.data_for(code)
        finally:
            st.close()

    def row(self, table, ref):
        st = open_store(self.path, onedrive_roots=[])
        try:
            return st.read(table, ref=ref)
        finally:
            st.close()

    def steps(self):
        st = open_store(self.path, onedrive_roots=[])
        try:
            return st.con.execute("SELECT count(*) FROM applies").fetchone()[0]
        finally:
            st.close()

    # ---- the page ----
    def open_page(self, cdp, width, edit=True, hash_="#work&p=TUL&f=mode:all"):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/{hash_}"}, sid)
        self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tbody tr').length", sid) > 0), "the list drew")
        if edit:
            cdp.js("document.querySelector('[data-mode=edit]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-cell]')", sid)), "Edit shows the cells' pickers")
        return sid

    def until(self, cdp, sid, expr, what, seconds=10):
        self.assertTrue(wait(lambda: cdp.js(expr, sid), seconds), what)

    def cell_text(self, cdp, sid, ref, field):
        return cdp.js(f"(document.querySelector('[data-cell=\"{ref}:{field}\"]') || {{}}).textContent", sid)

    def toast(self, cdp, sid):
        return cdp.js("(document.querySelector('.toast-text') || {}).textContent || ''", sid)

    def focused(self, cdp, sid):
        return cdp.js("(document.activeElement && (document.activeElement.dataset.cell || document.activeElement.dataset.value || document.activeElement.dataset.day || document.activeElement.tagName)) || ''", sid)

    def no_panel(self, cdp, sid):
        return cdp.js("document.querySelectorAll('[data-pop]').length === 0", sid)

    def undo(self, cdp, sid, what, said=None):
        """Undo the last change; the toast then says what the cell went back to (`said`, when given, word for word)."""
        before = self.steps()
        click(cdp, sid, "[data-undo]")
        if said is None:
            self.until(cdp, sid, "/ is back to | is blank again\\.$/.test((document.querySelector('.toast-text') || {}).textContent || '')", f"{what}: the undo said what went back")
        else:
            self.until(cdp, sid, f"(document.querySelector('.toast-text') || {{}}).textContent === {json.dumps(said)}", f"{what}: the undo said {said!r}")
        self.assertEqual(self.steps(), before + 1, f"{what}: the undo is one step of its own")

    def changed_once(self, before, what):
        self.assertEqual(self.steps(), before + 1, f"{what}: one change is one step")

    def plain_words(self, cdp, sid):
        text = self.toast(cdp, sid)
        self.assertFalse(text.lower().startswith("clark"), text)
        self.assertNotIn("Ask clark", text)

    def test_view_has_no_pickers_and_a_row_double_click_opens_the_peek(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_page(cdp, width, edit=False)
                self.assertEqual(cdp.js("document.querySelectorAll('[data-cell], [data-pop], .cell-pick').length", sid), 0, "View changes nothing")
                dblclick(cdp, sid, "tr[data-id='TUL-A-001'] .t")
                self.until(cdp, sid, "location.hash.includes('item=TUL-A-001')", "a double click on a row opens the item's peek (its address)")
                self.assertEqual(cdp.js("clarkPage.peek()", sid), {"kind": "item", "id": "TUL-A-001"})
                cdp.js("clarkPage.closePeek()", sid)
                self.until(cdp, sid, "!location.hash.includes('item=')", "the peek closed")
                cdp.js("document.querySelector(\"tr[data-id='TUL-007']\").focus()", sid)
                key(cdp, sid, "Enter")
                self.until(cdp, sid, "location.hash.includes('item=TUL-007')", "Enter on a row opens its peek")

    def test_the_table_is_one_tab_stop_and_the_arrows_move_inside_it(self):
        # the rows are one tab stop; a group heading's open/shut button (#68) is a control of its own, so it is left out here
        stops = "[...document.querySelectorAll('#work table.items *')].filter(e => e.tabIndex >= 0 && !e.disabled && !e.closest('tr.grp')).map(e => e.dataset.id || e.dataset.cell)"
        for edit in (False, True):
            with self.subTest(edit=edit), chrome() as cdp:
                sid = self.open_page(cdp, 1400, edit=edit)
                rows = cdp.js("[...document.querySelectorAll('#work tbody tr[data-id]')].map(r => r.dataset.id)", sid)
                self.assertGreater(len(rows), 10)
                self.assertTrue(cdp.js("[...document.querySelectorAll('#work tr.grp')].every(g => { const b = g.querySelector('button'); return b && b.tabIndex >= 0; })", sid),
                                "each group heading is shut or opened by a button of its own")
                self.assertEqual(cdp.js(stops, sid), [rows[0]], "one tab stop: the first row, however long the list")
                cdp.js("document.querySelector('#work tbody tr[data-id]').focus()", sid)
                key(cdp, sid, "ArrowDown")
                self.assertEqual(cdp.js("document.activeElement.dataset.id", sid), rows[1], "Down moves to the next row")
                self.assertEqual(cdp.js(stops, sid), [rows[1]], "the tab stop follows")
                key(cdp, sid, "End")
                self.assertEqual(cdp.js("document.activeElement.dataset.id", sid), rows[-1], "End: the last row")
                key(cdp, sid, "Home")
                self.assertEqual(cdp.js("document.activeElement.dataset.id", sid), rows[0], "Home: the first row")
                key(cdp, sid, "ArrowUp")
                self.assertEqual(cdp.js("document.activeElement.dataset.id", sid), rows[0], "Up on the first row stays")
                if not edit:
                    continue
                key(cdp, sid, "ArrowRight")
                self.assertEqual(self.focused(cdp, sid), f"{rows[0]}:owner", "Right moves into the row's cells")
                key(cdp, sid, "ArrowRight")
                self.assertEqual(self.focused(cdp, sid), f"{rows[0]}:due")
                key(cdp, sid, "ArrowDown")
                self.assertEqual(self.focused(cdp, sid), f"{rows[1]}:due", "Down from a cell: the same cell of the next row")
                self.assertTrue(self.no_panel(cdp, sid), "a plain Down opens no picker")
                key(cdp, sid, "ArrowLeft")
                key(cdp, sid, "ArrowLeft")
                self.assertEqual(cdp.js("document.activeElement.dataset.id", sid), rows[1], "Left from the first cell: back to the row")
                key(cdp, sid, "ArrowRight")
                key(cdp, sid, "Enter")
                self.until(cdp, sid, "!!document.querySelector('[data-pop] input.cp-in')", "Enter on a cell opens its picker")
                key(cdp, sid, "ArrowLeft")
                key(cdp, sid, "Escape")
                self.until(cdp, sid, "document.querySelectorAll('[data-pop]').length === 0", "closed")
                self.assertEqual(self.focused(cdp, sid), f"{rows[1]}:owner", "an arrow in the picker's box stays in the box")
                self.assertEqual(cdp.js(stops, sid), [rows[1]], "still one tab stop")
                cdp.js(f"document.querySelector(\"tr[data-id='{rows[1]}']\").focus()", sid)
                key(cdp, sid, "Enter")
                self.until(cdp, sid, f"location.hash.includes('item={rows[1]}')", "Enter on a row opens its peek")

    def test_priority_by_click_and_by_keyboard_one_step_with_undo_and_esc_leaves_it(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_page(cdp, width)
                cell = "[data-cell='TUL-A-001:priority']"
                self.assertEqual(self.cell_text(cdp, sid, "TUL-A-001", "priority"), "Urgent")
                # each picker cell looks changeable before any hover: a caret after its value and a quiet edge under it
                looks = cdp.js("[...document.querySelectorAll('.cell-pick')].map(b => [getComputedStyle(b, '::after').content, getComputedStyle(b).boxShadow !== 'none'])", sid)
                self.assertTrue(looks and all(x == ['"▾"', True] for x in looks), looks[:4])
                # by click: the menu opens on the value it has; a pick changes the row and the store, in one step, and the peek stays shut
                before = self.steps()
                click(cdp, sid, cell)
                self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "the priority menu opened")
                self.assertEqual(cdp.js("[...document.querySelectorAll('[data-pop] [role=menuitemradio]')].map(b => b.textContent)", sid), ["Urgent", "High", "Medium", "Low"])
                self.assertEqual(self.focused(cdp, sid), "Urgent", "focus starts on the value it has")
                self.assertEqual(cdp.js(f"document.querySelector(\"{cell}\").getAttribute('aria-expanded')", sid), "true")
                click(cdp, sid, "[data-pop] [data-value=Low]")
                self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "the toast offers Undo")
                self.assertEqual(self.row("actions", "TUL-A-001")["priority"], "Low")
                self.until(cdp, sid, f"document.querySelector(\"{cell}\").textContent === 'Low'", "the row shows what clark saved")
                self.changed_once(before, "priority")
                self.assertEqual(self.toast(cdp, sid), "Priority of TUL-A-001 changed to Low.")
                self.plain_words(cdp, sid)
                self.assertNotIn("item=", cdp.js("location.hash", sid), "a cell click never opens the peek")
                self.assertTrue(self.no_panel(cdp, sid))
                self.assertEqual(self.sent[-1][1], {"project": "TUL", "kind": "actions", "op": "update", "id": "TUL-A-001", "changes": {"priority": "Low"}, "place": "cell"})
                self.undo(cdp, sid, "priority", "Priority of TUL-A-001 is back to Urgent.")
                self.assertEqual(self.row("actions", "TUL-A-001")["priority"], "Urgent")
                self.until(cdp, sid, f"document.querySelector(\"{cell}\").textContent === 'Urgent'", "Undo draws the row as it was")
                # by keyboard: Enter opens, Down moves, Enter picks; focus is back on the cell
                cdp.js(f"document.querySelector(\"{cell}\").focus()", sid)
                key(cdp, sid, "Enter")
                self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "Enter opens the menu")
                key(cdp, sid, "ArrowDown")
                self.assertEqual(self.focused(cdp, sid), "High")
                key(cdp, sid, "Enter")
                self.until(cdp, sid, "!!document.querySelector('[data-undo]') && document.querySelector(\"" + cell + "\").textContent === 'High'", "the keyboard pick saved")
                self.assertEqual(self.row("actions", "TUL-A-001")["priority"], "High")
                self.until(cdp, sid, f"document.activeElement === document.querySelector(\"{cell}\")", "focus is back on the cell")
                self.undo(cdp, sid, "priority by keyboard")
                # Esc: the menu closes, the value is as it was, nothing is sent, focus is back on the cell
                n, before = len(self.sent), self.steps()
                cdp.js(f"document.querySelector(\"{cell}\").focus()", sid)
                key(cdp, sid, "ArrowDown", alt=True)
                self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "Alt+Down opens the menu too")
                key(cdp, sid, "ArrowDown")
                key(cdp, sid, "Escape")
                self.until(cdp, sid, "document.querySelectorAll('[data-pop]').length === 0", "one Esc closes it")
                self.assertEqual(self.focused(cdp, sid), "TUL-A-001:priority")
                self.assertEqual((len(self.sent), self.steps(), self.row("actions", "TUL-A-001")["priority"]), (n, before, "Urgent"), "Esc leaves it as it was")
                self.assertNotIn("item=", cdp.js("location.hash", sid))
                # a click away closes it too, and changes nothing
                click(cdp, sid, cell)
                self.until(cdp, sid, "!!document.querySelector('[data-pop]')", "open again")
                click(cdp, sid, "h1")
                self.until(cdp, sid, "document.querySelectorAll('[data-pop]').length === 0", "a click away closes it")
                self.assertEqual(len(self.sent), n)
                # a RAID item's priority and a decision's are not pickers
                self.assertEqual(cdp.js("[!!document.querySelector(\"[data-cell='TUL-007:priority']\"), !!document.querySelector(\"[data-cell='TUL-D-016:priority']\")]", sid), [False, False])
                self.assertEqual(cdp.js("document.querySelector(\"[data-fixed='TUL-007:priority']\").title", sid), "Set from impact and likelihood", "a risk's priority says why it can't be picked")
                self.assertEqual(cdp.js("[!!document.querySelector(\"[data-fixed='TUL-D-016:priority']\"), document.querySelector(\"tr[data-id='TUL-D-016'] .c-prio\").textContent]", sid), [False, "—"], "a decision's shows a dash")
                self.assertEqual(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), True, "no sideways scroll")

    def test_status_by_click_and_keyboard(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_page(cdp, width)
                cell = "[data-cell='TUL-007:status']"
                self.assertEqual(self.cell_text(cdp, sid, "TUL-007", "status"), "Red", "Edit shows the live look: an open risk reads its colour (#448)")
                before = self.steps()
                click(cdp, sid, cell)
                self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "the status menu opened")
                self.assertEqual(cdp.js("[...document.querySelectorAll('[data-pop] [role=menuitemradio]')].map(b => b.textContent)", sid), ["Open", "Closed", "Cancelled", "Red", "Amber", "Green"])
                self.assertEqual(cdp.js("document.querySelector(\"[data-cell='TUL-007:status']\").getAttribute('aria-label')", sid), "Status of TUL-007: Red. Change", "the label says the word on screen")
                groups = cdp.js("[...document.querySelectorAll('[data-pop][role=menu] [role=group]')].map(g => [document.getElementById(g.getAttribute('aria-labelledby')).textContent,"
                                " [...g.querySelectorAll('[role=menuitemradio]')].map(b => b.dataset.value), g.querySelectorAll('[aria-checked=true]').length])", sid)
                self.assertEqual(groups, [["Status", ["Open", "Closed", "Cancelled"], 1], ["Rating", ["rating:Red", "rating:Amber", "rating:Green"], 1]],
                                 "two labelled groups, one tick in each")
                self.assertEqual(cdp.js("[...document.querySelectorAll('[data-pop] [role=group] > [id]')].map(h => [h.textContent, h.offsetWidth > 1])", sid),
                                 [["Status", False], ["Rating", True]], "a Rating heading under the statuses; Status is named for a screen reader only")
                click(cdp, sid, "[data-pop] [data-value=Closed]")
                self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "saved, with Undo")
                r = self.row("raid", "TUL-007")
                self.assertEqual((r["status"], bool(r["closed"])), ("Closed", True), "closing sets its closing date, in the same step")
                self.changed_once(before, "status")
                self.until(cdp, sid, f"document.querySelector(\"{cell}\").textContent === 'Closed'", "the row shows Closed")
                self.assertEqual(cdp.js("document.querySelector(\"tr[data-id='TUL-007']\").classList.contains('done')", sid), True)
                self.undo(cdp, sid, "status", "Status of TUL-007 is back to Open.")
                r = self.row("raid", "TUL-007")
                self.assertEqual((r["status"], r["closed"]), ("Open", None))
                self.until(cdp, sid, f"document.querySelector(\"{cell}\").textContent === 'Red'", "Undo draws it Red, its live look")
                # keyboard: Space opens, End jumps, Enter picks
                cdp.js(f"document.querySelector(\"{cell}\").focus()", sid)
                key(cdp, sid, " ")
                self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "Space opens it")
                key(cdp, sid, "ArrowDown"); key(cdp, sid, "ArrowDown"); key(cdp, sid, "ArrowDown")
                self.assertEqual(self.focused(cdp, sid), "rating:Red", "Down moves on into the Rating group")
                key(cdp, sid, "ArrowUp")
                self.assertEqual(self.focused(cdp, sid), "Cancelled")
                key(cdp, sid, "Enter")
                self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "saved by keyboard")
                self.assertEqual(self.row("raid", "TUL-007")["status"], "Cancelled")
                self.undo(cdp, sid, "status by keyboard")
                self.assertEqual(self.row("raid", "TUL-007")["status"], "Open")
                # an action given Delayed reads Delayed in the cell, the same word as the toast, whatever its due date
                acell = "[data-cell='TUL-A-001:status']"
                click(cdp, sid, acell)
                self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "the action's status menu opened")
                click(cdp, sid, "[data-pop] [data-value=Delayed]")
                self.until(cdp, sid, f"document.querySelector(\"{acell}\").textContent === 'Delayed'", "the cell says Delayed")
                self.assertEqual(self.toast(cdp, sid), "Status of TUL-A-001 changed to Delayed.")
                self.undo(cdp, sid, "action status")
                self.until(cdp, sid, f"document.querySelector(\"{acell}\").textContent === 'Due soon'", "Undo draws its live look, Due soon")

    def test_rating_from_the_status_picker_sets_impact_and_likelihood_with_one_undo(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_page(cdp, width)
                cell = "[data-cell='TUL-007:status']"
                before = self.steps()
                click(cdp, sid, cell)
                self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "the status menu opened")
                click(cdp, sid, "[data-pop] [data-value='rating:Green']")
                self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "saved, with Undo")
                r = self.row("raid", "TUL-007")
                self.assertEqual((r["impact"], r["likelihood"], r["priority"], r["status"]), ("Low", "Low", "Low", "Open"))
                self.changed_once(before, "rating")
                self.assertEqual(self.toast(cdp, sid), "TUL-007 rated Green.")
                self.undo(cdp, sid, "rating")
                r = self.row("raid", "TUL-007")
                self.assertNotEqual((r["impact"], r["likelihood"]), ("Low", "Low"), "Undo puts impact and likelihood back")
                self.assertEqual(r["priority"], store_priority(r["impact"], r["likelihood"]))

    def menu_state(self, cdp, sid):
        """What the open status menu offers, and which of its entries are ticked."""
        return cdp.js("[[...document.querySelectorAll('[data-pop] [role=menuitemradio]')].map(b => b.dataset.value),"
                      " [...document.querySelectorAll('[data-pop] [role=menuitemradio][aria-checked=true]')].map(b => b.dataset.value)]", sid)

    def test_a_closed_risk_is_offered_a_rating_and_keeps_its_closed_look(self):
        """#448 (row 53, system/prototype/peek.js:260): the Rating section is offered whatever the status; a pick leaves the risk closed."""
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_page(cdp, width)
                cell = "[data-cell='TUL-008:status']"
                self.assertEqual(self.row("raid", "TUL-008")["status"], "Closed")
                self.assertEqual(self.cell_text(cdp, sid, "TUL-008", "status"), "Closed", "a closed risk reads Closed in the cell")
                click(cdp, sid, cell)
                self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "the status menu opened")
                self.assertEqual(self.menu_state(cdp, sid), [["Open", "Closed", "Cancelled", "rating:Red", "rating:Amber", "rating:Green"], ["Closed", "rating:Amber"]],
                                 "the Rating is offered on a closed risk, with its own rating ticked")
                before = self.steps()
                click(cdp, sid, "[data-pop] [data-value='rating:Green']")
                self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "saved, with Undo")
                r = self.row("raid", "TUL-008")
                self.assertEqual((r["status"], r["closed"], r["impact"], r["likelihood"], r["priority"]), ("Closed", "2026-10-14", "Low", "Low", "Low"),
                                 "rated, still closed, closing date untouched")
                self.changed_once(before, "rating of a closed risk")
                self.assertEqual(self.toast(cdp, sid), "TUL-008 rated Green.")
                self.assertEqual(self.cell_text(cdp, sid, "TUL-008", "status"), "Closed", "the cell keeps the closed look")
                self.undo(cdp, sid, "rating of a closed risk", "TUL-008 is back to Amber.")
                self.assertEqual(self.row("raid", "TUL-008")["priority"], "Medium")
                # a cancelled issue too, and an assumption is still not offered one
                click(cdp, sid, "[data-cell='TUL-012:status']")
                self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "the cancelled issue's menu opened")
                self.assertEqual(self.menu_state(cdp, sid)[1], ["Cancelled", "rating:Red"])
                key(cdp, sid, "Escape")
                self.until(cdp, sid, "document.querySelectorAll('[data-pop]').length === 0", "the menu shut")
                click(cdp, sid, "[data-cell='TUL-009:status']")
                self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "the assumption's menu opened")
                self.assertEqual(self.menu_state(cdp, sid)[0], ["Open", "Closed", "Cancelled"], "an assumption has no rating")

    def test_a_status_pick_redraws_the_cell_to_its_live_look_at_once(self):
        """#448 (row 54, system/prototype/core.js:200): after a pick the Status cell shows the look, not the raw word."""
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            cell = "[data-cell='TUL-007:status']"
            self.assertEqual(self.cell_text(cdp, sid, "TUL-007", "status"), "Red")
            self.assertEqual(cdp.js(f"document.querySelector(\"{cell}\").querySelector('.pill').className", sid), "pill r")
            click(cdp, sid, cell)
            self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "the menu opened")
            click(cdp, sid, "[data-pop] [data-value='rating:Green']")
            self.until(cdp, sid, f"document.querySelector(\"{cell}\").textContent === 'Green'", "the cell says Green at once")
            self.assertEqual(cdp.js(f"document.querySelector(\"{cell}\").querySelector('.pill').className", sid), "pill g")
            click(cdp, sid, cell)
            self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "the menu opened again")
            click(cdp, sid, "[data-pop] [data-value=Closed]")
            self.until(cdp, sid, f"document.querySelector(\"{cell}\").textContent === 'Closed'", "Closed reads Closed")
            self.assertEqual(cdp.js(f"document.querySelector(\"{cell}\").querySelector('.pill').className", sid), "pill n")
            self.assertEqual(self.cell_text(cdp, sid, "TUL-010", "status"), "Red", "an overdue issue is Red, as in View")
            self.assertEqual(self.cell_text(cdp, sid, "TUL-D-016", "status"), "Pending")

    def peek_picker(self, width):
        """#448 (row 55, system/prototype/peek.js:256): the peek's Status row opens the table's picker; one pick, one step, one Undo."""
        with chrome() as cdp:
            sid = self.open_page(cdp, width)
            cdp.js("clarkPage.openPeek('TUL-007', 'item')", sid)
            pcell = "#peek [data-cell='peek:TUL-007:status']"
            self.until(cdp, sid, f"!!document.querySelector(\"{pcell}\")", "the peek's Status row is a picker in Edit")
            self.assertEqual(cdp.js(f"document.querySelector(\"{pcell}\").textContent", sid), "Red")
            self.assertEqual(cdp.js(f"document.querySelector(\"{pcell}\").getAttribute('aria-label')", sid), "Status of TUL-007: Red. Change")
            click(cdp, sid, pcell)
            self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "the peek's menu opened")
            self.assertEqual(cdp.js("document.querySelectorAll('[data-pop]').length", sid), 1, "one picker open, not the table's too")
            self.assertEqual(self.menu_state(cdp, sid), [["Open", "Closed", "Cancelled", "rating:Red", "rating:Amber", "rating:Green"], ["Open", "rating:Red"]], "the table's own choices")
            before = self.steps()
            click(cdp, sid, "[data-pop] [data-value=Closed]")
            self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "saved, with Undo")
            self.assertEqual(self.row("raid", "TUL-007")["status"], "Closed")
            self.changed_once(before, "status from the peek")
            self.assertEqual(self.toast(cdp, sid), "Status of TUL-007 changed to Closed.")
            self.until(cdp, sid, f"document.querySelector(\"{pcell}\").textContent === 'Closed'", "the peek's cell says Closed")
            self.assertEqual(cdp.js("(document.querySelector('#peek [data-pk-rating]') || {}).textContent", sid), " · Red", "a closed risk keeps its rating word in the peek")
            self.assertEqual(self.cell_text(cdp, sid, "TUL-007", "status"), "Closed", "the table's cell says it too")
            # the rating of the now closed risk, from the peek
            click(cdp, sid, pcell)
            self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "the menu opened on a closed risk")
            click(cdp, sid, "[data-pop] [data-value='rating:Amber']")
            self.until(cdp, sid, "(document.querySelector('#peek [data-pk-rating]') || {}).textContent === ' · Amber'", "the peek says Closed · Amber")
            self.assertEqual(self.row("raid", "TUL-007")["status"], "Closed")
            self.undo(cdp, sid, "rating from the peek", "TUL-007 is back to Red.")
            self.until(cdp, sid, "(document.querySelector('#peek [data-pk-rating]') || {}).textContent === ' · Red'", "Undo draws Closed · Red again in the peek")
            self.assertEqual(self.row("raid", "TUL-007")["priority"], "High")

    # One test for each width: each starts on a fresh store, since the first leaves TUL-007 closed.
    def test_the_peek_has_the_same_status_picker_as_the_table(self):
        self.peek_picker(1400)

    def test_the_peek_has_the_same_status_picker_as_the_table_at_900(self):
        self.peek_picker(900)

    def test_a_pick_in_the_peek_is_about_the_open_item_even_with_two_rows_selected(self):
        """#448: the peek's picker never turns into the table's bulk change (#196)."""
        mod = 4 if sys.platform == "darwin" else 2
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            for ref, mods, n in (("TUL-007", 0, 1), ("TUL-010", mod, 2)):      # as the test above: wait for each to be picked before the next
                click(cdp, sid, f"tr[data-id='{ref}'] .c-item .t", mods)
                self.until(cdp, sid, f"document.querySelectorAll(\"tr[data-id].picked\").length === {n} && document.querySelector(\"tr[data-id='{ref}']\").classList.contains('picked')", f"{ref} picked, {n} in all")
            cdp.js("clarkPage.openPeek('TUL-007', 'item')", sid)
            pcell = "#peek [data-cell='peek:TUL-007:status']"
            self.until(cdp, sid, f"!!document.querySelector(\"{pcell}\")", "the peek's picker is there")
            click(cdp, sid, pcell)
            self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "the menu opened")
            before = self.steps()
            click(cdp, sid, "[data-pop] [data-value=Cancelled]")
            self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "saved at once, no question first")
            self.assertEqual((self.row("raid", "TUL-007")["status"], self.row("raid", "TUL-010")["status"]), ("Cancelled", "Open"), "only the open item changed")
            self.changed_once(before, "one item, from the peek")

    def test_the_view_peek_of_a_closed_risk_says_closed_and_its_rating_word_with_no_picker(self):
        """#448 (done-when 5): in View the peek of a closed risk says Closed and its rating word; no picker, no internal field. The
        published file itself is checked in test_peek.PublishedList."""
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_page(cdp, width, edit=False)
                cdp.js("clarkPage.openPeek('TUL-008', 'item')", sid)
                self.until(cdp, sid, "!!document.querySelector('#peek [data-pk-rating]')", "the peek says the rating word")
                self.assertEqual(cdp.js("document.querySelector('#peek [data-row=status] dd').textContent.replace(/\\s+/g, ' ').trim()", sid), "Closed · Amber")
                self.assertEqual(cdp.js("document.querySelectorAll('#peek [data-cell], #peek .cell-pick, [data-pop]').length", sid), 0, "View has no picker")
                labels = cdp.js("[...document.querySelectorAll('#peek dt')].map(d => d.textContent)", sid)
                self.assertNotIn("Shown to client", labels)

    def rating_drawn(self, cdp, sid, ref):
        """The row's Priority cell and the Rating ticked in its status picker (opened and shut again)."""
        prio = cdp.js(f"document.querySelector(\"tr[data-id='{ref}'] .c-prio\").textContent", sid)
        click(cdp, sid, f"[data-cell='{ref}:status']")
        self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "the status menu opened")
        ticked = cdp.js("[...document.querySelectorAll(\"[data-pop] [role=menuitemradio][aria-checked=true]\")].map(b => b.dataset.value).filter(v => v.startsWith('rating:'))", sid)
        key(cdp, sid, "Escape")
        self.until(cdp, sid, "document.querySelectorAll('[data-pop]').length === 0", "the menu shut")
        return [prio, ticked]

    def test_a_rating_pick_redraws_the_colour_from_the_reply_and_undo_puts_it_back(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            cdp.js("window.__replies = []; const f = window.fetch; window.fetch = async (...a) => { const r = await f(...a);"
                   " if (String(a[0]).endsWith('/api/change')) r.clone().json().then(j => window.__replies.push(j)); return r; }", sid)
            self.assertEqual(self.rating_drawn(cdp, sid, "TUL-007"), ["High", ["rating:Red"]], "a Red risk to start with")
            click(cdp, sid, "[data-cell='TUL-007:status']")
            self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "the status menu opened")
            click(cdp, sid, "[data-pop] [data-value='rating:Amber']")
            self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "saved, with Undo")
            self.until(cdp, sid, "window.__replies.length === 1", "the change replied")
            item = cdp.js("window.__replies[0].item", sid)
            self.assertEqual((item["impact"], item["likelihood"], item.get("priority")), ("Medium", "Medium", "Medium"), "the reply carries the worked-out priority")
            self.assertEqual(self.rating_drawn(cdp, sid, "TUL-007"), ["Medium", ["rating:Amber"]], "the cell shows Amber at once, no reload")
            self.undo(cdp, sid, "rating", "TUL-007 is back to Red.")
            self.until(cdp, sid, "document.querySelector(\"tr[data-id='TUL-007'] .c-prio\").textContent === 'High'", "Undo draws it Red again")
            self.assertEqual(self.rating_drawn(cdp, sid, "TUL-007"), ["High", ["rating:Red"]])

    def test_a_rating_pick_with_two_rows_selected_changes_only_that_row(self):
        mod = 4 if sys.platform == "darwin" else 2                       # Cmd on a Mac, Ctrl elsewhere
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            for ref, mods, n in (("TUL-007", 0, 1), ("TUL-010", mod, 2)):      # as test_multi_select does: scroll to it, click its title, and wait for it to be picked before the next (the selection bar pushes the rows down)
                click(cdp, sid, f"tr[data-id='{ref}'] .c-item .t", mods)
                self.until(cdp, sid, f"document.querySelectorAll(\"tr[data-id].picked\").length === {n} && document.querySelector(\"tr[data-id='{ref}']\").classList.contains('picked')", f"{ref} picked, {n} in all")
            before, other = self.steps(), self.row("raid", "TUL-010")
            click(cdp, sid, "[data-cell='TUL-007:status']")
            self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "the status menu opened")
            click(cdp, sid, "[data-pop] [data-value='rating:Green']")
            self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "saved, with Undo")
            self.assertEqual(self.toast(cdp, sid), "TUL-007 rated Green.", "the one row, not a question about all of them")
            self.assertNotIn("Change the status of all", cdp.js("document.body.textContent", sid))
            self.changed_once(before, "rating")
            self.assertEqual(self.row("raid", "TUL-007")["priority"], "Low")
            r = self.row("raid", "TUL-010")
            self.assertEqual((r["impact"], r["likelihood"], r["status"]), (other["impact"], other["likelihood"], other["status"]), "the other selected row is untouched")

    def test_a_pending_decision_made_gets_todays_date_and_no_undo(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            click(cdp, sid, "[data-cell='TUL-D-016:status']")
            self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "the menu opened")
            self.assertEqual(cdp.js("[...document.querySelectorAll('[data-pop] [role=menuitemradio]')].map(b => b.textContent)", sid), ["Pending", "MadeCan't be undone", "Withdrawn"])
            self.assertEqual(cdp.js("document.querySelector('[data-pop] [data-value=Made] .mi-note').textContent", sid), "Can't be undone", "the warning is under Made, before the pick")
            click(cdp, sid, "[data-pop] [data-value=Made]")
            self.until(cdp, sid, "(document.querySelector('.toast-text') || {}).textContent.includes('is now made')", "the toast says it is made")
            self.assertEqual(self.toast(cdp, sid), "TUL-D-016 is now made, on 28-10-2026. This can't be undone. To change it, record a new decision.")
            self.assertEqual(cdp.js("!!document.querySelector('[data-undo]')", sid), False, "a made decision has no Undo")
            r = self.row("decisions", "TUL-D-016")
            self.assertEqual((r["status"], r["date"]), ("Made", TODAY))
            self.plain_words(cdp, sid)
            click(cdp, sid, "[data-cell='TUL-D-016:status']")
            self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "the menu opened again")
            self.assertEqual(cdp.js("[...document.querySelectorAll('[data-pop] [role=menuitemradio]')].map(b => b.textContent)", sid), ["Made", "Withdrawn"], "no way back to Pending")
            key(cdp, sid, "Escape")

    def test_owner_by_typing_by_choosing_and_by_keyboard_and_esc_leaves_it(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_page(cdp, width)
                cell = "[data-cell='TUL-A-001:owner']"
                before = self.steps()
                click(cdp, sid, cell)
                self.until(cdp, sid, "!!document.querySelector('[data-pop] input.cp-in')", "the owner picker opened")
                self.assertEqual(cdp.js("document.activeElement.value", sid), "Ada Quillfeather", "the box holds the owner, selected")
                self.assertGreaterEqual(cdp.js("document.querySelectorAll('[data-pop] [data-name]').length", sid), 3, "the project's people")
                cdp.call("Input.insertText", {"text": "Zelda Quince"}, sid)
                key(cdp, sid, "Enter")
                self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "saved, with Undo")
                self.assertEqual(self.row("actions", "TUL-A-001")["owner"], "Zelda Quince")
                self.changed_once(before, "owner")
                self.until(cdp, sid, f"document.querySelector(\"{cell}\").textContent.includes('Zelda Quince')", "the row shows the new owner")
                self.assertEqual(self.toast(cdp, sid), "Owner of TUL-A-001 changed to Zelda Quince.")
                self.undo(cdp, sid, "owner", "Owner of TUL-A-001 is back to Ada Quillfeather.")
                self.assertEqual(self.row("actions", "TUL-A-001")["owner"], "Ada Quillfeather")
                self.until(cdp, sid, f"document.querySelector(\"{cell}\").textContent.includes('Ada Quillfeather')", "Undo draws the owner back")
                # choose a name with the keyboard: Enter opens, type to narrow, Down into the names, Enter picks
                cdp.js(f"document.querySelector(\"{cell}\").focus()", sid)
                key(cdp, sid, "Enter")
                self.until(cdp, sid, "document.activeElement && document.activeElement.classList.contains('cp-in')", "focus is in the box")
                cdp.call("Input.insertText", {"text": "mar"}, sid)
                self.until(cdp, sid, "[...document.querySelectorAll('[data-pop] [data-name]')].map(b => b.dataset.name).join() === 'Edna Marblethorpe'", "typing narrows the names")
                key(cdp, sid, "ArrowDown")
                self.assertEqual(cdp.js("document.activeElement.dataset.name", sid), "Edna Marblethorpe")
                key(cdp, sid, "Enter")
                self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "the chosen name saved")
                self.assertEqual(self.row("actions", "TUL-A-001")["owner"], "Edna Marblethorpe")
                self.undo(cdp, sid, "owner by keyboard")
                # blank is refused in the panel, nothing is sent; Esc then leaves it as it was
                n = len(self.sent)
                click(cdp, sid, cell)
                self.until(cdp, sid, "!!document.querySelector('[data-pop] input.cp-in')", "open again")
                cdp.js("const i = document.querySelector('[data-pop] input.cp-in'); i.select();", sid)
                cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8}, sid)
                cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8}, sid)
                key(cdp, sid, "Enter")
                self.until(cdp, sid, "!!document.querySelector('[data-pop] .cp-problem')", "a blank owner is said in the panel")
                self.assertEqual(cdp.js("document.querySelector('[data-pop] .cp-problem').textContent", sid), "An owner can't be blank. Type a name, or TBC if no one is known yet.")
                # a name with a hidden character (pasted, say) is said in the panel too, and the box keeps what was typed
                cdp.call("Input.insertText", {"text": "Someone\u200bElse"}, sid)
                key(cdp, sid, "Enter")
                self.until(cdp, sid, "(document.querySelector('[data-pop] .cp-problem') || {}).textContent === "
                           "'That name has a hidden character in it, often from copying and pasting. Type the name again, then press Enter.'", "a hidden character is said in the panel")
                self.assertEqual(cdp.js("document.querySelector('[data-pop] input.cp-in').value", sid), "Someone\u200bElse", "the box keeps what was typed")
                self.assertEqual(len(self.sent), n, "nothing was sent")
                key(cdp, sid, "Escape")
                self.until(cdp, sid, "document.querySelectorAll('[data-pop]').length === 0", "one Esc closes it")
                self.assertEqual(self.focused(cdp, sid), "TUL-A-001:owner")
                self.assertEqual((len(self.sent), self.row("actions", "TUL-A-001")["owner"]), (n, "Ada Quillfeather"), "Esc leaves it as it was")

    def test_due_by_quick_choice_by_the_month_and_by_keyboard_in_one_panel(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_page(cdp, width)
                cell = "[data-cell='TUL-A-001:due']"
                before = self.steps()
                click(cdp, sid, cell)
                self.until(cdp, sid, "!!document.querySelector('[data-pop] .cp-g')", "the date picker opened")
                self.assertEqual(cdp.js("document.querySelectorAll('[data-pop]').length", sid), 1, "one panel")
                self.assertTrue(cdp.js("(() => { const b = document.querySelector('[data-pop]').getBoundingClientRect(); return b.top >= 0 && b.bottom <= innerHeight; })()", sid),
                                "the whole panel is inside the window, down to No date")
                self.assertEqual(cdp.js("document.querySelectorAll('input[type=date], input[type=datetime-local]').length", sid), 0, "no browser date popup")
                self.assertEqual(cdp.js("document.querySelector('[data-pop] .cp-t').textContent", sid), "November 2026")
                self.assertEqual(self.focused(cdp, sid), "2026-11-02", "focus is on the date it has")
                sel = cdp.js("(() => { const c = getComputedStyle(document.querySelector('[data-pop] [data-day=\"2026-11-02\"]')); return [c.fontWeight, c.textDecorationLine]; })()", sid)
                other = cdp.js("(() => { const c = getComputedStyle(document.querySelector('[data-pop] [data-day=\"2026-11-03\"]')); return [c.fontWeight, c.textDecorationLine]; })()", sid)
                self.assertEqual((sel, other), (["600", "underline"], ["400", "none"]), "the day it has is marked by more than its fill: heavier and underlined")
                self.assertEqual(cdp.js("[...document.querySelectorAll('[data-pop] [data-quick]')].map(b => b.firstChild.textContent)", sid), ["Today", "Tomorrow", "Friday", "Next week", "No date"])
                click(cdp, sid, "[data-pop] [data-quick='2026-10-29']")
                self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "saved, with Undo")
                self.assertEqual(self.row("actions", "TUL-A-001")["due_date"], "2026-10-29")
                self.changed_once(before, "due")
                self.until(cdp, sid, f"document.querySelector(\"{cell}\").textContent.startsWith('29-10-2026')", "the row shows the new date")
                self.assertEqual(self.toast(cdp, sid), "Due date of TUL-A-001 changed to 29-10-2026.")
                self.undo(cdp, sid, "due", "Due date of TUL-A-001 is back to 02-11-2026.")
                self.assertEqual(self.row("actions", "TUL-A-001")["due_date"], "2026-11-02")
                self.until(cdp, sid, f"document.querySelector(\"{cell}\").textContent.startsWith('02-11-2026')", "Undo draws the date back")
                # keyboard: Enter opens on the day, Right and Down move it, Page Down a month, Enter picks
                cdp.js(f"document.querySelector(\"{cell}\").focus()", sid)
                key(cdp, sid, "Enter")
                self.until(cdp, sid, "document.activeElement && document.activeElement.dataset.day === '2026-11-02'", "focus on the day")
                key(cdp, sid, "ArrowRight")
                key(cdp, sid, "ArrowDown")
                self.assertEqual(self.focused(cdp, sid), "2026-11-10")
                key(cdp, sid, "PageDown")
                self.until(cdp, sid, "document.activeElement && document.activeElement.dataset.day === '2026-12-10'", "Page Down moves a month")
                self.assertEqual(cdp.js("document.querySelector('[data-pop] .cp-t').textContent", sid), "December 2026")
                key(cdp, sid, "Enter")
                self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "the keyboard pick saved")
                self.assertEqual(self.row("actions", "TUL-A-001")["due_date"], "2026-12-10")
                self.undo(cdp, sid, "due by keyboard")
                # the month buttons, then Esc: one Esc closes the one panel and the date is as it was
                n = len(self.sent)
                click(cdp, sid, cell)
                self.until(cdp, sid, "!!document.querySelector('[data-pop] .cp-g')", "open again")
                click(cdp, sid, "[data-pop] [data-month='1']")
                self.until(cdp, sid, "document.querySelector('[data-pop] .cp-t').textContent === 'December 2026'", "› shows the next month")
                key(cdp, sid, "Escape")
                self.until(cdp, sid, "document.querySelectorAll('[data-pop]').length === 0", "one Esc closes it")
                self.assertEqual(self.focused(cdp, sid), "TUL-A-001:due")
                self.assertEqual((len(self.sent), self.row("actions", "TUL-A-001")["due_date"]), (n, "2026-11-02"), "Esc leaves the date as it was")
                # No date clears it, in one step with Undo
                click(cdp, sid, cell)
                self.until(cdp, sid, "!!document.querySelector('[data-pop] .cp-g')", "open again")
                click(cdp, sid, "[data-pop] [data-quick='']")
                self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "cleared, with Undo")
                self.assertIsNone(self.row("actions", "TUL-A-001")["due_date"])
                self.undo(cdp, sid, "due cleared")
                self.assertEqual(self.row("actions", "TUL-A-001")["due_date"], "2026-11-02")

    def test_every_inline_date_closes_on_one_esc_a_click_away_or_tab_and_changes_nothing(self):
        # #91: an action's due date, a pending decision's needed-by date and a made decision's date. Each is one panel of clark's
        # own (no browser calendar opens over it), so one Esc closes it; a click away and Tab close it too, and none of them sends
        # anything. (Enter and a chosen day applying the date in one step with Undo: test_due_by_quick_choice_by_the_month_and_by_
        # keyboard_in_one_panel and test_a_made_decisions_date_can_change_but_not_be_cleared.)
        dates = (("actions", "TUL-A-001", "due_date"), ("decisions", "TUL-D-016", "needed_by"), ("decisions", "TUL-D-015", "date"))
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_page(cdp, width)
                for table, ref, column in dates:
                    cell, was = f"[data-cell='{ref}:due']", self.row(table, ref)[column]
                    self.assertTrue(was, f"{ref} has a {column} to keep")
                    n, before = len(self.sent), self.steps()

                    def opened(how):
                        self.until(cdp, sid, "!!document.querySelector('[data-pop] .cp-g')", f"{ref}: {how} opens the date panel")
                        self.assertEqual(cdp.js("document.querySelectorAll('[data-pop]').length", sid), 1, f"{ref}: one panel")
                        self.assertEqual(cdp.js("document.querySelectorAll('input[type=date], input[type=datetime-local]').length", sid), 0,
                                         f"{ref}: no browser calendar opens with it")
                        self.until(cdp, sid, "document.activeElement && !!document.activeElement.dataset.day", f"{ref}: focus is on a day")

                    def kept(how):
                        self.until(cdp, sid, "document.querySelectorAll('[data-pop]').length === 0", f"{ref}: {how} closes the panel")
                        self.assertEqual((len(self.sent), self.steps(), self.row(table, ref)[column]), (n, before, was), f"{ref}: {how} changes nothing")
                        self.assertNotIn("item=", cdp.js("location.hash", sid), f"{ref}: {how} does not open the peek")
                        self.assertEqual(cdp.js("!!document.querySelector('[data-undo]')", sid), False, f"{ref}: {how} leaves nothing to undo")

                    # one Esc, after moving the day and the month: closed, as it was, focus back on the row's date
                    click(cdp, sid, cell)
                    opened("a click")
                    key(cdp, sid, "ArrowRight")
                    key(cdp, sid, "PageDown")
                    key(cdp, sid, "Escape")
                    kept("one Esc")
                    self.assertEqual(self.focused(cdp, sid), f"{ref}:due", f"{ref}: focus is back on the row's date")
                    # a click away
                    click(cdp, sid, cell)
                    opened("a click")
                    key(cdp, sid, "ArrowLeft")
                    click(cdp, sid, "h1")
                    kept("a click away")
                    # Tab: closed, and focus carries on from the row's date (not lost with the panel)
                    cdp.js(f"document.querySelector(\"{cell}\").focus()", sid)
                    key(cdp, sid, "Enter")
                    opened("Enter")
                    key(cdp, sid, "ArrowDown")
                    key(cdp, sid, "Tab")
                    kept("Tab")
                    self.assertTrue(cdp.js("(() => { const a = document.activeElement; return !!a && a !== document.body && a.isConnected && !a.closest('[data-pop]'); })()", sid),
                                    f"{ref}: after Tab, focus is on the page, not lost")
                    self.assertEqual(self.cell_text(cdp, sid, ref, "due")[:10], f"{was[8:10]}-{was[5:7]}-{was[:4]}", f"{ref}: the row still shows its date")

    def test_a_made_decisions_date_can_change_but_not_be_cleared(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            click(cdp, sid, "[data-cell='TUL-D-015:due']")
            self.until(cdp, sid, "!!document.querySelector('[data-pop] .cp-g')", "the date picker opened")
            self.assertEqual(cdp.js("document.querySelectorAll('[data-pop] [data-quick=\"\"]').length", sid), 0, "no No date for a made decision")
            self.assertEqual(self.focused(cdp, sid), "2026-10-20")
            key(cdp, sid, "ArrowLeft")
            key(cdp, sid, "Enter")
            self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "saved, with Undo")
            self.assertEqual(self.row("decisions", "TUL-D-015")["date"], "2026-10-19")
            self.assertEqual(self.toast(cdp, sid), "Decision date of TUL-D-015 changed to 19-10-2026.")
            self.undo(cdp, sid, "decision date")
            self.assertEqual(self.row("decisions", "TUL-D-015")["date"], "2026-10-20")

    def test_an_undo_after_opening_another_project_does_not_say_something_went_wrong(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            click(cdp, sid, "[data-cell='TUL-A-001:priority']")
            self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "the menu opened")
            click(cdp, sid, "[data-pop] [data-value=Low]")
            self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "saved, with Undo")
            # the person opens another project while the undo is on its way: the list of TUL is not read again, and that is fine
            cdp.js("(() => { const real = window.fetch; window.fetch = async (...a) => { const r = await real(...a); "
                   "if (String(a[0]).includes('/api/undo')) clarkPage.setProject('OTH'); return r; }; })()", sid)
            click(cdp, sid, "[data-undo]")
            self.until(cdp, sid, "clarkPage.project() === 'OTH'", "another project is open")
            self.until(cdp, sid, "(document.querySelector('.toast-text') || {}).textContent === 'Priority of TUL-A-001 is back to Urgent.'", "the undo said what went back, and nothing more")
            self.assertEqual(self.row("actions", "TUL-A-001")["priority"], "Urgent", "it was undone")
            self.assertNotIn("could not be refreshed", self.toast(cdp, sid))
            self.assertFalse(cdp.js("!!document.querySelector('.toast.problem')", sid), "no problem is said")

    def test_a_refusal_is_said_in_the_pages_words(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            # clark refuses (the item was archived meanwhile): the page says its own words, never the server's, and offers no Undo
            self.failure = lambda req: (400, {"ok": False, "message": "That item isn't in this project."})
            click(cdp, sid, "[data-cell='TUL-A-004:priority']")
            self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "the menu opened")
            click(cdp, sid, "[data-pop] [data-value=Low]")
            self.until(cdp, sid, "!!document.querySelector('.toast.problem')", "a problem toast")
            self.assertEqual(self.toast(cdp, sid), "That item is no longer in this project, and nothing was changed. Reload the page.")
            self.assertEqual(cdp.js("!!document.querySelector('[data-undo]')", sid), False)
            self.assertEqual(self.cell_text(cdp, sid, "TUL-A-004", "priority"), "High", "the row is as clark has it")
            self.failure = lambda req: (400, {"ok": False, "message": "Some server words a person must never read"})
            click(cdp, sid, "[data-cell='TUL-A-004:priority']")
            self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "the menu opened")
            click(cdp, sid, "[data-pop] [data-value=Low]")
            self.until(cdp, sid, "(document.querySelector('.toast-text') || {}).textContent !== \"That item is no longer in this project, and nothing was changed. Reload the page.\"", "a new message")
            self.assertNotIn("Some server words", self.toast(cdp, sid))


class NoBrowserCalendar(unittest.TestCase):
    def test_no_inline_date_uses_the_browsers_calendar(self):
        # #91: an inline date opened two panels when the browser's calendar opened over clark's own, and one Esc closed only one.
        # Every inline date is DuePick's one panel, so the page code has no browser date field but the draft email's Reply by,
        # which is a field in a dialog, not an inline date, and the board's "Pick a due date" dialog (#102), shown when a card
        # moves into a column that needs a date: also a dialog, not an inline date (it may still show the browser's calendar
        # over the dialog; that is raised on #7 for its own item). A new one must be clark's picker (edit/cells/DuePick.jsx).
        found = sorted(str(p.relative_to(PAGE_SRC)) for p in PAGE_SRC.rglob("*") if p.suffix in (".js", ".jsx")
                       and re.search(r"type\s*[=:]\s*[\"'](date|datetime-local|month|week)[\"']|showPicker\s*\(", p.read_text(encoding="utf-8")))
        self.assertEqual(found, ["components/DraftEmail.jsx", "edit/Board.jsx"])


if __name__ == "__main__":
    unittest.main()
