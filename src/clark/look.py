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


class LookError(ValueError):
    """The look cannot give a value, in plain words naming the token or the file. The one error this module raises for a missing file,
    a missing token, a token that refers to itself, a colour that is not a plain hex colour and a font token with no usable name."""


def _css(css=None):
    if css is not None:
        return css
    try:
        return TOKENS_CSS.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        raise LookError("clark's look file (src/clark/brand/tokens.css) is missing or cannot be read.") from None


def _block(pattern, text):
    """The inside of a block. The committed file closes each block with a brace at the start of a line; a short text with the
    brace after a space (a test's) is read too, with the same pattern up to the first brace."""
    m = re.search(pattern, text, re.S) or re.search(pattern.replace(r"\n\}", r"\}"), text, re.S)
    if not m:
        raise LookError("The look has no block of tokens in the shape clark reads (the first :root block, and the dark block).")
    return m.group(1)


def raw(name, mode="light", css=None, _seen=()):
    """A token's value as written in tokens.css (a var() to another token is followed). The first :root block is the light look; for
    "dark" the data-theme=dark block is read first. LookError when the token is not there or refers back to itself."""
    if name in _seen:
        raise LookError(f"The look's token {name} refers back to itself.")
    text = _css(css)
    blocks = [_block(LIGHT, text)]
    if mode == "dark":
        blocks.insert(0, _block(DARK, text))
    for block in blocks:
        m = re.search(r"(?<![\w-])" + re.escape(name) + r"\s*:\s*([^;]+);", block)
        if m:
            value = m.group(1).strip()
            ref = VAR.fullmatch(value)
            return raw(ref.group(1), mode, text, _seen + (name,)) if ref else value
    raise LookError(f"The look has no token named {name}.")


def colour(name, mode="light", css=None):
    """A colour token as six upper-case hex digits, no #: `colour("brand-navy")` is "062F3A". The name may carry its leading --.
    #fff is read as FFFFFF. LookError when the token is missing or is not a plain hex colour."""
    token = name if name.startswith("--") else "--" + name
    m = HEX.fullmatch(raw(token, mode, css))
    if not m:
        raise LookError(f"The look's token {token} is not a plain hex colour (such as #0E2430).")
    digits = m.group(1).upper()
    return "".join(c * 2 for c in digits) if len(digits) == 3 else digits


def families(name, css=None):
    """The font families a font token lists, in order, without quotes: ["Calibri", "Arial", "sans-serif"]. A name with anything
    but letters, digits, spaces, dots and hyphens is left out, so a family can never put markup or a quote into a file."""
    token = name if name.startswith("--") else "--" + name
    out = []
    for part in raw(token, "light", css).split(","):
        part = part.strip().strip("'\"").strip()
        if FAMILY.fullmatch(part):
            out.append(part)
    if not out:
        raise LookError(f"The look's token {token} names no usable font (use plain names, such as Arial).")
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
