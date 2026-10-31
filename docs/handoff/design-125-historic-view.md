# Design: #125 keeping and showing past reports

A design note for review, 29-10-2026. Nothing is built in the product. Mockups: in the prototype, open the profile menu › **Past reports (mockup)** (or `system/prototype/index.html#past`). The owner chooses; no build starts until he does.

## The answer in short
- **Keep both:** every published file, as it was sent, and a small copy of the report's data at each publish. Keep them all; archive, never delete.
- **Offer (a) first:** open a past published report exactly as it was. Then **(c)**, the changes since the last publication marked. **(b)**, the dashboard "as at" any date, comes later and is always labelled "rebuilt".
- **The way in:** a week picker beside "Week ending" on the Dashboard, listing the published weeks. The Published reports list (#120) stays as the full record.
- **The signal:** a banner, "You are looking at 21-10-2026, as it was published. Back to now.", a tinted frame, a faint watermark, and nothing on the page that can be edited.
- **A past report is never changed.** A correction goes into the next report.

## 1. What is kept?
**Recommendation: both.** The published file is the fixed record of what the client saw: it is kept byte for byte, with its SHA-256 (the `publications` row already holds one). Beside it, at the same moment, clark keeps a copy of the report's data (the rows that went into the page, as JSON). The file is the proof; the data copy is what (c), "changed since", and later search work from, without having to read a web page back. The published file already carries its own data block (`clark-data`), so the extra copy is small; it also holds the rows the client did not see, so the editor's own comparison is complete.
**Relies on:** #120 numbered publications (the number and the kept file), FR-83 publish log, #118 (reads the data copy), FR-43c (never deleted).

## 2. Which past views?
**Recommendation: (a) now, (c) next, (b) later.**
- **(a) A past published report as it was.** The kept file, opened read only. Nothing is redrawn, so it cannot differ from what was sent. Build this first.
- **(c) Two weeks compared.** Shown as changes marked against the publication before (the "Since the last report" block of #118, worked out between two data copies instead of from today). Side by side is harder to read on a laptop and is not recommended.
- **(b) The dashboard "as at" a date.** Rebuilt from the change history. Useful for "what did we know on the 14th?", but it is never what anyone was sent, so it must say "rebuilt from the change history" every time (mockup 1, "As at that date", with a dashed frame). Later, and only once #123's history covers every field that the report shows.
**Relies on:** (a) #120; (c) #118 and the data copies; (b) #123 history (FR-43a, never pruned).

## 3. How does a person get there?
**Recommendation: the week picker beside "Week ending" (mockup 1).** It is where people already look at the week. It lists this week (the draft) and each published week with its number; picking one opens it in the past view. The **Published reports list** (mockup 2; built in the prototype under Settings for #120) stays as the full record, with Open on each row. The **timeline** (mockup 3) reads well but repeats the list: do not build it now. One item's history stays in the peek's Activity tab (#123).
**Relies on:** #120 (the list of publications), the Dashboard's report bar.

## 4. How is "this is the past" shown?
**Recommendation: all four signals together, and none on its own.**
- A banner that stays at the top: "You are looking at 21-10-2026, as it was published. Back to now." and under it "Publication 7 · week ending 23-10-2026 · read only · corrections go into the next report".
- The report sits in a tinted frame with a faint watermark ("Publication 7 · 21-10-2026").
- Nothing in it can be edited, focused or clicked (no fields, no Edit, no sparkle). The way back is "Back to now", which opens this week's Dashboard.
- **On a client's copy:** the page says "Publication 7 · 21-10-2026" at its foot and on every printed page (the prototype does this now; #120 brings it to the product). Nothing more is needed: the client only ever has the files they were sent.
**Relies on:** #120 (the number on the page), FR-83a.

## 5. Can a past report be changed?
**Recommendation: never.** A kept file is written once and never overwritten; clark checks its SHA-256 when it opens one and says plainly if the file no longer matches. A mistake is put right in the next report, with an optional line "Correction to Publication 7: …". Publishing the same week twice makes a new number; it does not replace the old one.
**Relies on:** #120, FR-83 (the SHA-256), FR-43c.

## 6. What does the client see?
**Recommendation: only the reports they were sent, each saying its number and date.** No list of past reports for the client in v0.5: their folder already holds each week's file. When client comments arrive, each comment is tied to the publication number and the item (#120, #21), so a comment on Publication 6 opens Publication 6.
**Relies on:** #120, #21, #43 To client.

## 7. How long is it kept, and how big can it get?
**Recommendation: keep every publication for ever; old ones can be archived (hidden from the lists, kept on disk), never deleted.** The prototype keeps only the last 10 copies; that rule is dropped. The kept files live in clark's data folder (not in the database, and never on OneDrive, BRD section 8), so the daily backups (#111) stay small. Each kept file is copied once into the backup folder the user chooses, since it never changes; a restore never removes one (#111 already says "Published reports … are never touched").

Measured on the demo project (Tulip Records Migration, `dev/demo_data.py`: 6 milestones, 3 actions, 6 risks and issues, 5 decisions, 3 use cases on the page):

| What | One copy | One a week for a year (52) | Ten projects, a year |
|---|---|---|---|
| The published file | 160 KB (70 KB compressed) | 8.3 MB | 83 MB |
| The data copy (all rows, as JSON) | 12 KB (2.6 KB compressed) | 0.6 MB | 6 MB |
| The whole demo database today, two projects, 1,042 history rows | 450 KB | | |

About 150 KB of each file is the page's own code, the same every week; the data is about 8 KB. That is the price of a file that opens on its own, anywhere, as it was. At 83 MB a year for ten busy projects, no limit is needed; compressing kept files is possible later if it ever is.
**Relies on:** #111 backups, FR-43c archive, #120.

## 8. Search across past reports?
**Recommendation: later (v0.6 or after).** The data copies make it possible without reading web pages: search their text and open the matching publication in the past view.
**Relies on:** the data copies from 1.

## The mockups (in the prototype)
Profile menu › Past reports (mockup). Three ways in, chosen with the switch at the top: **Week picker** (with "As published" or "As at that date"), **Published reports** (Open on each row) and **Timeline** (a dot per publication, coloured by health, then Now). Each opens the same past view: the banner, the tinted frame and watermark, a report with nothing editable, and "Back to now". The publications in the mockup are made up. The self-test checks that each way in opens and shows the banner, that nothing in the frame can be edited, and that "Back to now" returns to the Dashboard.

## Follow-on build items (for a teammate to file; not filed)
| # | Title | Size | Tier | Depends on |
|---|---|---|---|---|
| 1 | Keep every published file and a copy of its data, write once, never pruned; old ones archived, not deleted | M | Full (store and schema) | #120, #39, #43 |
| 2 | Open a past publication read only: the banner, the tinted frame, "Back to now", SHA-256 checked | M | Full (a new server route) | 1 |
| 3 | A week picker beside "Week ending" that lists the published weeks and opens them | S | Light | 2 |
| 4 | The Published reports list opens the past view, and can archive an old one | S | Light | 1, 2 |
| 5 | Compare with the publication before: changes marked, from the two data copies | M | Full (a new server route) | 1, #118 |
| 6 | Backups copy each kept file once; a restore never removes one | S | Full (backup is a guarded copy) | 1, #111 |
| 7 | Prototype: keep every publication (drop the last-10 rule), with Archive | S | Light | none |
| 8 | Later: the dashboard "as at" a date, rebuilt from the change history | L | Full (reads the store's history) | #123 |
| 9 | Later: search across past reports | M | Full (a new server route) | 1 |

## For the owner to choose
1. Keep both (file and data copy), or the file only?
2. (b) "as at" a date: later, as recommended, or in v0.5?
3. The week picker as the main way in, or the Published reports list only?
