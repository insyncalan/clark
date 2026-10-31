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
"""
import base64
import json
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


def preact_flags(held=True):
    """JSX through esbuild (the automatic runtime, from Preact), each library specifier mapped to its vendored file, and Help's words."""
    modules = json.loads((VENDOR / "manifest.json").read_text(encoding="utf-8"))["modules"]
    return ["--jsx=automatic", "--jsx-import-source=preact", "--loader:.jsx=jsx",
            *(f"--alias:{spec}={VENDOR / path}" for spec, path in sorted(modules.items())),
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


def font_css():
    """One @font-face per vendored font file, the woff2 inlined as a base64 data: URI (the same files give the same bytes)."""
    rules = []
    for folder in FONTS:
        for f in json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["fonts"]:
            data = base64.b64encode((folder / f["file"]).read_bytes()).decode("ascii")
            rules.append(f"@font-face {{ font-family: \"{f['family']}\"; font-style: {f['style']}; font-weight: {f['weight']}; "
                         f"font-display: swap; src: url(data:font/woff2;base64,{data}) format(\"woff2\"); "
                         f"unicode-range: {f['unicode_range']}; }}\n")
    return "".join(rules)


EDIT_CSS = SRC / "edit" / "edit.css"       # styles of the Edit parts only (#136): in the served page, never in the published one


def page_css(entry=ENTRY_VIEW):
    """The CSS the page inlines: the font, the demo brand's tokens and the shell's own styles; for the served page (entry main.jsx)
    also the Edit parts' (edit/edit.css), so a published file holds none of their class names."""
    css = font_css() + TOKENS.read_text(encoding="utf-8") + (PAGE / "shell.css").read_text(encoding="utf-8")
    if entry == ENTRY:
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
    made = pages()
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
