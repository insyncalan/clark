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
    """A callout section's lines as [(text, is_heading)], in order: its title (else "Callout") as the heading (left out when its Heading switch is off, as the Word build does: content "heading" false, on when absent); one line
    "Category: <c>. Colour: <c>. Icon: <i>." with each empty part left out (Plain colour and No icon count as empty; no line when
    all are); then its words, one entry per paragraph. Ruling M8851 (row 1272): [] only when all five fields (title, category, colour, icon, words)
    are empty (the colour and icon as the callout itself stores them: Plain and No icon are empty, and a tone's default words do not count), so a callout with just a category, colour or icon still gets its heading and its Category/Colour/Icon line."""
    c = sec.get("content") if isinstance(sec.get("content"), dict) else {}
    got = callout.words(c)
    words = _plain(c["html"]) if isinstance(c.get("html"), str) and c["html"] else "\n".join(p for p in c.get("paras") or () if isinstance(p, str))
    title = c.get("title") if isinstance(c.get("title"), str) else ""
    colour = "" if got["colour_name"] == callout.COLOURS["plain"] else got["colour_name"]
    own = (isinstance(c.get("category"), str) and c["category"].strip(), c.get("colour") not in (None, "plain"), c.get("icon") not in (None, "none"))
    if not (title or words or any(own)):
        return []
    parts = [f"{label}: {value}." for label, value in (("Category", got["category"]), ("Colour", colour), ("Icon", got["icon_name"])) if value]
    head = [(title or "Callout", True)] if c.get("heading", True) else []
    return head + ([(" ".join(parts), False)] if parts else []) + [(w, False) for w in words.split("\n") if w.strip()]
