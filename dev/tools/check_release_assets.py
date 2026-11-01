"""Fail when a published GitHub release has no download attached (the v0.3.0 and v0.4.0 gap).

Run by whoever verifies the release (step 20 of dev/RELEASING.md), after publishing and before saying a release is done:
    python3 dev/tools/check_release_assets.py            # every published release
    python3 dev/tools/check_release_assets.py v0.4.0     # one tag

It reads only `gh api repos/<owner>/<repo>/releases` (REST, no GraphQL). A release passes when it has an asset named
clark-<version>-mac.zip that is not empty. A tag named on the command line that matches no published release (a typo, or a
release that is still a draft) fails too. Exit 0 when all pass, 1 when any fails, 2 when the releases can't be read.
The pure check is `problems(releases, tags)`, tested with made-up data.
"""
import json
import subprocess
import sys

REPO = "insyncalan/clark"
FIRST_CHECKED = (0, 1, 0)


def _ver(tag):
    try:
        return tuple(int(p) for p in tag.lstrip("v").split("."))
    except ValueError:
        return None


def _fix(tag):
    """The way to put a missing download right, in full: the build command and where the steps are."""
    version = tag.lstrip("v")
    return (f"Build it again from the tag with `python3 dev/tools/package.py mac --release --notes "
            f"dev/release-notes/{version}-plain.md --out ../zips` and attach it with its SHA-256 as in dev/RELEASING.md "
            f"(steps 5 to 10), then run this check again.")


def problems(releases, tags=None):
    """One plain line for each published release (or the named tags) that lacks its clark-X.Y.Z-mac.zip asset, and one for each
    named tag that matches no published release."""
    out = []
    published = {r.get("tag_name", "") for r in releases if not r.get("draft")}
    for tag in sorted(tags or ()):
        if tag not in published:
            out.append(f"No published release named {tag} was found. Check the tag and that the release is published, "
                       f"not a draft.")
    for r in releases:
        tag = r.get("tag_name", "")
        if r.get("draft") or _ver(tag) is None or _ver(tag) < FIRST_CHECKED or (tags and tag not in tags):
            continue
        want = f"clark-{tag.lstrip('v')}-mac.zip"
        have = {a.get("name"): a.get("size", 0) for a in r.get("assets", [])}
        if have.get(want):
            continue
        if want in have:
            why = f"{want} is on the release but it is empty."
        elif have:
            why = f"the release has no file named {want}; it has {', '.join(sorted(str(n) for n in have))}."
        else:
            why = f"the release has no download; {want} is missing."
        out.append(f"{tag}: {why} {_fix(tag)}")
    return out


def main(argv=None):
    tags = set(argv if argv is not None else sys.argv[1:])
    run = subprocess.run(["gh", "api", f"repos/{REPO}/releases?per_page=100"], capture_output=True, text=True, encoding="utf-8")
    if run.returncode != 0:
        print("The releases can't be read (is gh signed in?). Run `gh auth login`, then try again.", file=sys.stderr)
        return 2
    found = problems(json.loads(run.stdout), tags)
    for line in found:
        print(line)
    if not found:
        print("Every published release has its download attached.")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
