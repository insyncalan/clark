"""Turn what is inside the Python image into THIRD-PARTY-IMAGE.txt and a package list (item 637, v1.1 Windows download).

Run on a computer that has Docker, with the image named in docker/compose.yaml loaded:
    python3 dev/tools/image_licences.py --image python:3.12.12-slim-bookworm --out build/image-licences

It asks the image three things with `docker run --rm --entrypoint` (nothing is written inside the image):
the Debian packages (dpkg-query), the Python packages (pip list --format=json) and each package's copyright file.
It writes THIRD-PARTY-IMAGE.txt (readable), image-packages.json (the list, one entry per package) and image-packages.txt (one
line per package, what a test compares). The pure parts (parse_dpkg, parse_pip, copyright_licences, render_text) are tested
with made-up data in tests/test_image_licences.py; the docker calls are not run by the tests.
Exit 0 when written, 2 when Docker cannot be run or answers nothing.
"""
import json
import os
import re
import subprocess
import sys

DOCKER_TIMEOUT = 300          # seconds one docker call may take
COPYLEFT = re.compile(r"\b(?:A?GPL|LGPL)", re.I)
LICENSE_LINE = re.compile(r"^License:\s*(\S.*?)\s*$", re.M)


def parse_dpkg(text):
    """[(package, version, source)] from `dpkg-query -W -f='${binary:Package}\\t${Version}\\t${source:Package}\\n'`, sorted.
    A line that is not three tab-separated fields is skipped."""
    rows = []
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].strip() and parts[1].strip():
            rows.append((parts[0].strip(), parts[1].strip(), parts[2].strip() or parts[0].strip()))
    return sorted(set(rows))


def parse_pip(text):
    """[(name, version)] from `pip list --format=json`, sorted by lower-case name. An unreadable answer gives []."""
    try:
        data = json.loads(text)
    except ValueError:
        return []
    if not isinstance(data, list):
        return []
    rows = [(str(d["name"]), str(d["version"])) for d in data if isinstance(d, dict) and "name" in d and "version" in d]
    return sorted(rows, key=lambda r: r[0].lower())


def copyright_licences(text):
    """The licence names a Debian copyright file states, in order of first appearance, e.g. ['GPL-2+', 'LGPL-2.1+'].
    Only lines that start with `License:` count; a file in the old free-text form gives []. Alternatives joined by `or`/`and`
    stay as written."""
    seen = []
    for name in LICENSE_LINE.findall(text):
        if name not in seen:
            seen.append(name)
    return seen


def is_copyleft(licences):
    """True when any licence name is a GPL, LGPL or AGPL form (those need the source or an offer)."""
    return any(COPYLEFT.search(n) for n in licences)


def package_line(name, version):
    return f"{name} {version}"


def render_text(image, debian, pip, licences):
    """THIRD-PARTY-IMAGE.txt. `licences` maps a Debian package name to its list of licence names ([] = not stated in
    machine-readable form, shown as 'see /usr/share/doc/<package>/copyright in the image')."""
    out = [f"Third-party software in the container image {image}", "",
           "This list was generated from the image itself, not written by hand. The image holds only the Python runtime; "
           "clark's own code is not in it. Each package keeps its own licence.", "",
           "## Debian packages", ""]
    source_needed = []
    for name, version, source in debian:
        lic = licences.get(name, [])
        shown = ", ".join(lic) if lic else f"see /usr/share/doc/{name}/copyright in the image"
        out.append(f"{name} {version} (source package {source}): {shown}")
        if is_copyleft(lic) or not lic:
            source_needed.append(source)
    out += ["", "## Python packages", ""]
    out += [package_line(n, v) for n, v in pip] or ["(none)"]
    out += ["", "## Source packages to ship or offer (GPL or LGPL, or not machine-readable)", ""]
    out += sorted(set(source_needed)) or ["(none)"]
    return "\n".join(out) + "\n"


def packages_txt(debian, pip):
    """image-packages.txt: one line per package, `deb <name> <version>` or `pip <name> <version>`, sorted."""
    return "".join(f"deb {n} {v}\n" for n, v, _ in debian) + "".join(f"pip {n} {v}\n" for n, v in pip)


def packages_json(image, debian, pip):
    return json.dumps({"image": image,
                       "debian": [{"name": n, "version": v, "source": s} for n, v, s in debian],
                       "pip": [{"name": n, "version": v} for n, v in pip]}, indent=2, sort_keys=True) + "\n"


def _docker(image, *cmd):
    r = subprocess.run(["docker", "run", "--rm", "--entrypoint", cmd[0], image, *cmd[1:]],
                       capture_output=True, text=True, encoding="utf-8", timeout=DOCKER_TIMEOUT)
    if r.returncode != 0:
        raise RuntimeError(f"docker answered {r.returncode} for {' '.join(cmd[:2])}: {r.stderr.strip()[:200]}")
    return r.stdout


def main(argv):
    image, out_dir = None, "image-licences"
    args = list(argv)
    while args:
        a = args.pop(0)
        if a == "--image" and args:
            image = args.pop(0)
        elif a == "--out" and args:
            out_dir = args.pop(0)
        else:
            print("Usage: image_licences.py --image <name:tag> [--out <folder>]", file=sys.stderr)
            return 2
    if not image:
        print("Usage: image_licences.py --image <name:tag> [--out <folder>]", file=sys.stderr)
        return 2
    try:
        debian = parse_dpkg(_docker(image, "dpkg-query", "-W", "-f=${binary:Package}\t${Version}\t${source:Package}\n"))
        pip = parse_pip(_docker(image, "python3", "-m", "pip", "list", "--format=json"))
        licences = {}
        for name, _v, _s in debian:
            base = name.split(":")[0]
            try:
                licences[name] = copyright_licences(_docker(image, "cat", f"/usr/share/doc/{base}/copyright"))
            except RuntimeError:
                licences[name] = []
    except (OSError, RuntimeError, subprocess.SubprocessError) as e:
        print(f"Could not read the image: {e}", file=sys.stderr)
        return 2
    if not debian:
        print("The image gave no Debian package list. Nothing was written.", file=sys.stderr)
        return 2
    os.makedirs(out_dir, exist_ok=True)
    for fname, body in (("THIRD-PARTY-IMAGE.txt", render_text(image, debian, pip, licences)),
                        ("image-packages.txt", packages_txt(debian, pip)),
                        ("image-packages.json", packages_json(image, debian, pip))):
        with open(os.path.join(out_dir, fname), "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
    print(f"Wrote 3 files to {out_dir}: {len(debian)} Debian and {len(pip)} Python packages.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
