"""The page the server sends (#35): the committed, built page.html, with a user's own brand layered over the demo one.

page.html is built by dev/tools/build_page.py and committed; nothing is built when clark runs. It carries the demo brand's
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

The font is Readex Pro (vendor/fonts/readex-pro/, SIL Open Font License): the build inlines it as @font-face rules with the woff2
as base64 `data:` URIs at the top of the demo block, so the page is still one file and the policy's `font-src 'self' data:`
is enough. A user's own brand sets `--font`; the font-face rules stay, so naming "Readex Pro" in it works.
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PAGE = HERE / "page.html"
VIEW_PAGE = HERE / "page-view.html"      # #65: the same page with no Edit part and no route that changes anything
BRANDING = ROOT / "system" / "branding"
LOCAL_TOKENS = ("tokens.css", "design-system/tokens.css")     # the first that exists
MARK = "</style>\n</head>"
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


def local_tokens(branding=None):
    """The text of the user's own brand tokens, or None when there isn't one."""
    base = Path(branding) if branding is not None else BRANDING
    for name in LOCAL_TOKENS:
        p = base / name
        if p.is_file():
            return strip_css_comments(p.read_text(encoding="utf-8"))
    return None


def page_html(branding=None, view=False):
    """The page, with the user's own brand tokens layered over the demo ones when they exist. view=True gives the published
    page (page-view.html) in place of the served one."""
    html = (VIEW_PAGE if view else PAGE).read_text(encoding="utf-8")
    css = local_tokens(branding)
    if css is None:
        return html
    css = escape_style(css)
    return html.replace(MARK, f'</style>\n<style id="brand-local">\n{CLIENT_BRAND}{css}\n</style>\n</head>', 1)
