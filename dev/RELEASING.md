# Releasing clark

One page. A release has no workflow: the download is built and attached by hand, so every step below is done before a release is called finished. Each step has a name, a check and a place to see it. Only a HIGH finding blocks a release; every MEDIUM and LOW is ticketed (Tech Debt, with a Severity label, on the board) before the cut.

**Why this exists.** v0.3.0 and v0.4.0 were published without a zip: nothing made attaching it a step, and nothing failed when it was missing (ticket PR 216). Steps 6 and 9 close that gap.

1. **Cut from the release branch.** Branch `release-X.Y.Z` from current `main`; the version (`src/clark/__init__.py`) and the hand-check sheet go in one commit. Check: `git log` shows one version commit on top of main.
2. **Notes.** `dev/release-notes/X.Y.Z-plain.md`: plain words, British English, no persona or branch names, no line starting with the product name, every bullet backed by code on the tagged commit. Check: the plain-words and no-real-names tests pass.
3. **Gate green.** The release pull request's "Tests passed" is green on the exact commit that will be tagged, with macOS required on release branches. Check: the run id is written in the HEAD-LOG row.
4. **Tag and publish.** Tag `vX.Y.Z` on the gate commit and publish the GitHub release with the notes. Check: the tag points at the gate commit.
5. **Build the zip from the tag.** From a clean checkout of the tag, never from a working folder:
   `python3 dev/tools/package.py mac --release --notes dev/release-notes/X.Y.Z-plain.md --out DIR`
   (the same commit gives the same bytes: build twice and compare if in doubt).
6. **Attach `clark-X.Y.Z-mac.zip` and its SHA-256 to the GitHub release.** Put the digest in the release notes, with the command to check it: `shasum -a 256 clark-X.Y.Z-mac.zip`. Every zip in the release has its digest in the notes.
7. **Sign it** (once #282 is in; until then the digest in the notes is the check). Attach the signature beside the zip. Until then the digest is only as trustworthy as the page it is on; say so in the release body.
8. **Verify the download.** Download the zip from the release page and compare its digest with the notes. Check: they match.
9. **Run `python3 dev/tools/check_release_assets.py vX.Y.Z`.** It must print that the download is attached. A release without it is not finished.
10. **Board.** Every item in the release is State Shipped, with the Release field set to this version; items that did not make it move to the next release. Check: read the board back.
11. **HEAD-LOG row.** Add the row to `dev/HEAD-LOG.md`: tag and commit, publish time, gate run id, contents, verdicts, what is not in it, Tech Debt carried.
12. **Papers.** the radar and the owner's needs paper say the release is published and what the next release is.

## Who does what

| Role | Steps |
|------|-------|
| The Head | Tags, publishes and edits the release body (4, 6, 7) |
| The builder | Supplies the zip and its digest (5) |
| The release-branch owner | Builds the release branch and notes (1, 2) |
| The board keeper | Keeps the board, the HEAD-LOG text and the papers (10, 11, 12) |
| Whoever verifies | Gate, download check and asset check (3, 8, 9) |
