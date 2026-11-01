# Releasing clark

One page. A release has no workflow: the download is built and attached by hand, so every step below is done before a release is called finished. Each step is one action and says what you should see. Do the steps in order; none of them looks at something made in a later step.

Only a finding marked HIGH holds a release back. Every MEDIUM and LOW gets a Tech Debt card on the clark project board with a Severity label; it may be filed after the cut.

**Why this exists.** v0.3.0 and v0.4.0 were published without a zip: nothing made attaching it a step, and nothing failed when it was missing (found by the check made in pull request 216). v0.1.0 passed on fakes and its `clark.command` failed on a real Mac. So the zip is attached, downloaded back and launched for real before the release is published, and the check at step 20 fails if the zip is missing afterwards.

**Beta.** Every clark release is Beta and a pre-release until version 1.0. The title says so, the Pre-release box is ticked, and the notes say so.

**The digest** (the SHA-256 line of the zip) goes in the GitHub release text. It cannot go in the notes file in the repo: that file is already tagged, and a copy of it is inside the zip, so it cannot hold the digest of the zip it is in.

1. **Cut from the release branch.** Branch `release-X.Y.Z` from current `main`, and put the version (`src/clark/__init__.py`) and the hand-check sheet `dev/handchecks/X.Y.Z-sheet.md` in one commit. You should see: `git log --oneline -3` shows one version commit on top of main.
2. **Write the notes.** Copy the last notes file to `dev/release-notes/X.Y.Z-plain.md` and rewrite it. Keep the first line `# clark X.Y.Z (Beta), Mac` and the line saying the whole of clark is Beta until version 1.0. Use plain words and British English, name no team member and no branch, and back every bullet with code on the tagged commit. You should see: `python3 dev/run_tests.py test_no_real_names` reports every test passed.
3. **Gate green.** Open the release pull request and read its "Tests passed" check, with macOS required on release branches. You should see: a green tick on the exact commit that will be tagged. Write down the run number; step 22 needs it.
4. **Tag, and do not publish yet.** Tag `vX.Y.Z` on the gate commit and push the tag. You should see: `git rev-parse vX.Y.Z^{commit}` prints the gate commit, and the GitHub Releases page has no release for it yet.
5. **Check out the tag in an empty folder.** Run `git clone https://github.com/insyncalan/clark clark-release && cd clark-release && git checkout vX.Y.Z`. Never build from a working folder. You should see: `git status` says "HEAD detached at vX.Y.Z" and nothing to commit.
6. **Build the zip.** In that folder run `python3 dev/tools/package.py mac --release --notes dev/release-notes/X.Y.Z-plain.md --out ../zips`. You should see: "Built the Mac download" and the file `../zips/clark-X.Y.Z-mac.zip`. This zip is for the team only; it is built from the private copy. (If in doubt, build a second time into another folder and run `shasum -a 256` on both zips; the two lines must be the same.)
7. **Take the digest.** Run `shasum -a 256 ../zips/clark-X.Y.Z-mac.zip`. You should see: one line of 64 letters and digits, then the file name. Copy the 64-character part.
8. **Create the release as a draft.** On GitHub, from tag `vX.Y.Z`, choose Draft a new release. Title: `clark X.Y.Z (Beta), Mac`. Tick Pre-release. Paste in the notes file. Choose Save draft, not Publish. You should see: the release listed as a Draft and marked Pre-release, its text starting `# clark X.Y.Z (Beta), Mac`.
9. **Put the digest in the release text.** Edit the draft's text (not the file in the repo) and add at the end: "To check the download is whole, run `shasum -a 256 clark-X.Y.Z-mac.zip` and compare the result with: " followed by the digest, then a new line "This download is not signed yet; check it with the digest above." (Signing is not available yet.) You should see: both lines at the end of the draft's text.
10. **Attach the zip.** Add `../zips/clark-X.Y.Z-mac.zip` to the draft as a release file and save the draft. You should see: the zip listed under Assets.
11. **Download it back.** Signed in to GitHub, download the zip from the draft's page into a new empty folder. You should see: `clark-X.Y.Z-mac.zip` in that folder.
12. **Compare the digest.** In that folder run `shasum -a 256 clark-X.Y.Z-mac.zip`. You should see: the same 64 characters as in step 7. If not, do not go on: attach the zip again.
13. **Unzip it into another new empty folder.** Run `unzip clark-X.Y.Z-mac.zip -d ../clark-unzipped`, then `cd ../clark-unzipped/clark-X.Y.Z`. You should see: `clark.command`, `START-HERE.txt` and the folders `clark` and `src` when you run `ls`.
14. **Run the doctor with the Mac's own Python.** In that folder run `PATH=/usr/bin:/bin python3 -m clark.doctor --data ../clark-check-data --port 8791`. You should see: no "To fix" line and the last line "Everything clark needs is ready." If it says the connection is in use, run it again with another port and use that port in steps 15 to 18. If anything else needs fixing, do not go on.
15. **Launch it.** In the same folder run `PATH=/usr/bin:/bin ./clark.command --data ../clark-check-data --port 8791`. You should see: "Starting clark...", then a clark window opens in Chrome showing the clark page. If you see "Permission denied", "Press any key" or no window, do not go on.
16. **Ask clark if it is well.** Run `curl -s http://127.0.0.1:8791/health`. You should see: `{"ok": true}`.
17. **Launch it a second time.** Run the same command as step 15 again. You should see: "It is already running. Opening its window." and a window opens; no second clark starts.
18. **Close every clark window.** You should see: about a minute later `curl -s http://127.0.0.1:8791/health` prints nothing, because clark has stopped by itself.
19. **Publish the release.** Open the draft on GitHub, check Pre-release is still ticked, and choose Publish release. This is the last step before the board and the log. You should see: the release page with a Pre-release badge, the title `clark X.Y.Z (Beta), Mac` and the zip under Assets.
20. **Run the check on the live release.** Run `python3 dev/tools/check_release_assets.py vX.Y.Z`. You should see: "Every published release has its download attached." If you see a line starting with the tag, or "No published release named", the release is not finished: follow that line.
21. **Board.** Open the clark project board and filter Release = X.Y.Z. You should see: every card in State Shipped. Move any card that did not make it to the next release.
22. **HEAD-LOG row.** Add the row to `dev/HEAD-LOG.md`: tag and commit, publish time, the gate run number from step 3, contents, verdicts, what is not in it, Tech Debt carried. You should see: the new row at the top of the list, newest first.
23. **Hand over the hand-check sheet.** Give `dev/handchecks/X.Y.Z-sheet.md` to the person who checks the screens. You should see: them confirm they have it. It does not hold the release up.

## Who does what

| Role | What they do | Steps |
|------|--------------|-------|
| The Head | Leads the team; tags, creates the draft and publishes the release | 4, 8, 9, 10, 19 |
| The builder | Builds the zip and takes its digest | 5, 6, 7 |
| The release-branch owner | Builds the release branch and writes the notes | 1, 2 |
| The board keeper | Keeps the board and the HEAD-LOG text, and hands over the hand-check sheet | 21, 22, 23 |
| Whoever verifies | Reads the gate, downloads the zip, launches it for real and runs the asset check | 3, 11, 12, 13, 14, 15, 16, 17, 18, 20 |
