"""Row 1390 slice 9: a Text section as lines of the Report sheet (excel_cover.lines). Pure: a published text section goes in and a list
of {"kind": "heading" | "text", "text"} lines comes out. No workbook, no store, no file, no clock. Standard library only.

A Text section is its heading and its words, as plain paragraphs (never a tag; a new paragraph or list item is a new line). A section
whose words are empty has no lines at all, heading included. A section with no title is its words alone: no empty heading is drawn.
The writer (excel.write_cover) escapes every line, so words that start like a formula stay text.
"""
TITLE_LIMIT = 200


def text_lines(sec, plain):
    """The Report lines of one published Text section ({"title", "body"} with `body` HTML). `plain` turns the body into its words
    (excel_cover.plain: cleaned, cut under Excel's cell limit); it is given so this module reads no other module."""
    if not isinstance(sec, dict) or not isinstance(sec.get("body"), str):
        return []              # a body that is not text is nothing, not its Python spelling
    words = plain(sec["body"])
    if not isinstance(words, str) or not words.strip():
        return []
    title = sec.get("title")
    title = title[:TITLE_LIMIT] if isinstance(title, str) and title.strip() else ""      # kept as typed (the writer escapes it), as the Cover always did
    return ([{"kind": "heading", "text": title}] if title else []) + [{"kind": "text", "text": words}]
