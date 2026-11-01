"""Build clark's page: one HTML file with everything inline (#35; development only, needs the pinned esbuild).

Run: python3 dev/tools/build_page.py            # writes src/clark/page/page.html and page-view.html
     python3 dev/tools/build_page.py --check    # exits 1 if either committed page is not what the sources give

Two pages come from the same components (#65): page.html (entry main.jsx) is the one clark serves, with the Edit parts;
page-view.html (entry view.jsx) is the one a published file is made from, with no Edit part, no api.js and no stores/changes.js,
so the routes that change things are not named in it. publish.py reads page.html until the Head decides to switch it.

Copied in outline from creaite v2.6.9 dev/tools/build_dashboard_js.py (`preact_flags`) and split_dashboard.py, cut down: JSX
through Preact's automatic runtime, and every library name (`preact`, `preact/hooks`, `preact/jsx-runtime`,
`@preact/signals`, `@preact/signals-core`) mapped to its vendored file from vendor/preact/manifest.json, so nothing is looked
up anywhere else. The result is repeatable (the same sources give the same bytes). The built page is committed and nothing is
built when clark runs. The icon (#73) goes in as data: links in <head> (the SVG favicon, a 32 px PNG fallback, the 180 px Apple
touch icon) and as the top bar's logo icon (a CSS background): the server has no route for files, and its policy allows data:
images. The demo brand's tokens.css and the shell's CSS go in as the first inline <style>; the server adds a
user's own brand after it as a second one, and the page's script as one inline <script> (the server's policy lists script
hashes only, so an external script file would be blocked: #33).

The fonts are Inter and Montserrat (vendor/fonts/inter/ and vendor/fonts/montserrat/, SIL Open Font License, not from creaite). Their woff2 files go in as base64
`data:` URIs in @font-face rules at the top of that first <style> (the policy allows `font-src 'self' data:`), so the page
stays one file and loads nothing from the internet. The rules are written from each font folder's manifest.json.

A manifest is data, and the build trusts nothing in it (#236): each entry's file must be a plain woff2 file name inside that
font's own folder (no absolute path, no '..', no sub-folder, no symlink that leads out), a regular file that starts with the
woff2 signature and is no bigger than MAX_FONT_BYTES; family, style, weight and unicode_range must match strict shapes, so
nothing can be written into the CSS. Anything else stops the build with FontManifestError naming the manifest entry, and no
page is written.
"""
import base64
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import esbuild  # noqa: E402
sys.path.insert(0, str(HERE.parents[1] / "src"))
from clark import page  # noqa: E402
from clark.page import strip_css_comments  # noqa: E402

ROOT = HERE.parents[1]
PAGE = ROOT / "src" / "clark" / "page"
SRC = PAGE / "src"
OUT = PAGE / "page.html"
OUT_VIEW = PAGE / "page-view.html"
ENTRY = "main.jsx"
ENTRY_VIEW = "view.jsx"
VENDOR = ROOT / "vendor" / "preact"
VENDOR_TIPTAP = ROOT / "vendor" / "tiptap"       # the editor (#66): bundled by the Edit entry only
FONTS = (ROOT / "vendor" / "fonts" / "inter", ROOT / "vendor" / "fonts" / "montserrat")      # one folder per family, each with its manifest.json
TOKENS = ROOT / "src" / "clark" / "brand" / "tokens.css"
ASSETS = PAGE / "assets"
ICONS = (("icon", "image/svg+xml", "clark-icon.svg"), ("icon", "image/png", "clark-icon-32.png"),
         ("apple-touch-icon", "image/png", "clark-icon-180.png"))      # rel, type, file (#73)
TITLE = "clark"
BODY = '<div id="app"></div>'


class BuildError(RuntimeError):
    """esbuild refused the source (a syntax error, a missing import or file); the message is esbuild's."""


class FontManifestError(ValueError):
    """A font manifest entry was refused (#236); the message names the manifest and the entry, never a resolved path."""


class VendorManifestError(ValueError):
    """A module entry in vendor/preact/manifest.json was refused (#236); the message names the manifest and entry, never a resolved path."""


MODULE_SPEC = re.compile(r"[a-z@][a-z0-9@/._-]{0,100}")       # goes onto an esbuild command line: no space, '=', quote or leading '-'
SHA256 = re.compile(r"[0-9a-f]{64}")
MAX_MODULE_BYTES = 4 * 1024 * 1024
MAX_FONT_BYTES = 512 * 1024         # one woff2 file; the vendored ones are about 20 KB each
WOFF2_MAGIC = b"wOF2"
SHOWABLE_NAME = re.compile(r"[^\x00-\x1f\x7f/\\:]{1,60}")      # a file name safe to show in a refusal: printable, no path separator
FONT_FILE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\.woff2")
FONT_FIELDS = (                     # (field, the shape it must match in full, what it must be): nothing else can reach the CSS
    ("family", re.compile(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,63}"),
     "family is missing or has characters that are not allowed (use letters, digits, space, '_' and '-')"),
    ("style", re.compile(r"normal|italic"), "style must be normal or italic"),
    ("weight", re.compile(r"[1-9]00"), "weight must be 100, 200 ... 900"),
    ("unicode_range", re.compile(r"U\+[0-9A-Fa-f?]{1,6}(-[0-9A-Fa-f]{1,6})?(, U\+[0-9A-Fa-f?]{1,6}(-[0-9A-Fa-f]{1,6})?)*"),
     "unicode_range is missing or is not a list of ranges such as U+0000-00FF"),
)
FONT_SUBSET = re.compile(r"[a-z][a-z0-9-]{0,31}")      # optional ("latin"); it is checked but not used in the CSS
FONT_KEYS = frozenset(name for name, _, _ in FONT_FIELDS) | {"file", "subset"}      # a key outside these is refused (#263)
MANIFEST_KEYS = frozenset({"fonts", "files", "package"})       # "files" and "package" are the record of where the fonts came from


HELP = SRC / "help"
SHOWN_DIR = HELP / "shown"      # made by the build, git-ignored: inside src, so the bundle still takes nothing from outside it


def help_content_path(held=True):
    """The file Help's words are bundled from. The source (helpContent.json) is whole; the entries held back in helpLater.json
    (a part of clark that is not on the page yet) are left out of the built page, so their words, example dates and template
    names never reach it. held=False gives the whole source (the logic tests)."""
    whole = HELP / "helpContent.json"
    if not held:
        return whole
    later = json.loads((HELP / "helpLater.json").read_text(encoding="utf-8"))
    raw = json.loads(whole.read_text(encoding="utf-8"))
    raw["howto"]["tasks"] = [t for t in raw["howto"]["tasks"] if t["id"] not in later.get("howto", {})]
    raw["reference"]["sections"] = [s for s in raw["reference"]["sections"] if s["id"] not in later.get("reference", {})]
    SHOWN_DIR.mkdir(exist_ok=True)
    out = SHOWN_DIR / "helpContent.json"
    out.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return out


def vendor_modules(vendor=None):
    """[(specifier, absolute path)] for the modules in vendor/preact/manifest.json, sorted. The manifest is data (#236): a module's
    path must be one of the manifest's own fingerprinted "files" entries, a plain relative path that stays inside the vendor
    folder (no link out), a regular file whose sha256 matches; the specifier must match MODULE_SPEC. Anything else raises
    VendorManifestError naming the manifest and the entry."""
    vendor = VENDOR if vendor is None else vendor
    name = _manifest_name(vendor)
    try:
        data = json.loads((vendor / "manifest.json").read_text(encoding="utf-8"))
        modules, files = data["modules"], data["files"]
    except (OSError, ValueError, KeyError, TypeError):
        raise VendorManifestError(f"{name}: cannot be read as a vendor manifest ('modules' and 'files')") from None
    if not isinstance(modules, dict) or not isinstance(files, dict):
        raise VendorManifestError(f"{name}: 'modules' and 'files' must both be objects")
    home = os.path.realpath(vendor)
    out = []
    for i, (spec, path) in enumerate(sorted(modules.items()), 1):
        where = f"{name}, module {i}"
        if not isinstance(spec, str) or not MODULE_SPEC.fullmatch(spec):
            raise VendorManifestError(f"{where}: the specifier is not an allowed name (lower-case letters, digits, '@', '/', '.', '_', '-')")
        where += f" ({spec})"
        if not isinstance(path, str) or not path:
            raise VendorManifestError(f"{where}: the path is missing or is not a name")
        if os.path.isabs(path) or path.startswith(("/", "\\")) or re.match(r"[A-Za-z]:", path):
            raise VendorManifestError(f"{where}: the path is absolute; it must be a file listed under 'files'")
        if ".." in re.split(r"[/\\]", path):
            raise VendorManifestError(f"{where}: the path climbs out of the vendor folder with '..'")
        want = files.get(path)
        if not isinstance(want, str):
            raise VendorManifestError(f"{where}: the path is not one of the manifest's 'files' entries")
        if not SHA256.fullmatch(want):
            raise VendorManifestError(f"{where}: the file's fingerprint in 'files' is not a sha256")
        real = os.path.realpath(os.path.join(home, path))
        if real != os.path.join(home, os.path.normpath(path)):
            raise VendorManifestError(f"{where}: the path is or passes through a link, or leaves the vendor folder")
        try:
            st = os.stat(real)
        except OSError:
            raise VendorManifestError(f"{where}: the file is not there") from None
        if not stat.S_ISREG(st.st_mode):
            raise VendorManifestError(f"{where}: the file is not a regular file")
        if st.st_size > MAX_MODULE_BYTES:
            raise VendorManifestError(f"{where}: the file is too big for a module")
        with open(real, "rb") as fh:
            body = fh.read(MAX_MODULE_BYTES + 1)
        if len(body) > MAX_MODULE_BYTES or hashlib.sha256(body).hexdigest() != want:
            raise VendorManifestError(f"{where}: the file does not match its sha256 in 'files'")
        out.append((spec, real))
    return out


def preact_flags(held=True):
    """JSX through esbuild (the automatic runtime, from Preact), each library specifier mapped to its vendored file, and Help's words."""
    return ["--jsx=automatic", "--jsx-import-source=preact", "--loader:.jsx=jsx",
            *(f"--alias:{spec}={path}" for spec, path in vendor_modules()),
            f"--alias:tiptap={VENDOR_TIPTAP / 'tiptap.module.js'}",      # the editor (#66); only the Edit entry imports it
            f"--alias:clark-help-content={help_content_path(held)}"]


def bundle(entry=ENTRY):
    """The page's script, one IIFE, minified, from src/<entry> and what it imports."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "page.js"
        args = ["--bundle", "--format=iife", "--minify", "--target=es2020", "--legal-comments=none", "--charset=utf8",
                "--tsconfig-raw={}",             # a tsconfig.json in a parent folder would add "use strict" and change the bytes (creaite, 13-10-2026)
                *preact_flags(), entry, f"--outfile={out}"]
        done = esbuild.run(args, cwd=SRC, capture_output=True, text=True)
        if done.returncode != 0:
            raise BuildError(f"esbuild failed on src/{entry}:\n{done.stderr.strip()}")
        return out.read_text(encoding="utf-8")


def data_uri(mime, name):
    return f"data:{mime};base64,{base64.b64encode((ASSETS / name).read_bytes()).decode('ascii')}"


def icon_links():
    """The three <link>s for the favicon, the PNG fallback and the touch icon; the files are inside the page."""
    return "".join(page.icon_link(rel, mime, base64.b64encode((ASSETS / name).read_bytes()).decode("ascii")) for rel, mime, name in ICONS)


def _manifest_name(folder):
    try:
        return str((folder / "manifest.json").relative_to(ROOT))
    except ValueError:
        return f"{folder.name}/manifest.json"


def _shown_key(key):
    """A manifest key as it can be shown in a refusal: quoted if it is plain printable text, else a general word (never an echo of odd text)."""
    return f"'{key}'" if isinstance(key, str) and SHOWABLE_NAME.fullmatch(key) else "a key with unusual characters"


def font_bytes(folder, name, where):
    """The bytes of the font file `name` from `folder`'s manifest, or FontManifestError in plain words naming `where`."""
    if not isinstance(name, str) or not name:
        raise FontManifestError(f"{where}: the 'file' setting is empty or is not text; set it to the font's file name, for example Inter-Regular.woff2")
    if os.path.isabs(name) or name.startswith(("/", "\\")) or re.match(r"[A-Za-z]:", name):
        raise FontManifestError(f"{where}: the file is an absolute path; it must be a file name inside the font's own folder")
    if ".." in re.split(r"[/\\]", name):
        raise FontManifestError(f"{where}: the file name contains '..', which points outside the font's folder; use only the file name, with no folders in it")
    if "/" in name or "\\" in name:
        raise FontManifestError(f"{where}: the file is in a sub-folder; it must sit in the font's own folder")
    if not FONT_FILE.fullmatch(name):
        raise FontManifestError(f"{where}: the file name must end in .woff2 and use only letters, digits, '.', '_' and '-'; rename the file and set 'file' to the new name")
    home = os.path.realpath(folder)
    path = os.path.join(home, name)
    real = os.path.realpath(path)
    if os.path.dirname(real) != home or not Path(real).is_relative_to(home):
        raise FontManifestError(f"{where}: the file is a shortcut (symbolic link) to something outside the font's own folder; "
                                f"copy the real font file into that folder and point 'file' at the copy")
    try:
        st = os.stat(real)
    except OSError:
        raise FontManifestError(f"{where}: no file with that name is in the font's folder; add the font file or correct the name in 'file'") from None
    if os.path.islink(path):         # a link that stays in the folder is refused too: the file read must be the file named
        raise FontManifestError(f"{where}: the file is a shortcut (symbolic link), even to a file in the same folder; "
                                f"copy the real font file into the folder and point 'file' at the copy")
    if not stat.S_ISREG(st.st_mode):
        raise FontManifestError(f"{where}: the name points at a folder or another kind of item, not a font file; point 'file' at the .woff2 file")
    if st.st_size > MAX_FONT_BYTES:
        raise FontManifestError(f"{where}: the file is bigger than {MAX_FONT_BYTES // 1024} KB; use a smaller or trimmed (subset) version of the font")
    with open(real, "rb") as fh:
        data = fh.read(MAX_FONT_BYTES + 1)       # a file that grows after the stat is still capped
    if len(data) > MAX_FONT_BYTES:
        raise FontManifestError(f"{where}: the file changed size while the build was reading it and is now over {MAX_FONT_BYTES // 1024} KB; "
                                f"run the build again, and if it repeats, replace the file with a smaller one")
    if not data.startswith(WOFF2_MAGIC):
        raise FontManifestError(f"{where}: the file is not a woff2 font (it may be another kind of file renamed to .woff2); replace it with the original font file")
    return data


def font_css(folders=None):
    """One @font-face per vendored font file, the woff2 inlined as a base64 data: URI (the same files give the same bytes).
    Every entry is checked first (#236); a refused one raises FontManifestError. `folders` defaults to FONTS."""
    rules = []
    for folder in (FONTS if folders is None else folders):
        manifest = _manifest_name(folder)
        try:
            text = (folder / "manifest.json").read_text(encoding="utf-8")
        except OSError:
            raise FontManifestError(f"{manifest} is missing or cannot be opened") from None
        except ValueError:
            raise FontManifestError(f"{manifest} is not valid JSON (check commas and quotes)") from None
        try:
            data = json.loads(text)
        except ValueError:
            raise FontManifestError(f"{manifest} is not valid JSON (check commas and quotes)") from None
        if not isinstance(data, dict):
            raise FontManifestError(f"{manifest} must be one block of settings, written with {{ }} braces, with a 'fonts' list inside")
        for key in data:
            if key not in MANIFEST_KEYS:
                raise FontManifestError(f"{manifest}: {_shown_key(key)} is not a setting a font manifest has (allowed: files, fonts, package); remove it or correct its spelling")
        if "fonts" not in data:
            raise FontManifestError(f"{manifest} has no 'fonts' list")
        fonts = data["fonts"]
        if not isinstance(fonts, list):
            raise FontManifestError(f"'fonts' in {manifest} must be a list of fonts, written with [ ] brackets")
        for i, f in enumerate(fonts, 1):
            if not isinstance(f, dict):
                raise FontManifestError(f"{manifest}, font {i} is not a block of settings; each font needs family, style, weight, unicode_range and file")
            label = f.get("file")
            shown = label if isinstance(label, str) and SHOWABLE_NAME.fullmatch(label) else ""     # a typo'd name is named too; a path is never echoed
            where = f"{manifest}, font {i}" + (f" ({shown!r})" if shown else "")
            for key in f:
                if key not in FONT_KEYS:
                    raise FontManifestError(f"{where}: {_shown_key(key)} is not a setting a font has (allowed: {', '.join(sorted(FONT_KEYS))}); remove it or correct its spelling")
            for field, shape, rule in FONT_FIELDS:
                value = f.get(field)
                if not isinstance(value, str) or not shape.fullmatch(value):
                    raise FontManifestError(f"{where}: {rule}")
            if "subset" in f and not (isinstance(f["subset"], str) and FONT_SUBSET.fullmatch(f["subset"])):
                raise FontManifestError(f"{where}: subset must be a short lower-case name such as latin")
            data = base64.b64encode(font_bytes(folder, f.get("file"), where)).decode("ascii")
            rules.append(f"@font-face {{ font-family: \"{f['family']}\"; font-style: {f['style']}; font-weight: {f['weight']}; "
                         f"font-display: swap; src: url(data:font/woff2;base64,{data}) format(\"woff2\"); "
                         f"unicode-range: {f['unicode_range']}; }}\n")
    return "".join(rules)


EDIT_CSS = SRC / "edit" / "edit.css"       # styles of the Edit parts only (#136): in the served page, never in the published one
EDIT_ENTRIES = (ENTRY, "main-test.jsx")   # the served page and the browser tests' copy of it (served sources plus a test hook)


def page_css(entry=ENTRY_VIEW):
    """The CSS the page inlines: the font, the demo brand's tokens and the shell's own styles; for the served page (entry main.jsx)
    and its test copy (main-test.jsx) also the Edit parts' (edit/edit.css), so a published file holds none of their class names."""
    css = font_css() + TOKENS.read_text(encoding="utf-8") + (PAGE / "shell.css").read_text(encoding="utf-8")
    if entry in EDIT_ENTRIES:
        css += EDIT_CSS.read_text(encoding="utf-8")
    return strip_css_comments(css)             # the built page carries no comment: a source comment can name a person


def build(entry=ENTRY):
    """The whole page as text: the served page (main.jsx), or with entry=ENTRY_VIEW the page a published file is made from."""
    # "<!--" inside a script puts an HTML parser into its escaped state, and the page carries no comment: the vendored editor's Markdown
    # and HTML-comment patterns hold it as text, so it is written with an escape that means the same in a string or a pattern.
    script = bundle(entry).replace("</script", "<\\/script").replace("<!--", "<!\\x2d-")
    css = page_css(entry).replace("</style", "<\\/style")
    css += f'.logo-icon {{ background-image: url("{data_uri("image/svg+xml", "clark-icon.svg")}"); }}\n'
    return (f'<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>{TITLE}</title>{icon_links()}\n'
            f'<style id="brand-demo">\n{css}</style>\n</head>\n<body>{BODY}\n<script>{script}</script>\n</body></html>\n')


def pages():
    """(file, text) for each page the build makes."""
    return ((OUT, build(ENTRY)), (OUT_VIEW, build(ENTRY_VIEW)))


def main(argv):
    try:
        made = pages()          # every page is made before any is written, so a refused font or module leaves the committed pages alone
    except (FontManifestError, VendorManifestError) as e:
        print(f"build refused: {e}", file=sys.stderr)
        return 1
    if "--check" in argv:
        stale = [f for f, text in made if (f.read_text(encoding="utf-8") if f.exists() else "") != text]
        for f in stale:
            print(f"src/clark/page/{f.name} is out of date: run python3 dev/tools/build_page.py")
        if stale:
            return 1
        print("page.html and page-view.html are up to date")
        return 0
    for f, text in made:
        f.write_bytes(text.encode("utf-8"))      # bytes, so no newline translation and it works on Python 3.9
        print(f"wrote {f.relative_to(ROOT)} ({len(text):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
