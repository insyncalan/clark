"""#194: the arrow keys on the Work items table and the board.

Run: python3 dev/run_tests.py test_list_keys
Part 1 reads the sources (no J or K key, only arrows and Enter, the cursor is drawn, Help lists the keys). Part 2 drives the committed
page in headless Chrome at 1400 and 900 px with real key events over a real demo store. The browser parts are required: they fail,
never skip, without Chrome.
"""
import time
import unittest
from _editor_checks import for_url

from _paths import ROOT
from _new_page import reload_to_new_page_cdp

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
FOCUS = "((document.activeElement.dataset || {}).id || '')"
CELL_FOCUS = "(((document.activeElement && document.activeElement.dataset) || {}).cell || '')"


class Source(unittest.TestCase):
    def test_no_letter_keys_only_arrows_and_enter(self):
        for name, text in (("listKeys", LIST_KEYS), ("table", WORK), ("board", BOARD)):
            self.assertNotIn('"j"', text.lower(), name)
            self.assertNotIn('"k"', text.lower(), name)

    def test_the_cursor_is_drawn_not_only_coloured(self):
        self.assertIn("table.items tr[data-id]:focus-visible { outline: 2px solid", CSS)
        self.assertIn(".bc-main:focus-visible { outline: 2px solid", CSS)

    def test_help_lists_every_key(self):
        for words in ("Work items table: move the cursor", "Work items board: move from card to card", "[[Enter]] on a cell opens that cell", "[[Right]] and [[Left]] move across the cells of the row", "[[Esc]] closes the open item and returns to the row"):   # #381: the peek keys are in Help too
            self.assertIn(words, HELP)


class Keys(ie.Live):
    def board(self, cdp, sid):
        cdp.js("localStorage.setItem('clark.work.v1', JSON.stringify({TUL: {view: 'board', group: 'status', lane: null, collapsed: []}}))", sid)
        reload_to_new_page_cdp(cdp, sid)
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
                self.assertIn("solid", cdp.js("getComputedStyle(document.activeElement).outlineStyle", sid), "a drawn cursor")

    def test_enter_opens_the_cursor_rows_peek_(self):
        for width in (1400, 900):
            with self.subTest(width=width), ie.chrome() as cdp:
                sid = self.open_page(cdp, width, edit=False)
                rows = cdp.js(ROWS, sid)
                cdp.js("document.querySelector('#work tbody tr[data-id]').focus()", sid)
                key(cdp, sid, "ArrowDown")
                self.assertEqual(cdp.js(FOCUS, sid), rows[1])
                key(cdp, sid, "Enter")
                self.until(cdp, sid, f"location.hash.includes('item={rows[1]}')", "Enter opens the cursor row's peek")

    def test_enter_opens_the_peek_and_the_arrows_never_open_or_close_it_while_the_peek_keeps_its_arrows(self):
        for width in (1400, 900):
            with self.subTest(width=width), ie.chrome() as cdp:
                sid = self.open_page(cdp, width, edit=False)
                rows = cdp.js(ROWS, sid)
                cdp.js("window.__seen = []; window.addEventListener('keydown', (e) => window.__seen.push([e.key, e.defaultPrevented]))", sid)
                cdp.js("document.querySelector('#work tbody tr[data-id]').focus()", sid)
                key(cdp, sid, "Enter")
                self.until(cdp, sid, f"location.hash.includes('item={rows[0]}')", "Enter opens the peek (row 824: Right walks the cells)")
                self.until(cdp, sid, "!!document.activeElement.closest('#peek')", "focus is in the peek")
                # Left and Right with the focus inside the peek are not taken: the peek's tabs and the page keep them. Up and Down are the
                # peek's own (#246, the peek steps to the item before or after in the list it was opened from), so they are taken.
                cdp.js("window.__seen.length = 0", sid)
                for name in ("ArrowLeft", "ArrowRight"):
                    key(cdp, sid, name)
                self.assertEqual(cdp.js("window.__seen.filter(x => x[1]).length", sid), 0, "Left and Right in the peek were not taken")
                self.assertTrue(cdp.js(f"location.hash.includes('item={rows[0]}')", sid), "and the peek stayed on its item, open")
                key(cdp, sid, "ArrowDown")
                self.until(cdp, sid, f"location.hash.includes('item={rows[1]}')", "Down steps the open peek to the next item")
                self.until(cdp, sid, "!!document.activeElement.closest('#peek')", "and the focus stays in the peek")
                key(cdp, sid, "ArrowUp")
                self.until(cdp, sid, f"location.hash.includes('item={rows[0]}')", "Up steps it back")
                self.until(cdp, sid, "!!document.activeElement.closest('#peek')", "and the focus is still in the peek, settled, before it is moved")
                self.assertEqual(cdp.js("window.__seen.filter(x => x[1]).length", sid), 2, "Down and Up in the peek were taken, once each")
                # The peek's own effect (Peek.jsx: after a step the focus goes to Close when it is on the page) runs after the render has been
                # drawn; until it has, blurring to the page lets it take the focus back and the next keys are the peek's. Wait for two frames.
                cdp.js("window.__settled = false; requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(() => { window.__settled = true; }, 0)))", sid)
                self.until(cdp, sid, "window.__settled === true", "the peek has finished reacting to the step")
                cdp.js("document.body.focus(); document.activeElement.blur()", sid)
                cdp.js("window.__seen.length = 0", sid)
                key(cdp, sid, "ArrowLeft")
                key(cdp, sid, "ArrowDown")
                self.assertEqual(cdp.js("window.__seen.filter(x => x[1]).length", sid), 0, "a key aimed at the page is left to the page")
                self.assertTrue(cdp.js("location.hash.includes('item=')", sid), "Left on the page does not close the peek")
                cdp.js("document.querySelector('[data-pk-close]').focus()", sid)
                key(cdp, sid, "Escape")
                self.until(cdp, sid, "!location.hash.includes('item=')", "Esc closes the peek")
                self.until(cdp, sid, f"{FOCUS} === '{rows[0]}'", "focus returns to the row")
                key(cdp, sid, "Enter")
                self.until(cdp, sid, f"location.hash.includes('item={rows[0]}')", "Enter opens it again")
                self.until(cdp, sid, "!!document.activeElement.closest('#peek')", "and the focus has moved into the peek, so it cannot move there after the row is focused")
                cdp.js(f"document.querySelector('#work tr[data-id=\"{rows[0]}\"]').focus()", sid)
                self.until(cdp, sid, f"{FOCUS} === '{rows[0]}'", "the row has the focus before Left is pressed")
                key(cdp, sid, "ArrowLeft")
                self.assertTrue(cdp.js(f"location.hash.includes('item={rows[0]}')", sid), "Left from the row no longer closes the peek (row 824)")

    def test_rows_and_cards_say_their_place_in_the_list(self):
        for width in (1400, 900):
            with self.subTest(width=width), ie.chrome() as cdp:
                sid = self.open_page(cdp, width, edit=False)
                n = len(cdp.js(ROWS, sid))
                places = cdp.js("[...document.querySelectorAll('#work tbody tr[data-id]')].map(r => [r.getAttribute('aria-posinset'), r.getAttribute('aria-setsize')].join('/'))", sid)
                self.assertEqual(places, [f"{i + 1}/{n}" for i in range(n)], "rows: place of size, in the order drawn")
                self.board(cdp, sid)
                cards = cdp.js("[...document.querySelectorAll('#work-board article[data-id]')].map(a => [a.getAttribute('aria-posinset'), a.getAttribute('aria-setsize')].join('/'))", sid)
                self.assertEqual(cards, [f"{i + 1}/{len(cards)}" for i in range(len(cards))], "cards: place of size, in reading order")

    def test_a_key_inside_a_card_is_left_alone(self):
        for width in (1400, 900):
            with self.subTest(width=width), ie.chrome() as cdp:
                sid = self.open_page(cdp, width, edit=False)
                self.board(cdp, sid)
                cdp.js("(() => { const i = document.createElement('input'); i.id = 'probe'; document.querySelector('#work-board .bc-main').appendChild(i); i.focus(); })()", sid)
                for name in ("ArrowRight", "ArrowDown", "End"):
                    key(cdp, sid, name)
                self.assertEqual(cdp.js("document.activeElement.id", sid), "probe", "an arrow on something inside a card does not move the cursor")

    def test_a_key_on_a_child_of_a_row_or_card_never_moves_the_cursor(self):
        # the child is a real button inside the row (or card), the thing a person can focus there; an arrow on it belongs to it
        for width in (1400, 900):
            with self.subTest(width=width), ie.chrome() as cdp:
                sid = self.open_page(cdp, width, edit=False)
                add = "(() => { const b = document.createElement('button'); b.id = 'kid'; b.type = 'button'; %s.appendChild(b); b.focus(); })()"
                cdp.js(add % "document.querySelector('#work tbody tr[data-id]')", sid)
                for name in ("ArrowDown", "ArrowUp", "ArrowRight", "ArrowLeft", "Home", "End", "Enter"):
                    key(cdp, sid, name)
                self.assertEqual(cdp.js("document.activeElement.id", sid), "kid", "a key on a child of a row stays on the child")
                self.assertFalse(cdp.js("location.hash.includes('item=')", sid), "and opens nothing")
                self.board(cdp, sid)
                cdp.js(add % "document.querySelector('#work-board .bc-main')", sid)
                for name in ("ArrowDown", "ArrowUp", "ArrowRight", "ArrowLeft", "Home", "End", "Enter"):
                    key(cdp, sid, name)
                self.assertEqual(cdp.js("document.activeElement.id", sid), "kid", "a key on a child of a card stays on the child")
                self.assertFalse(cdp.js("location.hash.includes('item=')", sid), "and opens nothing")

    def test_the_arrows_on_an_empty_a_one_row_and_a_filtered_list(self):
        for width in (1400, 900):
            with self.subTest(width=width), ie.chrome() as cdp:
                sid = self.open_page(cdp, width, edit=False)
                rows = cdp.js(ROWS, sid)
                filt = lambda f: (cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{self.s.port}/?n={abs(hash(f))}#work&p=TUL&f={f}")}, sid), time.sleep(2.5))   # a fresh load: the filter is read from the address
                filt("mode:open;type:decision;priority:low")
                self.until(cdp, sid, "document.querySelectorAll('#work tbody tr[data-id]').length === 0", "an empty list")
                cdp.js("window.__errs = []; window.addEventListener('error', (e) => window.__errs.push(String(e.message)))", sid)
                for name in ("ArrowDown", "ArrowUp", "Home", "End", "Enter"):
                    key(cdp, sid, name)
                self.assertEqual(cdp.js("window.__errs.length", sid), 0, "keys on an empty list do nothing and raise nothing")
                self.assertFalse(cdp.js("location.hash.includes('item=')", sid))
                filt("mode:open;type:decision")
                self.until(cdp, sid, "document.querySelectorAll('#work tbody tr[data-id]').length === 1", "one row")
                one = cdp.js(ROWS, sid)[0]
                cdp.js("document.querySelector('#work tbody tr[data-id]').focus()", sid)
                for name in ("ArrowDown", "ArrowUp", "Home", "End"):
                    key(cdp, sid, name)
                    self.assertEqual(cdp.js(FOCUS, sid), one, f"{name} on the only row stays on it")
                self.assertEqual(cdp.js("document.querySelectorAll('#work tr[data-id][tabindex=\"0\"]').length", sid), 1, "one tab stop")
                filt("mode:closed;type:risk")
                self.until(cdp, sid, "document.querySelectorAll('#work tbody tr[data-id]').length > 1", "a filtered list")
                shown = cdp.js(ROWS, sid)
                self.assertLess(len(shown), len(rows))
                cdp.js("document.querySelector('#work tbody tr[data-id]').focus()", sid)
                key(cdp, sid, "End")
                self.assertEqual(cdp.js(FOCUS, sid), shown[-1], "End goes to the last row that is drawn, not the last of the unfiltered list")
                key(cdp, sid, "ArrowDown")
                self.assertEqual(cdp.js(FOCUS, sid), shown[-1])

    def test_a_collapsed_board_column_is_skipped_by_the_arrows(self):
        for width in (1400, 900):
            with self.subTest(width=width), ie.chrome() as cdp:
                sid = self.open_page(cdp, width, edit=False)
                self.board(cdp, sid)
                cards = "[...document.querySelectorAll('#work-board .bc-main')].map(c => c.closest('[data-id]').dataset.id)"
                before = cdp.js(cards, sid)
                cdp.js("[...document.querySelectorAll('#work-board [data-toggle]')].find(b => b.closest('.col').querySelector('.bc-main')).click()", sid)
                self.until(cdp, sid, "!!document.querySelector('#work-board .col.shut')", "a column collapsed")
                after = cdp.js(cards, sid)
                self.assertLess(len(after), len(before), "the collapsed column's cards are not drawn")
                cdp.js("document.querySelector('#work-board .bc-main').focus()", sid)
                seen = [cdp.js("document.activeElement.closest('[data-id]').dataset.id", sid)]
                for _ in range(len(after) + 2):
                    key(cdp, sid, "ArrowRight")
                    seen.append(cdp.js("document.activeElement.closest('[data-id]').dataset.id", sid))
                self.assertTrue(set(seen) <= set(after), "the cursor only visits drawn cards")
                self.assertEqual(seen[-1], after[-1], "and stops on the last drawn card")
                self.assertEqual(cdp.js("document.querySelectorAll('#work-board .bc-main[tabindex=\"0\"]').length", sid), 1, "one tab stop")

    def test_the_first_and_last_row_stop_the_peek_steps_and_the_cursor(self):
        for width in (1400, 900):
            with self.subTest(width=width), ie.chrome() as cdp:
                sid = self.open_page(cdp, width, edit=False)
                rows = cdp.js(ROWS, sid)
                cdp.js("document.querySelector('#work tbody tr[data-id]').focus()", sid)
                key(cdp, sid, "ArrowUp")
                self.assertEqual(cdp.js(FOCUS, sid), rows[0], "Up on the first row stays")
                key(cdp, sid, "End")
                self.assertEqual(cdp.js(FOCUS, sid), rows[-1])
                key(cdp, sid, "ArrowDown")
                self.assertEqual(cdp.js(FOCUS, sid), rows[-1], "Down on the last row stays")
                key(cdp, sid, "Enter")
                self.until(cdp, sid, f"location.hash.includes('item={rows[-1]}')", "the last row's peek")
                key(cdp, sid, "ArrowDown")
                self.assertTrue(cdp.js(f"location.hash.includes('item={rows[-1]}')", sid), "Down in the peek on the last item stays on it (no wrap)")

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

    def test_enter_on_every_kind_of_cell_opens_its_picker_and_esc_returns_to_the_cell(self):
        # #381 (#194 Done-when 5): not only the owner cell. Enter is the cell button's own, so the row never turns it into the peek.
        for width in (1400, 900):
            with self.subTest(width=width), ie.chrome() as cdp:
                sid = self.open_page(cdp, width, edit=True)
                first = cdp.js(ROWS, sid)[0]
                for field in ("owner", "due", "priority", "status"):
                    cell = f"{first}:{field}"
                    with self.subTest(field=field):
                        self.until(cdp, sid, f"!!document.querySelector('[data-cell=\"{cell}\"]')", f"the {field} cell")
                        cdp.js(f"document.querySelector('[data-cell=\"{cell}\"]').focus()", sid)
                        key(cdp, sid, "Enter")
                        self.until(cdp, sid, "!!document.querySelector('[data-pop]')", f"Enter on the {field} cell opens its picker")
                        self.assertFalse(cdp.js("location.hash.includes('item=')", sid), "and not the peek")
                        key(cdp, sid, "Escape")
                        self.until(cdp, sid, "!document.querySelector('[data-pop]')", "Esc closes the picker")
                        self.until(cdp, sid, f"{CELL_FOCUS} === '{cell}'", "focus is back on the cell")
                        self.assertFalse(cdp.js("location.hash.includes('item=')", sid), "Esc did not open a peek either")

    def test_arrows_home_and_end_inside_an_open_picker_never_move_the_row_cursor(self):
        # #381 (#194 Done-when 6): nothing steals a key from an open picker; the cursor stays on the row that opened it.
        for width in (1400, 900):
            with self.subTest(width=width), ie.chrome() as cdp:
                sid = self.open_page(cdp, width, edit=True)
                first = cdp.js(ROWS, sid)[0]
                for field in ("owner", "priority"):
                    cell = f"{first}:{field}"
                    with self.subTest(field=field):
                        cdp.js(f"document.querySelector('[data-cell=\"{cell}\"]').focus()", sid)
                        key(cdp, sid, "Enter")
                        self.until(cdp, sid, "!!document.querySelector('[data-pop]')", "the picker is open")
                        for name in ("ArrowDown", "ArrowUp", "ArrowRight", "ArrowLeft", "Home", "End"):
                            key(cdp, sid, name)
                            self.assertTrue(cdp.js("!!document.querySelector('[data-pop]')", sid), f"{name} left the picker open")
                            self.assertTrue(cdp.js("!!(document.activeElement && document.activeElement.closest('[data-pop]'))", sid), f"{name} left the focus in the picker")
                        self.assertFalse(cdp.js("location.hash.includes('item=')", sid), "no peek opened")
                        key(cdp, sid, "Escape")
                        self.until(cdp, sid, f"{CELL_FOCUS} === '{cell}'", "Esc: back on the cell that opened it")
                        self.assertEqual(cdp.js("(document.activeElement.closest('tr[data-id]') || {dataset: {}}).dataset.id", sid), first, "the cursor row never changed")

    def test_up_and_down_on_a_cell_keep_the_column_and_stop_at_the_first_and_last_row(self):
        # #381: Up and Down on a cell go to the same cell one row on; the ends stay; Home and End on a cell are left to the cell.
        for width in (1400, 900):
            with self.subTest(width=width), ie.chrome() as cdp:
                sid = self.open_page(cdp, width, edit=True)
                rows = cdp.js(ROWS, sid)
                cdp.js(f"document.querySelector('[data-cell=\"{rows[0]}:due\"]').focus()", sid)
                key(cdp, sid, "ArrowUp")
                self.assertEqual(self.focused(cdp, sid), f"{rows[0]}:due", "Up on the first row stays on its cell")
                key(cdp, sid, "ArrowDown")
                self.assertEqual(self.focused(cdp, sid), f"{rows[1]}:due", "Down: the same column, the next row")
                for name in ("Home", "End"):
                    key(cdp, sid, name)
                    self.assertEqual(self.focused(cdp, sid), f"{rows[1]}:due", f"{name} on a cell is not the row cursor's")
                cdp.js(f"document.querySelector('[data-cell=\"{rows[-1]}:due\"]').focus()", sid)
                key(cdp, sid, "ArrowDown")
                self.assertEqual(self.focused(cdp, sid), f"{rows[-1]}:due", "Down on the last row stays on its cell")
                self.assertFalse(cdp.js("location.hash.includes('item=')", sid), "no peek opened")

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
                self.assertIn("solid", cdp.js("getComputedStyle(document.activeElement).outlineStyle", sid), "a drawn cursor")
                key(cdp, sid, "Enter")
                self.until(cdp, sid, f"location.hash.includes('item={ids[0]}')", "Enter opens the card's peek")
                self.assertEqual(cdp.js("(document.querySelector('[data-move]') || {}).tagName || 'none'", sid), "BUTTON", "View: the board still has Move to (#442)")

    def test_space_does_not_open_a_row_or_card_and_shift_arrows_are_the_selections(self):
        shift = lambda cdp, sid, name, vk: [cdp.call("Input.dispatchKeyEvent", {"type": t, "key": name, "code": name, "windowsVirtualKeyCode": vk, "modifiers": 8}, sid) for t in ("keyDown", "keyUp")]
        for width in (1400, 900):
            with self.subTest(width=width), ie.chrome() as cdp:
                sid = self.open_page(cdp, width, edit=False)
                rows = cdp.js(ROWS, sid)
                cdp.js("document.querySelector('#work tbody tr[data-id]').focus()", sid)
                key(cdp, sid, " ")
                self.assertFalse(cdp.js("location.hash.includes('item=')", sid), "Space does not open a row")
                shift(cdp, sid, "ArrowDown", 40)
                self.assertEqual(cdp.js(FOCUS, sid), rows[1], "Shift+Down is the selection's: it moves the cursor on, extending the selection")
                self.board(cdp, sid)
                cdp.js("document.querySelector('#work-board .bc-main').focus()", sid)
                first = cdp.js("document.activeElement.closest('[data-id]').dataset.id", sid)
                key(cdp, sid, " ")
                self.assertFalse(cdp.js("location.hash.includes('item=')", sid), "Space does not open a card")
                shift(cdp, sid, "ArrowRight", 39)
                self.assertEqual(cdp.js("document.activeElement.closest('[data-id]').dataset.id", sid), first, "Shift+Right is not an arrow-key move on a card")
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
