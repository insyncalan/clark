# Design note: #645 Context help: "?" opens a side peek for the page you are on

Status: design only, written 04-11-2026. Nothing is built. Size of the whole item: M to L, split below.

## 1. Goal, in the owner's words
"In creaite, when I hit ? on a page I get a peek on the right-hand side with context help, then I can click through to the fuller help. I'd like that here too. Add to 1.0 release."

## 2. What exists today
- "?" and the top-bar button both call `openHelp()` in `src/clark/page/src/help/helpStore.js`, which opens the whole Help panel (`help/Help.jsx`) as a layer in place of the page. It opens on the tab used last, not on the page you were looking at. `help/HelpButton.jsx` is the button; `edit/index.js` wires it (Edit-served pages only; a published file has none).
- Help entries carry a "where": the `w` field in `help/helpContent.json` (for example "Dashboard > Edit"). It is free text for people, not a key a program can match, and many reference sections have none (`top-bar`, `sections`, `work-items`, `milestones-page`, `settings`).
- The right-hand panel pattern: the item peek, `components/Peek.jsx` (opens beside the list, width dragged from the left edge, Esc and Close through `closePeek()`, slide-out in `peek/exit.js`, width in `stores/peekState.js`). The ask clark panel (`edit/AskPanel.jsx`, `edit/askPanelState.js`) is a second right-hand panel with its own focus handling. All three must share the right edge without fighting.
- The current screen is `view` (and `mode`, `project`) in `stores/report.js`; `helpStore.js` already watches it and closes Help when it changes.
- Focus return: `helpStore.js` already records where focus was (`opener`, `locate`, `giveFocusBack`); the peek can reuse it.
- Key rules: `installKeys` in `helpStore.js` ignores "?" inside a field, a dialog or a menu.
- Tests: `tests/test_help_panel.py` (real browser), `test_help_shown.py`, `test_help_logic.py`.

## 3. Proposed build (each step is one pull request)
Dependency: build with or after #642 step 2, so the peek and the full Help share one set of entries (see `README.md`).
1. **A page key on entries (S).** Add an optional `page` list to entries in `helpContent.json` naming the screens they belong to (`dashboard`, `dashboard+edit`, `work`, `milestones`, `settings`, and a settings card where useful). Add `contextFor(page)` to `helpLogic.js`. Held entries (`helpLater.json`) stay held: the peek must not describe a part that is not built.
2. **Short context text (M, wording needs sign-off).** A `context` field for each of the five screens: two to five short lines, plain words, for that screen only, plus the id of the matching place in the full Help.
3. **The peek panel (L).** New `help/HelpPeek.jsx` and state in `helpStore.js` (open or not, the page it was opened on). A right-hand panel in the style of the item peek: a heading, the context lines, and at the foot a link to the full Help. Focus moves into it on open and returns to where it was on close. Esc and Close close it and leave the page as it was. One right-hand panel at a time (open question 3). None in a published file.
4. **Wire "?" and the button (S).** "?" and the button open the peek. The full Help is reached from the peek's link, from the profile menu's Help entry (open question 5) and from `window.clarkPage.help.open(where)` (unchanged, so existing callers and tests still work).
5. **Link to the full Help (S).** The foot link opens `Help.jsx` on the matching entry (`placeOf`, `follow`); Back returns to the page with the peek closed.
6. **Follow or stay (S, after the owner answers question 1).** Either the peek re-reads `view` and updates as you move between pages, or it stays on the page where it was opened and closes on a page change (today's rule for Help).

## 4. Tests each step needs
- Step 1: logic tests (every live screen has context entries; every `page` value is a real screen, same list as `LIVE_SCREENS` in `helpStore.js`; an unknown page falls back to the start of full Help).
- Step 2: content tests (length limit, bold control names exist on the page, in the style of `test_help_shown.py`).
- Step 3: browser tests: opens beside the page without covering the control focused before; focus goes in and returns; Esc and Close close it; fits at 900 px; both themes; absent in a published file; opening the item peek or ask clark closes it.
- Step 4: "?" outside a field opens the peek, in a field, dialog or menu it does not; the button does the same; `help.open("howto-...")` still opens the full panel.
- Step 5: the link lands on the right entry and flashes it; Back returns to the same page and scroll position.
- Step 6: per the answer; moving pages either updates or closes, never shows the wrong page's help.
- Screen reader check: the peek has a name as a region, and a change of page is announced politely.

## 5. New visible wording needing the owner's sign-off
Not final copy.
- The peek heading (with the page name).
- The context text for Dashboard (View and Edit), Work items, Milestones, Settings and its cards, Publications.
- The foot link to the full Help and the Close label.
- The line shown for a page with no context text.
- The accessible name of the region.

## 6. Risks
- Two sets of entries drifting apart: the reason for the dependency on #642.
- Three panels on the right (item peek, ask clark, Help peek): needs one rule and a test.
- "?" is also the search shortcut inside full Help; the new behaviour must not break `installKeys`.
- At 900 px a peek may cover most of the page; follow the item peek's width rules in `stores/peekState.js`.
- `w` is free text, so it cannot drive the link; step 1 adds a real key instead of parsing it.
- Today Help closes on any page change; the new rule must be written down and tested so a peek never shows stale help.

## 7. Open questions for the owner
1. (From the item) Does the peek follow the page as you move between pages while it is open, or stay on the page where you opened it?
2. (From the item) Does the peek ever show a picture, or text only, with pictures only in the full Help?
3. If an item peek or ask clark is open and you press "?", should the Help peek replace it, sit beside it, or wait?
4. Does a second "?" close the peek, or move focus to its link?
5. Should the profile menu's Help entry open the peek or the full Help?
6. Which settings cards get their own context text, or one text for Settings as a whole?

## 8. Decided by the owner, 04-11-2026
- The peek opens on a page that has help context, and every page has help context (so "?" always opens the peek; the full Help opens from its link and from the profile menu's Help entry). It closes on a click outside it, Esc, or leaving the page. Text only, no pictures.
- Pressing "?" replaces whatever peek is open (the item peek or ask clark). A second "?", Esc, a click outside or leaving the page closes it.
- Settings: one text for the whole page with a short line per card and a link to the full Help.
- Consequence for the build: step 1 (page key) must cover every screen, including Publications and Settings cards, and a test fails if any screen has no context text.
