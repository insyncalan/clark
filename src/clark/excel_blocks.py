"""Row 1390 slice 8: a Dashboard section type as lines of the Report sheet (excel_cover.lines), one function for each type.

Pure: a published section (what publish.select kept, with its `content`) goes in and a list of Cover lines comes out
({"kind": "heading" | "text", "text": ...}). Nothing is read from a store, a file or a clock. A section with nothing to say gives no
lines at all, heading included. Every reader is total: a value of the wrong shape is nothing, never an error. The text is plain
words; the writer stores it as text (a value that starts with = + - @ is never a formula).

Drawn so far: reportheadline (the first new type; the others follow in later slices).
Standard library only, Python 3.9.
"""
from clark.section_kinds import reportheadline

HEADING = "Report headline"


def _s(value):
    return value.strip() if isinstance(value, str) else ""


def reportheadline_block(sec):
    """The section's heading, then "<health word> · <headline>" on one line (each part only when it is there), then the supporting
    sentence on its own line. Nothing when all three are empty."""
    c = sec.get("content")
    c = c if isinstance(c, dict) else {}
    health = c.get("health")
    word = reportheadline.WORDS.get(health, "") if isinstance(health, str) and health else ""
    first = " · ".join(p for p in (word, _s(c.get("headline"))) if p)
    body = [{"kind": "text", "text": t} for t in (first, _s(c.get("sentence"))) if t]
    return [{"kind": "heading", "text": _s(sec.get("title")) or HEADING}] + body if body else []


BLOCKS = {"reportheadline": reportheadline_block}


def block(sec):
    """The lines for one published section of a type in BLOCKS, or [] (never an error)."""
    make = BLOCKS.get(sec.get("type"))
    if make is None:
        return []
    try:
        return make(sec)
    except Exception:
        return []
