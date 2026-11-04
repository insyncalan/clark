# v1.0 items: design notes and build order

Written 04-11-2026 for the Head. Design only: nothing here is built, and main stays frozen for 0.9.0. Each note lists proposed steps (one pull request each), tests, new wording for the owner's sign-off, risks and open questions.

Open board items with Release "v.1.0" (read from the board's REST list on 04-11-2026): two.

| Item | Title | Size | Note |
|------|-------|------|------|
| #642 | Help overhaul: easy to find your way, with pictures and step-by-step guides for the hard parts | XL (11 steps) | `item-642.md` |
| #645 | Context help: "?" opens a side peek for the page you are on, with a link to the full Help | M to L (6 steps) | `item-645.md` |

## Suggested build order
1. #642 step 1: the mockup, signed by the owner. No other Help work starts before this.
2. #642 step 2: the entry shape (guides, picture ids). This is the one shared set of entries.
3. #645 step 1 (the page key on entries) goes in with #642 step 2 as one shape change.
4. #642 steps 3 and 4 (navigation, search) and #645 steps 2 to 5 (context text, the peek, the key and button, the link). Both touch `help/Help.jsx` and `help/helpStore.js`, so do not build them at the same time on the same files.
5. #642 step 5 (picture pipeline), then the guides (steps 6 to 10) one at a time.
6. #645 step 6 once the owner says whether the peek follows the page.

## Dependencies
- #645 builds with or after #642 step 2: the peek and the full Help read one set of entries.
- #645 step 5 (link to the full Help) needs the places #642 creates; until then it links to today's entries.
- Guides for parts not yet built stay held in `helpLater.json`; `tests/test_help_shown.py` guards this.
- Both wait for 0.9.0 to be released (main is frozen).

## Questions that block the start
See the last section of each note. The ones that decide the first step: #642 questions 1, 5 and 7 (structure) and #645 questions 1 and 3 (how the peek behaves).
