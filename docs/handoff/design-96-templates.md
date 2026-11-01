# Design note: #96 Section templates and the Add a section dialog (first slice; guarded changes needed)

First slice: Text, Text and image, Key figures (three and four), RAID cards (three and four), Work items list, Documents and links, Callout, Key dates. The second slice (Headline band, Image gallery, Table, Link preview, Image with caption, Quote, Contacts, Checklist, One document) adds entries to the same catalogue.

## 1. What the store allows today (read from the code)
- `changes.py`: a `new` request takes `values` with `type` and `title` only, plus `after`. `values.type` other than `text` is refused (`ONLY_TEXT`). There is no `body`. A `new` may carry `beside` (#149): the new section becomes the second half of `after`, in the same step.
- `store.py` / `schema.sql`: a section's `type` is one of nine (`current glance usecases milestones text raid actions decisions docs`, a CHECK and `SECTION_TYPES`). Only a text section may have a `body` (`_section_rules`). Only a text section may be deleted (`cancel`). There is no column for what a template holds (figures, a callout's kind, dates, images, the chosen work items).
- Result: **only the plain Text template can be created today.** Every other template in the slice needs the guarded change in section 6.

## 2. The catalogue, as data
Lives in `src/clark/page/src/logic/templates.js` (pure, no DOM, no signals; one list, so the second slice and Help's Section templates (#82) read the same data). One entry:

| field | meaning |
|---|---|
| `id` | stable key (`text`, `text-image`, `figures-3`, `figures-4`, `raid-3`, `raid-4`, `work-items`, `docs-links`, `callout`, `key-dates`) |
| `name` | what the dialog calls it |
| `kind` | one of the kinds: Text and pictures, Figures, Work items, Files and links, People and dates, Notes |
| `fit` | `["full"]`, `["half"]` or both: where it looks right. Half-width ones may be placed beside the section above |
| `description` | one plain sentence |
| `holds` | what it holds, as a short list, shown in the preview |
| `type` | the section type the store will have to accept (section 6) |
| `title` | the starting title (`New section` for Text, which keeps today's wording) |
| `body` | the starting content, `""` until the store has a field for it |

`ACCEPTS` in the same file mirrors what the store takes now (`types: ["text"]`). A template whose `type` is not accepted is **listed and readable but not placeable**: its description, parts and width show as for any template, the arrow keys reach it, a second line says "Coming with a later release.", and Add section stays off (the preview says why). A test sends the real request for such a template to the real route and expects the refusal, so the list cannot drift from the store. When the guarded change lands the owner adds the new types to `ACCEPTS` and that test is replaced.

## 3. The dialog's flow
1. **Open.** `openAddSection(after, opener)` (`edit/addDialog.js`) dispatches the cancelable, bubbling event `clark:add-section` on the document with `detail: { after, opener }`. `after` is the section the new one goes below (`null`: the end); `opener` is the element to give focus back to. #101's gutter "+" and the menu's "Add a section below…" call that function (or dispatch the event) and need nothing else. The dialog host (`edit/AddDialog.jsx`) is mounted once in Edit, beside the Toast, and ignores the event in View.
2. **Choose.** A search box, the kinds (All, Recently used when there is one, then each kind with its count for the current search), the templates as a radio group (name, fit, one-line description), and a preview of the chosen one (description, what it holds, fit).
3. **Place it** (the group's heading; the button is **Add section**, the prototype's word). "On its own row" (default), or "Beside the section above (half width)". Beside names the section (Beside “Summary” (half width)) and is offered only when the template fits half **and** the section above (the one the new one goes below) is on a row of its own (design-95 section 8: beside only a section that is alone). The last section can have a partner. Otherwise it is shown unavailable with the reason in words (the section already shares its row; the template needs the full width).
4. **Do it.** Add section sends the change(s) through `stores/changes.js` (one Undo with the toast), closes the dialog, and gives the new section's title focus, selected (as Add does today). A refusal from clark shows in the toast and focus returns to the opener.

**Placement.** The new section goes below the **row** of the chosen section, not just below that section: if the chosen section is the left half of a pair, inserting after it would pair the new one with it and break the pair. `anchor()` takes the last section of the chosen section's row. If that section is the last one, alone, and carries a stale `beside = 1` (a flag on the last section is ignored by the page), `changes.py` clears it in the same step as the add (#244), or the new section would pair with it.
**Beside the section above:** one request, `{ op: "new", values, after, beside: 1 }` (#149): the new section becomes the **second half of `after`**, clark sets the pairing on `after` in the same step, and one Undo removes the section and the pairing. It is refused for a section that already has a partner. The page offers it only for a section on a row of its own, so `after` is used as it is (not moved to the end of its row), and it works for the last section. A plain add below a last section carrying a stale `beside = 1` is also one request: `new` clears the flag in the same step, so one Undo takes back the section and restores the flag (#244).

**Keyboard and focus.** On open, focus goes to the search box. Tab and Shift+Tab stay inside the dialog (a trap). Esc closes and gives focus back to the opener (or the chosen section's handle if the opener is gone). Down in the search box moves to the chosen template; the arrow keys move between templates (native radios, so the choice follows focus); Enter anywhere in the form places it (when a usable template is chosen). The rest of the page is `inert` while the dialog is open (the Toast stays live). It is `role="dialog"`, `aria-modal`, labelled by its heading; the counts and the preview are announced politely. No text smaller than 13 px; tokens only.

**Recently used.** The last three template ids in this browser's `localStorage` (a per-person convenience, read and written in try/catch; the dialog works without it).

## 4. Plain words
Every string a person reads is in `templates.js` or the dialog. Refusals: "That section already shares its row. Place it on its own row." · "This template needs the full width. Place it on its own row." · "That section isn't in the report any more. Reload the page."

## 5. What is built in this slice (no guarded change)
`logic/templates.js` and its tests; `edit/addDialog.js` (the entry point); `edit/AddDialog.jsx`; `actions.addFromTemplate`; styles in `shell.css`; wiring in `edit/index.js` and `App.jsx`. The existing "Add a text section below" button is left as it is (#101 replaces it).

## 6. Guarded changes needed before the other six templates can be made (STOP: not made here)
1. **`schema.sql` and `store.py` (`SECTION_TYPES`, `_section_rules`, the delete rule at `cancel`).** New section types for the six templates: `textimage`, `figures`, `raidcards`, `workitems`, `doclinks`, `callout`, `keydates` (seven, with `figures` and `raidcards` covering three and four across by their content). Alternatively one type `template` plus a `template` column. The "Only a text section has a body" rule is widened to these types, and they may be deleted like a text section (report sections are exempt from the never-delete rule).
2. **A field for what a template holds.** The existing `body` (a string) can carry it as JSON if the store allows `body` on the new types; otherwise a new `content` column. Needed by the second step of each template (filling it in), and by the starting content.
3. **`changes.py`: `new` accepts any of the new types (remove `ONLY_TEXT`), and `values` gains `body`.** (`beside` in `new` is already there, #149.)
4. **`publish.py` (not guarded):** an empty template stays out of the published page (the issue's "empty templates stay out"). Needs item 2 to know what empty is.

After 1 and 3 the build only adds the types to `ACCEPTS`.

## 7. Tests (what each Done-when line has)
`tests/test_templates.py`: the catalogue (every entry complete, ids unique, kinds known, the first slice present, plain words, no stale `ACCEPTS`), search and kinds and counts, Recently used, `anchor`, `besideState` for each refusal, and the request each template sends (text: the exact `new` request; beside: one `new` with `beside`; a pair's left half; the stale flag, still one request). In the real page with the real routes: open by the event, focus on the search box, the trap, Esc and focus back, a text template placed below and Undo, placed beside a lone section and beside the last section (one request, one Undo, rows right), a refusal when the section above already has a partner, the stale-flag add (one request, one Undo), the plain add and its Undo, an unavailable template cannot be placed and the real route refuses its type, the page behind is inert, and the dialog fits at 1400 and 900 px with text of 13 px or more.

## 8. Which existing section type each template could reuse (decide before the guarded step)
Read from `schema.sql`/`store.py` (types: `current glance usecases milestones text raid actions decisions docs`). Nothing here changes the store.

| Template | Closest existing type | Reuse it? | Why |
|---|---|---|---|
| Text | `text` | Yes, already | Today's only placeable template. |
| Text and image | `text` | No: needs its own | A picture and a caption are content a text section's `body` does not hold. |
| Key figures, three / four | `glance` | Partly | `glance` is the report's one At a glance section, live tiles (#45). A figures section is placed any number of times, mixes live and typed figures and has its own labels, so it needs its own type. |
| RAID cards, three / four | `raid` | No | `raid` lists every RAID item as a table; a card section shows three or four chosen items with a line each. |
| Work items list | `raid`, `actions`, `decisions` | No | Those are fixed to one record type; this one is a saved filter across types. |
| Documents and links | `docs` | Maybe | `docs` shows the project's documents; this one is a list of files and links picked for this report. If `docs` can hold a chosen list, it could be reused; otherwise a new type. |
| Callout | none | New | A short message with a kind (information, decision, warning). |
| Key dates | `milestones` | Maybe | `milestones` shows the project's milestone calendar; Key dates is a short list, typed or taken from milestones. Reuse only if `milestones` can show a chosen few. |

So six or seven need a new type (or one `template` type with a column), as section 6 says; Documents and links and Key dates are the two for the lead to decide. This choice sets the CHECK, the delete rule and what "empty" means for publish.
