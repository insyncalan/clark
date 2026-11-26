"""Row 1390 slice 8: a Dashboard section type as lines of the Report sheet (excel_cover.lines), one function for each type.

Pure: a published section (what publish.select kept, with its `content`) goes in and a list of Cover lines comes out
({"kind": "heading" | "text", "text": ...}). Nothing is read from a store, a file or a clock. A section with nothing to say gives no
lines at all, heading included. Every reader is total: a value of the wrong shape is nothing, never an error. The text is plain
words; the writer stores it as text (a value that starts with = + - @ is never a formula).

Drawn: reportheadline, headline, quote, textimage, imagecap, gallery, figures3, figures4, table, contacts, checklist, keydates (row 1631 P2).
A section's own title is its heading; a section with no title has no heading line (no default words are invented). A picture is never drawn:
the words say "picture not in this export" (a gallery: "N pictures not in this export") and the captions stay. A checklist or Key dates
line that points at a work item or a milestone by id is not drawn (the Cover has no store to read it from); typed lines are.
Standard library only, Python 3.9.
"""
from clark import sanitise, timefmt
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


PICTURE = "picture not in this export"
PICTURES = "{n} pictures not in this export"
DOT = " · "
TICKED, UNTICKED = "\u2611 ", "\u2610 "      # the Word export's own ticks (docx_build.py), glyph and one space


def _content(sec):
    c = sec.get("content")
    return c if isinstance(c, dict) else {}


def _list(value):
    return value if isinstance(value, list) else []


def _dicts(value):
    return [x for x in _list(value) if isinstance(x, dict)]


def _plain(html):
    """Words from stored HTML or text; never a tag, never an error."""
    text = _s(html)
    if not text:
        return ""
    try:
        return sanitise.plain_text(text).strip()
    except Exception:
        return ""


def _t(lines):
    return [{"kind": "text", "text": t} for t in lines if t]


def _framed(sec, lines):
    """The heading (the section's own title, when it has one) before the lines; nothing when there are no lines."""
    lines = _t(lines)
    title = _s(sec.get("title"))
    return ([{"kind": "heading", "text": title}] if title else []) + lines if lines else []


def headline_block(sec):
    c = _content(sec)
    return _framed(sec, [_s(c.get("words")), PICTURE if c.get("image") else ""])


def quote_block(sec):
    c = _content(sec)
    out = []
    for q in _dicts(c.get("quotes")):
        if _s(q.get("quote")):
            out += [_s(q.get("quote")), DOT.join(p for p in (_s(q.get("by")), _s(q.get("role"))) if p)]
    return _framed(sec, out)


def textimage_block(sec):
    c = _content(sec)
    words = _plain(c.get("html")) or "\n".join(_s(w) for w in _list(c.get("words")) if _s(w))
    return _framed(sec, [_s(c.get("heading")), words, PICTURE if c.get("image") else "", _s(c.get("caption")) if c.get("image") else ""])


def imagecap_block(sec):
    c = _content(sec)
    return _framed(sec, [PICTURE, _s(c.get("caption"))] if c.get("image") else [])


def gallery_block(sec):
    shown = _dicts(_content(sec).get("pictures"))
    if not shown:
        return []
    first = PICTURE if len(shown) == 1 else PICTURES.format(n=len(shown))
    return _framed(sec, [first] + [_s(p.get("caption")) for p in shown])


def figures_block(sec):
    out = []
    for f in _dicts(sec.get("figures")):
        out.append(DOT.join(p for p in (_s(f.get("label")), _s(f.get("value")), _s(f.get("detail"))) if p))
    return _framed(sec, out)


def table_block(sec):
    c = _content(sec)
    cols = [_s(x) for x in _list(c.get("cols"))]
    rows = [[_s(x) for x in r] for r in _list(c.get("rows")) if isinstance(r, list)]
    return _framed(sec, [DOT.join(cols) if any(cols) else ""] + [DOT.join(r) for r in rows if any(r)] + [_s(c.get("caption"))])


def contacts_block(sec):
    out = []
    for p in _dicts(_content(sec).get("people")):
        if _s(p.get("name")):
            out.append(DOT.join(x for x in (_s(p.get("name")), _s(p.get("role")), _s(p.get("email")), _s(p.get("phone"))) if x))
    return _framed(sec, out)


def checklist_block(sec):
    out = []
    for i in _dicts(sec.get("items")):
        if _s(i.get("text")):
            out.append((TICKED if i.get("done") == 1 else UNTICKED) + _s(i.get("text")))
    return _framed(sec, out)


def keydates_block(sec):
    out = []
    for i in _dicts(sec.get("items")):
        if _s(i.get("label")) and _s(i.get("date")):
            out.append(f"{_s(i.get('label'))}{DOT}{timefmt.day_text(_s(i.get('date')))}")
    return _framed(sec, out)


BLOCKS = {"reportheadline": reportheadline_block, "headline": headline_block, "quote": quote_block, "textimage": textimage_block,
          "imagecap": imagecap_block, "gallery": gallery_block, "figures3": figures_block, "figures4": figures_block,
          "table": table_block, "contacts": contacts_block, "checklist": checklist_block, "keydates": keydates_block}


def block(sec):
    """The lines for one published section of a type in BLOCKS, or [] (never an error)."""
    make = BLOCKS.get(sec.get("type"))
    if make is None:
        return []
    try:
        return make(sec)
    except Exception:
        return []
