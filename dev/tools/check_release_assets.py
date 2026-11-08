"""Fail when a published GitHub release has no download attached (the v0.3.0 and v0.4.0 gap).

Run by whoever verifies the release (step 20 of dev/RELEASING.md), after publishing and before saying a release is done:
    python3 dev/tools/check_release_assets.py            # every published release
    python3 dev/tools/check_release_assets.py v0.4.0     # one tag
    python3 dev/tools/check_release_assets.py --repo owner/name v0.4.0     # releases kept in another repository

It reads only `gh api repos/<owner>/<repo>/releases` (REST, no GraphQL), page by page, from insyncalan/clark unless
`--repo owner/name` (or `--repo=owner/name`) names another repository. A release passes when it has an asset
named clark-<version>-mac.zip that is not empty, is marked Pre-release, has "(Beta)" in its title and "Beta" in its text.
From 0.5.0 on it must also carry the zip's own SHA-256 in its text (the 64-character digest GitHub reports for the zip asset;
when GitHub gives no digest for the asset, as on an older release, any 64-character SHA-256 in the text passes and the check says
so), and its zip must have been attached before the release was published (the order in dev/RELEASING.md: build, attach, launch, then publish; 0.3.0 and 0.4.0 got their zips afterwards).
Once RELEASE_PUBLIC_KEY in src/clark/updates.py is a real key (not the placeholder), the release must also carry
clark-<version>-mac.zip.sig (dev/RELEASING.md step 7a), and that file must verify over the zip's bytes with that key
(updates.check_signature); a missing, wrong-length or non-verifying .sig fails. While the key is still the placeholder the app
asks for no signature, so the check does not either (it says so on standard error).
A tag named on the command line that matches no published release (a typo, or a release that is still a draft) fails too.
Exit 0 when all pass, 1 when any fails, 2 when the releases can't be read (gh missing, not signed in, no answer within
60 seconds, or an unreadable answer).
The pure check is `problems(releases, tags, notes)`, tested with made-up data.
"""
import json
import os
import re
import subprocess
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[:0] = [os.path.join(_REPO_ROOT, "src"), os.path.join(_REPO_ROOT, "vendor")]
from clark import updates  # noqa: E402  (the release key and the verifier the app itself uses)

REPO = "insyncalan/clark"
REPO_FORM = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
GH_TIMEOUT = 60              # seconds one `gh api` call may take before the check gives up (exit 2)
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


def _asset(r, name):
    for a in r.get("assets", []):
        if a.get("name") == name:
            return a
    return None


def _signature_lines(r, tag, want, notes, fetch, key):
    """The lines for a release whose .sig is missing or does not verify against the release key (none while the key is the placeholder)."""
    if not updates.signature_required(key):
        return []
    sig_name = want + updates.SIGNATURE_SUFFIX
    sig, zipped = _asset(r, sig_name), _asset(r, want)
    if sig is None:
        return [f"{tag}: the release has no {sig_name}, so the app would refuse this update as unsigned. The owner signs the zip "
                f"(`python3 dev/tools/sign_release.py sign {want}`, dev/RELEASING.md step 7a), attaches the .sig beside the zip, "
                f"then run this check again."]
    if fetch is None:
        return []
    sig_bytes, zip_bytes = fetch(sig), fetch(zipped)
    if sig_bytes is None or zip_bytes is None:
        return [f"{tag}: {sig_name} or {want} could not be downloaded to check the signature. Try again in a minute."]
    try:
        updates.check_signature(zip_bytes, sig_bytes, key)
    except updates.UpdateError as e:
        return [f"{tag}: {sig_name} does not verify over {want} with the release key ({e.key}: {e}). Sign the zip again with "
                f"the release key (dev/RELEASING.md step 7a) and replace the .sig on the release."]
    return []


def _rules(r, tag, want, notes=None, fetch=None, key=None):
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
    out.extend(_signature_lines(r, tag, want, notes, fetch, key))
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


def problems(releases, tags=None, notes=None, fetch=None, key=None):
    """One plain line for each published release (or the named tags) that lacks its clark-X.Y.Z-mac.zip asset, and one for each
    named tag that matches no published release. `fetch(asset)` returns an asset's bytes (None when it can't be read); `key` is a
    public key for tests (None: the one built into the app). Without `fetch` a signature is only checked to be attached."""
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
            out.extend(_rules(r, tag, want, notes, fetch, key))
            continue
        if want in have:
            why = f"{want} is on the release but it is empty."
        elif have:
            why = f"the release has no file named {want}; it has {', '.join(sorted(str(n) for n in have))}."
        else:
            why = f"the release has no download; {want} is missing."
        out.append(f"{tag}: {why} {_fix(tag)}")
    return out


def _download(repo):
    """A function that returns an asset's bytes through `gh api` (None when gh can't give them)."""
    def fetch(asset):
        try:
            run = subprocess.run(["gh", "api", "-H", "Accept: application/octet-stream",
                                  f"repos/{repo}/releases/assets/{asset.get('id')}"], capture_output=True, timeout=GH_TIMEOUT * 5)
        except (subprocess.TimeoutExpired, OSError):
            return None
        return run.stdout if run.returncode == 0 else None
    return fetch


def _args(argv):
    """(repository, tags) from the command line, or None after printing a plain line when --repo is not owner/name."""
    repo, tags, i = REPO, set(), 0
    while i < len(argv):
        a = argv[i]
        if a == "--repo" or a.startswith("--repo="):
            if a == "--repo":
                i += 1
            repo = argv[i] if a == "--repo" and i < len(argv) else a[7:]
            if not REPO_FORM.fullmatch(repo) or repo.split("/")[0] in (".", "..") or repo.split("/")[1] in (".", ".."):
                print("--repo needs the repository as owner/name, for example --repo insyncalan/clark.", file=sys.stderr)
                return None
        else:
            tags.add(a)
        i += 1
    return repo, tags


def main(argv=None):
    parsed = _args(argv if argv is not None else sys.argv[1:])
    if parsed is None:
        return 2
    repo, tags = parsed
    releases = []
    for page in range(1, 50):
        try:
            run = subprocess.run(["gh", "api", f"repos/{repo}/releases?per_page=100&page={page}"], capture_output=True,
                                 text=True, encoding="utf-8", timeout=GH_TIMEOUT)
        except subprocess.TimeoutExpired:
            print(f"The releases can't be read: GitHub did not answer within {GH_TIMEOUT} seconds. Check the network "
                  f"connection, then try again.", file=sys.stderr)
            return 2
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
    if not updates.signature_required():
        print("RELEASE_PUBLIC_KEY is still the placeholder, so no release's .sig was asked for or checked.", file=sys.stderr)
    found = problems(releases, tags, notes, _download(repo))
    for line in found:
        print(line)
    for line in notes:
        print("Note: " + line)
    if not found:
        print("Every published release has its download attached.")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
