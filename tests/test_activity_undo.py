"""The Activity tab's Undo several (the page part): a tick box on each change that can be undone, a header tick, click, Cmd or Ctrl
and Shift ranges, the bar ("N selected", Undo N, Clear), the preview (a dry run) with what is left and why, one new change that
undoes them all and is itself undoable, the second confirm above 25, Esc, and the selection clearing after the undo.

Run: python3 dev/run_tests.py test_activity_undo
A real server over a real demo store (fictional data) with the real change, undo and activity routes, and the committed page in
headless Chrome at 1400 and 900 px, light and dark. The browser parts are required: they fail, never skip, without Chrome.
"""
import json
import re
import unittest

from _paths import ROOT

from clark import activity_read, changes, page
from test_dark_contrast import dark_blocks, ratio
from test_peek import key
from test_peek_activity import light_tokens
import test_undo_key as tuk
from test_server import chrome, wait
from test_work_filters import where, dblclick

SRC = ROOT / "src" / "clark" / "page" / "src"
TOKENS = ROOT / "src" / "clark" / "brand" / "tokens.css"
ITEM = "TUL-A-001"
CTRL, SHIFT = 4, 8      # Cmd (Ctrl-click is a right click on a Mac; the page takes either)


def click_with(cdp, sid, selector, modifiers=0):
    """A real mouse click on the left of an element, with Cmd/Ctrl/Shift held as `modifiers`."""
    x, y = where(cdp, sid, selector)
    x = cdp.js(f"document.querySelector({json.dumps(selector)}).getBoundingClientRect().x + 24", sid)
    common = {"x": x, "y": y, "button": "left", "modifiers": modifiers}
    cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y, "modifiers": modifiers}, sid)
    cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "buttons": 1, "clickCount": 1, **common}, sid)
    cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "buttons": 0, "clickCount": 1, **common}, sid)


class Tab(unittest.TestCase):
    setUp = tuk.UndoKey.__dict__["setUp"]
    read = tuk.UndoKey.__dict__["read"]
    priority = tuk.UndoKey.__dict__["priority"]
    steps = tuk.UndoKey.__dict__["steps"]
    open_page = tuk.UndoKey.__dict__["open_page"]
    until = tuk.UndoKey.__dict__["until"]
    toast = tuk.UndoKey.__dict__["toast"]

    def setUp(self):                                               # noqa: F811
        self.fresh()

    def fresh(self):
        """A new demo store and server (each case starts from a history of its own)."""
        tuk.UndoKey.setUp(self)
        self.s.httpd.activity = activity_read.make_read(self.path, self.read)
        self.make = changes.make_change(self.path, [], tuk.USER)
        self.undo = changes.make_undo(self.path, [], tuk.USER)

    def alter(self, n):
        """n changes of TUL-A-001's priority, each its own step; the steps, oldest first."""
        out = []
        for i in range(n):
            status, body = self.make({"project": "TUL", "kind": "actions", "op": "update", "id": ITEM,
                                      "changes": {"priority": "Low" if i % 2 == 0 else "High"}, "place": "cell"})
            self.assertEqual(status, 200, body)
            out.append(body["apply_id"])
        return out

    def open_activity(self, cdp, width, scheme="light"):
        sid = self.open_page(cdp, width, scheme)
        dblclick(cdp, sid, f"#work tbody tr[data-id='{ITEM}'] .c-item")
        self.until(cdp, sid, "!!document.querySelector('[data-pk-tab=activity]')", "the peek has its tabs in Edit")
        tuk.click(cdp, sid, "[data-pk-tab=activity]")
        self.until(cdp, sid, "document.querySelectorAll('[data-activity-row]').length > 0", "the history is drawn")
        return sid

    def ticked(self, cdp, sid):
        return cdp.js("Array.from(document.querySelectorAll('[data-pa-tick]')).filter(e => e.checked).map(e => e.dataset.paTick)", sid)

    def row(self, step):
        return f"[data-activity-row][data-step='{step}'] .pa-meta"

    def range(self, cdp, sid, done):
        """Click the newest of the changes made, then Shift-click the oldest: the range between them, and nothing older."""
        click_with(cdp, sid, self.row(done[-1]))
        click_with(cdp, sid, self.row(done[0]), SHIFT)

    def bar(self, cdp, sid):
        return cdp.js("(document.querySelector('[data-pa-count]') || {}).textContent || ''", sid)

    def test_ticks_ranges_header_preview_skipped_one_step_and_undoing_the_undo(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                self.fresh()
                done = self.alter(4)
                self.assertEqual(self.undo({"project": "TUL", "apply_id": done[-1]})[0], 200)  # an undo row: it says why it has no tick
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    sid = self.open_activity(cdp, width, scheme)
                    steps = [str(s) for s in reversed(done)]                                   # newest first, as drawn
                    undo_row = cdp.js("document.querySelectorAll('[data-activity-row]:not([data-step])').length", sid)
                    self.assertGreaterEqual(undo_row, 1, "a row that cannot be chosen has no tick")
                    self.assertIn("undo", cdp.js("document.querySelector('[data-pa-why]').textContent", sid).lower(), "and says why in words")
                    self.assertFalse(cdp.js("!!document.querySelector('[data-activity-row]:not([data-step]) [data-pa-tick]')", sid))
                    self.assertEqual(cdp.js("document.querySelector('[data-pa-all-label]').textContent", sid), "Select all changes that can be undone")
                    self.assertEqual(cdp.js("!!document.querySelector('[data-pa-undo-n]')", sid), False, "no bar with nothing chosen")
                    click_with(cdp, sid, self.row(steps[0]))                                  # a click chooses just that one
                    self.until(cdp, sid, "document.querySelectorAll('[data-pa-tick]:checked').length === 1", "one chosen")
                    click_with(cdp, sid, self.row(steps[2]), CTRL)                            # Ctrl adds
                    self.until(cdp, sid, "document.querySelectorAll('[data-pa-tick]:checked').length === 2", "two chosen")
                    self.assertEqual(sorted(self.ticked(cdp, sid)), sorted([steps[0], steps[2]]))
                    click_with(cdp, sid, self.row(steps[1]), SHIFT)                           # Shift: from the last click to here
                    self.until(cdp, sid, "document.querySelectorAll('[data-pa-tick]:checked').length === 2", "a range from the anchor")
                    self.assertEqual(sorted(self.ticked(cdp, sid)), sorted([steps[2], steps[1]]))
                    cdp.js("document.querySelector('[data-pa-all]').click()", sid)           # the header tick: every row that can be undone
                    every = cdp.js("new Set(Array.from(document.querySelectorAll('[data-pa-tick]')).map(e => e.dataset.paTick)).size", sid)
                    self.until(cdp, sid, f"new Set(Array.from(document.querySelectorAll('[data-pa-tick]:checked')).map(e => e.dataset.paTick)).size === {every}", "every change that can be undone")
                    self.assertEqual(self.bar(cdp, sid), f"{every} selected")
                    cdp.js("document.querySelector('[data-pa-clear]').click()", sid)
                    self.until(cdp, sid, "!document.querySelector('[data-pa-bar]')", "Clear empties it")
                    # choose three, one of which is undone already: the preview names it and the reason
                    for i, mod in ((0, 0), (1, CTRL), (2, CTRL)):
                        click_with(cdp, sid, self.row(steps[i]), mod)
                    self.until(cdp, sid, "document.querySelectorAll('[data-pa-tick]:checked').length === 3", "three chosen")
                    self.assertEqual(self.bar(cdp, sid), "3 selected")
                    self.assertEqual(cdp.js("document.querySelector('[data-pa-undo-n]').textContent", sid), "Undo 3")
                    before, n = self.steps(), len(self.sent)
                    cdp.js("document.querySelector('[data-pa-undo-n]').click()", sid)
                    self.until(cdp, sid, "!!document.querySelector('[data-pa-preview]')", "the preview shows first")
                    self.assertEqual(self.steps(), before, "a preview writes nothing")
                    self.assertTrue(self.sent[n][1].get("preview"), "it is a dry run")
                    text = cdp.js("document.querySelector('[data-pa-preview]').textContent", sid)
                    self.assertIn("2 changes will be undone", text)
                    self.assertIn("1 change will be left as it is", text)
                    self.assertIn("This has been undone already.", text, "the reason is in words")
                    self.assertEqual(cdp.js("document.activeElement.dataset.paHead !== undefined", sid), True, "the keyboard lands on the preview")
                    key(cdp, sid, "Escape")                                                   # Esc closes the preview and keeps the choice
                    self.until(cdp, sid, "!document.querySelector('[data-pa-preview]')", "Esc closed the preview")
                    self.assertEqual(self.bar(cdp, sid), "3 selected")
                    self.assertTrue(cdp.js("!!document.querySelector('#peek')", sid), "the peek stays")
                    cdp.js("document.querySelector('[data-pa-undo-n]').click()", sid)
                    self.until(cdp, sid, "!!document.querySelector('[data-pa-go]')", "the preview is back")
                    cdp.js("document.querySelector('[data-pa-go]').click()", sid)
                    self.until(cdp, sid, "/Undone: 2 changes/.test((document.querySelector('.toast-text') || {}).textContent || '')", "one undo said what went back")
                    self.assertEqual(self.steps(), before + 1, "one new change for the whole batch")
                    self.until(cdp, sid, "!document.querySelector('[data-pa-bar]')", "the selection cleared after the undo")
                    self.assertEqual(self.ticked(cdp, sid), [])
                    after = self.priority()
                    self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "the batch is itself undoable")
                    cdp.js("document.querySelector('[data-undo]').click()", sid)
                    self.assertTrue(wait(lambda: self.steps() == before + 2), f"the toast's Undo took the whole batch back, as one more change: {self.sent[-1]} {self.toast(cdp, sid)}")
                    self.until(cdp, sid, "/^Undone/.test((document.querySelector('.toast-text') || {}).textContent || '')", "and said so")
                    self.assertEqual(self.steps(), before + 2)
                    self.assertIsNotNone(after)
                    self.assertTrue(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), "no sideways scroll")

    def test_above_25_a_second_confirm_is_asked_and_at_25_it_is_not(self):
        done = self.alter(26)
        with chrome() as cdp:
            sid = self.open_activity(cdp, 1400)
            self.range(cdp, sid, done)
            self.until(cdp, sid, "document.querySelectorAll('[data-pa-tick]:checked').length === 26", "all 26 chosen")
            self.assertEqual(self.bar(cdp, sid), "26 selected")
            cdp.js("document.querySelector('[data-pa-undo-n]').click()", sid)
            self.until(cdp, sid, "!!document.querySelector('[data-pa-go]')", "the preview")
            before, n = self.steps(), len(self.sent)
            cdp.js("document.querySelector('[data-pa-go]').click()", sid)
            self.until(cdp, sid, "!!document.querySelector('[data-pa-sure]')", "the second confirm")
            self.assertIn("26", cdp.js("document.querySelector('[data-pa-sure]').textContent", sid))
            self.assertEqual((self.steps(), len(self.sent)), (before, n), "nothing is sent until it is confirmed")
            cdp.js("document.querySelector('[data-pa-back]').click()", sid)
            self.until(cdp, sid, "!document.querySelector('[data-pa-sure]') && !document.querySelector('[data-pa-preview]')", "No goes back")
            self.assertEqual(self.bar(cdp, sid), "26 selected", "the choice is kept")
            cdp.js("document.querySelector('[data-pa-undo-n]').click()", sid)
            self.until(cdp, sid, "!!document.querySelector('[data-pa-go]')", "the preview again")
            cdp.js("document.querySelector('[data-pa-go]').click()", sid)
            self.until(cdp, sid, "!!document.querySelector('[data-pa-yes]')", "asks again")
            cdp.js("document.querySelector('[data-pa-yes]').click()", sid)
            self.until(cdp, sid, "/^Undone: 26 changes/.test((document.querySelector('.toast-text') || {}).textContent || '')", "all 26 went back")
            self.assertEqual(self.steps(), before + 1)
            self.assertTrue(self.sent[-1][1].get("confirm"), "the run said it was confirmed")
            self.assertEqual(sorted(self.sent[-1][1]["steps"]), sorted(done))

    def test_at_exactly_25_there_is_no_second_question(self):
        done = self.alter(25)
        with chrome() as cdp:
            sid = self.open_activity(cdp, 1400)
            self.range(cdp, sid, done)
            self.until(cdp, sid, "document.querySelectorAll('[data-pa-tick]:checked').length === 25", "25 chosen")
            cdp.js("document.querySelector('[data-pa-undo-n]').click()", sid)
            self.until(cdp, sid, "!!document.querySelector('[data-pa-go]')", "the preview")
            cdp.js("document.querySelector('[data-pa-go]').click()", sid)
            self.until(cdp, sid, "/^Undone: 25 changes/.test((document.querySelector('.toast-text') || {}).textContent || '')", "25 go back at once")
            self.assertFalse(cdp.js("!!document.querySelector('[data-pa-sure]')", sid))

    def test_esc_clears_the_choice_then_closes_the_peek_and_the_keyboard_can_choose(self):
        done = self.alter(3)
        with chrome() as cdp:
            sid = self.open_activity(cdp, 1400)
            steps = [str(s) for s in reversed(done)]
            cdp.js(f"document.querySelector(\"[data-pa-tick='{steps[0]}']\").focus()", sid)
            key(cdp, sid, " ")                                                              # Space on a tick box
            self.until(cdp, sid, "document.querySelectorAll('[data-pa-tick]:checked').length === 1", "Space chose it")
            self.assertEqual(cdp.js("(document.querySelector('[data-pa-live]') || {}).textContent.trim()", sid), "1 selected")
            self.assertEqual(cdp.js("document.querySelectorAll('[aria-live=polite]').length", sid) >= 1, True)
            key(cdp, sid, "Escape")
            self.until(cdp, sid, "document.querySelectorAll('[data-pa-tick]:checked').length === 0", "Esc cleared it")
            self.assertTrue(cdp.js("!!document.querySelector('#peek')", sid), "the peek stayed")
            key(cdp, sid, "Escape")
            self.until(cdp, sid, "!document.querySelector('#peek')", "a second Esc closes the peek")

    def test_the_tab_is_in_the_served_page_only_and_the_text_reads_at_4_5_to_1(self):
        served, view = page.PAGE.read_text(encoding="utf-8"), page.VIEW_PAGE.read_text(encoding="utf-8")
        for word in ("Select all changes that can be undone", "data-pa-undo-n", "data-pa-tick"):
            self.assertIn(word, served, word)
            self.assertNotIn(word, view, word)
        css = TOKENS.read_text(encoding="utf-8")
        for mode, tokens in [("light", light_tokens(css))] + [("dark", b) for b in dark_blocks(css)]:
            for fg, bg in (("--text", "--brand-blue-tint"), ("--text-muted", "--brand-blue-tint"), ("--heading", "--brand-blue-tint"),
                           ("--text", "--grey-50"), ("--heading", "--grey-50"), ("--status-red-text", "--grey-50"), ("--status-red-text", "--surface")):
                with self.subTest(mode=mode, fg=fg, bg=bg):
                    self.assertGreaterEqual(ratio(tokens[fg], tokens[bg]), 4.5)

    def test_the_rules_say_why_a_row_cannot_be_chosen(self):
        src = (SRC / "edit" / "activityUndo.js").read_text(encoding="utf-8")
        for words in ("A comment has nothing to undo.", "This was an undo", "This change can't be undone from here."):
            self.assertIn(words, src)
        self.assertNotRegex(src, r"#\d+")


if __name__ == "__main__":
    unittest.main()
