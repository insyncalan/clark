"""What the workbook's Cover sheet says, as plain lines (#85b): no workbook, no file, no clock and no database.

The caller gives the project row, its report sections, its At a glance tiles and the words for the export's date; this gives
back a list of {"kind", "text"} lines in the order the Cover shows them. Writing them into cells (one label column and one
wide wrapped column, no merged cells), the text escaping and the sheet order are the workbook's job (excel.py). Standard
library only, Python 3.9.

What the Cover holds, top to bottom, in one column in the dashboard's order: the title band (the report title, tagged
INTERNAL when the internal note is given), then in the order of `sections` the Current state, At a glance (health, its
reason, each tile that is shown) and every text section (the Summary, This week and Next week sections are text sections). A
section with nothing to show (an empty body, no visible tile) is left off, heading and all. A hidden section and a hidden tile
are not here at all: not dimmed, not blank. Last, a quiet "About this export" block: who exported it and when, the caution,
sending changes back, where to make changes, and the full INTERNAL sentence.
Nothing else of a project reaches the Cover; every line is built from the fields named below, so no other field can leak in.

that changing one is one edit: CAUTION, RETURN_WITH, RETURN_ANYONE, WHERE_TO_EDIT, IDS.
"""
from clark import sanitise

CAUTION = "This workbook shows the project as it was on the date above. It does not include changes made in clark since."
RETURN_WITH = ("If you change anything here, send the file back to {owner}{email}. They then import your changes into clark, "
               "which checks each one before saving it.")
RETURN_ANYONE = ("If you change anything here, send the file back to the person who sent it to you. They then import your changes into "
                 "clark, which checks each one before saving it.")
WHERE_TO_EDIT = ("Make your changes on the Actions, Risks and issues, Decisions, Milestones and Use cases sheets. Changes made on "
                 "this Cover are ignored.")
ABOUT = "About this export"
INTERNAL_TAG = "INTERNAL"
MORE = " … (continues in clark)"
LIMIT = 32000                 # under Excel's 32,767 characters in one cell, with room for MORE
IDS = ("Please don't change or move IDs. Each ID stays with its own row: if you change one, or sort only the ID column, "
       "the details go to another item when the file is imported. Leave the ID empty for a new item.")                                       # #128: says what the import (#129) really does with an ID
KINDS = ("title", "heading", "health", "tile", "text", "about", "exported", "caution", "return", "where", "ids", "internal")


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


def _line(kind, text, colour=None):
    """One Cover line. `colour` (red, amber, green or None) is the health pill's, the only line that has one."""
    line = {"kind": kind, "text": text}
    if colour:
        line["colour"] = colour
    return line


def _text(text):
    """A body as lines: none at all when it is empty, so the Cover has no blank rows."""
    return [_line("text", text)] if text.strip() else []


def _tile_text(tile):
    """One shown tile as a line: 'Overdue actions: 3'. The health tile adds its reason on the next line."""
    return f"{tile.get('title', '')}: {tile.get('value', '')}" + (f" ({tile['detail']})" if tile.get("detail") else "")


def lines(project, sections, tiles, exported, by=None, owner=None, email=None, internal=""):
    """The Cover as a list of {"kind", "text"}.

    project  the project row: "name" (or "code"), "current_state" (HTML); read only
    sections the report_sections rows in order: type, title, body (HTML), hidden
    tiles    glance.tiles(...) output (the editor's, with `hidden`): title, value, detail, tile, reason
    exported the words for the export's date and time, for example excel.exported_text()
    by       the name that exported it (Settings › Profile); owner, email: who the file goes back to
    internal the INTERNAL sentence (excel.INTERNAL_NOTE): the title band's tag and the last line of the About block"""
    name = str(project.get("name") or project.get("code") or "").strip()
    title = _line("title", cut(name, 200))
    if internal:
        title["tag"] = INTERNAL_TAG
    out = [title]
    for sec in sections or []:
        if sec.get("hidden"):
            continue
        kind = sec.get("type")
        if kind == "current":
            body = _text(plain(project.get("current_state")))
            if body:
                out += [_line("heading", cut(sec.get("title") or "Current state", 200))] + body
        elif kind == "glance":
            part = []
            for t in tiles or []:
                if t.get("hidden"):
                    continue
                if t.get("tile") == "health":           # the pill: its cell takes the page's colour; the words say it too
                    part.append(_line("health", cut(_tile_text(t), 500), (t.get("pill") or {}).get("colour")))
                    if str(t.get("reason") or "").strip():
                        part.append(_line("text", cut(str(t["reason"]).strip(), 2000)))
                else:
                    part.append(_line("tile", cut(_tile_text(t), 500)))
            if part:
                out += [_line("heading", cut(sec.get("title") or "At a glance", 200))] + part
        elif kind == "text":
            body = _text(plain(sec.get("body")))
            if body:
                out += [_line("heading", cut(sec.get("title") or "", 200))] + body
    stamp = str(exported).strip()
    out += [_line("about", ABOUT),
            _line("exported", cut(f"{stamp} by {str(by).strip()}" if by and str(by).strip() else stamp, 400)),
            _line("caution", CAUTION), _line("return", cut(return_note(owner, email), 1000)), _line("where", WHERE_TO_EDIT), _line("ids", IDS)]
    if internal:
        out.append(_line("internal", internal))
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
    kept = glance.kept_rows(inputs["data"], today, sections=inputs.get("sections"), label_rules=inputs.get("label_rules"))
    tiles = glance.tiles(inputs["data"], today, for_client=True, kept=kept)
    sections = [dict(s, hidden=0) for s in shown["sections"]]
    return lines(shown["data"]["project"], sections, tiles, exported, by, owner, email, internal)
