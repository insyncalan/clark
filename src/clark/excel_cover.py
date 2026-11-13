"""What the workbook's Cover sheet says, as plain lines (item 85b): no workbook, no file, no clock and no database.

The caller gives the project row, its report sections, its At a glance tiles and the words for the export's date; this gives
back a list of {"kind", ...} lines in the order the Cover shows them. Writing them into cells (a 12-column grid of merged cells,
the text escaping, the row heights and the sheet order) is the workbook's job (excel.py). Standard library only, Python 3.9.

What the Cover holds, top to bottom, in the dashboard's order (Option A of the signed mockup): the title band (the report title,
tagged INTERNAL when the internal note is given, and a subtitle line: Weekly report, the week ending and the client, as the
page's band shows them), then in the order of `sections` the Current state, At a glance (one "tiles" line: health with its
reason, then each tile that is shown with its number and sub-line) and every text section. This week and Next week, when both
have words and follow one another, are ONE "pair" line, drawn side by side. A section with nothing to show is left off,
heading and all. A hidden section and a hidden tile are not here at all. Last, a quiet "About this export" block: when and by
whom it was exported, the caution, sending changes back, where to make changes and the IDs note. There is no Internal line
there: the title band's tag says it.
Nothing else of a project reaches the Cover; every line is built from the fields named below, so no other field can leak in.

The sentences are constants so that changing one is one edit: CAUTION, RETURN_WITH, RETURN_ANYONE, WHERE_TO_EDIT, IDS, LOCKED_CELLS.
"""
from clark import sanitise
from clark import timefmt

CAUTION = "This workbook shows the project as it was on the date above. It does not include changes made in clark since."
RETURN_WITH = ("If you change anything here, send the file back to {owner}{email}. They then import your changes into clark, "
               "which checks each one before saving it.")
RETURN_ANYONE = ("If you change anything here, send the file back to the person who sent it to you. They then import your changes into "
                 "clark, which checks each one before saving it.")
WHERE_TO_EDIT = ("Make your changes on the Actions, Risks & Issues, Decisions, Milestones and Use cases sheets. Changes made on "
                 "this Cover are ignored.")
ABOUT = "About this export"
INTERNAL_TAG = "INTERNAL"
MORE = " … (continues in clark)"
LIMIT = 32000                 # under Excel's 32,767 characters in one cell, with room for MORE
IDS = ("Please don't change or move IDs. Each ID stays with its own row: if you change one, or sort only the ID column, "
       "the details go to another item when the file is imported. Leave the ID empty for a new item.")                                       # #128: says what the import (#129) really does with an ID
LOCKED_CELLS = ("Some cells are locked so they are not changed by mistake, such as the ID column and the columns clark works out. "
                "To change them, choose Review, then Unprotect Sheet. There is no password. "
                "Excel will not sort a protected sheet; unprotect it first.")
SUBTITLE_KIND = "Weekly report"
KINDS = ("title", "subtitle", "heading", "text", "tiles", "pair", "about", "exported", "caution", "return", "where", "ids", "locked")
LINE_POINTS = 13.5            # one line of the 10 point body text, for the row heights
MAX_ROW_POINTS = 409          # Excel's tallest row


def cut(text, limit=LIMIT):
    """`text`, or its first `limit` characters and a mark that it goes on, if it is longer than a cell can hold."""
    text = str(text or "")
    return text if len(text) <= limit else text[:limit - len(MORE)].rstrip() + MORE


def plain(html):
    """A section's words from its HTML: paragraphs, list items and line breaks as new lines; never a tag. A body too long for
    the cleaner is cut before it is read, so a hostile one can't stop the export."""
    text = str(html or "")
    try:
        return cut(sanitise.plain_text(text))
    except sanitise.SanitiseError:
        try:
            return cut(sanitise.plain_text(text[:LIMIT]))
        except sanitise.SanitiseError:
            return ""


def return_note(owner=None, email=None):
    """The return note: to the owner by name (and address, when there is one), else to whoever sent the file."""
    owner = str(owner or "").strip()
    if not owner:
        return RETURN_ANYONE
    email = str(email or "").strip()
    return RETURN_WITH.format(owner=owner, email=f" ({email})" if email else "")


def _line(kind, text="", **more):
    """One Cover line: {"kind", "text"} and whatever else that kind carries."""
    line = {"kind": kind, "text": text}
    line.update(more)
    return line


def _text(text):
    """A body as lines: none at all when it is empty, so the Cover has no blank rows."""
    return [_line("text", text)] if text.strip() else []


def show_date(iso):
    """DD-MM-YYYY, as the page's band shows a week ending; text that is not a stored day is shown as stored."""
    return timefmt.day_text(str(iso or "").strip())


def long_date(iso):
    """'Friday 30 October 2026' from a stored YYYY-MM-DD that is a real day (the signed Option A wording); text that is not a
    stored day is shown as stored. The day names and the months are English, whatever the computer's language."""
    from clark import draft_email, milestone_rows
    day = draft_email._as_day(str(iso or "").strip())
    if day is None:
        return str(iso or "").strip()
    return f"{draft_email.WEEKDAYS[day.weekday()]} {day.day} {milestone_rows.MONTHS[day.month - 1]} {day.year}"


def subtitle(project):
    """'Weekly report · Week ending Friday 23 October 2026 · for Example Client' (the signed Option A): from the same two fields
    of the project row as the page's report band. A part with nothing to show is left out."""
    parts = [SUBTITLE_KIND]
    week = str(project.get("week_ending") or "").strip()
    client = str(project.get("client_name") or "").strip()
    if week:
        parts.append(f"Week ending {long_date(week)}")
    if client:
        parts.append(f"for {client}")
    return cut(" \u00b7 ".join(parts), 500)


def rows_needed(text, chars):
    """How many lines `text` takes in a cell about `chars` characters wide: a new line starts a new one, a long line wraps at a
    space, a word longer than a line is broken where it falls. An estimate, because Excel does not fit a merged cell's height to
    its text, so the writer sets the height."""
    chars = max(1, int(chars))
    total = 0
    for para in str(text or "").split("\n"):
        n, line = 1, 0
        for word in para.split(" "):
            need = len(word) + (1 if line else 0)
            if line and line + need > chars:
                n, line, need = n + 1, 0, len(word)
            while need > chars:
                n, need = n + 1, need - chars
            line += need
        total += n
    return total


def height(text, chars, minimum=15, line=LINE_POINTS):
    """The row height in points for `text` in a cell `chars` characters wide, from its length (see rows_needed)."""
    return min(MAX_ROW_POINTS, max(minimum, rows_needed(text, chars) * line + 4))


def _tile(t):
    """One shown tile as the Cover keeps it: its title, its big number (the words, for health), its sub-line and its colour.
    The health tile's sub-line is its reason."""
    health = t.get("tile") == "health"
    detail = str(t.get("reason") or "").strip() if health else str(t.get("detail") or "").strip()
    colour = (t.get("pill") or {}).get("colour") if health else t.get("colour")
    return {"tile": t.get("tile"), "title": cut(str(t.get("title") or ""), 200), "value": cut(str(t.get("value", "")), 200),
            "detail": cut(detail, 2000), "colour": colour or None}


def lines(project, sections, tiles, exported, by=None, owner=None, email=None, internal=""):
    """The Cover as a list of {"kind", "text", ...}.

    project  the project row: "name" (or "code"), "current_state" (HTML), "week_ending" and "client_name"; read only
    sections the report_sections rows in order: type, title, body (HTML), hidden
    tiles    glance.tiles(...) output (the editor's, with `hidden`): tile, title, value, detail, reason, colour, pill
    exported the words for the export's date and time, for example excel.exported_text()
    by       the name that exported it (Settings › Profile); owner, email: who the file goes back to
    internal the INTERNAL sentence (excel.INTERNAL_NOTE): when given, the title band carries the tag INTERNAL. The sentence
             itself is not on the Cover."""
    name = str(project.get("name") or project.get("code") or "").strip()
    title = _line("title", cut(name, 200))
    if internal:
        title["tag"] = INTERNAL_TAG
    out = [title, _line("subtitle", subtitle(project))]
    shown = [s for s in sections or [] if not s.get("hidden")]
    skip = None
    for i, sec in enumerate(shown):
        if i == skip:
            continue
        kind = sec.get("type")
        if kind == "current":
            body = _text(plain(project.get("current_state")))
            if body:
                out += [_line("heading", cut(sec.get("title") or "Current state", 200))] + body
        elif kind == "glance":
            part = [_tile(t) for t in tiles or [] if not t.get("hidden")]
            if part:
                out += [_line("heading", cut(sec.get("title") or "At a glance", 200)), _line("tiles", "", tiles=part)]
        elif kind == "text":
            body = plain(sec.get("body"))
            nxt = shown[i + 1] if i + 1 < len(shown) else {}
            if (str(sec.get("title") or "").strip().lower() == "this week" and nxt.get("type") == "text"
                    and str(nxt.get("title") or "").strip().lower() == "next week"
                    and body.strip() and plain(nxt.get("body")).strip()):
                left = {"title": cut(sec.get("title"), 200), "text": body}
                right = {"title": cut(nxt.get("title"), 200), "text": plain(nxt.get("body"))}
                out.append(_line("pair", "", left=left, right=right))
                skip = i + 1
            elif body.strip():
                out += [_line("heading", cut(sec.get("title") or "", 200))] + _text(body)
    stamp = str(exported).strip()
    out += [_line("about", ABOUT),
            _line("exported", cut(f"{stamp} by {str(by).strip()}" if by and str(by).strip() else stamp, 400)),
            _line("caution", CAUTION), _line("return", cut(return_note(owner, email), 1000)),
            _line("where", WHERE_TO_EDIT), _line("ids", IDS),
            _line("locked", LOCKED_CELLS)]
    return out


def from_store(store, code, exported, by=None, owner=None, email=None, internal="", as_at=None):
    """The Cover for project `code`, worked out from the store the way the published page is (#39): `publish.select` decides what
    is shown, so a hidden section, a hidden row and a Sensitive item are absent here as they are there, and the tiles count what
    the page counts (`glance.tiles(for_client=True)`). Nothing is read that the page does not read. Needs the project to
    exist (publish.PublishError otherwise). The tile settings (order, hidden) are the defaults until the page reads them too."""
    from clark import glance, publish
    inputs = publish.read_inputs(store, code, as_at)
    shown = publish.select(inputs)
    today = inputs["as_at"]
    kept = glance.kept_rows(inputs["data"], today, sections=inputs.get("sections"), label_rules=inputs.get("label_rules"),
                             deleted=inputs.get("sections_deleted"))
    tiles = glance.tiles(inputs["data"], today, for_client=True, kept=kept)
    sections = [dict(s, hidden=0) for s in shown["sections"]]
    return lines(shown["data"]["project"], sections, tiles, exported, by, owner, email, internal)
