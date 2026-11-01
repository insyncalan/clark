"""Rebuild vendor/manifest.json, the record of clark's bundled Python libraries (#34; development only).

Run: python3 dev/tools/vendor_manifest.py [--check]
Writes each library's version and licence, and the SHA-256 of every file in vendor/ except the manifest, __pycache__
and the front-end folders (vendor/preact/, vendor/tiptap/ and vendor/fonts/ keep their own manifests). Run it only when a library is
deliberately upgraded: replace the folder, change LIBRARIES, run this, run the tests, and commit the library and the
manifest together. --check writes nothing and exits 1 if the folder doesn't match. Standard library only.
Adapted from creaite v2.6.9's dev/tools/vendor_manifest.py (BL-239), without creaite's doctor and paths modules.
"""
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VENDOR = REPO / "vendor"
MANIFEST = "manifest.json"
OWN_MANIFESTS = ("preact", "tiptap", "fonts")    # front-end folders and the font, each checked against its own manifest
ABOUT = ("SHA-256 of every bundled Python library file, with each library's version and licence (#34). Rebuilt only by "
         "dev/tools/vendor_manifest.py when a library is deliberately upgraded.")
# library: (version, licence, its licence file in vendor/licenses/, where it came from)
LIBRARIES = {
    "openpyxl": ("3.1.5", "MIT", "licenses/openpyxl-3.1.5-LICENSE.txt",
                 "creaite v2.6.9 (db5adb2) system/scripts/vendor/openpyxl/"),
    "et_xmlfile": ("2.0.0", "MIT", "licenses/et_xmlfile-2.0.0-LICENSE.txt",
                   "creaite v2.6.9 (db5adb2) system/scripts/vendor/et_xmlfile/"),
    "ed25519_verify": ("1", "CC0-1.0", "licenses/ed25519_verify-1-LICENSE.txt",
                       "written for clark from RFC 8032 section 5.1.7 (verify only; the signer is in dev/tools)"),
}


def _skipped(rel):
    """True for what the manifest doesn't cover: itself, compiled caches and the front-end folders."""
    parts = rel.split("/")
    return rel == MANIFEST or "__pycache__" in parts or parts[0] in OWN_MANIFESTS or rel.endswith(".pyc")


def vendor_files(folder=VENDOR):
    """{relative path: SHA-256} for every file the manifest covers in `folder`, sorted by path."""
    folder = Path(folder)
    out = {}
    for p in sorted(folder.rglob("*")):
        rel = p.relative_to(folder).as_posix()
        if p.is_file() and not _skipped(rel):
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def manifest(folder=VENDOR):
    """The manifest for `folder` as it is now."""
    libs = {name: {"version": v, "licence": lic, "licence_file": f, "from": src}
            for name, (v, lic, f, src) in LIBRARIES.items()}
    return {"about": ABOUT, "libraries": libs, "files": vendor_files(folder)}


def problems(folder=VENDOR):
    """What differs between `folder` and its manifest: a missing, changed or extra file, or a library without its files."""
    folder = Path(folder)
    try:
        want = json.loads((folder / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return [f"unreadable: {MANIFEST} ({e})"]
    files, have = want.get("files", {}), vendor_files(folder)
    out = [f"missing: {n}" for n in sorted(set(files) - set(have))]
    out += [f"changed: {n}" for n in sorted(set(files) & set(have)) if files[n] != have[n]]
    out += [f"extra: {n}" for n in sorted(set(have) - set(files))]
    for name, lib in sorted(want.get("libraries", {}).items()):
        if lib.get("licence_file") not in files:
            out.append(f"library {name} has no licence file")
        if f"{name}/__init__.py" not in files:
            out.append(f"library {name} has no files")
    return out


def main(argv):
    """Rebuild the manifest, or check it with --check; the exit code."""
    if argv[:1] == ["--check"]:
        p = problems()
        print("\n".join(p) or "vendor/ matches its manifest.")
        return 1 if p else 0
    if argv:
        print(__doc__)
        return 2
    m = manifest()
    (VENDOR / MANIFEST).write_text(json.dumps(m, indent=1) + "\n", encoding="utf-8")
    print(f"Wrote vendor/{MANIFEST}: {len(m['files'])} files, {len(m['libraries'])} libraries.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
