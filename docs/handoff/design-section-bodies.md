# Design note: a section that carries content (one note for #121, #189 and #48)

Three items are blocked by one gap: the store cannot hold what a template section contains. This note gives the facts, the choices, a recommended default for each, the exact files and the tests. It changes no code.

- **#121** Needs from you (a list of rows: what is needed, from whom, by when).
- **#189** Progress tracker (groups of lines with typed numbers, an overall bar).
- **#48** Word report export and import (its store step adds a migration, and so competes for the same version number).

Read against `origin/main` at `d9b38cbf`. The files named below are identical on the #96 branch (`0bc01081`), checked by diff, so nothing here depends on that branch landing first. Line numbers are approximate; names are exact.

## 0. The three decisions for the lead

| # | Decision | Choices | Recommended default |
|---|---|---|---|
| 1 | How a section holds its content | A one type per template, JSON in the existing `body` column. B one `template` type plus a template id. C side tables. D JSON hidden inside a text section. | **A.** Two new types now (`needs`, `tracker`), each with its own checker, content as JSON in `body`. D is refused. Take B instead if four or more further typed templates are expected within one release (section 3). |
| 2 | Migration order and numbers | (a) section bodies first. (b) Word first. (c) one combined step. (d) no migration for section bodies. | **Number by landing order, one separate step per item, no combined step.** Whichever of section bodies and Word is merged first takes the next free number; the other renumbers at its merge. The ruled numbers (#120 = 3, #115 = 4, Word = 5) cannot hold while #120 is held, because the runner refuses a gap. |
| 3 | How the shared work lands | One shared base item first, then #121, #189 and the #48 store step on top. Or each item carries its own guarded change. | **One shared base item** (types, body write, checker, migration, publish branch, History redaction), read once by two non-builders. #121 and #189 then add only a page component, a publish table and tests. `ONLY_TEXT` is removed once, in the base. |

Smaller defaults, if not overruled: Excel and Word exports do not carry either template in the first slice (they leave them out, section 8); each save replaces the whole body in one step; text limits are in sections 6 and 7; numbers are stored as whole tenths.

## 1. The shared root cause (read from the code)

| Fact | Where |
|---|---|
| A new section takes `type` and `title` only. A type other than `text` is refused with `ONLY_TEXT`. `_add` always makes `type: "text"`. | `changes.py`: `CHANGE_KINDS["report_sections"]`, `ONLY_TEXT`, the `op == NEW` branch of `_do_change`, `_add` |
| A section update takes `title`, `hidden`, `beside` only. There is no request that writes a body. | `changes.py` `CHANGE_KINDS`; `_checked_changes` |
| A reply never carries a body. | `changes.py` `SHOWN` |
| The page writes no body either: `RICH_WRITES = {}`. | `page/src/edit/richSave.js` |
| `type` is one of nine, in three places that must agree. | `schema.sql` (a CHECK), `store.py` `SECTION_TYPES` and `ALLOWED` |
| Only a text section may have a body. Only a text section may be deleted. | `store.py` `_section_rules`; `delete_row` |
| The store already reads `body` for the page. | `store.py` (two `SELECT id, type, title, body, ...` reads) |
| Publish keeps a section only if its type is in publish's own `SECTION_TYPES`, and passes a text body through `clean_html`. | `publish.py` `SECTION_TYPES`, `select()` |
| A new type in the live page shows "Not shown on this page yet", and in a published file it is not drawn at all. | `Section.jsx`; `Dashboard.jsx` `fileDraws` |
| Excel and Word leave out a type they do not know. | `excel_cover.py` (only current, glance, text); `docx_build.py` `TITLES`, `sections()` |
| A CHECK cannot be changed in SQLite, so a new type means making `report_sections` again. | `schema.sql`, `schema_v2.sql` |

The #96 note (section 6) lists the same gap for six more templates. No branch has landed it.

## 2. What the migration runner does today (`store.py`)

- `SCHEMA_VERSION = 2`, `MIGRATIONS = ((2, migrate_to_2),)`.
- `migration_plan` refuses a table with a gap or a wrong end, and refuses a file newer than clark knows.
- `open_store` checks the plan first (a refused plan takes no copy), then takes **one** safety copy (`backup.make(..., "migrate")`) before the first step, then runs every step in **one** `BEGIN IMMEDIATE`. If the copy cannot be made the update is refused in plain words and nothing changes.
- `migrate` switches foreign keys off, runs the steps, writes the version after each, then refuses and rolls back if any **new** foreign-key violation appeared. An error rolls everything back. Foreign keys go back on, also after a failure.
- A step must be idempotent and must not read the live `schema.sql`. `migrate_to_2` reads the frozen `schema_v2.sql`; the #48 branch keeps its frozen text in a constant (`ITEM_EVENTS_V3`) with a test that pins it to what `schema.sql` makes today.
- A migrated file cannot be opened by an older clark (it is refused: "made by a newer clark").

What a rebuild of `report_sections` touches, checked in `schema.sql`:

| Thing | State |
|---|---|
| Rows | at most 100 per project (`MAX_SECTIONS`) |
| Foreign keys out | one: `project` references `projects(code)` with `ON DELETE CASCADE` |
| Foreign keys in | none (nothing references `report_sections`) |
| Triggers, indexes | none on this table |
| Autoincrement | none (the key is `project, id`) |
| `change_log` link | by text key only (`CODE-S-001`), no foreign key |

So this rebuild is smaller and simpler than the `item_events` rebuild already done in `migrate_to_2` (tens of thousands of rows, an autoincrement, a self reference, two indexes).

## 3. Decision 1: how a section holds its content

| Option | What it is | Guarded files it changes | Verdict |
|---|---|---|---|
| **A** one type per template | `needs` and `tracker` join the type list. Content is JSON in `body`. One checker per type. | `schema.sql`, `store.py`, `changes.py`, `history.py` | **Recommended.** |
| **B** one `template` type | One new type `template`, plus a `template` column (the id, never in an update list) and JSON in `body`. A checker per template id. | the same four, plus one more column in the rebuild | Pick this if four or more more types are coming soon: it needs one rebuild ever. |
| **C** side tables | A section stays type `text` with an empty body; rows live in new tables. | the same four plus new tables, keys, `TABLES`, `ROW_RULES`, Undo rules, a new change kind per operation, publish reads | Not recommended: largest change, and it still needs a migration (an existing file never re-runs `schema.sql`, so a new table also needs a step). |
| **D** JSON inside a text body | A marker in the text body says "this is a list". | none of the type list, but the body write opens for text | **Refused.** See the list below. |

Why not D (verified):
- Publish passes a text body through `clean_html` (`publish.py`, `select()`), which would drop or rewrite JSON.
- The Excel Cover prints a text body as plain lines (`excel_cover.py`, the `text` branch), so a hidden tracker would appear as raw JSON in a client-facing sheet.
- A plain text edit (the rich editor, once #188 lets it write) could overwrite the marker, or turn a text section into a list, with no checker in the way.
- The History view would show the JSON as "Text".

Why A over B for now: every place that decides what to do with a section already switches on `type` (publish, Word, Excel, the page's `data-type`, the minimap). With A each new template is one more case in those places. With B each place needs a second lookup on the template id. A also keeps the database's own list of allowed types as a second wall behind the Python rules. The price of A is one small rebuild step for each batch of new types. B pays that once. The break-even is about the third further typed template; the #96 catalogue names six more, so the lead may prefer B. If B is chosen, everything else in this note still holds: replace "type" with "type `template` and its `template` column" in sections 5 to 7.

A variant of A (call it A2): in the one rebuild, replace the list CHECK by a shape check (lower-case letters only, short) and rely on `SECTION_TYPES` in Python. One rebuild ever, dispatch by type kept, but the database stops being a second wall. Not recommended, because the attacker-style reader loses a check for no code saved.

### What A needs, file by file (the shared base)

| File | Change |
|---|---|
| `src/clark/schema.sql` | add `'needs'` and `'tracker'` to the `report_sections.type` CHECK (new databases). |
| `src/clark/store.py` | add both to `SECTION_TYPES`. `_section_rules`: a body is allowed for `text`, `needs`, `tracker`; for the two new types it is passed to the checker and the **canonical** result is stored, never the request's text. A new section of these types gets its starting body from the store (empty list or empty tracker), never from the request. `delete_row`: `needs` and `tracker` may be deleted like a text section (added by hand, so they may go). New frozen constant for the version's `report_sections` text, `migrate_to_N`, a `MIGRATIONS` entry, `SCHEMA_VERSION` + 1. |
| `src/clark/section_bodies.py` (new, not guarded, pure) | `check(type, body)`: parse, limit, return the canonical JSON text or raise `Invalid` in plain words that never quote the value. One function per type. |
| `src/clark/changes.py` | remove `ONLY_TEXT`; `new` accepts `text`, `needs`, `tracker` (an allow-list, never the request's spelling); `_add` makes the type it is given. `update` gains `body`, **only** for `needs` and `tracker` (a text body write stays closed until its own item, #188, opens it). The type is read inside the step, so the body is checked against the stored section's type. `SHOWN` unchanged. |
| `src/clark/history.py` | never show a section body's before and after; say "Changed" with the field called "Content". Also skip `body` in `_unpack` (a removed section's row). |
| `src/clark/publish.py` (not guarded) | see section 5. |
| page (not guarded) | see sections 6 and 7. |

Not changed: `server.py`, `__main__.py`, `excel.py`, `excel_import.py`, `excel_cover.py`, `docx_build.py`, `word_import.py`. `/api/change` and `/api/undo` are used as they are.

`_section_rules` runs on every write, including an Undo that puts a section or a body back (`_merged_row` calls the row rules, and `revert` only skips one project rule). So the checker is also the last wall for a body that comes back from `change_log`. Cost: if a later release makes a limit stricter, an Undo of an old body that is now over the limit is refused in plain words instead of restoring it. That is the safe side.

### Tests the base needs

- `tests/test_store_migration.py` style (see section 4 for the migration ones).
- `tests/test_changes.py` style: `new` of `needs` and of `tracker` works and makes the empty body; `new` of any other type is still refused; a body in a `new` request is refused; `update` of `body` on a text section is refused; on a `needs` and a `tracker` section it works as one step; an update that changes nothing makes no step and no Undo; `type` is still not changeable (`KEEPS_TYPE`); `CHANGE_KINDS` fields are all real columns (the existing test).
- `tests/test_store_*.py`: `_section_rules` refuses a body on a type that may not have one; refuses an over-limit, wrong-shape or hostile body (list in section 9); delete of a `needs` and a `tracker` works, of a `raid` section still refuses; Undo of that delete puts it back and re-checks the body.
- History tests: a body change and a removed row show no body text, for a needs, a tracker and a text section.
- A "never in the reply" test: the reply to a `new` and to an `update` has no body, in any field.

## 4. Decision 2: migration order and numbers

Facts:
- The runner refuses a gap, so a step's number is fixed by **what has landed**, not by the item. If #120 (held) is not on main, nothing can be 5, and Word cannot be 5.
- On the #48 Word branch the step is written as version 3 (`migrate_to_3`). It rebuilds `item_events` so that its route CHECK takes `'word'`. It touches no other table. The branch's own comment says to renumber it at merge.
- The #120 branch also writes its step as 3 (it rebuilds `publications`). The #115 note says "the next free number at merge".
- Section bodies rebuild `report_sections`. No two of these steps touch the same table, so they do not conflict in what they do, only in the number and in `schema.sql`/`store.py` text.
- The safety copy is one per open, not one per step, so two steps cost no extra copy and no extra transaction.
- No released clark is at version 3 (main is 2), so numbering by landing order breaks no file in the field.

| Order | What it means | Cost | Risk |
|---|---|---|---|
| **(a)** section bodies = 3, Word = 4 (or next free), #120 and #115 after | the base lands first because three items wait on it | Word renumbers one line and its test. #120 and #115 renumber later. | none new |
| **(b)** Word = 3, section bodies = 4 | Word's migration is already written | the base renumbers one line | none new |
| **(c)** one combined step | one number, two rebuilds in one function | couples two items: neither can land alone; one reader must read both rebuilds | a fault in either blocks both; harder to bisect |
| **(d)** no migration for section bodies | D (refused) or a text-only marker | saves a number | the safety problems in section 3; not safe |

Recommended: **number by landing order; one step per item; no combined step.** Section bodies and Word are independent, so either of (a) and (b) is correct and the lead need only say which merges first. Reason to expect the base first: #121, #189 and the six other #96 templates all wait on it, while Word's remaining work is its own writer.

### What each rebuild costs in safety (answer for the readers)

| Thing | Effect of the `report_sections` rebuild |
|---|---|
| Safety copy | one copy before the first step, by the existing runner. If it cannot be made, the open is refused with nothing changed. The copy is the only way back after a good migration, because an older clark will not open the new file. |
| Failure path | any error in the step rolls back every step and the version. A foreign-key problem **new** after the rebuild also rolls back. The message is plain and never shows SQLite's own words. A failed step leaves the safety copy on disk. |
| Triggers and foreign keys | none on the table; the one outgoing key is kept; the runner's before and after violation count covers it. |
| Undo of old steps | `change_log` names sections by text key and stores a type as text. Old steps (a section made, hidden, moved, deleted) undo the same way after the rebuild, because the new CHECK is a superset of the old. Test: make steps on a version-N file, migrate, undo them. |
| Published file | unchanged for old sections. A new type appears only after the publish branch is built. |
| Excel export and import | no change to either; section types are not in the Excel import. The Cover leaves a new type out until it is taught (section 8). |
| Help words | no change in the base. Main's Help already has a "Section templates" topic (`page/src/help/helpContent.json`) and a `helpLater.json` list. #121 and #189 each add their own entry there, in plain words, and the Help tests (`test_help_content.py`) must still pass. |
| Dev databases | a file migrated by a **different** branch's step 3 reports version 3 but lacks this step. The runner will not run it, and the first write of a new type fails on the CHECK. Say so to the team: use a fresh or restored copy when switching branches. The failure is a plain refusal, not a crash (a database `IntegrityError` already maps to plain words). |
| Restoring an old backup | `check_copy` accepts any version from 1 to current; the next open migrates again. A body made after the migration is not in the older copy (expected). |

Frozen text rule: put the rebuilt table's `CREATE TABLE` in a constant next to the step, as the Word branch does, and pin it with a test to what `schema.sql` makes today.

### Migration tests

1. A file at the version before this step, with sections of every kind (hidden, beside, a text body with HTML, a deleted-and-undone one), migrates: same rows in the same order, nothing lost, version up by one, foreign keys on afterwards.
2. The new CHECK accepts `needs` and `tracker` and still refuses an unknown type, from a migrated file **and** from a new database.
3. A migrated file and a new database have the same columns and the same CHECK text for `report_sections`.
4. A second open changes nothing and takes no copy.
5. A failing step (patched) leaves the file as it was: version, rows and foreign-key setting.
6. A safety copy exists before the step, opens, and holds the old version. A failed copy refuses the open and changes nothing.
7. Two windows opening one old file migrate once.
8. Steps made before the migration are undone after it (section made, deleted, hidden, moved).
9. The frozen text equals what `schema.sql` creates (pin test).
10. The table-order test still passes with the new number: runs from 2 with no gap, ends at `SCHEMA_VERSION`.

## 5. The published file, for both templates

Today `select()` copies only `id`, `type`, `title`, `beside` for a section, and `body` for text only. For `needs` and `tracker`:

- add the type to `SECTION_TYPES` in `publish.py`;
- re-run `section_bodies.check` on the stored body at publish time (never trust what is stored); if it fails, leave the section out;
- publish **fields picked by name** from the checked structure: for needs, the shown rows (`what`, `kind`, `from`, `by` as DD-MM-YYYY); for the tracker, the checked groups and lines. Rows with `hidden` set are left out. A section with nothing left to show is left out ("empty templates stay out");
- never pass any of it through `clean_html`; it is plain text, never markup;
- the page draws every value as text (Preact text nodes). **No** `dangerouslySetInnerHTML` in the two new components. The data block already escapes `<`, `>`, `&` and U+2028/9 (`data_block`), and the file has a content policy (`csp_meta`), so this is a second wall, not the only one;
- the page's own `fileDraws` in `Dashboard.jsx` gets a case for each type (drawn only when it has something to show), and `Section.jsx` gets a branch before the "Not shown on this page yet" line.

## 6. What #121 (Needs from you) adds on top of the base

**Stored content** (JSON text in `body`, canonical: sorted keys, no spaces, ASCII escapes):

```
{"v":1,"rows":[
  {"what":"Confirm the supplier list","kind":"information","from":"Client finance team","by":"<a real date>","hidden":0},
  {"what":"Choose the pilot site","kind":"decision","from":"Steering group","by":"","hidden":0}
]}
```

`kind` is `decision`, `information` or `date`. `by` is empty or a real date, stored as `YYYY-MM-DD`, shown as `DD-MM-YYYY`. `hidden` is 0 or 1 (the item's "hidden rows are absent"). Rows have no ids; the list order is the order.

**Limits (proposed, for the build to confirm):** at most 100 rows; `what` 1 to 300 characters; `from` at most 100; the whole body at most 64 KB; no keys other than these; year 2000 to 2100; no control, format (bidi, zero-width), private-use or surrogate characters, and `what` needs one visible character (the same character rules as `section_title`, reused, not copied).

**Page:** `NeedsFromYou.jsx` and a pure `logic/needs.js`; the entry in `logic/templates.js` (from #96) with `ACCEPTS.types` gaining `needs`. In Edit: an add-row line and a pencil on each row; each committed row save is one `change()` (one step, one Undo). In View and the published file: the same table, view only. Words: "Needs from you", "What is needed", "From", "By", "Nothing needed from you yet." (empty, Edit only).

**Not in this item:** live lines from pending decisions; Excel or Word carrying the rows.

**Tests:** checker unit tests (valid, every limit at and over, every wrong type, unknown key, wrong `kind`, bad date, duplicate keys); one step and one Undo for add, edit, hide, reorder and remove; a hidden row and a hidden section absent from View and the published file; an empty list absent from the file; the published data holds only the named fields; a planted marker in a `what`, `from` and `by` is escaped in the file and never in an attribute; the plain-words test reads every new string and fails on jargon (RAID, template, JSON, schema, id) or a sentence starting with the product name; browser checks at 1400 and 900 px, light and dark.

## 7. What #189 (Progress tracker) adds on top of the base

**Stored content:**

```
{"v":1,
 "overall":{"actual":null,"planned":null,"health":"","note":""},
 "columns":{"tasks":false,"agents":false,"workflows":false},
 "groups":[{"name":"Build","lines":[
   {"no":"1","text":"Set up the test site","start":"<a real date>","end":"<a real date>",
    "status":"planned|inprogress|completed|late","weight":100,"planned":1000,"achieved":800,
    "tasks":null,"agents":null,"workflows":null}]}]}
```

Totals, the overall figures, "n points behind plan" and "Weights add up to n%" are **worked out by the page** (a pure function, `logic/tracker.js`) and never stored, so they cannot disagree with the lines. Publish works out the same figures from the checked lines, with the same function if the build can share it, otherwise with a tested copy.

**Numbers are whole tenths** (`625` shows as 62.5%). Reason: sums of decimals drift (0.1 + 0.2) and a total that does not match its lines is the very thing the item forbids. The page converts when it reads and writes. This is a build choice the item did not state; the readers should say yes or no.

**Limits (proposed):** at most 20 groups; 100 lines per group; 500 lines in all; group name at most 80; line text at most 200; `no` at most 10; note at most 200; `status` one of four, `health` one of three or empty; tenths 0 to 1000; counts whole 0 to 99999 or null; dates real, and `end` not before `start`; the whole body at most 256 KB; same character rules as the other text. An over-limit says which limit, never the value.

**Open point to settle in the build (not in the item):** what `planned` and `achieved` mean. If they are percentages of each line, a total row that sums them can pass 100. If they are points of the whole, a line cannot exceed its weight and the checker can say so. The item's "Percentages accept 0 to 100" and "overall is the sum of the group totals" only fit together under one reading. The build note must state the reading and the checker must enforce it.

**Page:** `Tracker.jsx`, `logic/tracker.js`, styles in `shell.css`, the `logic/templates.js` entry with Full and Half, and `ACCEPTS.types` gaining `tracker`. Add, remove and reorder of lines and groups, typed values and a status pick; each committed edit is one `change()`. Behind-plan lines show "▼ n" and a hidden label for screen readers; colour is never the only signal. At 900 px the Full table drops the date and count columns.

**Tests:** as section 6, plus: totals and overall against fictional demo data; a group with no lines shows 0% and "No lines yet"; the behind-plan flag and its screen-reader words; every refusal leaves nothing written; the published page has no controls and no empty tracker; a landscape print check; weights not adding to 100 say so quietly.

## 8. What changes for #48 (Word)

- Its store step is renumbered at merge (section 4). Nothing else in its design changes.
- Word and Excel **silently leave out** `needs` and `tracker` sections (`docx_build.sections()` filters by `TITLES`; `excel_cover.py` only handles current, glance, text). That is safe, but it means a client who gets the Word file does not see "Needs from you". The Word issue lists published rows and sections in order, so the lead should decide whether "Needs from you" is added to `TITLES` in the Word build before or after the base. **Default: after.** #189 already says its exports come after the Excel Cover work.
- If a section type is added to the exports later, its text goes through the same Excel text guard (`escape_text`, which blocks a leading `=`, `+`, `-`, `@`) and the same Word text escape. A name or a note must never reach a cell un-escaped.
- `word_import.py` stages only new actions, risks, issues and decisions. It never writes a section, so Word import cannot reach a section body.

## 9. Undo, the reply and the log

- **One step, one Undo.** A save replaces the whole body in one `update`, so it is one `applies` row and one Undo. The page saves a committed row or cell, not each key press. `UNDOABLE["report_sections"]` is `None` (any field), so `body` is already covered.
- **No-op saves are free.** The stored text is canonical, so saving the same content changes nothing and makes no step.
- **Undo words** say "section" or its title and never repeat any content (as milestone Undo words already do for a reason or a client message).
- **The reply never carries a body** (`SHOWN`). After a change the page reads the project again (`readAgain` in `stores/changes.js`, the #188 fix is on main), so the next save starts from what is stored.
- **`change_log` must hold the whole old and new body**, because that is how Undo works. So it is the one place the content lives besides the table. It is local, it is never published, and History must not show it (section 3, `history.py`). It is also copied in backups.
- **The daily log** (`log.py`) holds no content by rule: a free-text detail becomes `<text, N characters>`. The change route logs a fixed message, the route and a status. A test passes a body full of markers through `change` and `undo` and scans the day's log file for them.
- **Refusals** name the field and the limit ("A line can be at most 200 characters.") and never quote the value.
- **Two windows:** the last save wins. The page reads again after each save, which covers one window. Optional hardening (cheap, recommended if the readers want it): the update carries the hash of the body the page read, and a changed body is refused with "This list changed in another window. Reload the page." Not in the default.

## 10. What the guarded-file readers must check (attacker-style)

| What could go wrong | Where to look | Test that would catch it |
|---|---|---|
| Script or markup in a `what`, `from`, `text`, `name` or `note` reaches the published page | `select()`, the two components | plant `<script>`, `"><img onerror=...>`, `</script>` and `javascript:` in every text field; publish; scan the file for each marker outside the escaped data block; assert the component source has no `dangerouslySetInnerHTML` |
| A body breaks out of the data block | `data_block` | plant `</script><script>x`, U+2028, U+2029; assert the block still parses as one JSON value and the file has one script block |
| A text body is turned into a list or a list into text | `changes.py` `update`, `_section_rules` | send `body` on a text section: refused; send a `needs` body to a `tracker` section: refused by the type's own checker; `type` in an update: refused |
| Hostile JSON: very deep nesting, huge numbers, `NaN`, `Infinity`, duplicate keys, a lone surrogate, a very long string, a number with thousands of digits, a wrong type for every field, unknown keys, a list where a string belongs, `true` where a whole number belongs | `section_bodies.check` | one test per case; each refuses in plain words, writes nothing and costs under a second. Needs: size checked **before** parsing; `parse_constant` refuses `NaN` and `Infinity`; duplicate keys refused by `object_pairs_hook`; `parse_int` refuses an over-long integer (Python 3.9 parses a huge integer slowly); `RecursionError` caught and refused; booleans refused where a number is wanted (`type(x) is int`); the string is checked for a lone surrogate by encoding it |
| A bidi override or zero-width character makes a name look like another (spoofing) | the text rules | plant U+202E, U+200B, U+2800 in `from` and `what`: refused |
| A date that is not a date (`31-02`, year 0, year 99999, text) reaches the file | `check` | one test per bad date; assert the file holds only `DD-MM-YYYY` |
| Hidden rows or hidden sections leak into the file | `select()` | plant a marker in a hidden row and a hidden section; four spellings; assert absent from the file |
| A field the checker does not know is stored and later published | `check` returns a **rebuilt** structure | send an extra key at every level; assert refused (not dropped silently) and never in the file |
| A name or note reaches an Excel cell as a formula | exports (later) | when the exports learn the types: `=1+1`, `+x`, `-x`, `@x` in every field; assert the cell is text |
| The content leaks into the log, a reply or History | `log.py`, `changes.py`, `history.py` | the marker scan in section 9; reply has no `body`; History rows have no body text for add, change, delete and undo |
| The migration loses rows or leaves the file half-done | the new step | the ten tests in section 4; add one that inspects the rows by value before and after |
| The safety copy fails or is not taken | `open_store`, `backup.make` | the existing "failed copy refuses and changes nothing" test, run for this version; assert the copy opens and holds the old version |
| A migrated dev database at the same number but without this step | process | the plain refusal on the first write of a new type; a note to the team |
| Undo restores a body that is no longer valid | `_section_rules` on revert | store a body, tighten a limit in a test, undo: refused in plain words, nothing half-written |
| A very large body fills the file or slows publish | limits, `MAX_BYTES` in `publish.py` | a body at the limit publishes; one byte over is refused; many bodies at the limit together pass 5 MB, and publish then refuses in its existing plain words (`MAX_BYTES`), writing nothing |
| Two sections of the new types paired with `beside` break the row rule | `order`, `_check_flags` | place a needs section beside a tracker (Half fit): rows are right |

## 11. What I could not verify

- Whether `ONLY_TEXT` removal collides with #96's own change to the same `new` request (it adds `beside` and `body` to `new`). Both touch `CHANGE_KINDS["report_sections"][NEW]` and the `values` check. The base should be built first, and #96 should rebase on it.
- The `publish.py` data block carries a `VERSION`. I did not confirm that adding new section keys needs no bump; the build must read the page's data reader and say so.
- What the existing Help "Section templates" topic says today about types it cannot place yet; I saw it exists but did not read its text in full.
- The #48 Word branch history is not joined to main's (no merge base), so I compared files, not diffs. The step-3 text is as written on that branch (`a5c16a50`).
- I did not run any test or build any page; every statement is from reading the code at the commits named.
- Dates are shown as `DD-MM-YYYY` and stored as `YYYY-MM-DD` here by analogy with other tables; the checker's year range (2000 to 2100) is my proposal, not a rule found in the code.
