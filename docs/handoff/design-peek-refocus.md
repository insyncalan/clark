# Design: focus and arrow keys while the peek is open (#246)

Reads: the arrow-keys PR 137 (head 3da0be37), the peek-arrows PR 273 (head 37555132) and the earlier read comments on both. Neither is on main yet; 273 lands first, then 137. No code here.

## 1. Where focus is
- **Opening** moves focus to the peek's Close button, on purpose, so a keyboard user lands inside the panel. The place it came from (row, card or other) is remembered.
- **While open** focus stays wherever the user put it. Only an arrow key steps the peek; a Tab or a click never does.
- **Closing** (Close, Esc, Left on a table row) returns focus to the remembered place. Main does this today.

## 2. What each key does (the rule once both PRs are in)
| Focus on | Up / Down | Left / Right | Esc |
| --- | --- | --- | --- |
| Table row, View | cursor moves, peek follows | Right opens, Left closes | closes; focus on that item's row |
| Table row, Edit | as View | walk the cells (no open or close) | as View |
| Board card | card to card, peek follows | card to card, peek follows | closes; focus on that item's card |
| A peek button (Close, Previous, Next, width, words) | step to the item before or after; focus stays, or goes to Close if the button turns off | nothing | closes; focus on the row or card |
| Box, tab, width edge, menu, dialog, or a modifier key held | the control's own | the control's own | the control's own first |
| The page itself | scrolls | nothing | nothing |

## 3. What each PR already does
- **273 (peek arrows):** one document handler takes only plain Up and Down aimed at a peek button; boxes, tabs, the edge, menus, dialogs and modifiers are left alone. A watcher makes the peek follow a row or card that an arrow key has just focused. Esc puts focus on the shown item's row. A polite status line says the place ("3 of 14, the last one"). Ends do not wrap. Tests: `test_peek_arrows.py` (7).
- **137 (arrow keys):** a shared cursor and one tab stop for the table and the board; Home and End; Right opens and Left closes from a table row; card-to-card arrows with a guard for keys inside a card; Enter on an Edit cell opens its picker; row and card positions for screen readers. The peek handler it first carried was narrowed so it takes no plain arrow while the peek is open (that is 273's job). Tests: `test_list_keys.py`.

## 4. Gaps left
1. **Swimlane order.** `itemIds()` (peek/list.js) groups by column only, so with a swimlane chosen on the board, Up and Down in the peek visit items in a different order from the cards. Previous and Next share this.
2. **Focus return to a row that left the list.** 273 says "back to where it was opened from" but no test covers a filter change, a status change that moves the card, or a collapsed group removing the row. The remembered element may be gone (`isConnected` false), and focus then falls to the page.
3. **Right and Left with the peek open on the board** do card to card; no test pins that the peek follows and does not open or close.
4. **Esc from a peek button on the board** returns to a card; only the table is tested.

## 5. The small build (about 60 lines of source, 5 tests)
1. **One order function.** Add `drawnOrder()` to peek/list.js, grouping by swimlane then column exactly as Board.jsx draws; make `itemIds()` return it, and have Board.jsx's card list use it, so the two cannot drift. Size: about 25 lines.
2. **Focus return fallback.** In Peek.jsx's close effect: if the remembered element is gone, focus the row or card for the shown item (`[data-id]`), else the nearest drawn neighbour from `drawnOrder()`, else the list's own tab stop. Size: about 20 lines.
3. **Tests (in `test_peek_arrows.py`, at 1400 and 900 px):**
   - Down from the last card of a lane lands on the first card of the next lane, and the peek follows.
   - Esc after a filter has removed the item focuses the neighbour, not the page.
   - Esc after the item's group is collapsed does the same.
   - Right and Left on a board card move card to card with the peek open, and do not close it.
   - Esc from a peek button on the board focuses the card.
4. Rebuild pages, check Help counts unchanged (no new key).

Order: after 273 and 137 are on main. No guarded file is touched. Size: small.
