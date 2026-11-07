# Phase 2: first-run setup page (spec only, nothing built)  #836

Goal: a person who double-clicks clark.app on first run sees a page in clark's own UI, in Chrome, that says what is ready and what is not, instead of a Terminal or a dialog. It is the doctor (`python3 -m clark.doctor`, src/clark/doctor.py) shown as a page.

## The one design point
Today the launcher refuses to start the server when a check fails (launch.py `launch()`: data folder in OneDrive, another copy on the port, mixed versions, interrupted update). A page needs a server. Phase 2 therefore needs a SETUP MODE: a server with no database and no data routes, serving only the setup page and its checks, started by the launcher when a check fails. That is the guarded server.py change (GUARDED-CHANGES.md). Without it, the dialogs of Phase 1 are the whole UI for failures that stop the server (Python too old, port taken, mixed versions); the page is for problems clark can show after it started, and for the first-run choices.

## Checks (each is an existing doctor check or launcher test; line numbers at origin/main b8ff42ae1)
| Check | Source | Words reused (file:line) | Missing |
|---|---|---|---|
| Chrome present | doctor.check_browser | doctor.py:142 "Chrome is there, so clark opens in its own window." and :143 "Chrome wasn't found, so clark will open in your usual browser. Install Chrome to give clark its own window." | wording about a tab (NEW-WORDS 2, 3) |
| Port free, or another clark's data | doctor.check_port, launch.report | doctor.py:164 "Nothing else on this computer is in the way of clark starting."; :166 "Your clark is already running with this data."; launch.py:88 "Another copy of clark is already open with different data (this one uses ...). Close that copy, then start clark again."; launch.py:91 "Nothing was started: clark is already open in another Terminal window, or another program is using the connection it needs..." | "Terminal window", "double-click clark.command" in :91 (NEW-WORDS 5). The page cannot show this one in setup mode on the same port (it is the port that is taken): it opens on the next free port |
| Data folder not in a synced folder | doctor.check_data_not_in_onedrive, platform.check_data_dir | doctor.py:123 "Your clark data isn't inside OneDrive."; doctor.py:125-130 the OneDrive FIX line (ends "Backups can still go to OneDrive."); platform.py:235-238 the refusal | Dropbox, iCloud Drive and Google Drive: there is no check at all (platform.onedrive_roots, platform.py:148, finds OneDrive only) and no words (NEW-WORDS 9). A folder chooser on the page (the choose-folder system dialog exists: platform.choose_folder, platform.py:423) |
| Data folder can be saved in | doctor.check_data_folder | doctor.py:115 "Your clark data can be saved in {folder}." and the FIX line after it | none |
| Python version | doctor.check_python (the applet checks 3.9 itself, before any page can exist) | doctor.py:82, :86, :92 "Python {version} is ready."; clark.command lines 5-6 ("This Mac needs Python 3.9 or newer ...") | the page never shows a failure for this (clark would not run); it shows the READY line only |
| Mixed versions | same_version.refuse, row 760 | same_version.py:23 "These clark files are not all from the same version, so clark will not start. Move the clark folder aside (rename it) and unzip the download again." | none (the setup page shows this line; today it is printed to a terminal) |
| Interrupted update | launch.finish_update, update_helper | update_helper.py:116 "not_restored" ("The update didn't install, and not everything could be put back yet ... Open clark again to finish putting it back..."), :123 "finished", :125 "busy" | none; the page offers a "Check again" button (NEW-WORDS 8) that re-runs the finish |
| Claude Code (advice only) | doctor.check_claude | doctor.py ~174-180 | none (optional; may be left out of first-run) |

## Routes (all guarded; GUARDED-CHANGES.md)
- GET /setup (the page; token-booted like the main page), GET /api/setup/checks (the list above, as {id, status, words}), POST /api/setup/folder (open the system folder chooser, check the answer with check_data_dir, store it), POST /api/setup/finish (re-run finish_update), POST /api/setup/done (leave setup mode and start normally). No new open (tokenless) route.
- The checks run in the existing doctor code: the page only draws its Line(status, words) results. No second copy of any wording.

## Build plan (sizes: S under 100 lines, M 100-300, L 300+; each one PR, in order)
1. Phase 1 (this branch): the Chrome tab (S, done), build_app.sh (S, done), the words (the owner), the translocation test on a downloaded zip (manual, 1 hour).
2. Packaging of clark.app into the zip and the update's list of entries (M, guarded; package.py, release_files.py, updates).
3. doctor as data: split doctor.run_check into a function that returns Lines without printing (S; doctor.py, not guarded).
4. Setup mode in the server: routes, no database, the launcher starts it on a failed check instead of saying a line (L, guarded, two reviewers; design note first, like design-71).
5. The setup page (M: one page, the chooser, Check again) plus its Help text and tests with headless Chrome.
6. Synced-folder check for Dropbox, iCloud Drive and Google Drive, with the words (S for the code, words need the owner).
7. Windows later (platform.py, issue 57); none of this is Mac-only except the existing platform calls.
Dependencies: 3 before 4 and 5; The owner's words (NEW-WORDS.md) before 2 and 5. Total about two M, one L, four S.
