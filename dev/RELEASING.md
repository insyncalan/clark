# Releasing clark

The release has no workflow: the download is built by hand with `dev/tools/package.py` and attached by hand.
Every step below is done before a release is called finished.

1. Cut commit: version in `src/clark/__init__.py`, `dev/release-notes/X.Y.Z-plain.md`, the hand-check sheet.
2. Tag `vX.Y.Z` on that commit and publish the GitHub release with the notes.
3. Build from a clean checkout of the tag:
   `python3 dev/tools/package.py mac --release --notes dev/release-notes/X.Y.Z-plain.md --out DIR`
   (the same commit gives the same bytes: build twice and compare if in doubt).
4. **Attach `clark-X.Y.Z-mac.zip` and its SHA-256 to the GitHub release** (the digest goes in the release notes).
5. **Run `python3 dev/tools/check_release_assets.py vX.Y.Z`.** It must print that the download is attached. A release
   without it is not finished.
