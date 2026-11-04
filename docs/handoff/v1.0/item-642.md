# Design note: #642 Help overhaul (v1.0)

Status: design only, written 04-11-2026. Nothing is built. Size of the whole item: XL, split below into steps of S, M and L.

## 1. Goal, in the owner's words
"A comprehensive overhaul of the user help: it has a great UX, is navigable, and includes images and instructions on key complex items, for example adding templates, moving sections, import and export of Excel." By 1.0 a new programme manager must be able to finish the weekly report from Help alone.

## 2. What exists today
- The panel: `src/clark/page/src/help/Help.jsx`. A layer that replaces the open page (`HelpLayer`), with three tabs (Start here, How do I..., Reference), one search box across all three, a contents list per tab (`Contents`), and a scroll-and-flash to a place.
- State and keys: `help/helpStore.js` (`openHelp`, `closeHelp`, `follow`, `goTo`, `installKeys`; "?" opens, "/" searches, Esc clears the search then closes). The last tab is remembered in `localStorage` under `clark.helpTab`.
- The button: `help/HelpButton.jsx`, in the top bar, wired through `edit/index.js` (`EDIT.HelpLayer`, `EDIT.HelpButton`, `EDIT.help`). A published file has no Help.
- Logic with no page: `help/helpLogic.js` (tabs, places such as `howto-add-an-item`, the search index, `resultsView`).
- Small markup: `help/helpText.jsx` (`**bold**`, backticks, `[[Key]]`, `[words](#place)`, `[words](go:screen)`). No images are possible today.
- Words: `help/helpContent.json` (about 2,200 lines: 30 how-to tasks, 34 reference sections, keys, icons). Held entries: `help/helpLater.json` (shown only when the part of clark they describe exists).
- Tests: `tests/test_help_content.py`, `test_help_logic.py`, `test_help_panel.py` (real browser), `test_help_parity.py`, `test_help_shown.py` (checks every bold name, key and screen in shown Help against the page source), `_help_shown.py`.
- The guides the owner named already exist as text: how-to `add-a-section-from-a-template`, `arrange-the-report`, `import-and-export`, `publish-the-report`, `save-as-a-pdf`, `undo-a-mistake`; reference `section-templates`, `excel`, `publishing`, `client-page`. The Edit parts they describe: `edit/AddDialog.jsx` and `logic/templates.js` (Add a section), `edit/Gutter.jsx` (grip, arrows, eye, section menu), `edit/ProfileMenu.jsx` and `edit/ExportBtn.jsx` (Excel out), `edit/Publish.jsx` and `edit/PublishedReports.jsx`, `edit/HandOver.jsx`, `edit/ActivityUndo.jsx`, `edit/Safety.jsx`.
- Gaps: no pictures; the start page lists jobs but with no "what next" links; the contents list scrolls away with the page; no way back other than Back; Help is a layer, so the screen it describes is not visible beside it.
- Screenshots today: `docs/img/*.png` (README pictures) are made by hand; no script retakes them.

## 3. Proposed build (each step is one pull request)
1. **Mockup and sign-off (S).** A static before-and-after mockup of the start page, the contents rail, a guide with numbered steps and pictures, and the search result list. No product code. The owner agrees the structure here, as the item's first done-when requires.
2. **Structure in the data (M).** Extend `helpContent.json` with a `guides` shape: id, title, a one-line job, numbered steps, an optional picture id per step, a `result` line ("what you should see"), and `next` links to other places. Keep how-to tasks as they are; move the six named hard jobs into guides. Update `helpLogic.js` (places, search index, link checks). No visible change yet. Consider one file per guide, as the single file is already large.
3. **Navigation (M).** Start page shows the jobs as large links; a contents rail that stays in view with the current guide marked; "what next" links at the end of each guide; a way back to the previous place beside Back. Keyboard: search, rail and guide reachable by Tab and arrows, at 1400 and 900 px, light and dark. Files: `Help.jsx`, the Help styles (find with `grep -rn "hp-two" src`), `helpStore.js` (a small place history).
4. **Search shows where (S).** Results show the guide, the step and the screen part. Extends `buildIndex` and `resultsView` in `helpLogic.js`.
5. **Picture pipeline (L).** (a) A script under `dev/` that starts clark on the demo data (`dev/demo_data.py`), drives a headless browser through a list of named shots (screen, what to open, what to click, which control to crop to, light or dark), and writes PNG files into a folder inside the program (suggest `src/clark/page/src/help/img/`). (b) `dev/tools/build_page.py` carries them in the page; nothing comes from the internet. (c) `Help.jsx` draws a step's picture with its text description, a caption and a larger view. (d) A test that every picture id in the content has a file and a description. The shots list is the one place naming which screen each picture shows, so a renamed screen fails the retake, not a reader.
6. **Guide: add a section from a template (M).** Add a section box and the template cards.
7. **Guide: move, hide and delete sections (M).** The grip, Alt with the arrows, the eye, the section menu.
8. **Guides: Excel in (M) and Excel out (M),** two pull requests. In: the import page (what is read, what will be added, updated or left, accepting). Out: the workbook's sheets and the cover.
9. **Guide: publishing (M).** Local and To client, the PDF, the Word copy, what the client sees.
10. **Guides the owner names later (S each).** Hand over, saved views, the as-at Dashboard, backups and restore.
11. **Steps name real controls (S).** The test below; do it with step 2 if cheap.

## 4. Tests each step needs
- Step 2: content shape test (every guide has numbered steps, a result line and a next link; every picture id is declared); the link test follows `next` links.
- Step 3: browser test in the style of `test_help_panel.py`: the rail stays in view after scrolling, "what next" opens the right place, Back and the place history work, Tab order reaches search, rail and guide, at 1400 and 900 px, light and dark, no sideways scroll.
- Step 4: logic test that a word in a step finds its guide and shows the step.
- Step 5: pipeline test on a tiny shots list (one shot taken, file exists, text description present); the script refuses a database that is not the demo one; a test that no outside address appears in the built page.
- Guides: every bold control name in a guide must exist on the page. Extend `test_help_shown.py` to read `guides` and check each step's named control against the page source, so a renamed button fails a test.
- No dead link: a test follows every link in every guide.
- Hand check (recorded in the release sheet): a person who has not seen the screens before follows each guide.

## 5. New visible wording needing the owner's sign-off
Not final copy; the owner writes or signs all of it.
- Start page: heading, introduction, and the names of the jobs ("Write this week's report", "Publish to the client", "Bring in my Excel workbook", "Undo a mistake" are the owner's phrasing to confirm).
- Contents rail heading, "what next" heading and link text, the back-a-place label.
- Search result wording for "found in this guide, step N".
- Each guide: title, one-line promise, every step, every "what you should see" line, every picture caption and text description.
- The missing-picture message and the label of the larger-picture control.

## 6. Risks
- Pictures go stale when a screen changes. Mitigation: the retake script and the control-name test; run the script in the release checklist.
- The program grows with pictures. Mitigation: crop to the control, optimise, light and dark only where they differ, agree a budget.
- Pictures must never show a real client, name or brand (`docs/RULES.md`): the script refuses any data that is not the demo data.
- #645 reads the same entries; changing the entry shape in step 2 touches both (see `item-645.md`).
- A later Windows version will want the pictures retaken there; the script must not assume Mac fonts.
- The search index and `test_help_shown.py` read the whole content file: a shape change must keep the held list (`helpLater.json`) working.

## 7. Open questions for the owner
1. Which jobs are on the start page, and in what order? Are steps 6 to 10 the full set for 1.0?
2. Light and dark pictures for every step, or only where the screen differs?
3. Should pictures be marked up (a ring or number on the control), and in which colour?
4. Is a size budget for pictures acceptable (suggest 3 MB in all), or no limit?
5. Help as a layer over the page (today), or beside it, so a person can read a step and see the screen?
6. Who is the "someone who has not seen the screens before" for the check?
7. Keep the three tabs (Start here, How do I..., Reference), or replace them with one contents tree?

## 8. Decided by the owner, 04-11-2026
- Pictures: light only. A size budget of 3 MB in all. Help stays a layer over the page.
- The three tabs stay (Start here, How do I..., Reference), with the contents list that stays in view, "what next" links and the way back, as in section 3.
- The "never seen the screens" check: the owner does it in production, after each guide ships.
- Jobs on the start page, in this order: 2. Add a work item; 3. Write this week's report; 4. Add a section from a template; 5. Move, hide and delete sections; 6. Publish to the client. Bringing in an Excel workbook is not one of the start page jobs (its guides, steps 8 and 9, are still built and sit under How do I...). The other jobs move under How do I...; Undo is a small link beside the jobs.
- Go ahead: build order in README.md, after 0.9.0 is released.
