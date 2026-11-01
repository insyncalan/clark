"""Table (F6, #96): the content of a section of type 'table': a small typed table. READY.

Stored (canonical JSON): {"v": 1, "cols": [text, ...], "rows": [[text, ...], ...], "caption": text}. Typed only. Every row
has as many cells as there are columns (a short row is padded, a long one refused). A table with no text in any header, cell
or caption is empty: it starts as '' (no content) and stays out of the published file; in the file a row with no text is left out.
"""
from clark.section_kinds.base import Bad

READY = True
LIMIT = 65536
EMPTY = ""

COLS_MAX, ROWS_MAX, CELL_MAX, CAPTION_MAX = 8, 30, 200, 200

NOT_OBJECT = "A table must be one set of fields. Check it and try again."
BAD_FIELD = "A table field has the wrong kind of value. Check it and try again."
TOO_MANY_COLS = f"A table can have {COLS_MAX} columns at most. Remove one and try again."
NO_COLS = "A table needs at least one column."
TOO_MANY_ROWS = f"A table can have {ROWS_MAX} rows at most. Remove one and try again."
TOO_LONG = f"A table cell can be {CELL_MAX} characters at most, and the caption {CAPTION_MAX}. Shorten it and try again."
RAGGED = "A row has more cells than the table has columns. Add a column or shorten the row."


def _text(value, most=CELL_MAX):
    if value is None:
        return ""
    if not isinstance(value, str):
        raise Bad(BAD_FIELD)
    value = value.strip()
    if len(value) > most:
        raise Bad(TOO_LONG)
    return value


def check(value, rules):
    """The table rebuilt cell by cell, or Bad in plain words that never quote it."""
    if not isinstance(value, dict) or value.get("v") != 1:
        raise Bad(NOT_OBJECT)
    cols, rows = value.get("cols", []), value.get("rows", [])
    cols, rows = [] if cols is None else cols, [] if rows is None else rows
    if type(cols) is not list or type(rows) is not list:
        raise Bad(BAD_FIELD)
    caption = _text(value.get("caption"), CAPTION_MAX)
    if not cols:
        if rows or caption:
            raise Bad(NO_COLS)
        return {"v": 1, "cols": [], "rows": [], "caption": ""}
    if len(cols) > COLS_MAX:
        raise Bad(TOO_MANY_COLS)
    if len(rows) > ROWS_MAX:
        raise Bad(TOO_MANY_ROWS)
    cols = [_text(c) for c in cols]
    out = []
    for r in rows:
        if type(r) is not list:
            raise Bad(BAD_FIELD)
        if len(r) > len(cols):
            raise Bad(RAGGED)
        cells = [_text(c) for c in r]
        out.append(cells + [""] * (len(cols) - len(cells)))
    return {"v": 1, "cols": cols, "rows": out, "caption": caption}


def published(value, ctx):
    """{"content": {cols, rows, caption}} with the rows that hold text, or None when no header, cell or caption has any."""
    cols, rows = list(value.get("cols", ())), [r for r in value.get("rows", ()) if any(r)]
    if not any(cols) and not rows:
        return None
    return {"content": {"cols": cols, "rows": [list(r) for r in rows], "caption": value.get("caption", "")}}
