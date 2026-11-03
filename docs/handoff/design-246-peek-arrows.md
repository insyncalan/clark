# Design: #246 arrow keys while the peek is open (with #289, the document key handler)

**Status:** the part that does not need PR 137 is built (section 6); the rest is the plan for after 137 merges.

## 1. What the prototype does today
The prototype has no arrow keys on the peek. Stepping is two buttons, Previous and Next, drawn as an up and a down chevron (`system/prototype/peek.js:90`; wired at `peek.js:72-74`, off at the ends). Two things are worth copying:
- **Focus stays where it was.** After a step the focus is kept on the button that had it, and falls back to Close, never to nothing (`peek.js:82-84`).
- **An open picker gets the key first.** The page's one key handler (`core.js:299-300`) hands a key to an open popup (`openPop.el._key`, whose own arrows are at `core.js:135-157`) and returns early for an open dialog, before it looks at `/` (`core.js:303`) or Esc (`core.js:310-317`). A box keeps its own arrows too: Up in the words box recalls the last words (`peek.js:382`).

The prototype has no row arrows either (grep of `system/prototype` finds arrows only on the calendar, pickers, tabs and the use-case list), so the matching prototype work is the same as #194 and #276, and is not part of this note.

## 2. The design in five lines
1. **Up and Down step the peek** to the item before and after in the list it was opened from (filters, order and collapsed groups as drawn; the same list Previous and Next use), whether the focus is on a list row or card (the row's own key moves the cursor and the peek follows it) or on one of the peek's buttons (Close, Previous, Next, width, words).
2. **Focus stays put.** From a peek button it stays on that button, and moves to Close if the button turns off (Next at the last item). From a row it stays on the row. A Tab or a click away never moves the peek: only an arrow key does.
3. **Esc, and Close, put the focus on the row or card of the item the peek is showing**, scrolled into view; if that row is not drawn, back where the peek was opened from.
4. **Right and Left, after PR 137:** Right on a table row in View opens the peek, Left on a table row closes it. On the board they keep moving card to card (#194 item 2), and in Edit they keep moving across the row's cells (#194 item 4), so there the way in is Enter and the way out is Esc.
5. **An arrow in a box, on the width edge, on a tab, with a menu, dialog or the palette open, or with Shift, Ctrl, Cmd or Alt held, is never taken.** Nor is a key aimed at the page itself, so the browser's own scrolling still works.

## 3. Where focus goes, key by key
| Situation | Up / Down | Right / Left | Focus after |
| --- | --- | --- | --- |
| On a table row, peek open | the row cursor moves and the peek follows (PR 137 only adds the board and the shared cursor; the table already moves) | View: Left closes (after 137); Right does nothing, the peek is open | on the new row |
| On a board card, peek open (after 137) | card to card in reading order, the peek follows | card to card, the peek follows; no open or close | on the new card |
| On Close, Previous, Next, width, words button | step to the previous or next item | nothing | stays; Close if the button turned off |
| On the width edge | nothing (the edge keeps Left, Right, Home) | the edge's own (widen, narrow) | stays |
| On a tab (Edit) | nothing | the tabs' own | stays |
| In a box (the words box) | the box's own (caret, history) | the box's own | stays |
| A menu, dialog or the palette is open | nothing from the peek | nothing from the peek | unchanged |
| Esc | not an arrow | not an arrow | row or card of the item shown |

## 4. What is announced
A polite line only a screen reader hears sits in the peek: after a step it says the item and its place ("A-12, 3 of 14"). Opening says nothing extra (the focus move onto Close already names the panel). It is a status line, so it is never read twice for one key.

## 5. The ends, a filter, the board
- **First and last item:** Up at the first and Down at the last do not wrap and do not move the peek; the line says "A-1, 1 of 14, the first one" or "..., the last one". (The table's arrows clamp at the ends the same way.)
- **A filtered list:** the list is the filtered, ordered, uncollapsed one drawn now, so the steps skip what the filter hides. If the item the peek shows has since dropped out of the list (a filter changed), Up and Down do nothing and the line says "A-12 is not in the list now"; Previous and Next are off then too.
- **The board:** the peek's list must be the board's reading order. Today `itemIds()` ignores swimlanes, so with a swimlane chosen the peek's order and the cards' order differ. After 137 the board's drawn order and the peek's list must come from one function, with a test that stepping Down from the last card of a lane lands on the first card of the next.
- **A milestone peek:** Up and Down step through the milestones, as Previous and Next do; the list-follows-cursor rule does not apply (milestone rows are not on the Work items table).

## 6. How the document handler lets arrows through (#289)
The peek's one document key handler (`Peek.jsx`) took only Esc and `/`, so on main no arrow was taken, and nothing broke. Adding Up and Down there is what #289 warned about, so the rule is written as a test, not a hope:
- The handler ignores a key that is already handled (`defaultPrevented`), so a row's own arrow wins, and nothing is stepped twice.
- It takes **only** Up or Down, **only** plain, **only** when the target is a `button` inside the peek that is not in a tab, separator, menu, listbox, dialog or box, and only when no menu, dialog or alert dialog is open anywhere. Everything else falls through untouched.
- Following the cursor is a separate watcher: an arrow key that has just moved the focus onto a row or card shows that item. It reads no key and moves nothing itself, so the row handlers stay as they are.

## 7. Built now, and what waits for PR 137
**Built, on main (`Peek.jsx`, `peek/list.js`, `tests/test_peek_arrows.py`):** points 1 (from the peek's buttons, and from table rows by the follow watcher), 2, 3, 5, the announcement and the ends, and section 6.

**Waits for PR 137** (it changes the same lines of `WorkItems.jsx` and adds the board arrows and `listKeys.js`; touching them now would conflict):
1. Right opens the peek and Left closes it on a table row in View (one line each in the table key handler).
2. The board: the follow watcher already looks for `#work article[data-id]` and `.bc-main`, so card arrows should work with no change; confirm with a test once the board has them, including a card whose child has the focus.
3. One list order for the board and the peek (section 5).
4. Help: one row for Up and Down in the peek, and the counts in the Help tests (137 also adds Help rows, so the two would conflict).
5. The prototype: the same keys, with `peek.js:82-84` as the model for the focus (tracked with #194 and #276).
