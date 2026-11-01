"""Fail when a published GitHub release has no download attached (the v0.3.0 and v0.4.0 gap).

Run by whoever verifies the release (step 20 of dev/RELEASING.md), after publishing and before saying a release is done:
    python3 dev/tools/check_release_assets.py            # every published release
    python3 dev/tools/check_release_assets.py v0.4.0     # one tag

It reads only `gh api repos/<owner>/<repo>/releases` (REST, no GraphQL), page by page. A release passes when it has an asset
named clark-<version>-mac.zip that is not empty, is marked Pre-release, has "(Beta)" in its title and "Beta" in its text.
From 0.5.0 on it must also carry the zip's own SHA-256 in its text (the 64-character digest GitHub reports for the zip asset;
when GitHub gives no digest for the asset, as on an older release, any 64-character SHA-256 in the text passes and the check says
so), and its zip must have been attached before the release was published (the order in dev/RELEASING.md: build, attach, launch, then publish; 0.3.0 and 0.4.0 got their zips afterwards).
A tag named on the command line that matches no published release (a typo, or a release that is still a draft) fails too.
Exit 0 when all pass, 1 when any fails, 2 when the releases can't be read (gh missing, not signed in, or an unreadable answer).
The pure check is `problems(releases, tags, notes)`, tested with made-up data.
"""
import json
import re
import subprocess
import sys

REPO = "insyncalan/clark"
FIRST_CHECKED = (0, 1, 0)
FIRST_ORDERED = (0, 5, 0)    # the first release cut with the build-attach-launch-then-publish steps
DIGEST = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])")


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


def _zip_digest(r, want):
    """The SHA-256 GitHub reports for the zip asset (lower case, 64 characters), or None when it gives none."""
    for a in r.get("assets", []):
        d = a.get("digest") or ""
        if a.get("name") == want and d.lower().startswith("sha256:") and DIGEST.fullmatch(d[7:]):
            return d[7:].lower()
    return None


def _rules(r, tag, want, notes=None):
    """The lines for a release that has its zip but breaks a release rule (Beta, pre-release, digest, publish order).
    A line added to `notes` (when given) is not a failure: it says a check was done in its looser form."""
    out = []
    if not r.get("prerelease"):
        out.append(f"{tag}: the release is not marked Pre-release. Every clark release is a pre-release until version 1.0: "
                   f"edit the release on GitHub and tick Pre-release.")
    if "(Beta)" not in (r.get("name") or ""):
        out.append(f"{tag}: the title does not say (Beta). Edit the release on GitHub and make the title "
                   f"`clark {tag.lstrip('v')} (Beta), Mac`.")
    if "Beta" not in (r.get("body") or ""):
        out.append(f"{tag}: the release text does not say clark is Beta. Edit the release text on GitHub and add the Beta line "
                   f"from the notes file.")
    if _ver(tag) < FIRST_ORDERED:
        return out
    body = r.get("body") or ""
    own = _zip_digest(r, want)
    if not DIGEST.search(body):
        out.append(f"{tag}: the release text has no SHA-256 for {want}. Run `shasum -a 256 {want}` and paste the 64-character "
                   f"line into the release text (dev/RELEASING.md steps 7 and 9).")
    elif own is None:
        if notes is not None:
            notes.append(f"{tag}: GitHub gives no SHA-256 for {want}, so the check could only see that the release text holds "
                         f"some 64-character SHA-256, not that it is the zip's. Run `shasum -a 256 {want}` on the download "
                         f"and compare it with the release text yourself.")
    elif own not in {m.group(0).lower() for m in DIGEST.finditer(body)}:
        out.append(f"{tag}: the SHA-256 in the release text is not the zip's. GitHub says the zip {want} is {own}. Edit the "
                   f"release text on GitHub and put that line in place of the wrong one (dev/RELEASING.md step 9).")
    attached = max((a.get("created_at") or "" for a in r.get("assets", []) if a.get("name") == want), default="")
    if r.get("published_at") and attached > r["published_at"]:
        out.append(f"{tag}: the zip was attached after the release was published. The zip must be attached to the draft and "
                   f"launched for real first, then the release published (dev/RELEASING.md steps 8 to 19). Do not publish "
                   f"the next release until you have followed them in that order.")
    return out


def problems(releases, tags=None, notes=None):
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
            out.extend(_rules(r, tag, want, notes))
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
    releases = []
    for page in range(1, 50):
        try:
            run = subprocess.run(["gh", "api", f"repos/{REPO}/releases?per_page=100&page={page}"], capture_output=True,
                                 text=True, encoding="utf-8")
        except OSError:
            print("The releases can't be read: the gh command was not found. Install the GitHub command line tool (gh), "
                  "run `gh auth login`, then try again.", file=sys.stderr)
            return 2
        if run.returncode != 0:
            print("The releases can't be read (is gh signed in?). Run `gh auth login`, then try again.", file=sys.stderr)
            return 2
        try:
            got = json.loads(run.stdout)
        except ValueError:
            print("The releases can't be read: GitHub's answer was not what the check expects. Try again in a minute.",
                  file=sys.stderr)
            return 2
        releases.extend(got)
        if len(got) < 100:
            break
    notes = []
    found = problems(releases, tags, notes)
    for line in found:
        print(line)
    for line in notes:
        print("Note: " + line)
    if not found:
        print("Every published release has its download attached.")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
