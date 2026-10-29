"""The pinned Tiptap editor and its Markdown extension, for BL-301 part A (development only, needs the internet once per machine).

Run: python3 dev/tools/tiptap.py fetch                  download, check and unpack every pinned package
     python3 dev/tools/tiptap.py bundle [--out FILE]    bundle dev/tiptap/editor.js into one IIFE and print its size
     python3 dev/tools/tiptap.py vendor                 build the ES module into vendor/tiptap/, with
                                                        every bundled package's licence and manifest.json (BL-301 A)
     python3 dev/tools/tiptap.py vendor --check         build it again in memory and compare byte for byte; writes
                                                        nothing (exit 1 when the committed folder differs)

Like dev/tools/esbuild.py: every npm tarball the editor needs (Tiptap, ProseMirror, marked and the rest, the whole
dependency tree resolved once and written in PACKAGES below) is downloaded from the npm registry with urllib, checked
against the SHA-256 written here, and unpacked to dev/.cache/tiptap/<PINNED>/node_modules/<name>/. A tarball whose hash
differs is refused and nothing of it is written. Nothing resolves a version at run time: no npm, no Node, no lock file.
The bundle is made by the pinned esbuild (dev/tools/esbuild.py), with NODE_PATH pointing at the cache.
Nothing in src/ may import or depend on this file: clark never installs anything when it runs.

To move to a new version: resolve the tree again once (npm install --package-lock-only --before=<a date two weeks back>
in a scratch folder), then for each package check the tarball against the registry's `dist.integrity` (sha512) and
write its SHA-256 here.
"""
import argparse
import gzip
import hashlib
import io
import json
import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import esbuild  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
PINNED = "3.31.3"                     # Tiptap, published 04-09-2026; 3.31.4 (30-09-2026) was under two weeks old
CUTOFF = "2026-09-29"                 # the tree was resolved with npm's --before at this date: every package is older
CACHE = REPO / "dev" / ".cache" / "tiptap"
ENTRY = REPO / "dev" / "tiptap" / "editor.js"
SOURCES = ("dev/tiptap/editor.js", "dev/tiptap/source.js", "dev/tiptap/writer.js")   # what the bundle is built from
VENDOR = REPO / "vendor" / "tiptap"
MODULE = "tiptap.module.js"           # the one ES module BL-301 A vendors
MANIFEST = "manifest.json"
LICENCES = "licenses"
EXPORTS = ("PINNED", "createEditor", "envelope", "wrap", "parser", "markdownOf", "roundTrip", "fromHtml", "roundTripAll",
           "Extension", "Mark", "Node", "mergeAttributes", "Plugin", "PluginKey",   # these six: the dashboard's wrapper
           "Decoration", "DecorationSet",                                          # BL-301 B: the note's links and chips
           "closeHistory")                                                          # #175: Notes starts a new undo step
GLOBAL_NAME = "CreaiteTiptap"
STAMP = ".creaite-sha256"             # written last in each unpacked package: its tarball's hash, so a half-unpack never counts

# (name, version, SHA-256 of the registry tarball). Each was checked against the registry's dist.integrity (sha512).
PACKAGES = (
    ("@tiptap/core", "3.31.3", "961200ec73ab42d806cef4423424c5e2650a1b015b95e92d498c205859fc7335"),
    ("@tiptap/extension-blockquote", "3.31.3", "17a1c8d916a2d372d7a066b7e6630fba27480c6512949d97d348275d962b2f09"),
    ("@tiptap/extension-bold", "3.31.3", "66fc5bdacab59812f38dbdd2840dcdd42e147ef5a59bd585b7844f9483d44513"),
    ("@tiptap/extension-bullet-list", "3.31.3", "ca2eb17ae5744d515d82a672b6e405e98d0bee73646de2f989375930a744a1d1"),
    ("@tiptap/extension-code", "3.31.3", "389e49ab563cdba83f1c43e153f1cefe617f1fd1f1c8c303621c2b7f65d2fa77"),
    ("@tiptap/extension-code-block", "3.31.3", "02ac80d6c5464cf0a487b6ce250ae0c9f9987c1fbfa72513fde7b96d2e11faa4"),
    ("@tiptap/extension-document", "3.31.3", "67c5912dddd2c05d9e92bd5277e07d01f380ea4d2fcd0836e4b78a26a6ab2555"),
    ("@tiptap/extension-dropcursor", "3.31.3", "397e8cd77ae6b4d6d4a9acb53ae66adb86d9980cfb674b2bae144e3085ac7805"),
    ("@tiptap/extension-gapcursor", "3.31.3", "32fb4cd3a4bf1d164ba90923410f9cd3e58c67fc38caee126e04b36f4f66e470"),
    ("@tiptap/extension-hard-break", "3.31.3", "1f4c7ce4301fcc028f470bdeb65c2b7f9ea5159cfc105fbdeba77374e3c65640"),
    ("@tiptap/extension-heading", "3.31.3", "0c4d27763bc54411023732a9f7f01cda40dd57fdf76a8218c3e89a0b3b5734dd"),
    ("@tiptap/extension-horizontal-rule", "3.31.3", "497694d7349be15b3c65204c7e0f6a3522d2aa5414138520183632ecc58542b2"),
    ("@tiptap/extension-image", "3.31.3", "a4853dd33f23d876e146438c0a9dd24bbaa73d839fd8b7f0a2133ec1952fcb6c"),
    ("@tiptap/extension-italic","3.31.3", "db2c14a8a3a6dedfb2e8fe534e76b97273b6703f51b450886c48bc86e97af363"),
    ("@tiptap/extension-link", "3.31.3", "56f2423ff1df1b004c440f3381a9cbc082e13276b2e4d7e775473a54fdc7e593"),
    ("@tiptap/extension-list", "3.31.3", "75d53843cfb846b26280ae63c08e0042eb71f0f5f02595b16d33c08035788ba1"),
    ("@tiptap/extension-list-item", "3.31.3", "c1c46ca9963127c0a1f196efd8b283d8d3700d6d1cf292957b0bfff6d20d2d34"),
    ("@tiptap/extension-list-keymap", "3.31.3", "316cbc917d3548972a63f9cc828a7efa3e36663a085645324db2356e2b5c5cc7"),
    ("@tiptap/extension-ordered-list", "3.31.3", "1db2f71d424ab482820bf80ebe15d6763bc9e18b607ed43bf64cfc012c58064c"),
    ("@tiptap/extension-paragraph", "3.31.3", "e6792ba31069eab2424695f7e34ad75c8a05fbd3372365c37460b2648eb14c94"),
    ("@tiptap/extension-strike", "3.31.3", "a83f5bb5e735893c75e7a66745ca6441b05bffd5ca50708d4cc7e2c56e6ad92b"),
    ("@tiptap/extension-table", "3.31.3", "7cce306697e8012eb90b457f9d9130ee577771c2f3215926cbbe4b6b8145bff5"),
    ("@tiptap/extension-text", "3.31.3", "37fbcdebd6746f3980b91efa87fe8392baa0b26c26765f74c4b6dc7ae8e78850"),
    ("@tiptap/extension-underline", "3.31.3", "55221c75c49ed5bab605bab9e85ae69ed4772281f94f26b1a8aab0a066ff87ab"),
    ("@tiptap/extensions", "3.31.3", "e7ca5c98b09db01d25505c5f8890ff8749ca163b5e0b9802598769b8ff1e6eb6"),
    ("@tiptap/markdown", "3.31.3", "aa4343bcab50f400dd53cba1e83ade99d8c3d43b45af88b62bf83c2b9d16462d"),
    ("@tiptap/pm", "3.31.3", "14b3ca13f3e8f8791dfc3896eb7adb749205ef80abfb623623ee89cf63b053ca"),
    ("@tiptap/starter-kit", "3.31.3", "d6d605b72f6f3a3169ce84fac6321302c30fd2d9d4b602dbcf0b18df4c7da251"),
    ("linkifyjs", "4.3.3", "112278d64bbbeae926fbbecb1931cb44ecce1e1332e7737be7ba7fc495f15191"),
    ("marked", "17.0.6", "d0ca499e365edfbdb6df8f769417bd7e9308d142f5e86e6ffe76918db6a399db"),
    ("orderedmap", "2.1.1", "9ad98abe6ac4156daef2232d7c1d2c8b3681545604c54f7f3754e791f12c168d"),
    ("prosemirror-changeset", "2.4.4", "2d952db2fa524fc3cd018d443b24126c04b7c45b42941d5b617a207beeb5fc86"),
    ("prosemirror-commands", "1.7.2", "7cca5b9379ff9f83d6bb54d69373e79715cad1f33d8b73d5cb604bc5e73e90d0"),
    ("prosemirror-dropcursor", "1.8.4", "9edb239ccca1818663e6049c728bf37c2e0e39a847f452c7b700e3e83bdee4ea"),
    ("prosemirror-gapcursor", "1.4.1", "961e88b82ce7f434cc781ba644a82810461cf9ba3993834f654384c493998eba"),
    ("prosemirror-history", "1.5.0", "5ffc66c053f3e2d4d6c1f7d5f352c4401fee49b075a5b1bb5b03e7b9d84172a7"),
    ("prosemirror-inputrules", "1.5.1", "785502d7e5ce0b9617d1aa6c0ef2aa2a0a6b06a5d8efb8942eb7c1b2d3b155aa"),
    ("prosemirror-keymap", "1.2.3", "3131823ce73eaf3487cada22c85b76349da02c114dee3de696f4c1c3c645ca8c"),
    ("prosemirror-model", "1.25.12", "0ac7e5deed004b7f983ca295fa1e84b19f7ee38995e39dee9809d9a4ebd5c6c8"),
    ("prosemirror-schema-list", "1.5.1", "c60638c4fd055328cebada5a36a661d454eb87114919bfc2bfbfbcda2b939c2e"),
    ("prosemirror-state", "1.4.4", "ad3eb60bd6db8e74b2576dc0b7c2800d6def362e0e990c9fb108fc4b724ee651"),
    ("prosemirror-tables", "1.8.5", "589a633cd06d12c0ab2a210846ea208d3be9dd37f5b068be19f437733f22089b"),
    ("prosemirror-transform", "1.12.2", "a9b778a065f7a5d723b9aaeb6c7026216dba678086abe9d24b52d7abb96366dc"),
    ("prosemirror-view", "1.42.6", "cf47baf6a53d609220fdc9b6a71b7de04f5e4cc67b2a00d1f55d967f22a68c2c"),
    ("rope-sequence", "1.3.4", "2a483ee02e5a21b59b63a29bca162e6aa2cd8fafb474261040c3d8538a1f067c"),
    ("w3c-keyname", "2.2.8", "05d21484026d1f2dd842c843181e391e66d60f1d5dff292d562c3f40302dab36"),
)


class TiptapError(RuntimeError):
    """A pinned package could not be provided (a failed download, a hash that doesn't match, an unsafe tarball) or the
    bundle failed."""


def tarball_url(name, version):
    """The npm registry's tarball address for `name` at `version` (a scoped name's file is named without its scope)."""
    return f"https://registry.npmjs.org/{name}/-/{name.rsplit('/', 1)[-1]}-{version}.tgz"


def modules_dir():
    """The node_modules folder the pinned packages are unpacked into (one per Tiptap version)."""
    return CACHE / PINNED / "node_modules"


def verify(data, name, version, sha256):
    """Refuse `data` unless its SHA-256 is the one pinned for `name`."""
    got = hashlib.sha256(data).hexdigest()
    if got != sha256:
        raise TiptapError(f"{name} {version}: SHA-256 {got} is not the pinned {sha256}; nothing was unpacked")


def _safe_member(member):
    """The path inside the package of a tarball member (without npm's `package/` prefix), or None for a folder entry.
    Links, devices, absolute paths and `..` are refused: a tarball never writes outside its own folder."""
    parts = Path(member.name).parts
    if member.name.startswith("/") or ".." in parts or len(parts) < 2:
        raise TiptapError(f"unsafe path in the tarball: {member.name}")
    if member.isdir():
        return None
    if not member.isfile():
        raise TiptapError(f"the tarball's {member.name} is not a plain file")
    return Path(*parts[1:])


def unpack(data, dest, sha256):
    """Unpack the npm tarball `data` into `dest` (the package's folder), through a temporary folder renamed into place,
    so a failure leaves nothing behind; the stamp file holding `sha256` is written last."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=".part-", dir=dest.parent))
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            for member in tar.getmembers():
                rel = _safe_member(member)
                if rel is None:
                    continue
                out = tmp / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(tar.extractfile(member).read())
        (tmp / STAMP).write_text(sha256, encoding="utf-8")
        if dest.exists():
            shutil.rmtree(dest)
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
    return dest


def is_unpacked(dest, sha256):
    """True when `dest` holds a complete unpack of the tarball with this hash."""
    stamp = dest / STAMP
    return stamp.is_file() and stamp.read_text(encoding="utf-8").strip() == sha256


def ensure(packages=PACKAGES, fetch=None):
    """Download, check and unpack every pinned package not already in the cache; return the node_modules folder.
    `fetch` defaults to esbuild's (urllib, then curl with the system's certificates)."""
    fetch = fetch or esbuild.fetch
    root = modules_dir()
    for name, version, sha256 in packages:
        dest = root / name
        if is_unpacked(dest, sha256):
            continue
        data = fetch(tarball_url(name, version))
        verify(data, name, version, sha256)
        unpack(data, dest, sha256)
    return root


def bundle(entry=ENTRY, minify=True, fmt="iife", metafile=None):
    """The bundle (bytes) of `entry` and everything it imports, by the pinned esbuild from the pinned packages: an IIFE
    setting `window.CreaiteTiptap` (the gate's), or with fmt="esm" the ES module that is vendored. With `metafile` (a
    path), esbuild also writes there what went into the bundle."""
    root = ensure()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "tiptap.js"
        args = ["--bundle", str(entry), f"--format={fmt}", "--tsconfig-raw={}",
                "--charset=utf8", "--target=es2020", "--log-level=warning", "--legal-comments=none",
                f'--define:__TIPTAP_PINNED__="{PINNED}"',
                f"--outfile={out}"] + (["--minify"] if minify else [])
        args += [f"--global-name={GLOBAL_NAME}"] if fmt == "iife" else []
        args += [f"--metafile={metafile}"] if metafile else []
        r = esbuild.run(args, capture_output=True, text=True, env=dict(os.environ, NODE_PATH=str(root)))
        if r.returncode != 0:
            raise TiptapError(f"esbuild failed on {entry.name}:\n{r.stderr.strip()}")
        return out.read_bytes()


def sizes(data):
    """(raw bytes, gzipped bytes) of a bundle."""
    return len(data), len(gzip.compress(data, compresslevel=9, mtime=0))


def _package_of(path):
    """The npm package name a bundled file belongs to (`@tiptap/core`, `marked`), or None for creaite's own source."""
    parts = Path(path).as_posix().split("node_modules/")
    if len(parts) < 2:
        return None
    bits = parts[-1].split("/")
    return "/".join(bits[:2]) if bits[0].startswith("@") else bits[0]


def bundled_packages(meta):
    """The pinned packages esbuild put into the bundle, from its metafile (a dict): sorted names. A package that isn't
    pinned is refused (the bundle would hold code nobody checked)."""
    names = sorted({n for n in map(_package_of, meta.get("inputs", {})) if n})
    pinned = {name for name, _, _ in PACKAGES}
    stray = [n for n in names if n not in pinned]
    if stray:
        raise TiptapError(f"the bundle holds packages that aren't pinned: {', '.join(stray)}")
    return names


LICENCE_NAMES = ("LICENSE", "LICENCE", "THIRD_PARTY_LICENSES")


def licence_files(name, version):
    """{vendored path: bytes} for `name`'s licence files (LICENSE*, THIRD_PARTY_LICENSES*), read from the cache;
    a package without one is refused."""
    folder = modules_dir() / name
    found = sorted(f for f in folder.iterdir() if f.is_file() and f.name.upper().startswith(LICENCE_NAMES))
    if not found:
        raise TiptapError(f"{name} {version} has no licence file in its tarball")
    stem = name.replace("@", "").replace("/", "-")
    return {f"{LICENCES}/{stem}-{version}-{f.name}": f.read_bytes() for f in found}


def _sha(data):
    """The SHA-256 of `data`, as hex."""
    return hashlib.sha256(data).hexdigest()


def vendor_files():
    """{vendored path: bytes}: the ES module, every bundled package's licence files and manifest.json (BL-239's form:
    each file's SHA-256, with the versions, the tarballs' SHA-256s and licences, and what the build was made from).
    The same inputs give the same bytes on any machine (no times, no absolute paths)."""
    with tempfile.TemporaryDirectory() as tmp:
        meta_path = Path(tmp) / "meta.json"
        module = bundle(fmt="esm", metafile=meta_path)
        names = bundled_packages(json.loads(meta_path.read_text(encoding="utf-8")))
    pins = {name: (version, sha) for name, version, sha in PACKAGES}
    out, packages = {MODULE: module}, {}
    for name in names:
        version, sha = pins[name]
        lic = licence_files(name, version)
        out.update(lic)
        about = json.loads((modules_dir() / name / "package.json").read_text(encoding="utf-8"))
        packages[name] = {"version": version, "licence": about.get("license"), "tarball": tarball_url(name, version),
                          "sha256": sha, "licence_files": sorted(lic)}
    raw, gz = sizes(module)
    manifest = {
        "about": "BL-301 A (BL-239's form): the pinned Tiptap editor as one ES module, built in development by "
                 "dev/tools/tiptap.py vendor from dev/tiptap/ with the pinned esbuild; every bundled package's version, "
                 "tarball SHA-256 and licence; the SHA-256 of every file here. Never edited by hand.",
        "tiptap": PINNED,
        "build": {"esbuild": esbuild.PINNED, "format": "esm", "target": "es2020", "minified": True,
                  "sources": {p: _sha((REPO / p).read_bytes()) for p in SOURCES},
                  "bytes": raw, "gzipped": gz},
        "exports": list(EXPORTS),
        "packages": packages,
        "files": {p: _sha(out[p]) for p in sorted(out)},
    }
    out[MANIFEST] = (json.dumps(manifest, indent=1) + "\n").encode("utf-8")
    return out


def write_vendor(dest=VENDOR):
    """Replace `dest` with a fresh vendor build (through a temporary folder renamed into place); the files written."""
    files = vendor_files()
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=".tiptap-", dir=dest.parent))
    try:
        for rel, data in files.items():
            (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            (tmp / rel).write_bytes(data)
        if dest.exists():
            shutil.rmtree(dest)
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
    return files


def _tree(folder):
    """{path relative to `folder`: bytes} for every file under it (macOS's .DS_Store left out)."""
    folder = Path(folder)
    if not folder.is_dir():
        return {}
    return {f.relative_to(folder).as_posix(): f.read_bytes() for f in sorted(folder.rglob("*"))
            if f.is_file() and f.name != ".DS_Store"}


def compare(want, have):
    """['missing: x', 'changed: y', 'extra: z'] between two {path: value} maps ([] when they are the same)."""
    return ([f"missing: {p}" for p in sorted(set(want) - set(have))]
            + [f"changed: {p}" for p in sorted(set(want) & set(have)) if want[p] != have[p]]
            + [f"extra: {p}" for p in sorted(set(have) - set(want))])


def manifest_problems(folder=VENDOR):
    """The committed folder against its own manifest.json (no build, no cache: what CI can always check):
    ['missing: x', 'changed: y', 'extra: z'], or one line when the manifest can't be read."""
    have = _tree(folder)
    try:
        want = json.loads(have.pop(MANIFEST).decode("utf-8"))["files"]
    except (KeyError, ValueError):
        return [f"unreadable: {MANIFEST}"]
    return compare(want, {p: _sha(b) for p, b in have.items()})


def fresh_build_problems(folder=VENDOR):
    """The committed folder against a fresh build from dev/tiptap/ and the pinned packages: [] when byte for byte the
    same. Builds in memory; writes nothing to `folder`."""
    return compare(vendor_files(), _tree(folder))


def is_cached():
    """True when every pinned package and the pinned esbuild are already in dev/.cache (so a fresh build downloads
    nothing)."""
    try:
        have_esbuild = esbuild.target(esbuild.platform_key()).is_file()
    except esbuild.EsbuildError:
        return False
    return have_esbuild and all(is_unpacked(modules_dir() / name, sha) for name, _, sha in PACKAGES)


def stale(folder=VENDOR):
    """Why the vendored editor is out of date, or None (dev/tools/check.py's VENDORED check): its files against its
    manifest, then dev/tiptap/'s sources against the hashes it was built from (both need no cache), then, when the
    pinned packages are already in dev/.cache, the folder against a fresh build. Never downloads anything."""
    fix = "run python3 dev/tools/tiptap.py fetch, then vendor, and commit vendor/tiptap/"
    problems = manifest_problems(folder)
    if problems:
        return f"doesn't match its manifest ({'; '.join(problems[:3])}): {fix}"
    built = json.loads((Path(folder) / MANIFEST).read_text(encoding="utf-8"))["build"]["sources"]
    changed = [p for p in SOURCES if built.get(p) != _sha((REPO / p).read_bytes())]
    if changed:
        return f"was built from older {', '.join(changed)}: {fix}"
    problems = fresh_build_problems(folder) if is_cached() else []
    return f"isn't a fresh build ({'; '.join(problems[:3])}): {fix}" if problems else None


def _vendor_command(check):
    """`vendor` and `vendor --check` for main(): 0, or 1 when --check finds a difference."""
    if check:
        problems = fresh_build_problems()
        for p in problems:
            print(p)
        print("tiptap: vendor/tiptap/ " + ("is a fresh build." if not problems else
              "is not a fresh build: run python3 dev/tools/tiptap.py vendor and commit it."))
        return 1 if problems else 0
    files = write_vendor()
    raw, gz = sizes(files[MODULE])
    print(f"tiptap {PINNED}: wrote {len(files)} files to {VENDOR.relative_to(REPO)}; {MODULE} {raw} bytes "
          f"({raw / 1024:.1f} KiB), gzipped {gz} bytes ({gz / 1024:.1f} KiB)")
    return 0


def main(argv=None):
    """Command line: fetch; bundle with an optional --out file (prints the sizes); vendor [--check]. Exit 2 on a
    refusal."""
    ap = argparse.ArgumentParser(description="The pinned Tiptap editor (BL-301 part A; development only).")
    ap.add_argument("command", choices=("fetch", "bundle", "vendor"))
    ap.add_argument("--out", help="write the bundle here")
    ap.add_argument("--no-minify", action="store_true")
    ap.add_argument("--check", action="store_true", help="vendor: compare with a fresh build; write nothing")
    a = ap.parse_args(argv)
    try:
        if a.command == "fetch":
            print(f"tiptap: {len(PACKAGES)} packages in {ensure().relative_to(REPO)}")
            return 0
        if a.command == "vendor":
            return _vendor_command(a.check)
        data = bundle(minify=not a.no_minify)
    except (TiptapError, esbuild.EsbuildError) as e:
        print(f"tiptap: {e}", file=sys.stderr)
        return 2
    if a.out:
        Path(a.out).write_bytes(data)
    raw, gz = sizes(data)
    print(f"tiptap {PINNED}: bundle {raw} bytes ({raw / 1024:.1f} KiB), gzipped {gz} bytes ({gz / 1024:.1f} KiB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
