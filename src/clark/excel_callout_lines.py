"""Row 1272: a callout's text lines for the client Excel, as a pure function (no sheet, no workbook, no openpyxl).
The Report sheet writer calls `callout_lines(section)` and writes each (text, is_heading) as one row.
"""
import html
import re

from clark import sanitise
from clark.section_kinds import callout

_BLOCKS = re.compile(r"</(?:p|div|li|h[1-6]|blockquote|pre|tr)>|<br\s*/?>|<hr\s*/?>", re.I)
_TAGS = re.compile(r"<[^>]*>")


def _plain(value):
    clean = sanitise.clean_html(value or "")
    return html.unescape(_TAGS.sub("", _BLOCKS.sub("\n", clean))).strip()


def callout_lines(sec):
    """A callout section's lines as [(text, is_heading)], in order: its title (else "Callout") as the heading; one line
    "Category: <c>. Colour: <c>. Icon: <i>." with each empty part left out (Plain colour and No icon count as empty; no line when
    all are); then its words, one entry per paragraph. [] when it has no title and no words."""
    c = sec.get("content") if isinstance(sec.get("content"), dict) else {}
    got = callout.words(c)
    words = _plain(c["html"]) if isinstance(c.get("html"), str) and c["html"] else "\n".join(p for p in c.get("paras") or () if isinstance(p, str))
    title = c.get("title") if isinstance(c.get("title"), str) else ""
    if not title and not words:
        return []
    colour = "" if got["colour_name"] == callout.COLOURS["plain"] else got["colour_name"]
    parts = [f"{label}: {value}." for label, value in (("Category", got["category"]), ("Colour", colour), ("Icon", got["icon_name"])) if value]
    return [(title or "Callout", True)] + ([(" ".join(parts), False)] if parts else []) + [(w, False) for w in words.split("\n") if w.strip()]
