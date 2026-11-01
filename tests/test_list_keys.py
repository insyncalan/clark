"""#194: the arrow keys on the Work items table, the board and the peek.

Run: python3 dev/run_tests.py test_list_keys
Part 1 reads the sources (no J or K key, only arrows and Enter, the cursor is drawn, Help lists the keys). Part 2 drives the committed
page in headless Chrome at 1400 and 900 px with real key events over a real demo store. The browser parts are required: they fail,
never skip, without Chrome. The peek's own component is not on the page yet, so the peek is read from the address and clarkPage.peek(); Help's lines for the peek keys wait for it.
"""
import unittest

from _paths import ROOT

import test_inline_edits as ie  # noqa: E402  (not bound by name, so its own tests are not run again here)
from test_inline_edits import key  # noqa: E402
from test_server import chrome  # noqa: E402,F401  (the browser tier: this file drives Chrome through ie.chrome())

PAGE = ROOT / "src" / "clark" / "page"
LIST_KEYS = (PAGE / "src" / "listKeys.js").read_text(encoding="utf-8")
WORK = (PAGE / "src" / "components" / "WorkItems.jsx").read_text(encoding="utf-8")
BOARD = (PAGE / "src" / "edit" / "Board.jsx").read_text(encoding="utf-8")
CSS = (PAGE / "shell.css").read_text(encoding="utf-8")
HELP = (PAGE / "src" / "help" / "helpContent.json").read_text(encoding="utf-8")
ROWS = "[...document.querySelectorAll('#work tbody tr[data-id]')].map(r => r.dataset.id)"
FOCUS = "(document.activeElement.dataset || {}).id || ''"


class Source(unittest.TestCase):
    def test_no_letter_keys_only_arrows_and_enter(self):
        for name, text in (("listKeys", LIST_KEYS), ("table", WORK), ("board", BOARD)):
            self.assertNotIn('"j"', text.lower(), name)
            self.assertNotIn('"k"', text.lower(), name)

    def test_the_cursor_is_drawn_not_only_coloured(self):
        self.assertIn("table.items tr[data-id]:focus-visible { outline: 2px dotted", CSS)
        self.assertIn(".bc-main:focus-visible { outline: 2px dotted", CSS)

    def test_help_lists_every_key(self):
        for words in ("Work items table: move the cursor", "Work items board: move from card to card", "In Edit, [[Enter]] on a cell opens that cell"):
            self.assertIn(words, HELP)


class Keys(ie.Live):
    def board(self, cdp, sid):
        cdp.js("localStorage.setItem('clark.work.v1', JSON.stringify({TUL: {view: 'board', group: 'status', lane: null, collapsed: []}}))", sid)
        cdp.call("Page.reload", {}, sid)
        self.until(cdp, sid, "!!document.querySelector('#work-board .bcard')", "the board")

    def test_the_table_cursor_is_one_tab_stop_and_never_lands_on_a_heading(self):
        for width in (1400, 900):
            with self.subTest(width=width), ie.chrome() as cdp:
                sid = self.open_page(cdp, width, edit=False)
                rows = cdp.js(ROWS, sid)
                cdp.js("document.querySelector('#work tbody tr[data-id]').focus()", sid)
                for want in rows[1:4]:
                    key(cdp, sid, "ArrowDown")
                    self.assertEqual(cdp.js(FOCUS, sid), want)
                key(cdp, sid, "End")
                self.assertEqual(cdp.js(FOCUS, sid), rows[-1])
                key(cdp, sid, "Home")
                self.assertEqual(cdp.js(FOCUS, sid), rows[0])
                self.assertEqual(cdp.js("document.querySelectorAll('#work tr[data-id][tabindex=\"0\"]').length", sid), 1, "one tab stop")
                self.assertIn("dotted", cdp.js("getComputedStyle(document.activeElement).outlineStyle", sid), "a drawn cursor")

    def test_right_opens_the_peek_up_and_down_take_it_along_left_closes(self):
        for width in (1400, 900):
            with self.subTest(width=width), ie.chrome() as cdp:
                sid = self.open_page(cdp, width, edit=False)
                rows = cdp.js(ROWS, sid)
                cdp.js("document.querySelector('#work tbody tr[data-id]').focus()", sid)
                key(cdp, sid, "ArrowRight")
                self.until(cdp, sid, f"location.hash.includes('item={rows[0]}')", "Right opens the peek")
                self.until(cdp, sid, "document.activeElement.hasAttribute('data-pk-close')", "the peek takes focus when it opens")
                cdp.js(f"document.querySelector('#work tr[data-id=\"{rows[0]}\"]').focus()", sid)      # back to the cursor, as a reader would
                key(cdp, sid, "ArrowDown")
                self.until(cdp, sid, f"location.hash.includes('item={rows[1]}')", "Down: the peek follows the cursor")
                self.assertEqual(cdp.js(FOCUS, sid), rows[1])
                key(cdp, sid, "ArrowUp")
                self.until(cdp, sid, f"location.hash.includes('item={rows[0]}')", "Up: the peek follows back")
                key(cdp, sid, "ArrowLeft")
                self.until(cdp, sid, "!location.hash.includes('item=')", "Left closes the peek")
                self.assertEqual(cdp.js(FOCUS, sid), rows[0], "focus stays on the row")
                key(cdp, sid, "ArrowDown")                       # no peek open: Down only moves
                self.assertFalse(cdp.js("location.hash.includes('item=')", sid))
                key(cdp, sid, "Enter")
                self.until(cdp, sid, f"location.hash.includes('item={rows[1]}')", "Enter opens the cursor row's peek")

    def test_focus_returns_to_the_row_when_the_peek_closes_from_elsewhere(self):
        with ie.chrome() as cdp:
            sid = self.open_page(cdp, 1400, edit=False)
            rows = cdp.js(ROWS, sid)
            cdp.js("document.querySelector('#work tbody tr[data-id]').focus()", sid)
            key(cdp, sid, "Enter")
            self.until(cdp, sid, f"location.hash.includes('item={rows[0]}')", "open")
            cdp.js("document.activeElement.blur()", sid)       # as if the peek held focus and has gone
            cdp.js("clarkPage.closePeek()", sid)
            self.until(cdp, sid, f"{FOCUS} === {rows[0]!r}", "focus is back on the row")

    def test_in_edit_the_row_keeps_its_cells_and_enter_on_a_cell_opens_its_picker(self):
        for width in (1400, 900):
            with self.subTest(width=width), ie.chrome() as cdp:
                sid = self.open_page(cdp, width, edit=True)
                rows = cdp.js(ROWS, sid)
                cdp.js("document.querySelector('#work tbody tr[data-id]').focus()", sid)
                key(cdp, sid, "ArrowRight")
                self.assertEqual(self.focused(cdp, sid), f"{rows[0]}:owner", "Right on the row goes to its first cell")
                self.assertFalse(cdp.js("location.hash.includes('item=')", sid), "Right did not open the peek in Edit")
                key(cdp, sid, "ArrowRight")
                self.assertEqual(self.focused(cdp, sid), f"{rows[0]}:due")
                key(cdp, sid, "ArrowLeft")
                self.assertEqual(self.focused(cdp, sid), f"{rows[0]}:owner")
                key(cdp, sid, "Enter")
                self.until(cdp, sid, "!!document.querySelector('[data-pop]')", "Enter on a cell opens its picker")
                self.assertFalse(cdp.js("location.hash.includes('item=')", sid), "and not the peek")

    def test_a_key_in_a_box_is_left_alone(self):
        with ie.chrome() as cdp:
            sid = self.open_page(cdp, 1400, edit=False)
            cdp.js("document.querySelector('#work tbody tr[data-id]').focus()", sid)
            key(cdp, sid, "ArrowDown")
            before = cdp.js(FOCUS, sid)
            cdp.js("(() => { const i = document.createElement('input'); i.id = 'probe'; document.querySelector('#work tbody tr[data-id]').appendChild(i); i.focus(); })()", sid)
            key(cdp, sid, "ArrowRight")
            key(cdp, sid, "ArrowDown")
            self.assertEqual(cdp.js("document.activeElement.id", sid), "probe")
            self.assertFalse(cdp.js("location.hash.includes('item=')", sid), "a box's own keys do not open a peek")
            self.assertTrue(before)

    def test_the_board_is_one_tab_stop_and_the_arrows_walk_the_cards(self):
        for width in (1400, 900):
            with self.subTest(width=width), ie.chrome() as cdp:
                sid = self.open_page(cdp, width, edit=False)
                self.board(cdp, sid)
                cards = "[...document.querySelectorAll('#work-board .bc-main')].map(c => c.closest('[data-id]').dataset.id)"
                ids = cdp.js(cards, sid)
                self.assertGreater(len(ids), 3)
                self.assertEqual(cdp.js("document.querySelectorAll('#work-board .bc-main[tabindex=\"0\"]').length", sid), 1, "one tab stop")
                cdp.js("document.querySelector('#work-board .bc-main').focus()", sid)
                at = lambda: cdp.js("document.activeElement.closest('[data-id]').dataset.id", sid)
                key(cdp, sid, "ArrowRight")
                self.assertEqual(at(), ids[1], "Right: the next card")
                key(cdp, sid, "ArrowDown")
                self.assertEqual(at(), ids[2], "Down: the next card in reading order")
                key(cdp, sid, "ArrowLeft")
                self.assertEqual(at(), ids[1])
                key(cdp, sid, "ArrowUp")
                self.assertEqual(at(), ids[0])
                key(cdp, sid, "ArrowUp")
                self.assertEqual(at(), ids[0], "stays on the first")
                key(cdp, sid, "End")
                self.assertEqual(at(), ids[-1])
                key(cdp, sid, "Home")
                self.assertEqual(at(), ids[0])
                self.assertIn("dotted", cdp.js("getComputedStyle(document.activeElement).outlineStyle", sid), "a drawn cursor")
                key(cdp, sid, "Enter")
                self.until(cdp, sid, f"location.hash.includes('item={ids[0]}')", "Enter opens the card's peek")
                self.until(cdp, sid, "document.activeElement.hasAttribute('data-pk-close')", "the peek takes focus when it opens")
                cdp.js(f"document.querySelector('#work-board [data-id=\"{ids[0]}\"] .bc-main').focus()", sid)      # back to the cursor, as a reader would
                key(cdp, sid, "ArrowDown")
                self.until(cdp, sid, f"location.hash.includes('item={ids[1]}')", "with the peek open, the peek follows the cursor")
                self.assertEqual(cdp.js("(document.querySelector('[data-move]') || {}).tagName || 'none'", sid), "none", "View: no Move to button")

    def test_space_does_not_open_a_row_or_card_and_shift_arrows_are_left_alone(self):
        shift = lambda cdp, sid, name, vk: [cdp.call("Input.dispatchKeyEvent", {"type": t, "key": name, "code": name, "windowsVirtualKeyCode": vk, "modifiers": 8}, sid) for t in ("keyDown", "keyUp")]
        for width in (1400, 900):
            with self.subTest(width=width), ie.chrome() as cdp:
                sid = self.open_page(cdp, width, edit=False)
                rows = cdp.js(ROWS, sid)
                cdp.js("document.querySelector('#work tbody tr[data-id]').focus()", sid)
                key(cdp, sid, " ")
                self.assertFalse(cdp.js("location.hash.includes('item=')", sid), "Space does not open a row")
                shift(cdp, sid, "ArrowDown", 40)
                self.assertEqual(cdp.js(FOCUS, sid), rows[0], "Shift+Down does not move the row cursor")
                self.board(cdp, sid)
                cdp.js("document.querySelector('#work-board .bc-main').focus()", sid)
                first = cdp.js("document.activeElement.closest('[data-id]').dataset.id", sid)
                key(cdp, sid, " ")
                self.assertFalse(cdp.js("location.hash.includes('item=')", sid), "Space does not open a card")
                shift(cdp, sid, "ArrowRight", 39)
                self.assertEqual(cdp.js("document.activeElement.closest('[data-id]').dataset.id", sid), first, "Shift+Right does not move the card cursor")
                key(cdp, sid, "Enter")
                self.until(cdp, sid, f"location.hash.includes('item={first}')", "Enter still opens the card")

    def test_the_board_is_one_tab_stop_in_edit_too(self):
        for width in (1400, 900):
            with self.subTest(width=width), ie.chrome() as cdp:
                sid = self.open_page(cdp, width, edit=True)
                self.board(cdp, sid)
                self.assertEqual(cdp.js("document.querySelectorAll('#work-board .bc-main[tabindex=\"0\"]').length", sid), 1, "one tab stop")
                self.assertGreater(cdp.js("document.querySelectorAll('#work-board .bc-main[tabindex=\"-1\"]').length", sid), 2)


if __name__ == "__main__":
    unittest.main()
