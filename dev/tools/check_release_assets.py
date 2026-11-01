"""Fail when a published GitHub release has no download attached (the v0.3.0 and v0.4.0 gap).

Run by the Head after publishing, and before saying a release is done:
    python3 dev/tools/check_release_assets.py            # every published release
    python3 dev/tools/check_release_assets.py v0.4.0     # one tag

It reads only `gh api repos/<owner>/<repo>/releases` (REST, no GraphQL). A release passes when it has an asset named
clark-<version>-mac.zip that is not empty. Exit 0 when all pass, 1 when any fails, 2 when the releases can't be read.
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


def problems(releases, tags=None):
    """One plain line for each published release (or the named tags) that lacks its clark-X.Y.Z-mac.zip asset."""
    out = []
    for r in releases:
        tag = r.get("tag_name", "")
        if r.get("draft") or _ver(tag) is None or _ver(tag) < FIRST_CHECKED or (tags and tag not in tags):
            continue
        want = f"clark-{tag.lstrip('v')}-mac.zip"
        have = {a.get("name"): a.get("size", 0) for a in r.get("assets", [])}
        if not have.get(want):
            out.append(f"{tag}: no {want} attached. Build it (dev/tools/package.py mac --release), then attach it and "
                       f"its SHA-256 to the release.")
    return out


def main(argv=None):
    tags = set(argv if argv is not None else sys.argv[1:])
    run = subprocess.run(["gh", "api", f"repos/{REPO}/releases?per_page=100"], capture_output=True, text=True, encoding="utf-8")
    if run.returncode != 0:
        print("The releases can't be read (is gh signed in?).", file=sys.stderr)
        return 2
    found = problems(json.loads(run.stdout), tags)
    for line in found:
        print(line)
    if not found:
        print("Every published release has its download attached.")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
