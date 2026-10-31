"""The committed look, read: the one place Word, Excel, the email and the offline page take their colours and fonts from.

The look is src/clark/brand/tokens.css (colour, type, shape and motion tokens; light first, then dark). The page inlines that file;
the files clark makes outside the page (a Word file, a workbook, an email, the offline page) cannot read a stylesheet, so each
reads the value it needs here, once, when clark starts. Nothing in those modules writes a hex or a font name of its own: a
change to the look reaches them with no edit there, and tests/test_export_colours.py names any token a file does not follow.

Two tokens are for the files that cannot carry the page's fonts (Inter and Montserrat are embedded in the page, and Word, Excel and
a mail app do not have them): --font-office is the one font Word and Excel use (a font Office has), and --font-email is the
family list an email carries (Outlook's Word engine, so Calibri first). Both are in the look, so one place sets them.

Reads only the committed look, not a person's own tokens.css in system/branding/ (the page layers that one over this).
Standard library only, Python 3.9.
"""
import re
from pathlib import Path

TOKENS_CSS = Path(__file__).resolve().parent / "brand" / "tokens.css"
LIGHT = r":root\s*\{(.*?)\n\}"
DARK = r":root\[data-theme=dark\]\s*\{(.*?)\n\}"
HEX = re.compile(r"#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})")
VAR = re.compile(r"var\(\s*(--[\w-]+)\s*\)")
FAMILY = re.compile(r"[A-Za-z0-9][A-Za-z0-9 .-]*")        # one font family name: letters, digits, spaces, dots and hyphens only
GENERIC = ("sans-serif", "serif", "monospace")


def _css(css=None):
    return TOKENS_CSS.read_text(encoding="utf-8") if css is None else css


def raw(name, mode="light", css=None):
    """A token's value as written in tokens.css (a var() to another token is followed). The first :root block is the light look; for
    "dark" the data-theme=dark block is read first. KeyError when the token is not there."""
    text = _css(css)
    blocks = [re.search(LIGHT, text, re.S).group(1)]
    if mode == "dark":
        blocks.insert(0, re.search(DARK, text, re.S).group(1))
    for block in blocks:
        m = re.search(r"(?<![\w-])" + re.escape(name) + r"\s*:\s*([^;]+);", block)
        if m:
            value = m.group(1).strip()
            ref = VAR.fullmatch(value)
            return raw(ref.group(1), mode, text) if ref else value
    raise KeyError(name)


def colour(name, mode="light", css=None):
    """A colour token as six upper-case hex digits, no #: `colour("brand-navy")` is "062F3A". The name may carry its leading --.
    #fff is read as FFFFFF. KeyError when the token is missing; ValueError when it is not a plain hex colour."""
    value = raw(name if name.startswith("--") else "--" + name, mode, css)
    m = HEX.fullmatch(value)
    if not m:
        raise ValueError(f"{name} is not a plain hex colour in the look")
    digits = m.group(1).upper()
    return "".join(c * 2 for c in digits) if len(digits) == 3 else digits


def families(name, css=None):
    """The font families a font token lists, in order, without quotes: ["Calibri", "Arial", "sans-serif"]. A name with anything
    but letters, digits, spaces, dots and hyphens is left out, so a family can never put markup or a quote into a file."""
    out = []
    for part in raw(name if name.startswith("--") else "--" + name, "light", css).split(","):
        part = part.strip().strip("'\"").strip()
        if FAMILY.fullmatch(part):
            out.append(part)
    return out


def office_font(css=None):
    """The font for Word and Excel: the first family of --font-office."""
    return families("--font-office", css)[0]


def family_list(name, css=None):
    """A font token as the value of a font-family: its families, a name with a space in single quotes, no other character
    that could end a style attribute or a style block."""
    return ",".join(f"'{f}'" if " " in f else f for f in families(name, css))


def email_font_family(css=None):
    """The font-family value for an email's inline styles: the families of --font-email."""
    return family_list("--font-email", css)
