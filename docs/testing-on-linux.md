# Testing on the Linux boxes

**In short:** a Linux box runs the whole test suite on what main *would be* after a pull request merges, on Python 3.9 and on the newest Python, one suite at a time, and posts the result with the commits it tested. It catches what a Mac never shows (Linux Chrome draws scroll bars, has no mouse, and is slower under load). This page says how to run one, how to read it, how to add or replace a box, and what a box may cost.

All paths here are made up (`/home/runner/clark` is the checkout, `/home/runner/.local/bin/python3.9` the oldest Python). Use your own.

## What the boxes are for

- **The merge-result test.** For one pull request: main as it is now, with the pull request's head merged in, run as the full suite on Python 3.9 (the oldest clark supports) and on the newest Python. This is the result a merge is judged on.
- **The batch test.** After several pull requests have been merged one after another without a combined run, the full suite on main itself, at the commit asked for, on both Pythons. It proves the merges did not break each other.
- **The prototype self-test** (`system/prototype/run_selftest.py`), when a change touches the prototype.

## How a merge-result test is run

1. **Make sure nothing else is running.** One full suite at a time per box: two at once slow each other down and turn passing tests red. Check with:

   ```
   pgrep -f '^[^ ]*python[^ ]* [^ ]*(run_tests|run_selftest)\.py'
   ```

   It prints nothing when the box is free. Do not use `pgrep -fa 'run_tests|run_selftest'`: it also matches shell loops that are only waiting for a run to end (their command line contains the words), so it never comes back empty. A run that spins the processor on purpose (`--stress`) must never overlap any other run either.

2. **Fetch, and pin main.** Fetch every pull request's head, then note main's commit once, at the start. Every pull request in a batch is merged onto that same commit, even if main moves meanwhile.

   ```
   cd /home/runner/clark
   git fetch origin '+refs/heads/main:refs/remotes/origin/main' '+refs/pull/*/head:refs/remotes/origin/pr-head/*'
   MAIN=$(git rev-parse origin/main)
   ```

   Never test GitHub's own `refs/pull/<n>/merge`. GitHub builds it when it gets round to it, so it can sit on an old main, and the result then says nothing about the merge you are about to make.

3. **Merge in a throwaway worktree.** A detached worktree on the pinned main, with the pull request's head merged in (the `-c` settings give the merge commit a neutral author without touching your git settings):

   ```
   git worktree add --detach /home/runner/wt-merge-123 "$MAIN"
   cd /home/runner/wt-merge-123
   git -c user.name="merge test" -c user.email="merge-test@example.invalid" merge --no-edit origin/pr-head/123
   HEAD_SHA=$(git rev-parse origin/pr-head/123); BASE=$(git merge-base "$MAIN" "$HEAD_SHA")
   ```

   If the merge stops on a conflict, do not fix it: post "does not merge cleanly on main `<sha>`" and remove the worktree.

4. **Run the suite, once per Python, one after the other:**

   ```
   export CLARK_CHROME=/home/runner/chromium/chrome
   /home/runner/.local/bin/python3.9 dev/run_tests.py -j 4
   /home/runner/.local/bin/python3.15 dev/run_tests.py -j 4
   ```

   `-j 4` runs four test files at a time; more makes the browser files flaky on a shared box. A batch test is the same command in a detached worktree on the main commit asked for, with no merge.

5. **The prototype self-test**, when it is wanted: `/home/runner/.local/bin/python3.15 system/prototype/run_selftest.py` (add `--all` to see the passing checks too). It reads `CLARK_CHROME` and passes the Linux flags only once pull request #107 has merged; that pull request is still open, so until then it looks for the Mac's Chrome only and needs #107's change applied in the throwaway worktree.

## How to read the result

- The **last line** is the summary: `Python 3.9.25: pass, 2697 tests in 912.4 s` (made-up figures), or `FAIL`, or `no tests ran` (which also counts as a failure). The line above it counts the files: `231 files passed, 0 failed.`
- Each file prints `OK` or `FAIL` as it ends. A `FAIL` names the tests that failed and the last error line; the end of its output is printed at the bottom.
- **A file that fails under load is run again on its own** when the rest have finished. If it then passes, the runner counts it as passing, prints `Passed alone after failing under load: <file>`, and logs it (see them with `dev/run_tests.py --flaky`). Report it, but it does not make the result red.
- **A `FAIL ... (…, alone)` line** means the file failed on its own too. That is a real failure: report the test and its error.
- More than 15 failed files are not re-run (`--rerun-max`): something is wrong for the whole box (Chrome missing, the disk full), not with the change.
- Some failures happen only on Linux. The known ones, and what causes them, are listed in `dev/FLAKY-TESTS.md`, which is being written for plan item #155 (on its `155-flaky-ledger` branch) and is not on main yet. Check it before calling a Linux-only failure new.

## Where results are posted

On the team's channel issue in the plan repo, and on the issue or pull request that asked for the run, one comment per pull request. Each one gives:

- the pull request number and its **head** commit;
- the **main** commit it was merged onto and the **merge base**;
- for each Python: its version, pass or FAIL, and the number of tests;
- any file that passed alone after failing under load, and any test that also failed alone, with its error line.

For example (made-up commits): "PR #123, head 1a2b3c4, merged onto main 5d6e7f8 (merge base 9c8b7a6): 3.9.25 pass, 2669 tests; 3.15.2 pass, 2669 tests; no file re-run."

## Cleaning up

After each run:

```
cd /home/runner/clark
git worktree remove --force /home/runner/wt-merge-123
git worktree prune
```

- The runner deletes each test file's temporary folder (`/tmp/clark-test-run-<number>/`) when the run ends, and the next run deletes those of a run that was killed. Delete one by hand only if it is from **your own** run and that run has stopped.
- The browser tests keep Chrome's profile inside that folder. The prototype self-test makes a fresh one in `/tmp` and removes it; if a run was killed, its profile may stay. Remove only profiles your own runs left.
- **Never delete other people's** worktrees, temporary folders, Chrome profiles or processes, even when they look finished. Ask the owner.
- Check free space with `df -h /home /tmp`. A full disk makes every browser file fail.

## Adding or replacing a box, in five steps

1. **Install the tools:** Python 3.9 and the newest Python (for example in `/home/runner/.local/bin/`), git, the GitHub command-line tool `gh` (signed in to an account that can read the private repo), and a Chromium or Google Chrome that runs headless.
2. **Tell the tests where Chrome is.** Set `CLARK_CHROME` to the browser's full path, for example in the shell profile: `export CLARK_CHROME=/home/runner/chromium/chrome`. Without it, the tests look on the PATH for `google-chrome`, then `chromium`, then `chromium-browser`, then the Mac's app folders (`dev/tools/run_support.py`, `chrome_path`). A browser test that finds no Chrome fails; it never skips. The runner adds the flags that stop Chrome asking for a keychain (`--use-mock-keychain --password-store=basic`) itself. The flag that tells headless Chrome there is a mouse, so Linux matches the Mac, is on the `linux-hover-tests` branch and not on main yet; until it merges, the checks of faint controls at rest fail on Linux.
3. **Clone the private repo:** `gh repo clone <owner>/clark /home/runner/clark`.
4. **Run one file, then the whole suite.** One file first, to prove Python and Chrome work: `/home/runner/.local/bin/python3.9 dev/run_tests.py test_layout`, then a browser file such as `test_chrome_launch`. Then the full suite on main, on both Pythons, one after the other, as in "How a merge-result test is run".
5. **Clean up** as above, check free space, and add the box to the plan (see the cost rule) before it takes work.

## The cost rule

A box costs money for every hour it is switched on, whether or not it is running tests. The plan lists the boxes that may be on, and the guard that checks running machines works from that list: a box that is not in the plan is powered off. So a new box goes into the plan first, a box that is replaced or no longer needed comes out of it and is switched off, and anything that would add cost (a bigger box, a second one, paid minutes) is raised with the project owner before it is spent.
