"""The page the server sends (#35): the committed, built page.html, with a user's own brand layered over the demo one.

page.html and page-view.html are built by dev/tools/build_page.py and are NOT committed (#495): CI, dev/run_tests.py and
dev/tools/package.py build them, and a source checkout builds them (ensure_built below) the first time it needs them. The
download holds them already built and has no dev/ folder, so a download never calls the bundler and installs nothing. It carries the demo brand's
tokens in <style id="brand-demo">. If the user has a brand of their own, a tokens.css in system/branding/ (git ignores it),
its text goes in as a second <style id="brand-local"> after the demo one, so the same token names take the user's values. The
server hashes the exact bytes it sends, so the policy covers both blocks (#33). A user's own brand is a client's, so the
top bar's clark icon (#73) is hidden by default under it: the block starts with --logo-icon: none, which the brand's own
tokens.css can set back to inline-block.

The three icon links in page.html's head (#73: the SVG favicon, the 32 px PNG fallback, the Apple touch icon) are written by
icon_link(), and pinned by ICON_LINKS: the SHA-256 of each picture's decoded bytes, with the rel and mime of its link. The build
and publish.outside_addresses both use icon_link(), so there is one format: the scan lets a <link> through only if its whole text
equals icon_link() of one of these pictures, character for character, and each picture at most once. Changing an icon is a
deliberate edit of ICON_LINKS (tests/test_icons.py fails until the table and the page agree).

The fonts are Inter and Montserrat (vendor/fonts/inter/ and vendor/fonts/montserrat/, SIL Open Font License): the build inlines them as @font-face rules with the woff2
as base64 `data:` URIs at the top of the demo block, so the page is still one file and the policy's `font-src 'self' data:`
is enough. A user's own brand sets `--font`; the font-face rules stay, so naming "Inter" or "Montserrat" in it works.

The brand's pictures (#98). A user's tokens.css can say `--image-cover: url("assets/cover.jpg")`, a path relative to the page,
which is served from /. The server answers GET /assets/<name> for the names in PICTURES and no others, from the `assets`
folder beside the user's tokens.css (brand_picture below); the brand's own path in the page is not changed, so the published
file (which takes the same page text) carries no new address. The name is looked up in PICTURES, never joined onto a path.
The brand block goes after the element with id="brand-demo" (DEMO_ID), found by that id and not by one exact string; a page
without that element, when there is a local brand, raises PageError rather than leaving the brand out without a word.
"""
import hashlib
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PAGE = HERE / "page.html"
VIEW_PAGE = HERE / "page-view.html"      # #65: the same page with no Edit part and no route that changes anything
BRANDING = ROOT / "system" / "branding"
LOCAL_TOKENS = ("tokens.css", "design-system/tokens.css")     # the first that exists
DEMO_ID = "brand-demo"            # the named hook: the local brand is layered after the element with this id
PICTURE_DIR = "assets"            # beside the user's tokens.css
PICTURES = {"cover.png": "image/png", "cover.jpg": "image/jpeg", "cover.jpeg": "image/jpeg", "cover.webp": "image/webp"}
PICTURE_MAX_BYTES = 5 * 1024 * 1024
CLIENT_BRAND = ":root { --logo-icon: none; }\n"      # before the user's tokens, so theirs win


ICON_LINKS = {      # SHA-256 of the picture's decoded bytes: (rel, mime) of its <link>
    "11d8526dbc1e91b74e541db82a2cb8ed04784ad702c6279410ad8f1858d8a384": ("icon", "image/svg+xml"),               # clark-icon.svg
    "5b46bd7786aab805faa93c1dcc250c1d284cb5c9e43adf96f656bc44e1e714df": ("icon", "image/png"),                   # clark-icon-32.png
    "ca3e8e79d1761c245d596d22287ccef7030933f7d358daced0cfad9cbdb22a7e": ("apple-touch-icon", "image/png"),       # clark-icon-180.png
}


def icon_link(rel, mime, payload):
    """The one spelling of an icon <link>: the build writes it and the finished-file scan rebuilds it to compare. `payload` is
    the picture's base64."""
    return f'<link rel="{rel}" type="{mime}" href="data:{mime};base64,{payload}">'


COMMENT = re.compile(r"/\*.*?\*/", re.S)


def strip_css_comments(css):
    """`css` without its comments (and without an unterminated one). A built or published file carries no comment at all: a
    comment in a source file can name a person or a date, and a file that leaves the machine must not carry either."""
    out = COMMENT.sub("", css)
    i = out.find("/*")
    return out if i < 0 else out[:i]


STYLE_UNSAFE = re.compile(r"<(?=/style|!--|script)", re.I)


def escape_style(css):
    """`css` made safe to sit inside a <style> element. A `<` that starts `</style`, `<!--` or `<script`, in any letter case,
    gets a backslash after it (`<\\/style`). In CSS a backslash before a character that is not a hex digit means that
    character, so the style reads the same, but the page's HTML can no longer see the end of the element (`</STYLE>` ends it
    just as `</style>` does), a comment or a script start inside it. (#106; the one escape for every brand text.)"""
    return STYLE_UNSAFE.sub("<\\\\", css)


def local_tokens_file(branding=None):
    """The user's own tokens.css as a Path (the first of LOCAL_TOKENS that exists), or None."""
    base = Path(branding) if branding is not None else BRANDING
    for name in LOCAL_TOKENS:
        if (base / name).is_file():
            return base / name
    return None


def local_tokens(branding=None):
    """The text of the user's own brand tokens, or None when there isn't one."""
    p = local_tokens_file(branding)
    return None if p is None else strip_css_comments(p.read_text(encoding="utf-8"))


def looks_like(ctype, head):
    """Whether the first bytes of a file are the kind of picture `ctype` says (PNG, JPEG or WebP)."""
    if ctype == "image/png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if ctype == "image/jpeg":
        return head.startswith(b"\xff\xd8\xff")
    return head[:4] == b"RIFF" and head[8:12] == b"WEBP"


def brand_picture(name, branding=None):
    """(bytes, content type) of one of the brand's pictures, or None. `name` must be one of PICTURES; the file is
    <the user's tokens.css folder>/assets/<name>, and it must still be inside the pictures folder (itself inside the brand folder) after symlinks are
    followed, be a regular file, be at most PICTURE_MAX_BYTES, and begin with the bytes its type needs. None for anything
    else (no tokens.css, no file, a link out of the folder, a wrong type): the server answers 404."""
    ctype = PICTURES.get(name)
    tokens = local_tokens_file(branding)
    if ctype is None or tokens is None:
        return None
    base = (Path(branding) if branding is not None else BRANDING).resolve()
    try:
        folder = (tokens.parent / PICTURE_DIR).resolve()
        found = (tokens.parent / PICTURE_DIR / name).resolve()
        if not folder.is_relative_to(base) or not found.is_relative_to(folder) or not found.is_file():       # inside the pictures folder, which is inside the brand folder
            return None
        with open(found, "rb") as f:
            data = f.read(PICTURE_MAX_BYTES + 1)
    except (OSError, RuntimeError, ValueError):
        return None
    return (data, ctype) if len(data) <= PICTURE_MAX_BYTES and looks_like(ctype, data[:16]) else None


class PageError(Exception):
    """The built page is not the shape clark expects. Said in words, with what to do next."""


SOURCES = HERE / "src"
BUILDER = ROOT / "dev" / "tools" / "build_page.py"      # in a source checkout only: the download has no dev/ folder
CACHE = ROOT / "dev" / ".cache"                          # git-ignored: the build stamp and the build lock
STAMP = CACHE / "pages.stamp"
LOCK = CACHE / "pages.lock"
_checked = False

try:
    import fcntl
except ImportError:         # Windows: only the in-process lock
    fcntl = None


def build_inputs():
    """Every file the build reads, sorted: the page's sources (not the built help copy), its shell CSS, this module (the build
    imports it), its assets, the brand tokens, the vendored libraries and fonts, and the two build tools."""
    files = []
    if SOURCES.is_dir():
        files += [f for f in SOURCES.rglob("*") if f.is_file() and "__pycache__" not in f.parts and "shown" not in f.relative_to(SOURCES).parts[:-1]]
    files += [HERE / "shell.css", HERE / "__init__.py", ROOT / "src" / "clark" / "brand" / "tokens.css",
              ROOT / "dev" / "tools" / "build_page.py", ROOT / "dev" / "tools" / "esbuild.py"]
    for d in (HERE / "assets", ROOT / "vendor" / "preact", ROOT / "vendor" / "tiptap", ROOT / "vendor" / "fonts"):
        if d.is_dir():
            files += [f for f in d.rglob("*") if f.is_file() and "__pycache__" not in f.parts]
    return sorted({f for f in files if f.is_file()})


def source_stamp():
    """A SHA-256 over the relative path and the content of every build input: the pages are stale when it differs from STAMP."""
    h = hashlib.sha256()
    for f in build_inputs():
        try:
            rel = f.relative_to(ROOT).as_posix()
        except ValueError:
            rel = f.as_posix()
        h.update(rel.encode("utf-8") + b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def _stamp_is(want):
    try:
        return STAMP.read_text(encoding="utf-8").strip() == want
    except OSError:
        return False


_build_lock = threading.Lock()


class _file_lock:
    """An exclusive flock on LOCK, so two processes never build at once; a no-op where fcntl does not exist."""

    def __enter__(self):
        self.f = None
        if fcntl is not None:
            CACHE.mkdir(parents=True, exist_ok=True)
            self.f = open(LOCK, "a+b")
            fcntl.flock(self.f, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        if self.f is not None:
            self.f.close()          # closing releases the lock


def ensure_built():
    """Make sure both generated pages exist and match their sources. In a source checkout (dev/tools/build_page.py is there) a
    missing page, or one built from other sources (the stamp differs: see source_stamp), is built with the pinned bundler.
    Anywhere else (the download) nothing is built: a missing page is a PageError. Never installs anything; the bundler is fetched
    by dev/tools/esbuild.py only in development. The check and the build run under an in-process lock and a cross-process file
    lock (dev/.cache/pages.lock), and the check is made again inside them, so two threads or two servers build once and the
    second waits for the first; the builder writes each page to a temporary file and swaps it in, so a reader never sees half a
    page. The server builds at start (clark.__main__). A source edited while a server runs is not rebuilt: restart the server."""
    global _checked
    pages = (PAGE, VIEW_PAGE)
    if not BUILDER.is_file():
        if not all(p.is_file() for p in pages):
            raise PageError("This copy of clark is missing its page files and cannot make them. Download clark again.")
        return
    if _checked and all(p.is_file() for p in pages):
        return
    with _build_lock, _file_lock():
        if _checked and all(p.is_file() for p in pages):
            return
        want = source_stamp()
        if not all(p.is_file() for p in pages) or not _stamp_is(want):
            done = subprocess.run([sys.executable, str(BUILDER)], cwd=str(ROOT), capture_output=True, text=True)
            if done.returncode != 0 or not all(p.is_file() for p in pages):
                raise PageError("The page could not be built (python3 dev/tools/build_page.py): "
                                + (done.stderr.strip().splitlines() or done.stdout.strip().splitlines() or ["no reason given"])[-1])
            CACHE.mkdir(parents=True, exist_ok=True)
            tmp = STAMP.with_name(STAMP.name + ".tmp")
            tmp.write_text(want, encoding="utf-8")
            os.replace(tmp, STAMP)
        _checked = True


DEMO_OPEN = re.compile(r"<style\b[^>]*?\sid\s*=\s*[\"']?" + DEMO_ID + r"[\"']?(?=[\s>/])[^>]*>", re.I)
STYLE_CLOSE = re.compile(r"</style\s*>", re.I)


def after_demo_block(html):
    """The index just after the closing tag of the demo block, found by its id (any spacing, attribute order or line ending),
    or raises PageError."""
    m = DEMO_OPEN.search(html)
    end = STYLE_CLOSE.search(html, m.end()) if m else None
    if end is None:
        raise PageError(f'The page has no <style id="{DEMO_ID}"> block, so your brand cannot be layered over it. Rebuild the '
                        "page (python3 dev/tools/build_page.py) and start clark again.")
    return end.end()


def page_html(branding=None, view=False):
    """The page, with the user's own brand tokens layered over the demo ones when they exist. view=True gives the published
    page (page-view.html) in place of the served one."""
    ensure_built()
    html = (VIEW_PAGE if view else PAGE).read_text(encoding="utf-8")
    css = local_tokens(branding)
    if css is None:
        return html
    css = escape_style(css)
    i = after_demo_block(html)
    return html[:i] + f'\n<style id="brand-local">\n{CLIENT_BRAND}{css}\n</style>' + html[i:]
