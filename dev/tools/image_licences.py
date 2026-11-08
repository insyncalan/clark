"""The licence papers for the container image the Windows zip carries (#637; development only).

Run: python3 dev/tools/image_licences.py --image python:3.12.12-slim-bookworm --out DIR
     python3 dev/tools/image_licences.py --status FILE [--copyright FILE] [--pip FILE] --out DIR      (no Docker needed)

The image is the stock, unmodified, pinned Python image: nothing of clark is in it. It holds Debian's minimal packages
(many GPL or LGPL), CPython (PSF-2.0) and OpenSSL (Apache-2.0). Shipping the tar is a distribution of those, so the zip
carries three generated files, written to --out:
  THIRD-PARTY-IMAGE.txt       every package with its version and licences, then the packages whose licence asks for the
                              source, then the offer or source text
  image-sbom.cdx.json         the same list as a CycloneDX 1.5 software bill of materials
  image-source-packages.txt   one line per Debian SOURCE package (name and version) whose binaries are GPL or LGPL: the
                              list the source folder in the zip is made from (apt-get source NAME=VERSION)
--image runs the image once with Docker and reads /var/lib/dpkg/status, every /usr/share/doc/*/copyright and pip list.
--status/--copyright/--pip read the same three things from files (the copyright file holds each file after a line
"@@@ /usr/share/doc/NAME/copyright"). Engineering reading, not legal advice: the wording of the notice is the lawyer's.
Standard library only.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

COPYLEFT = re.compile(r"\b(?:A?GPL|LGPL)(?:-?\d(?:\.\d)?)?(?:\+|-only|-or-later)?\b|GNU (?:Lesser |Library |Affero )?General Public", re.I)
SEPARATOR = "@@@ "
DUMP = ('cat /var/lib/dpkg/status; echo "@@@@@@STATUS-END"; for f in /usr/share/doc/*/copyright; do echo "@@@ $f"; cat "$f"; done; '
        'echo "@@@@@@COPYRIGHT-END"; python3 -m pip list --format=json 2>/dev/null || echo "[]"')


def parse_status(text):
    """The installed packages in a dpkg status file: [{name, version, source, source_version, arch}], sorted by name."""
    found = []
    for block in re.split(r"\n\s*\n", text.strip()):
        fields = {}
        for line in block.splitlines():
            if line[:1] in (" ", "\t") or ":" not in line:
                continue
            key, _, value = line.partition(":")
            fields[key.strip().lower()] = value.strip()
        if "package" not in fields or "installed" not in fields.get("status", ""):
            continue
        if fields["status"].split()[-1] != "installed":
            continue
        source = fields.get("source", fields["package"])
        match = re.match(r"(\S+)(?:\s+\(([^)]+)\))?", source)
        found.append({"name": fields["package"], "version": fields.get("version", ""), "arch": fields.get("architecture", ""),
                      "source": match.group(1), "source_version": match.group(2) or fields.get("version", "")})
    return sorted(found, key=lambda p: p["name"])


def split_copyright(text):
    """{package name: its copyright file} from the stream the image dump prints."""
    files, name, lines = {}, None, []
    for line in text.splitlines():
        if line.startswith(SEPARATOR):
            if name:
                files[name] = "\n".join(lines)
            m = re.match(r"@@@ /usr/share/doc/([^/]+)/copyright", line)
            name, lines = (m.group(1) if m else None), []
        else:
            lines.append(line)
    if name:
        files[name] = "\n".join(lines)
    return files


def licences_of(copyright_text):
    """The licence names a copyright file states: DEP-5 'License:' lines, or the well-known names found in free text."""
    if not copyright_text:
        return []
    names = set()
    for m in re.finditer(r"^License:\s*(.+)$", copyright_text, re.M):
        for part in re.split(r"\s+(?:and|or)\s+|,", m.group(1)):
            part = part.strip()
            if part:
                names.add(part)
    if not names:
        for label, rx in (("GPL", r"GNU General Public"), ("LGPL", r"GNU (?:Lesser|Library) General Public"),
                          ("Apache-2.0", r"Apache License"), ("MIT", r"\bMIT\b|Expat"), ("BSD", r"\bBSD\b"),
                          ("PSF-2.0", r"Python Software Foundation"), ("public-domain", r"public[- ]domain")):
            if re.search(rx, copyright_text, re.I):
                names.add(label)
    return sorted(names)


def needs_source(licences, copyright_text=""):
    """True when a package's licence asks for source or a written offer: GPL, LGPL or AGPL in any version."""
    return any(COPYLEFT.search(name) for name in licences) or (not licences and bool(COPYLEFT.search(copyright_text or "")))


def describe(packages, copyrights):
    """Each package with `licences` (a list; empty when no copyright file) and `copyleft` (True when source is owed)."""
    out = []
    for pkg in packages:
        text = copyrights.get(pkg["name"], "")
        lic = licences_of(text)
        # No copyright file at all: the licence is unknown, so the source is listed too (never silently left out).
        out.append(dict(pkg, licences=lic, copyleft=needs_source(lic, text) or not text, has_copyright=bool(text)))
    return out


def source_packages(described):
    """[(source name, source version)] for the Debian source packages behind the copyleft binaries, sorted, no repeats."""
    return sorted({(p["source"], p["source_version"]) for p in described if p["copyleft"]})


def render_source_list(described):
    return "".join(f"{name} {version}\n" for name, version in source_packages(described))


def render_sbom(described, pip=(), base=""):
    """A CycloneDX 1.5 document (a dict): the Debian packages, the pip packages and the base image reference."""
    components = []
    for p in described:
        comp = {"type": "library", "name": p["name"], "version": p["version"],
                "purl": f"pkg:deb/debian/{p['name']}@{p['version']}?arch={p['arch']}"}
        if p["licences"]:
            comp["licenses"] = [{"license": {"name": name}} for name in p["licences"]]
        components.append(comp)
    for item in pip:
        components.append({"type": "library", "name": item["name"], "version": item["version"],
                           "purl": f"pkg:pypi/{item['name'].lower()}@{item['version']}"})
    meta = {"component": {"type": "container", "name": base or "image", "version": ""}}
    return {"bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1, "metadata": meta, "components": components}


def render_third_party(described, pip=(), base=""):
    """THIRD-PARTY-IMAGE.txt as one string."""
    lines = ["Third-party software in the container image", "",
             f"Base image: {base or 'not named'}. It is the unmodified official image: nothing of clark is in it. Each package",
             "keeps its own licence, which applies to that package and not to clark's own code (see LICENSE and NOTICE.md).",
             "CPython is under the PSF-2.0 licence and OpenSSL under Apache-2.0; Debian packages are listed below.", "",
             f"Debian packages ({len(described)}): name, version, licences", ""]
    for p in described:
        lic = ", ".join(p["licences"]) if p["licences"] else ("see /usr/share/doc/%s/copyright in the image" % p["name"])
        lines.append(f"  {p['name']} {p['version']}: {lic}")
    if pip:
        lines += ["", f"Python packages ({len(pip)}):", ""] + [f"  {i['name']} {i['version']}" for i in pip]
    owed = [p for p in described if p["copyleft"]]
    lines += ["", f"Packages under the GPL or LGPL, whose source is owed ({len(owed)}):", ""]
    lines += [f"  {p['name']} {p['version']} (source package {p['source']} {p['source_version']})" for p in owed]
    lines += ["", "The source of these packages is in the folder image-source/ of the zip, one Debian source package each,",
              "listed in image-source-packages.txt. The same source is on Debian's mirrors (https://deb.debian.org/debian).", ""]
    return "\n".join(lines)


def parse_dump(text):
    """(status text, {name: copyright}, pip list) from the stream the image dump prints."""
    status, _, rest = text.partition("@@@@@@STATUS-END")
    copy, _, pip = rest.partition("@@@@@@COPYRIGHT-END")
    try:
        items = json.loads(pip.strip() or "[]")
    except ValueError:
        items = []
    return status, split_copyright(copy), [i for i in items if isinstance(i, dict) and "name" in i and "version" in i]


def write_all(out, status, copyrights, pip, base=""):
    """Write the three files into `out` (made if missing); return the described packages."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    described = describe(parse_status(status), copyrights)
    (out / "THIRD-PARTY-IMAGE.txt").write_text(render_third_party(described, pip, base), encoding="utf-8")
    (out / "image-sbom.cdx.json").write_text(json.dumps(render_sbom(described, pip, base), indent=2) + "\n", encoding="utf-8")
    (out / "image-source-packages.txt").write_text(render_source_list(described), encoding="utf-8")
    return described


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--image")
    ap.add_argument("--status")
    ap.add_argument("--copyright")
    ap.add_argument("--pip")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    if args.image:
        run = subprocess.run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "sh", args.image, "-c", DUMP],
                             capture_output=True, text=True)
        if run.returncode:
            print("docker could not read the image: " + run.stderr.strip()[:200], file=sys.stderr)
            return 1
        status, copyrights, pip = parse_dump(run.stdout)
    elif args.status:
        status = Path(args.status).read_text(encoding="utf-8", errors="replace")
        copyrights = split_copyright(Path(args.copyright).read_text(encoding="utf-8", errors="replace")) if args.copyright else {}
        pip = json.loads(Path(args.pip).read_text(encoding="utf-8")) if args.pip else []
    else:
        ap.error("name --image or --status")
    described = write_all(args.out, status, copyrights, pip, args.image or "")
    if not described:
        print("no installed packages found: nothing written is complete", file=sys.stderr)
        return 1
    print(f"{len(described)} packages, {len(source_packages(described))} source packages owed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
