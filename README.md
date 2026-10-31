# clark

**The weekly project report, written from the work itself.**

clark is a report editor for programme managers. It keeps a project's actions, risks, issues, decisions, milestones and use cases in one place on your own computer, with a history and Undo. You can move them in and out of Excel, and publish the weekly report as one web page you can send to a client. Nothing leaves your computer unless you publish a report.

> **Beta.** clark is in Beta until version 1.0. It works and is tested, but expect rough edges and changes between versions. It runs on a Mac today. Windows and Linux downloads come later.

## What you can do with it

- **Write the weekly report** where you read it: switch between View and Edit, add and move sections, change a status, owner or date in place, and Undo anything.
- **Keep the log.** Actions, risks, issues and decisions, each with an owner, a due date and a history.
- **Track milestones** on a timeline or a calendar, with a slipped date shown against the agreed one.
- **Choose what the client sees.** Each item and section can be left out of the published page with one click.
- **Work with Excel.** Import a tracker you already have, and export your work items, milestones and use cases back out.
- **Publish** as a single web page. It opens anywhere, with no server and no sign-in.

## Install (Mac)

1. Open this repository's **Releases** page and download the latest `clark-…-mac.zip`. Unzip it.
2. clark needs **Google Chrome** and Python 3.9 or newer. To check your Mac is ready, open Terminal in the unzipped folder and type `python3 -m clark.doctor`. It tells you what to fix, if anything, and where to get it.
3. Double-click `clark.command`. The file `START-HERE.txt` in the folder explains the prompts your Mac may show the first time.

To look around with made-up projects first, open Terminal in the folder and type `python3 -m clark --demo --open`.

## Where your data lives

Your data stays on your computer, in `~/Library/Application Support/clark/`. That folder holds your database (`clark.db`), clark's safety copies (in a `backups` folder beside it) and a log file. Two rules:

- **Keep it out of OneDrive, Dropbox and any other synced folder.** They can damage a database that is open.
- **Safety copies** are made before every Undo, before every Excel import and once a day. The newest 14 are kept. Settings › Safety lists them and puts one back. If clark will not start, close it and type `python3 -m clark restore` in Terminal to see them.

To keep your data somewhere else, start clark with `python3 -m clark --data FOLDER`.

## If something goes wrong

Open an issue on this repository and say what you did, what you expected and what you saw. For a security problem, do not open an issue: email alan@januscollab.com (the steps are in `SECURITY.md`). If clark says it did not start, it names a log file (`server.log` in the data folder): please attach it. Do not attach your database or any real client information.

## For people who build clark

- **Run the tests:** `python3 dev/run_tests.py`.
- **Set up the page-file merge driver, once per clone:** `python3 dev/tools/install_merge_driver.py`. `src/clark/page/page.html` and `page-view.html` are built from the sources, so a merge rebuilds them (`dev/tools/merge_page.py`) instead of conflicting. **The rebuild runs the merged branch's own `dev/tools/build_page.py` (and the code it imports from `dev/tools` and `src/clark`) with your rights, during the merge, so a bad change there spreads through the driver: before merging a branch you do not trust, check `git diff HEAD...BRANCH -- dev/tools src/clark`.** If a merge still reports a conflict on them, the sources conflict or the merge is a rebase: fix the sources, then run `python3 dev/tools/build_page.py`. `python3 dev/tools/build_page.py --check` (also run by `tests/test_one_editor_gate.py`) fails when a committed page is not what the sources give.
- `docs/PROJECT-BRIEF.md` says what clark is for.
- `docs/ARCHITECTURE.md` and `docs/handoff/` say how it is built and why.
- `docs/RULES.md` lists the rules the project follows: no real names or client data, plain words, British English.
- the reuse record lists the code it builds on, with where each part comes from.

All data in this repository is fictional demo data.

## Licence

You may read the code, and download and run clark on computers that you or your employer own, for your own work, including reports you make for your employer or your clients. You may not copy it, change it, or build on it without permission. The full words are in `LICENSE`. To ask for permission, write to alan@januscollab.com.
