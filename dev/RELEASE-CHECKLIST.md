# Release checklist

One page. The Head runs a release; each step has a name, a check and a place to see it. Only a HIGH finding blocks a release; every MEDIUM and LOW is ticketed (Tech Debt, with a Severity label, on the board) before the cut.

1. **Cut from the release branch.** Branch `release-X.Y.Z` from current `main`; the version is bumped in one commit. Check: `git log` shows one version commit on top of main.
2. **Gate green.** The release pull request's "Tests passed" is green on the exact commit that will be tagged, with macOS required on release branches. Check: the run id is written in the HEAD-LOG row.
3. **Notes.** `dev/release-notes/X.Y.Z-plain.md`: plain words, British English, no persona or branch names, no line starting with the product name, every bullet backed by code on the tagged commit. Check: the plain-words and no-real-names tests pass.
4. **Tag and build the zip from the tag.** Build `clark-X.Y.Z-mac.zip` from the tagged commit, never from a working folder. Check: the tag points at the gate commit.
5. **Attach the zip AND its SHA-256 to the release.** Put the digest in the release body, and the command to check it: `shasum -a 256 clark-X.Y.Z-mac.zip`. Every zip in the release has its digest in the notes.
6. **Sign it** (once the signing key exists). Attach the signature beside the zip. Until then the digest is only as trustworthy as the page it is on; say so in the body.
7. **Verify the download.** Download the zip from the release page and compare its digest with the body. Check: they match.
8. **Board.** Every item in the release is State Shipped, with the Release field set to this version; items that did not make it are moved to the next release. Check: read the board back.
9. **HEAD-LOG row.** Add the row to `dev/HEAD-LOG.md`: tag and commit, publish time, gate run id, contents, verdicts, what is not in it, Tech Debt carried.
10. **Papers.** RADAR and Needs Alan say the release is published and what the next release is.

Who does what: the Head tags, publishes and edits the release body; the builder supplies the zip and its digest; Wanda builds the release branch and notes; Friday keeps the board, the HEAD-LOG text and the papers.
