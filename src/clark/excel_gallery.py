"""Row 1390 slice 8: the gallery section as lines of the Report sheet (excel_cover.lines).

Pure: a published gallery section (what publish.select kept, with its `content`) goes in and a list of Cover lines comes out
({"kind": "heading" | "text", "text": ...}). The pictures are not put in the workbook: each picture's caption is a line, then one
line says how many pictures are not in this export. A section with no picture gives no lines, heading included. Total: a value
of the wrong shape is nothing, never an error. Plain text only; the writer stores it as text (a value that starts with = + - @ is
never a formula). Standard library only, Python 3.9.
"""
HEADING = "Gallery"
ONE = "1 picture not in this export"
MANY = "{n} pictures not in this export"
MAX = 6                      # the gallery holds six slots (section_kinds.gallery.SLOTS)
CAPTION_LIMIT = 500


def _caption(pic):
    text = pic.get("caption") if isinstance(pic, dict) else None
    return " ".join(text.split())[:CAPTION_LIMIT] if isinstance(text, str) else ""


def note(count):
    """The line that says how many pictures are left out."""
    return ONE if count == 1 else MANY.format(n=count)


def gallery_block(sec):
    """Heading (the section's title, else "Gallery"), each caption on its own line in slot order, then the not-in-this-export line."""
    content = sec.get("content")
    pics = content.get("pictures") if isinstance(content, dict) else None
    pics = [p for p in pics if isinstance(p, dict)][:MAX] if isinstance(pics, list) else []
    if not pics:
        return []
    title = sec.get("title")
    head = " ".join(title.split()) if isinstance(title, str) else ""
    out = [{"kind": "heading", "text": head or HEADING}]
    out += [{"kind": "text", "text": c} for c in map(_caption, pics) if c]
    out.append({"kind": "text", "text": note(len(pics))})
    return out
