# Readiness pass: v0.2 ideas #41 to #45

Written by a teammate, 28-10-2026, for the project lead to paste into the issues. Each item gets a testable Done-when, what it touches and its dependencies (v0.1 items are #28 to #39). Visual checks are at 1400 and 900 px only. The prototype is the reference for screens and behaviour, not for code. **Open** marks a decision still needed before the build.

## #41 Report editor, one editor everywhere, inline editing (XL, Light)
**Recommendation: split into three** before the build, because an XL item can't be reviewed or finished as one.
- **41a:** sections, View and Edit, and moving, hiding and adding text sections. Size M.
- **41b:** one rich editor (toolbar, bubble, `/` menu) used for every rich field. Size L.
- **41c:** inline editing of fields, single click opening the peek, the eye with Undo, the project-record picker, the contents minimap and the sticky bar. Size L.

**Done when:**
- View and Edit modes switch without a reload. In View, nothing on the page can be edited (a browser test tries every field).
- A text section can be added, renamed, moved up or down, and hidden. Each is one step with Undo, and the order and hidden flags are saved in `report_sections`.
- Every rich field uses the same editor component (a test counts editor instances by type). Rich text is saved as clean HTML; a test feeds in script, style, `on*` attributes and `javascript:` links, and checks they are removed.
- Inline edits save at once through `/api/change` and show in the peek's Activity tab.
- The eye hides a row from the published page, is undoable, and the row is missing from the next published file (it uses #39's check).
- The minimap lists every visible section, and clicking one scrolls to it. The sticky bar stays visible at both widths.

**Touches:** page code (`src/clark/page/`), `/api/change` and `/api/undo` on the server, `report_sections`, `report_hidden`.
**Depends on:** #31, #33, #35, #36, #39. A new server route needs #33's "every route is authorised" test to stay green.
**Decided:** the editor is Tiptap 3.31.3 (MIT, released 04-09-2026), vendored from creaite v2.6.9 by #34. It is wrapped as creaite wraps it: a copy of `src/core/editor.js` with `creaiteEditor()` renamed `clarkEditor()`, plus `TextEditor.jsx`, `EditorBar.jsx` and `SlashMenu.jsx`. The test that counts editor instances is a copy of creaite's `test_one_editor_gate.py`. ("editor is full rich editor tiptap, like creaite"; 28-10-2026: "ensure we leverage the tech from creaite e.g. preact etc.")

## #42 Peek and Sneak peek (L, Light)
**Done when:**
- The peek opens on a row in under 150 ms and shows the item's fields and its Activity tab, read from `history`.
- The width can be dragged between set limits and is remembered for each user.
- Sneak peek opens with `//` outside a field, with the sparkle in the peek's top bar, and with the foot line. Esc closes it and returns focus to where it was.
- Typed words are read by plain code with no model call. The result is shown as from → to changes, and Enter or Shift+Enter applies them as one step.
- A toast offers Undo. The changed fields flash, and Undo puts them back.
- A change whose wording came from a source file needs a confirm and never applies on Enter alone (a test fakes a marked reading).
- A browser test covers each opener, apply, Undo and the confirm case.

**Touches:** page code from creaite's `Peek.jsx`, `peek/`, `Toast.jsx`, `sneak.js` and `core/instant.js`; a new `src/clark/sneak.py` (from creaite's `sneak_peek.py`; not guarded); `/api/sneak/read`.
**Depends on:** #31 and #33, plus 41c's change path.
**Decided:** both Enter and Shift+Enter apply ("both"; BRD FR-42).

## #43 Publish To client (M, Light)
Rescoped after the owner's #24, one output: "a single report output managed by the user / editor". To client stays. The guarded copy of creaite's client checks goes, so review drops to Light and the size to M.

**Done when:**
- The Publish dialog shows Local, always on, and To client, unticked every time it opens. To client is disabled until a client folder is set for the project.
- The published file holds only rows with the client flag on that aren't hidden, and no Sensitive row or internal note. Test projects plant one of each, and each is absent from the file. New work items have the flag on by default.
- With To client ticked, the file is copied into the client folder and its SHA-256 there matches the published file.
- A `publications` row records both paths, the time and the SHA-256.
- No route other than the Publish dialog's own can send To client. A test calls every route and finds only one that writes outside the local folder.

**Touches:** `src/clark/publish.py`, `/api/publish`, `publications`, Settings.
**Depends on:** #31, #33 and #39. #24 is decided (one output).
**Review:** Light, one reviewer who isn't the builder. The route test above stays, because To client is the one place clark writes outside its own folders.

## #44 Milestones: timeline, list, slippage, Movement (L, Light)
**Done when:**
- The timeline shows every milestone of the project at its forecast date, or its agreed date if there's no forecast. Zoom changes the date range, and the state colours match #32's six states.
- The rail list shows 5 milestones, then "Show all".
- A slipped milestone shows a marker from its agreed date to its forecast date, labelled with the days of slip, checked against #32's slip function.
- Movement lists each date change from `change_log` in date order, with any linked decision. The internal note is never written into a published file (a test publishes and searches for it).
- The Milestones sheet exports and imports through #37 and #38 with every field, and the round trip changes nothing.

**Touches:** page code, `milestones`, `change_log` reads, the Excel milestones sheet.
**Depends on:** #32, #36, #37 and #38.
**Open:** where the internal note is stored. Recommendation: a new `internal_note` column on `milestones`, left out by the publish build.

## #45 At a glance tiles and the use case summary (M, Light)
**Done when:**
- The health tile spans two tile widths. It shows the pill (clicking it cycles or picks the health, saved at once with Undo) and the multi-line reason edited in place.
- The Overdue actions and High risks and issues tiles count from the data, checked by a test against the demo data. Decisions needed is hidden by default and can be shown, and its hidden flag is saved in `glance_tiles`.
- The use case summary strip shows a count for each status. Each row shows its reference, title, status word and headline, with the status words lined up in one column (measured in a browser at both widths). Clicking a row opens its standing and linked work items in place.
- Both sections appear in the published page in view-only mode.

**Touches:** page code, `projects` (health, reason), `glance_tiles`, `use_cases`.
**Depends on:** #31, #35, #36 and #39.
