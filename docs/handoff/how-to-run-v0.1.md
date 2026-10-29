# How to run the v0.1 build (for the FDE teams)

Written by a teammate, 28-10-2026. It follows `Team/03` (who may push what) and `Team/04` (gates and review). Where clark's `docs/RULES.md` is stricter, it wins. **Nothing starts until the owner has answered #26 (which teams are active on clark)** and the other start-blockers on #5 (#23, #25, #27).

## Before you start
- Read the item's issue first: its Done-when, size, tier and dependencies. Guarded items (#31, #33) also have a design note (`docs/handoff/design-31-store.md`, `design-33-server.md`). **Don't build a guarded item until the note has been read by its reviewers.**
- Work in your own worktree under `~/dev.env/wt-<branch>` (laptop rule, `Team/07`). Never commit in the main checkout. One item, one worktree, one owner.
- Use fictional demo data only, and never commit anything under `system/branding/` or `comms/`.

## Starting clark
From the top folder of your worktree (no setup and no `PYTHONPATH` needed):
```
python3 -m clark --demo            # fictional demo data in a temporary folder, removed when you stop
python3 -m clark                   # your own data, in ~/Library/Application Support/clark/ (made on first run)
python3 -m clark --data ~/clark-data --port 8800 --open
```
- It prints the address (always `127.0.0.1`), for example `Open http://127.0.0.1:8766/#dashboard&p=TUL to use clark.` With `--open` it also opens that address in your browser. Ctrl+C stops it, and it ends with `clark has stopped.`
- **The first page is empty until a project is open.** Until the project list (#36) is built, the page opens a project from its address. With `--demo`, or when your data has exactly one project, the launcher prints the address with the project in it (`#dashboard&p=TUL`): use that address. For any other project, add `#dashboard&p=` and its code to the address yourself, for example `http://127.0.0.1:8766/#dashboard&p=ABC`.
- `--port N` sets the port (default 8766, or the `CLARK_PORT` setting). If the port is in use, clark says so before it starts anything, suggests a free port, and exits with code 1.
- `--data FOLDER` keeps the database in that folder instead. A folder inside OneDrive is refused.
- `--demo` and `--data` can't be used together. Fictional data only: never point `--data` at a real engagement's data on a shared machine.

## Branches
| Who | Branch | Example |
|---|---|---|
| An FDE team | `team-<name>-<issue>-<short-name>` | `team-a-31-store` |
| A release line (the Head only) | `v0.1-<purpose>` | `v0.1-release` |

You may push your own `team-` branches as often as you like. You may not push to `main`, any `v0.1-` branch or any tag, and never force-push. If a push is refused, **stop and tell the Head**; don't try another route.

## The local test runner
There is no CI yet, because of the GitHub Actions billing limit. Before every push:
```
python3 dev/run_tests.py            # the newest Python
/usr/bin/python3 dev/run_tests.py   # Python 3.9, the oldest supported
```
Both must pass. Paste the last lines of each run, with the Python version and the commit, into the item when you report.

## Reporting on the item
At each step, post a comment on the item's own issue:
```
Team <Name>, HH:MM: <what changed>. Branch team-<name>-<n>-<slug>, head <sha>. Tests: 3.14 pass (N), 3.9 pass (N). Next: <step>.
```
Push before you post, and check the push with `git ls-remote origin <branch>`. If something isn't pushed, say so.

**Heartbeat** every 15 minutes while working, on your channel issue on the planning repo (#10 a teammate, #11 a teammate: their reserved channels, Team/05), as `Team/06` says. It covers what is running, what finished (with its sha), blockers, and `Capacity: n of m agents running; send work`. If nothing changed, one line is enough.

## Review pairs (the reviewer is never the builder)
| Builder | Reviewer, Light items | Reviewers, Full (guarded) items |
|---|---|---|
|  |  | A teammate, plus a second independent reader: the Head (#25: "the Head Reads") |
|  |  | A teammate, plus the second reader |

- Reviewers are read-only, in their own throwaway worktree, and are given the exact head sha and the Done-when.
- The verdict goes on the item: `Review, HH:MM: <sha> PASS` or a list of findings tagged HIGH, MEDIUM or LOW.
- Any HIGH or MEDIUM blocks the item until it is fixed and re-reviewed. A LOW becomes a follow-up issue.
- For guarded items, the owner approves the exact copied code in his own words before merging.

## Pull requests and merging
- Open a pull request only when the Head says go. The Head merges; FDE teams never merge.
- The pull request body has the item link, the head sha, both test runs and the review verdicts.
- **Head:** the Head is Head and leads clark (the owner, 28-10-2026, #26: "the Head will. lead and owns HEAD"). Which teams build is for the Head to propose.

## Order of work (from #5), in two lanes
```
A teammate: #28 repo and runner ─▶ #31 store (guarded) ─▶ #30 demo data ─▶ #33 server (guarded) ─▶ #35 page and tokens ─▶ #36 work items list ─▶ #39 publish
A teammate:           (after #28) ─▶ #34 vendor and reuse ─▶ #29 brand tests ─▶ #32 milestone state ─▶ #37 Excel export ─▶ #38 Excel import
```
- Start #28 first. It's small, and everything else needs it.
- #31 and #34 run side by side, then #29.
- A teammate reviews each a teammate item as it lands, and a teammate reviews a teammate's. Reviews come before starting the next item where they block a dependency: #31 before #30, #32 and #33; #33 before #35.
- #39 is last. When it passes, the Head cuts `v0.1-release` and runs the whole suite on both Pythons at that exact commit.

## When things go wrong
- **A test is flaky:** measure it alone five times before changing a wait (`Team/07`).
- **A usage limit:** say so once on your channel and stop.
- **A finding against your item:** fix it on the same branch, push, post the new sha, and ask for a re-review.
