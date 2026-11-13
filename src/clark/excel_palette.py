"""The Excel export's palette, read from the SAME local brand the page uses (item 711), with the committed look as the floor.

`palette()` is pure: it reads the user's own tokens.css (clark.page.local_tokens, comment-stripped CSS or None), layers it over the
committed src/clark/brand/tokens.css, and returns the colours, status pairs and office font the workbook draws with. It never writes
anything, never caches (a second call with another brand gives another palette) and puts no brand data anywhere but the returned value.

Rules:
- A brand file may hold only some names; the rest come from the committed look. var() chains are followed (look.py).
- PER TOKEN: a value that is missing or not a plain hex colour (rgb(), hsl(), color-mix() ...) falls back to the committed value, and a
  warning is added to `Palette.warnings` (and to the caller's `warnings` list, the export's own).
- PER PAIR: a text-on-fill pair under 4.5:1 (each status tint and its text, the header, the title band, the tag, the quiet rows, the late
  text, the headings) gives up BOTH of its tokens to the committed values, with a warning.
- The font is the first family of the brand's --font-office that look.py accepts and that is not a generic, else the committed one.
Standard library only, Python 3.9. excel.export() builds the palette once and hands it to the workbook writers; its notes go to the log only.
"""
import re
from dataclasses import dataclass, field

from clark import excel_colours as base
from clark import look

MIN_CONTRAST = 4.5
MAX_FONT_NAME = 31      # Excel's limit for a font name
# NOTE (row 1021): the status cells read the --tone-* tokens. A brand file that only sets the older --status-* names no longer restyles them
# (it is ignored silently, as any name the export does not read); it sets --tone-red-text, --tone-red-tint ... to restyle the status cells.
# (fill token, text token, what it draws), each checked at 4.5:1. The status pairs come from excel_colours.COLOURS.
EXTRA_PAIRS = (
    ("brand-navy", "white", "the header and the title band"),
    ("status-red", "white", "the cover's INTERNAL tag"),
    ("tone-urgent", "white", "the Urgent tile's white letter"),
    ("grey-50", "grey-700", "the cover's quiet rows"),
    ("white", "tone-red-text", "a late date"),
    ("white", "brand-blue", "the cover's headings"),
    ("brand-navy", "grey-100", "the cover's subtitle"),
    ("grey-50", "brand-ink", "the cover's tiles"),
)
DECL = re.compile(r"(--[\w-]+)\s*:\s*([^;]+)(?:;|$)")   # the last declaration of a block may have no closing semicolon


def _channel(hexa):
    h = hexa.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def luminance(hexa):
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in _channel(hexa)]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast_ratio(hex_a, hex_b):
    """The WCAG contrast ratio of two hex colours (with or without #, 3 or 6 digits): 1.0 to 21.0."""
    hi, lo = sorted((luminance(hex_a), luminance(hex_b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@dataclass(frozen=True)
class Palette:
    tokens: dict            # token name -> hex (no #), the same 17 names as excel_colours.TOKEN_NAMES
    colours: dict           # colour name -> (fill token, text token), the same as excel_colours.COLOURS
    font: str               # the office font
    warnings: list = field(default_factory=list)

    @property
    def header_fill(self):
        return self.tokens["brand-navy"]

    @property
    def header_text(self):
        return self.tokens["white"]

    @property
    def late_text(self):
        return self.tokens["tone-red-text"]

    def hexes(self, name):
        """(fill hex, text hex) for a colour name, as excel_colours.hexes."""
        fill, text = self.colours[name]
        return self.tokens[fill], self.tokens[text]


def _light_rules(css):
    """The declarations text of every top-level rule whose selector is exactly `:root` (the light look). A dark selector
    (`:root[data-theme=dark]`) and anything inside an at-rule (`@media (prefers-color-scheme: dark)`) is skipped whole, by brace depth,
    so a dark value can never reach the workbook whatever the order of the blocks or where the closing braces sit."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    out, depth, start, selector, mark = [], 0, 0, "", 0
    for i, ch in enumerate(css):
        if ch == "{":
            if depth == 0:
                selector, mark = css[start:i].strip(), i + 1
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0:
                if selector == ":root":
                    out.append(css[mark:i])
                start = i + 1
    return out


def _declarations(css):
    """{name: value} of the light :root block(s), later ones over earlier; None when there is none."""
    blocks = _light_rules(css)
    if not blocks:
        return None
    return {k: v.strip() for block in blocks for k, v in DECL.findall(block)}


def _merged(brand_css):
    """(css text with the brand's names layered over the committed ones, warning or None)."""
    committed = _declarations(look._css()) or {}
    brand = _declarations(brand_css)
    note = None
    if brand is None:
        brand, note = {}, "The brand's colours file could not be read, so clark's standard colours were used in the workbook."
    merged = dict(committed)
    merged.update({k: v.strip() for k, v in brand.items()})
    return ":root {\n" + "\n".join(f"{k}: {v};" for k, v in merged.items()) + "\n}", note


MAX_BRAND_BYTES = 256 * 1024      # a brand's tokens.css bigger than this is not read


def _brand_css(branding, notes):
    """The local brand's token text (comments removed), or None. A file that is too big, not UTF-8 or unreadable never blocks an export:
    the committed look is used and a note is added."""
    from clark import page          # late: the page module is large and the committed palette needs none of it
    try:
        path = page.local_tokens_file(branding)
        if path is None:
            return None
        if path.stat().st_size > MAX_BRAND_BYTES:
            notes.append("The brand's colours file is too large to read, so clark's standard colours were used in the workbook.")
            return None
        return page.strip_css_comments(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        notes.append("The brand's colours file could not be read, so clark's standard colours were used in the workbook.")
        return None


def palette(css=None, branding=None, warnings=None):
    """The workbook's palette. `css` is the brand's token text (default: the local brand, clark.page.local_tokens(branding), or none).
    `warnings` is an optional list that also receives each warning string."""
    notes = []
    if css is None:
        css = _brand_css(branding, notes)
    committed = dict(base.TOKENS)
    tokens, font = dict(committed), look.office_font()
    colours = dict(base.COLOURS)
    if css is not None:
        merged, note = _merged(css)
        if note:
            notes.append(note)
        for name in base.TOKEN_NAMES:
            try:
                tokens[name] = look.colour(name, css=merged)
            except look.LookError as e:
                notes.append(f"The brand colour {name} could not be used, so clark's standard colour was used for it in the workbook.")
        for _ in range(len(base.TOKEN_NAMES)):
            bad = [(f, t, what) for f, t, what in _pairs(colours) if contrast_ratio(tokens[f], tokens[t]) < MIN_CONTRAST]
            changed = False
            for f, t, what in bad:
                if (tokens[f], tokens[t]) != (committed[f], committed[t]):
                    tokens[f], tokens[t] = committed[f], committed[t]
                    notes.append(f"Brand colours {f} and {t} ({what}) are under 4.5:1; the committed pair is used.")
                    changed = True
            if not changed:
                break
        try:
            font = next(f for f in look.families("--font-office", merged) if f.lower() not in look.GENERIC and len(f) <= MAX_FONT_NAME)
        except (look.LookError, StopIteration):
            font = look.office_font()
            if "--font-office" in (_declarations(css) or {}):
                notes.append("Brand --font-office names no usable font; the committed font is used.")
    if warnings is not None:
        warnings.extend(notes)
    return Palette(tokens, colours, font, notes)


def _pairs(colours):
    for name, (fill, text) in colours.items():
        yield fill, text, f"the {name} status"
    yield from EXTRA_PAIRS


def committed():
    """The committed (no brand) palette, with no brand read and nothing warned: what excel.py draws with when no palette is given."""
    return Palette(dict(base.TOKENS), dict(base.COLOURS), look.office_font(), [])
