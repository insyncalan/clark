"""Vendor the pinned Preact and signals into vendor/preact/ (BL-256; development only).

Run: python3 -I dev/tools/vendor_preact.py [FOLDER]      (FOLDER: where dev/tools/fetch_preact.sh left the tarballs,
                                                          default ~/Downloads/preact-vendor)
     python3 dev/tools/vendor_preact.py --check          (the vendored files match manifest.json; writes nothing)

Each tarball is checked against the SHA-256 pinned below before it is opened. The tarballs are untrusted data: they are
read with tarfile, only the regular files named in FILES are read out of them (never extracted as a tree, so no path
in them decides where anything is written), and nothing in them is run. The files are written under their own fixed
names, and manifest.json records the versions, the tarballs' SHA-256s and each file's SHA-256, which
tests/test_vendor_preact.py checks. To move to a new version: fetch it with fetch_preact.sh, change PINS, run this,
rebuild the page, and commit the folder, the manifest and the page together. Standard library only.
"""
import hashlib
import json
import sys
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VENDOR = REPO / "vendor" / "preact"
MANIFEST = VENDOR / "manifest.json"
DEFAULT_FROM = Path("~/Downloads/preact-vendor").expanduser()

# against the registry's SHA-512 and by the coordinator on disk.
PINS = {
    "preact": ("preact", "10.29.8", "preact-10.29.8.tgz",
               "b18cb0a457f3d43c7bb30391a74ade7d13e03bc6e77915e061c70c0fe1123299", "2026-08-01"),
    "@preact/signals": ("signals", "2.11.2", "signals-2.11.2.tgz",
                        "616281d8da24cf912ab7525c699e5cda0fb7612bbc8d5d4425a0f62dd1dea962", "2026-09-04"),
    "@preact/signals-core": ("signals-core", "1.14.4", "signals-core-1.14.4.tgz",
                             "26dab47f2289a8ae668fc0af87c86f0fb69508b11ab61e194e8f3ac45cf041a3", "2026-07-07"),
}
# What the bundle and the type check need, per package (paths inside the tarball's package/ folder).
FILES = {
    "preact": ["LICENSE", "dist/preact.module.js", "hooks/dist/hooks.module.js",
               "jsx-runtime/dist/jsxRuntime.module.js", "src/index.d.ts", "src/jsx.d.ts", "src/dom.d.ts",
               "hooks/src/index.d.ts", "jsx-runtime/src/index.d.ts"],
    "@preact/signals": ["LICENSE", "dist/signals.module.js", "dist/signals.d.ts"],
    "@preact/signals-core": ["LICENSE", "dist/signals-core.module.js", "dist/signals-core.d.ts"],
}
# The specifiers the dashboard's modules may import, and the vendored file each one is (build_dashboard_js.py's
# esbuild aliases and dev/jsconfig.json's paths are written from this).
MODULES = {
    "preact": "preact/dist/preact.module.js",
    "preact/hooks": "preact/hooks/dist/hooks.module.js",
    "preact/jsx-runtime": "preact/jsx-runtime/dist/jsxRuntime.module.js",
    "@preact/signals": "signals/dist/signals.module.js",
    "@preact/signals-core": "signals-core/dist/signals-core.module.js",
}


class VendorError(RuntimeError):
    """A tarball is missing, doesn't match its pin, or lacks a file the bundle needs."""


def sha256(data):
    """The SHA-256 of `data`, as hex."""
    return hashlib.sha256(data).hexdigest()


def read_pinned(tgz, want):
    """The bytes of `tgz`, refused unless their SHA-256 is `want`."""
    if not tgz.is_file():
        raise VendorError(f"{tgz} isn't there: run dev/tools/fetch_preact.sh first")
    data = tgz.read_bytes()
    if sha256(data) != want:
        raise VendorError(f"{tgz.name}: SHA-256 {sha256(data)} is not the pinned {want}; nothing was written")
    return data


def members(data, names):
    """{name: bytes} for each of `names` (inside package/), read from the tarball `data`; regular files only."""
    import io
    out = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for name in names:
            try:
                m = tar.getmember("package/" + name)
            except KeyError:
                raise VendorError(f"package/{name} isn't in the tarball") from None
            if not m.isreg():
                raise VendorError(f"package/{name} isn't a regular file")
            out[name] = tar.extractfile(m).read()
    return out


def vendor(src=DEFAULT_FROM, dest=VENDOR):
    """Check every tarball, then write the files and manifest.json into `dest`. Returns the manifest."""
    got = {}
    for pkg, pin in PINS.items():
        got[pkg] = members(read_pinned(Path(src) / pin[2], pin[3]), FILES[pkg])   # every pin checked before anything is written
    manifest = {"packages": {}, "files": {}, "modules": MODULES}
    for pkg, (folder, version, tgz, pin, released) in PINS.items():
        manifest["packages"][pkg] = {"version": version, "released": released, "licence": "MIT", "folder": folder,
                                     "tarball": f"https://registry.npmjs.org/{pkg}/-/{tgz}", "sha256": pin}
        for name, data in got[pkg].items():
            path = Path(dest) / folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            manifest["files"][f"{folder}/{name}"] = sha256(data)
    Path(dest, "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def problems(dest=VENDOR):
    """What differs between `dest` and its manifest: a missing, changed or extra file, or a module outside it."""
    dest = Path(dest)
    try:
        manifest = json.loads((dest / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return [f"manifest.json: {e}"]
    out, want = [], manifest.get("files", {})
    for name, h in sorted(want.items()):
        p = dest / name
        if not p.is_file():
            out.append(f"missing: {name}")
        elif sha256(p.read_bytes()) != h:
            out.append(f"changed: {name}")
    have = {p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file()} - {"manifest.json"}
    out += [f"extra: {n}" for n in sorted(have - set(want))]
    out += [f"module {k} is not a vendored file: {v}" for k, v in sorted(manifest.get("modules", {}).items()) if v not in want]
    return out


def main(argv):
    """Vendor from the folder in `argv` (or check with --check); the exit code."""
    if argv[:1] == ["--check"]:
        p = problems()
        print("\n".join(p) or "vendor/preact matches its manifest.")
        return 1 if p else 0
    try:
        m = vendor(Path(argv[0]).expanduser() if argv else DEFAULT_FROM)
    except VendorError as e:
        print(f"vendor_preact: {e}", file=sys.stderr)
        return 1
    print(f"vendor_preact: {len(m['files'])} files from {len(m['packages'])} packages written to "
          f"{VENDOR.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
