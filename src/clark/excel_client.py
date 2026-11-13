"""The client-view workbook (item 713): what a client may see, as a spreadsheet, made at publish time.

`workbook_bytes(published)` takes what `publish.select()` (then `add_glance`) returns and writes an .xlsx of ONLY those rows and fields:
the same rows the published page shows, never a second filter. It reads nothing else (no store, no inputs), so a row, field or
state `select` left out cannot reach it. Client wording (client_message) stands in for a row's own text where the page shows it.
It is read-only by intent: no export id (so the import will not accept it), no history, no hidden Lists sheet, no internal
cover, no comments, no formulas, no links, no data rules. The author is the fixed neutral name the owner export uses.

`embed(published)` returns what goes at the top level of the page's data (published["data"]), the names the page menu reads
(clientMenu.js), a dict with exactly one key:
    {"client_workbook": {"name": "<file name>.xlsx", "base64": "<the .xlsx, base64, no line breaks>"}}
    {"client_workbook_too_large": True}        a real boolean, when the workbook is over MAX_WORKBOOK_BYTES; the page draws its own sentence
With neither key there is nothing to offer.
"""
import base64
import html
import io
import re
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter, quote_sheetname
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.xml.functions import tostring

from clark import excel, glance
from clark import excel_colours as colours
from clark import platform, publish, sanitise

NAME = re.compile(r'[^\\/:*?"<>|\x00-\x1f]{1,120}')      # what the page accepts as a download name
# The cap: 1.5 MB of workbook (about 2 MB as base64). The published file is already refused over publish.MAX_BYTES (5 MB), and
# the page, its styles and its data come first; 2 MB of text in the data block leaves room for them, and a 1.5 MB workbook is
# some 30,000 rows of client text, far past any report.
MAX_WORKBOOK_BYTES = 1_500_000

# The committed colours; a call takes the project's brand palette instead (row 999: `palette=`, per call, no module state).
PALETTE = {"fill": colours.HEADER_FILL, "text": colours.HEADER_TEXT}

FONT = excel.OFFICE_FONT
BODY = Font(name=FONT, size=11)


def styles(palette=None):
    """(head font, title font, sub font, header fill) for a palette {"fill", "text"}: the committed one when None."""
    p = palette or PALETTE
    return (Font(name=FONT, size=11, bold=True, color=p["text"]), Font(name=FONT, size=16, bold=True, color=p["text"]),
            Font(name=FONT, size=11, color=p["text"]), PatternFill("solid", fgColor=p["fill"]))


def palette_of(branding):
    """The {"fill", "text"} of the branding folder's look (the committed pair for a folder with none): the same reader as the
    local workbook, so the pair that fails 4.5:1 reverts."""
    from clark import excel_palette
    pal = excel_palette.palette(branding=branding)
    return {"fill": pal.header_fill, "text": pal.header_text}

# (header, field, width) per table: only fields the file carries (publish.PUBLISH_FIELDS). Headers are the export's own.
COLUMNS = {
    "actions": [("ID", "id", 12), ("Description", "_words", 50), ("Workstream", "workstream", 16), ("Owner", "owner", 16),
                ("Priority", "priority", 10), ("Due", "due_date", 12), ("Status", "status", 12), ("Raised", "raised", 12),
                ("Closed", "closed", 12), ("Latest update", "latest_update", 40)],
    "raid": [("ID", "id", 12), ("Type", "type", 10), ("Description", "_words", 50), ("Workstream", "workstream", 16),
             ("Owner", "owner", 16), ("Due", "due_date", 12), ("Impact", "impact", 10), ("Likelihood", "likelihood", 10),
             ("Priority", "priority", 10), ("Status", "status", 12), ("Raised", "raised", 12), ("Closed", "closed", 12)],
    "decisions": [("ID", "id", 12), ("Decision", "_words", 50), ("Status", "status", 12), ("Made by", "made_by", 16),
                  ("Needed by", "needed_by", 12), ("Date", "date", 12), ("Revisit", "revisit", 12)],
    "milestones": [("ID", "id", 12), ("Milestone", "name", 30), ("Description", "_words", 50), ("Workstream", "workstream", 16),
                   ("Original", "original_date", 12), ("Agreed", "baseline_date", 12), ("Forecast", "forecast_date", 12),
                   ("Shown state", "state_word", 14), ("% complete", "percent_complete", 11), ("Owner", "owner", 16),
                   ("State reason", "state_reason", 40), ("Achieved on", "actual_date", 12)],
    "use_cases": [("ID", "id", 12), ("Reference", "ref", 12), ("Use case", "title", 30), ("Status", "status", 12),
                  ("Headline", "headline", 40), ("Where it stands", "standing", 60)],
}
COMMITMENT = ("Commitment", "commitment", 14)      # a use case's flag: a column only while the file carries it (publish.PUBLISH_FIELDS)
OWN_TEXT = {"actions": "description", "raid": "description", "decisions": "decision", "milestones": "description"}
LEGACY_RICH = set(publish.LEGACY_RICH)      # (table, field): rich now, plain before (row 1005)
RICH = {"standing"}                      # HTML the editor wrote: shown as its text
EDITOR_LOCKED = {table: locked for _, table, _, locked in excel.SHEETS}     # each sheet's own locked set in the editor export
EDITOR_FIELD = {"state_word": "shown_state"}      # the client column that is the export's worked-out Shown state
DATE_FIELDS = excel.DATES | {"revisit"}
BLOCKS = re.compile(r"</(?:p|div|li|h[1-6]|blockquote|pre|tr)>|<br\s*/?>|<hr\s*/?>", re.I)
TAGS = re.compile(r"<[^>]*>")
SECTION_OF = {"actions": "actions", "raid": "raid", "decisions": "decisions", "milestones": "milestones", "use_cases": "usecases"}


def plain(value):
    """Cleaned HTML as plain text, one line per block."""
    clean = sanitise.clean_html(value or "")
    text = html.unescape(TAGS.sub("", BLOCKS.sub("\n", clean)))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def value_of(table, row, field):
    if field == "_words":
        own = row.get(OWN_TEXT[table])
        said = row.get("client_message")
        words = (sanitise.rich_plain_text(said) if (table, "client_message") in LEGACY_RICH else (said or "")).strip()     # row 1078: a milestone's client wording is rich too
        return words or (sanitise.rich_plain_text(own) if (table, OWN_TEXT[table]) in LEGACY_RICH else own)
    if (table, field) in LEGACY_RICH:                  # row 1005: the editor's HTML, or the plain text an older clark stored
        return sanitise.rich_plain_text(row.get(field))
    if field in RICH:
        return plain(row.get(field))
    return row.get(field)


def rows_of(published, table):
    rows = list(published["data"].get(table) or [])
    if table == "milestones":
        rows = [r for r in rows if r.get("status") != "Cancelled"]      # as the page leaves them out
    return rows


def sheet_tables(published):
    """The tables whose section the page shows, in the export's own sheet order."""
    shown = {s.get("type") for s in published["sections"]}
    return [t for t in excel.SHEET_OF if t in COLUMNS and SECTION_OF[t] in shown]


def title_text(published):
    p = published["data"].get("project") or {}
    week = p.get("week_ending")
    when = excel.to_cell("date", week) if week else None
    sub = f"Week ending {when if isinstance(when, str) else format(when, '%d-%m-%Y')}" if week else f"As at {glance.show_date(published['as_at'])}"
    return (p.get("name") or p.get("code") or ""), sub


def columns(table):
    """The sheet's columns: COLUMNS[table], each only if publish.PUBLISH_FIELDS carries its field (the whitelist; "_words" stands for
    the text field and its client wording), plus the use case flag when the file carries it."""
    allowed = set(publish.PUBLISH_FIELDS[table]) | {"_words", "state_word", "original_date"}
    cols = [c for c in COLUMNS[table] if c[1] in allowed]
    if table == "use_cases" and COMMITMENT[1] in publish.PUBLISH_FIELDS[table]:
        cols.insert(4, COMMITMENT)
    return cols


def write_sheet(wb, published, table, palette=None):
    HEAD, TITLE, SUB, HEAD_FILL = styles(palette)
    ws = wb.create_sheet(excel.SHEET_OF[table])
    cols = columns(table)
    editor_locked = excel.locked_fields(EDITOR_LOCKED[table])
    name, sub = title_text(published)
    for r, (text, font) in enumerate(((name, TITLE), (sub, SUB)), start=1):
        for c in range(1, len(cols) + 1):
            ws.cell(row=r, column=c).fill = HEAD_FILL
        cell = ws.cell(row=r, column=1, value=excel.cell_text(text))
        cell.font = font
        excel.protect_text_cell(cell)
    ws.row_dimensions[1].height = 26
    for i, (label, _, width) in enumerate(cols, start=1):
        head = ws.cell(row=4, column=i, value=label)
        head.font, head.fill = HEAD, HEAD_FILL
        head.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(i)].width = width
    for n, row in enumerate(rows_of(published, table), start=5):
        for i, (_, field, _) in enumerate(cols, start=1):
            v = value_of(table, row, field)
            cell = ws.cell(row=n, column=i, value=None if v in (None, "") else excel.to_cell("date" if field in DATE_FIELDS else field, v))
            cell.font = BODY
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            if field in DATE_FIELDS:
                cell.number_format = excel.DATE_FORMAT
                cell.alignment = Alignment(horizontal="left", wrap_text=True, vertical="top")      # a date is not flush to the next column's text
            excel.protect_text_cell(cell)
            if EDITOR_FIELD.get(field, field) not in editor_locked:       # the export's rule (item 727): only these stay editable
                cell.protection = excel.UNLOCKED
    ws.freeze_panes = "A5"
    excel.print_setup(ws)
    excel.protect_sheet(ws)           # as the export's sheets (item 727): no password, the same allowed actions
    return ws


def write_gantt_sheet(wb, published, palette=None):
    """The Gantt sheet (row 926), from publish.gantt_for_client's output alone (published["data"]["gantt"]): its lines are the eye-on
    lines only, with the hidden columns already not in them, dependencies and parents already cleaned. Days and Status are worked out
    from the start, end and Done %, which are never hidden. The sheet is the tab's name, and every cell is locked."""
    HEAD, TITLE, SUB, HEAD_FILL = styles(palette)
    g = published["data"]["gantt"]
    fields = set(g["columns"]) | {"_days", "_status"}
    cols = [(label, f, excel.GANTT_WIDTHS.get(f, 12)) for label, f in excel.GANTT_SHEET_COLUMNS if f in fields]
    ws = wb.create_sheet(excel.gantt_sheet_name(g["tab_name"], wb.sheetnames))
    name, sub = title_text(published)
    for r, (text, font) in enumerate(((name, TITLE), (sub, SUB)), start=1):
        for c in range(1, len(cols) + 1):
            ws.cell(row=r, column=c).fill = HEAD_FILL
        cell = ws.cell(row=r, column=1, value=excel.cell_text(text))
        cell.font = font
        excel.protect_text_cell(cell)
    ws.row_dimensions[1].height = 26
    for i, (label, _, width) in enumerate(cols, start=1):
        head = ws.cell(row=4, column=i, value=label)
        head.font, head.fill = HEAD, HEAD_FILL
        head.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(i)].width = width
    for n, line in enumerate(g["lines"], start=5):
        for i, (_, f, _) in enumerate(cols, start=1):
            cell = ws.cell(row=n, column=i, value=excel.gantt_cell(line, f, published["as_at"]))
            cell.font = BODY
            cell.alignment = Alignment(horizontal="left" if f in excel.GANTT_DATES else None, wrap_text=True, vertical="top")
            if f in excel.GANTT_DATES:
                cell.number_format = excel.DATE_FORMAT
            excel.protect_text_cell(cell)
    ws.freeze_panes = "C5"
    excel.print_setup(ws)
    excel.protect_sheet(ws)
    wb.defined_names[excel.CLIENT_COPY_NAME] = DefinedName(excel.CLIENT_COPY_NAME, attr_text=f"{quote_sheetname(ws.title)}!$A$1", hidden=True)   # row 926: the import's mark of a client copy (moving a row cannot remove it)
    return ws


def workbook_bytes(published, palette=None):
    """The client workbook as .xlsx bytes (the same bytes for the same published content)."""
    wb = Workbook()
    wb.remove(wb.active)
    for table in sheet_tables(published):
        write_sheet(wb, published, table, palette)
    if "gantt" in published.get("tabs", ()) and (published["data"].get("gantt") or {}).get("lines"):       # row 926: only when the file carries the Gantt tab (publish.gantt_for_client); row 1068: a table section's copy has no tab and no tab name, so no sheet
        write_gantt_sheet(wb, published, palette)
    name, sub = title_text(published)
    if not wb.sheetnames:                       # no table section on the page: one sheet with the title band alone
        ws = wb.create_sheet(excel.SHEET_OF["actions"])
        for cell, text in ((ws["A1"], name), (ws["A2"], sub)):
            cell.value = excel.cell_text(text)
            cell.font = BODY
            excel.protect_text_cell(cell)
        excel.print_setup(ws)
        excel.protect_sheet(ws)
    props = wb.properties
    props.creator = props.lastModifiedBy = excel.FIXED_NAME
    stamp = datetime.fromisoformat(published["as_at"] + "T00:00:00")
    props.created = props.modified = stamp
    props.title = excel.cell_text(name)
    out = io.BytesIO()
    wb.save(out)
    props.created = props.modified = stamp
    # openpyxl sets "modified" to the real time as it saves, so core.xml is written again with the published day
    return excel.fixed_zip(out.getvalue(), {"docProps/core.xml": tostring(props.to_tree())})


def file_name(published):
    project = published["data"].get("project") or {}
    return platform.safe_name(f"{project.get('code') or 'report'}-report-{project.get('week_ending') or published['as_at']}.xlsx")


def embed(published, palette=None):
    """What the page's data holds for the workbook: {"client_workbook": {"name", "base64"}} or, over the cap,
    {"client_workbook_too_large": True}."""
    data = workbook_bytes(published, palette)
    if len(data) > MAX_WORKBOOK_BYTES:
        return {"client_workbook_too_large": True}
    name = file_name(published)
    if not NAME.fullmatch(name):                  # the page's own rule for a download name
        name = "report.xlsx"
    return {"client_workbook": {"name": name, "base64": base64.b64encode(data).decode("ascii")}}
