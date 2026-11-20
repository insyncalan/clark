# Design note and threat model: the ask clark index (spike #1368, build #1366)

**Status, 20-11-2026:** written for the reopened spike #1368 (Done-when: a short design note with the recommendation, and the threat model, question 7 of the ticket). The index is built in PR 2001 (the Row 1366 branch, head `57e04185`), not yet on main. Every `file:line` below is in that head unless it names `main`. Nothing was run against the owner's library for this note: the measurements are the ones posted on #1368 (parts 1 to 3, 19-11-2026, the owner's laptop under load 8 to 11). Where something was not checked it says so.

## 1. What the spike measured (from #1368, not repeated here in full)

- Today a question opens files in path order and stops at 60 MB: 10 of 180 readable files, 22 to 24 s before the model; 9 of 183 test questions found (5%).
- Reading everything again for every question: 118 s, 179 of 183 found. Index: 126 s once, then 0.05 ms median a lookup, 181 of 183 found, 8.9 MB for 5,454 passages. (Easy test: the three rarest words of a passage. The real-question test was waived on the owner's word, 19-11 18:53.)
- Excel, PowerPoint, HTML read with no new dependency; pictures need the Mac's own text recognition through a Swift helper; the 200-page and 20 MB PDF limits are constants of ours, nothing in the library needed them.

## 2. Recommendation: what to build, in what order, what not to build

Built in PR 2001 (slice 1): the index file, the background reader, status counts, PDF, Excel, PowerPoint, web pages, the secret screen before storing, refresh by size and time, left-out list. See section 4 for where each is.

Next, in this order:
1. **Page budget for PDFs** (the spike: 2,000 pages, 100 MB, 120 s for one file in the background). Today the index still uses the question limits: `pdf_reader.MAX_BYTES` 20 MB and `MAX_PAGES` 200 (`main:src/clark/pdf_reader.py:22-23`, used at `ask_index.py:318`). Keep the separate process, the time limit and the output cap; a file over a limit stays counted as `too_long`, never dropped silently.
2. **Delete the index when its project is deleted in real use.** Only the demo seed calls `ask_index.remove` (`demo_seed.py:147`); no other caller exists in `src` at the head (grep checked). `refresh` removes it when no folder is left (`ask_index.py:214`). Without this, a deleted project keeps a copy of its folder text on disk.
3. **Scanned PDFs and pictures** through the Mac's Vision text recognition (spike: 0.16 to 0.43 s a page, 0.36 s a picture, 90 of 96 PNGs carry text). Needs the threat model item T7 below settled first.
4. **Online-only files**: stay unread (`reach.ONLINE`, `main:src/clark/reach.py:72`: "clark never downloads one"); count them. Revisit only with the owner's decision on the cost of a download.
5. **Lift the 20,000-file listing cap** (`main:src/clark/reach.py:98`) for the background run; the slice's own docstring lists it as not done (`ask_index.py:22`).

Do not build: a vector or model-based index (BM25 over FTS5 found 99% on the easy test; the real-question test was not run, so there is no evidence either way on vague questions); an index in `clark.db`; an index in a synced folder; a background run inside a question; recordings (out of scope, owner 19-11).

Not measured and still open: the Docker image's own SQLite (see section 6 for the Pythons measured on this box); the model's own time; the hostile-file numbers for the extra types beyond the tests named in section 3.

## 3. Threat model: an index holds copies of document text on disk

Assets: the text of every indexed document in a project's saved folders, plus file labels (folder, name, modified date). Attacker views: another user of the same computer; a backup or sync tool that copies the data folder; a hostile document in a source folder; a person who deletes a project or folder and expects the text to be gone.

| # | Threat | What the code does at head `57e04185` | Test | Gap |
|---|---|---|---|---|
| T1 | Other users read the index | Folder `ask-index/` is made 0700 and the file 0600, and both are put right again on every open, also if made looser (`ask_index.py:80-84`) | `test_ask_index_1366.py:138` (0600), `test_ask_index_review_1366.py:14-24` (0700/0600 restored) | Windows permissions: not checked. `os.chmod` (`ask_index.py:81,84`) follows a symlink at the index path; whether one can be planted there: not checked (the data folder is owner-only) |
| T2 | The index is synced or backed up | One file per project under `<data folder>/ask-index/<code>.db` (`ask_index.py:63-66`), the data folder is the one next to `clark.db` (`__main__.py:589`), never inside a source folder (`reach.never_inside`, `main:src/clark/reach.py:321`, used at `ask_index.py:183-191`); clark refuses a data folder inside OneDrive (`main:src/clark/__main__.py:252-254`); backups touch only `clark-<time>-<tag>.db` names (`main:src/clark/backup.py:55`), so the index is not backed up | name rule only | Time Machine and other whole-disk backup copy it: NOT checked; no exclusion is set (grep for xattr, tmutil: none in `src` on main) |
| T3 | Secrets end up in the copy | A file whose name or text looks like a password or key is screened before any text is stored; it leaves a row with a label and size only (`ask_index.py:344-345`, `main:src/clark/secret_screen.py:343,355`) | `test_ask_index_1366.py:188` (a secret is never stored), `test_ask_index_fresh_1366.py:74` (edited to hold a secret counts safety) | The screen is a pattern match: a secret it does not recognise is stored. The same limit as today's question path |
| T4 | Text of a removed or changed file stays in the file | `PRAGMA secure_delete=ON` (`ask_index.py:86`); a changed file's rows are dropped before reading (`ask_index.py:178-181,313`); after a run the segments are merged and the file is `VACUUM`ed (`ask_index.py:305-307`); a removed folder loses its passages (docstring `ask_index.py:16`) | `test_ask_index_fresh_1366.py` | Index is not marked as wiped if the process is killed between delete and VACUUM: not tested |
| T5 | A project is deleted, its text stays | `remove` deletes the file with `-wal`, `-shm`, `-journal` (`ask_index.py:69-73`) | demo seed only | **Gap, if a real project delete exists:** none was found at the head (grep of `src` finds only the demo remove, `store.py` `remove_demo`, calling `demo_seed.py:147`; grep only, not run). If none exists, the live leak is a removed folder, whose index goes only when the next background run starts (`ask_folders.py:207`, `ask_index.py:214`); the follow-up row must name which |
| T6 | A hostile document harms the reader | Files are reached only through `reach.read_bytes`: path opened one folder at a time with O_NOFOLLOW, regular files only (`main:src/clark/reach.py:347-348,413-416`). PDF in a separate process with page, size and time limits (`pdf_reader`). Excel: member count, declared and really unpacked bytes, rows, cells and 20 s checked before and during the read (`ask_index.py:44-50,107-139,141-161`). PowerPoint and web pages: standard library only; a DOCTYPE or entity declaration is refused, zip member count and unpacked size capped (`ask_extract.py:19-24`, doctype check at line 36) | `test_ask_index_fresh_1366.py:157` (Excel bomb), `test_ask_index_types_1366.py:140` (entity), `:154` (pptx bomb) | Excel runs openpyxl in the clark process (not a child process) behind those checks; macros and external links: not tested; HTML: size, line-count and unclosed-tag tests exist (`test_ask_index_types_1366.py:225,240,283`), no script-injection or encoding-attack test |
| T7 | Text recognition helper (planned, not built) | n/a | n/a | A Swift helper would run with the user's rights on untrusted images and PDFs. Needs: its own process, time and output cap, no network, no file name on its command line beyond a temp copy, before it is built |
| T8 | Online-only files are downloaded by a read | They are never opened; counted `online_only` (`ask_index.py:245`, `main:src/clark/reach.py:72`) | status tests | Cheap detection from file flags was measured on a Mac (8 files, none opened); other platforms: not checked |
| T9 | A question is answered from stale text | `current` and `stale` compare size and modified time; a changed file means this question reads the folders and the index is read again (`ask_index.py:502,516`, `Indexer.current`) | `test_ask_index_fresh_1366.py` | Same-size, same-time edits are missed (a limit of every size and time check) |
| T10 | A query breaks the index | Words only, each quoted, at most 40, joined with OR; an SQLite error returns no passages (`ask_index.py:366-385`) | `test_ask_index_1366.py` | none known |
| T11 | The index is sent to a provider | `search` returns at most the question's passage budget, in the same shape as today's folder read (`ask_index.py:553-562`); the whole file is never sent. Which passages go to the provider is unchanged from today's rule | n/a | Same exposure as before: the chosen passages leave the machine when the person asks |
| T12 | The background thread hurts the machine | One thread, `os.nice(10)`, stops at the next file on shutdown (`ask_index.py:565-670`) | pickup tests | CPU cost on a loaded box: not measured |

Residual risk accepted by this note: an indexed copy of document text exists on the owner's disk as long as the project has folders. It is in clark's data folder with the owner-only permissions in T1, and it is rebuildable. If the owner wants it encrypted at rest, that is a new decision (a key to keep, so it falls under "tokens, secrets or keys"): not recommended in this note.

## 4. Where it is built (PR 2001)

- Index file, open, permissions: `src/clark/ask_index.py:63-93`
- Refresh by size and time, the wipe: `ask_index.py:206-308`
- One file read into passages, the secret screen: `ask_index.py:311-357`
- Search and the question's read: `ask_index.py:366-385`, `553-562`
- Background thread: `ask_index.py:565-670`; started at `__main__.py:589`, stopped at `__main__.py:629`
- PowerPoint and web readers: `src/clark/ask_extract.py`
- A finished index answers a question: `ask_service.py:184-185`

## 5. Decisions for the owner and the Head

1. Accept the order in section 2.
2. Time Machine: exclude `ask-index/` from backups (needs a macOS step, not tested), or accept it is copied. (Not decided here.)
3. Raise the PDF limits for the background run only, to the spike's numbers, once the hostile-PDF tests are done.

## 6. Measured on this box (Linux aarch64, 20-11-2026) and what the ticket still asks

Question 3 of the ticket, "is SQLite FTS5 available on the Python this Mac has and the other supported ones". Command: `python -c 'import sqlite3; c=sqlite3.connect(":memory:"); print("ENABLE_FTS5" in [r[0] for r in c.execute("pragma compile_options")]); c.execute("create virtual table t using fts5(x)")'`, run on each interpreter found (`ls /usr/bin/python3*`, `~/.local/share/uv/python`):

| Python | SQLite | ENABLE_FTS5 | `create virtual table ... using fts5` |
|---|---|---|---|
| 3.9.25 (uv build) | 3.50.4 | yes | ok |
| 3.12.3 (`/usr/bin/python3`) | 3.45.1 | yes | ok, `bm25()` returns a rank |
| 3.14.9 (uv build) | 3.53.1 | yes | ok |
| 3.15.2 (uv build) | 3.53.1 | yes | ok |
| 3.9 on the owner's Mac (spike, #1368 part 1) | 3.54.0 | yes | reported, not rerun |

Not checked: the Docker image `python:3.12.12-slim-bookworm` (`docker/compose.yaml:17`), because `docker` is not installed on this box (`command -v docker` prints nothing); Python 3.10, 3.11, 3.13 (not installed here); a Python from python.org or the Command Line Tools on an IT-managed Mac; Windows. The uv builds are not the vendors' system builds, so they show FTS5 is common, not that every supported install has it. The code must therefore treat a missing FTS5 as a state, not an error: whether `ask_index` does so was not checked for this note.

What the ticket still asks that this note does not cover (quote, then status):

1. Done-when: "Each question above has a measured answer, posted as a comment here with the numbers." Questions 1 to 6 are posted. Question 7 ("The threat model") is section 3 of this note, from code reading only; no hostile file was run.
2. Question 4: "can Excel ..., PowerPoint and HTML be read safely". Part 1 on #1368 says "Hostile-file limits (zip bombs, huge sheets, macros, external links) not tested yet". Section 3 T6 names the tests in PR 2001 for a zip bomb and an entity; macros and external links are not tested.
3. Question 5: "can a standard-library Python 3.9 reach it on an IT-managed laptop". The spike says "Not checked: another laptop, IT permission prompts". Still open; T7 says the helper is not built.
4. Question 6: "what opening one costs (time, disk, an anti-virus scan)". The spike measured the count (8 files, 1.08 GB) and the cheap flag test, not the cost of opening one. Section 2 item 4 chooses never to open, so the cost stays unmeasured.
5. Question 1: "Which of the 300-file, 60 MB and 20-second limits is hit". Answered (60 MB). The model's own time was "not measured" and is not here.
6. Design note: "what to build first, in what order, and what not to build" is section 2. The ticket also says the note lives in the planning repository until the build starts, and that nothing is committed to this repository; this note is here (PR 2023). Where it should live is for the owner to say.
7. Done-when: the ticket asks that the owner and the Head read it and that the release and priority of the build ticket are set from it. Not done; section 5 lists the decisions.
8. The ticket's later comment, "the real-question test has been run and its result is in the design note", was waived by the owner on 19-11 18:53 (section 1). Not run.
9. The part 2 comment says the index should be "left out of Time Machine (to check how)". Not done: `grep -rn "tmutil\|xattr" src` finds nothing and this box is not a Mac, so how to exclude (`tmutil addexclusion` or the `com.apple.metadata:com_apple_backup_excludeItem` attribute) is not checked.
10. Part 3 recommended "up to 2,000 pages, 100 MB and 120 s for one file" with "hostile-PDF tests ... still to do". `pdf_reader.py:22-23` still has `MAX_BYTES` 20 MB and `MAX_PAGES` 200; the index reuses the question limits (section 2 item 1). No hostile-PDF numbers exist.
11. Project delete: `grep -rn "ask_index.remove" src` at this branch's base finds only the demo seed caller; the note's T5 gap stands (section 2 item 2).
