"""The Excel export (#37; BRD FR-70): one project's actions, risks & issues, decisions, milestones and use cases as a workbook.

Copied from creaite v2.6.9 (db5adb2), system/scripts/excel_sync.py: the sheet layout, the cell conversions (to_cell, from_cell,
cell_text), the drop-downs and locked columns, and the guard against overwriting a workbook with edits not yet imported (a
record of the SHA-256 of the file each export wrote, and of the last one imported). Each copied function names its original.
What is cut: the Projects, Workstreams, Promises, Links, Updates and Review sheets, links in plain text (#121; clark has no
linktext), the import itself, and creaite's paths and debug log. What differs is marked "clark:".

Formatting (#85a, #85c): the header in the brand navy, the ID and the item's title frozen, widths and wrapping by kind, and
conditional formatting from excel_colours.py (clark's own; creaite has none): a rule per value of Status, Priority, Impact,
Likelihood and State, so a value changed in Excel recolours itself, and a formula rule that makes the date of an open item past
its date red. The rules are fixed literals, never data; no cell holds a formula, and colour never changes a cell's value. Every
fixed-value column has a drop-down that refuses anything else; the project's own lists (workstreams, milestones, use cases) are
on a hidden "Lists" sheet that the import never reads. Owner stays free text. "Updated" stays the stored UTC text,
because the import compares it to spot a clash; it is not shown as a local time. Other stored times in the file (the state
file's exported_at, the workbook's created and modified times) are UTC too; a time shown to a person goes through
clark.timefmt.local_text (exported_text, for the cover).

The workbook is never the record: the store is. Dates are real Excel dates shown DD-MM-YYYY; they are stored YYYY-MM-DD.

`export()` takes the rows themselves ({table: [row dict, ...]}) and needs no database; `export_project()` reads them from the
store (#31) with Store.read. openpyxl is the copy in vendor/; whoever starts clark puts vendor/ on sys.path, as
dev/run_tests.py does.

INTERNAL ONLY: the Milestones sheet carries each milestone's Internal note, and Sensitive and client-hidden rows are exported
too. Never send this workbook to a client. It says so in the file itself (the document description, and a note on Milestones A1).

Text is a text cell on the way out (protect_text_cell: a string cell, with quotePrefix when it starts with = + - @, and no visible
apostrophe) and is read as it stands on the way in (from_cell), so a value such as =HYPERLINK(...) is only ever text and is never
run. The file is byte-for-byte the same for the same rows, the same day (see `moment`) and the same export id (see
`new_export_id`): each export carries a fresh random id, so two exports differ only by it.
"""
import hashlib
import io
import json
import logging
import re
import threading
import uuid
import warnings as warnings_lib
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont
from openpyxl.comments import Comment
from openpyxl.formatting.rule import FormulaRule, Rule
from openpyxl.packaging.custom import CustomPropertyList, StringProperty
from openpyxl.worksheet.properties import PageSetupProperties
from openpyxl.styles import Alignment, Border, Font, PatternFill, Protection, Side
from openpyxl.styles.differential import DifferentialStyle
from openpyxl.utils import get_column_letter
from openpyxl.xml.functions import fromstring, tostring
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.protection import SheetProtection

from clark import excel_colours as colours
from clark import excel_cover
from clark import glance
from clark import excel_palette
from clark import excel_picture
from clark import look
from clark import platform, sanitise
from clark.milestones import STATES, milestone_state
from clark.store import COMMITMENTS
from clark.timefmt import local_text, parse

EXTRA_ROWS = 500          # rows below the data that keep drop-downs and formats for new entries
DATE_FORMAT = "dd-mm-yyyy"
STATE_FILE = "excel-export-state.json"   # beside clark.db: what each export wrote, by workbook
# One read-change-write of a state file at a time (#147): the server answers each request on its own thread, and two exports
# (or an export and an import) that each read the whole file, add their record and write it back would otherwise lose one.
# Re-entrant, so mark_imported can hold it across its load_state and save_state. It covers one running clark only, not two
# clarks started on the same data folder.
STATE_LOCK = threading.RLock()

# Sheet layout (creaite excel_sync.SHEETS): (sheet name, table, [(column label, field)], locked fields).
# clark: + Workstream and Movement on milestones, + Use case on actions, RAID and decisions, + the Use cases sheet; Original
# and Shown state are worked out, not columns (see DERIVED); no Labels on milestones or use cases, as in creaite.
SHEETS = [
    ("Actions", "actions", [
        ("ID", "id"), ("Description", "description"), ("Project", "project"), ("Workstream", "workstream"),
        ("Owner", "owner"), ("Priority", "priority"), ("Due", "due_date"), ("Status", "status"),
        ("Raised", "raised"), ("Closed", "closed"), ("Latest update", "latest_update"),
        ("Client-visible", "client_visible"), ("Client wording", "client_message"), ("Milestone", "milestone"),
        ("Use case", "use_case"), ("Labels", "labels"), ("Source", "source"), ("Updated", "updated_at")],
     {"id", "source", "updated_at"}),
    ("Risks & Issues", "raid", [
        ("ID", "id"), ("Description", "description"), ("Project", "project"), ("Type", "type"),
        ("Workstream", "workstream"), ("Owner", "owner"), ("Response action", "response_action"),
        ("Due", "due_date"), ("Impact", "impact"), ("Likelihood", "likelihood"), ("Priority", "priority"),
        ("Status", "status"), ("Raised", "raised"), ("Closed", "closed"), ("Client-visible", "client_visible"),
        ("Client wording", "client_message"), ("Milestone", "milestone"), ("Use case", "use_case"), ("Labels", "labels"),
        ("Source", "source"), ("Updated", "updated_at")],
     {"id", "priority", "source", "updated_at"}),
    ("Decisions", "decisions", [
        ("ID", "id"), ("Decision", "decision"), ("Project", "project"), ("Status", "status"), ("Made by", "made_by"),
        ("Needed by", "needed_by"), ("Date", "date"), ("Reasoning", "reasoning"), ("Options", "options"),
        ("Revisit", "revisit"), ("Replaces", "replaces"), ("Client-visible", "client_visible"),
        ("Client wording", "client_message"), ("Use case", "use_case"), ("Labels", "labels"), ("Source", "source"),
        ("Updated", "updated_at")],
     {"id", "source", "updated_at"}),
    ("Milestones", "milestones", [
        ("ID", "id"), ("Milestone", "name"), ("Project", "project"), ("Description", "description"),
        ("Workstream", "workstream"), ("Original", "original_date"), ("Agreed", "baseline_date"),
        ("Forecast", "forecast_date"), ("Status", "status"), ("Order", "sort_order"), ("% complete", "percent_complete"),
        ("Owner", "owner"), ("Shown state", "shown_state"), ("State", "state"), ("State set by you", "state_set"),
        ("State reason", "state_reason"), ("Movement", "movement"), ("Achieved on", "actual_date"),
        ("Client-visible", "client_visible"), ("Client wording", "client_message"), ("Internal note", "internal_note"),
        ("Open work items", "open_items"), ("Source", "source"), ("Updated", "updated_at")],
     {"id", "original_date", "shown_state", "source", "updated_at", "open_items"}),
    ("Use cases", "use_cases", [                                       # clark's own table, in creaite's style
        ("ID", "id"), ("Use case", "title"), ("Project", "project"), ("Shown as", "ref"), ("Status", "status"),
        ("Commitment", "commitment"), ("Headline", "headline"), ("Where it stands", "standing"), ("Order", "sort_order"),
        ("Client-visible", "client_visible"), ("Linked milestones", "milestones"), ("Open work items", "open_items"), ("Source", "source"), ("Updated", "updated_at")],
     {"id", "source", "updated_at", "open_items"}),
]
TABLES = tuple(t for _, t, _, _ in SHEETS)
# The same layout as two lookups, for the import (#38): the sheet a table is written on, and each table's header label -> field.
# Derived from SHEETS, so the import reads exactly the labels the export writes.
SHEET_OF = {table: name for name, table, _, _ in SHEETS}
COLUMN_OF = {table: {label: field for label, field in cols} for _, table, cols, _ in SHEETS}
DATES = {"due_date", "raised", "closed", "date", "baseline_date", "forecast_date", "needed_by", "actual_date",
         "original_date"}
YES_NO = {"client_visible", "state_set"}
LABELLED = ("actions", "raid", "decisions")
RICH_WORDS = (("actions", "latest_update"), ("milestones", "description"), ("milestones", "client_message"), ("milestones", "internal_note"), ("use_cases", "standing"))     # rows 1005, 1060 (row 1078: + a milestone's client wording): rich now (the editor's HTML or an older plain text); the sheet carries its words, and the import compares a cell with the words (publish.LEGACY_RICH is the same list without the Movement note, which comes last; row 1060: a use case's Where it stands is HTML too)
DERIVED = {"original_date", "shown_state", "open_items"}    # clark: worked out for the sheet, never read back as a change
WIDE = {"description", "decision", "client_message", "latest_update", "response_action", "reasoning", "options", "revisit",
        "state_reason", "internal_note", "source", "headline", "standing"}
# clark: a NOT NULL DEFAULT '' text column. A blank cell there reads back as "" (creaite's blank_default, with no template: #24).
EMPTY_TEXT = {("actions", "client_message"), ("raid", "client_message"), ("decisions", "client_message"),
              ("use_cases", "ref"), ("use_cases", "headline"), ("use_cases", "standing")}
CHOICES = {
    ("actions", "status"): ["Open", "Delayed", "Closed", "Cancelled"],
    ("raid", "status"): ["Open", "Closed", "Cancelled"],
    ("milestones", "status"): ["Planned", "Done", "Cancelled"],
    ("milestones", "state"): [s for s in STATES if s != "Achieved"] + ["Achieved"],   # clark: + Forecast
    ("milestones", "movement"): ["hold", "rebaseline", "recover", "escalate"],         # clark: FR-53
    ("decisions", "status"): ["Pending", "Made", "Withdrawn"],
    ("use_cases", "status"): ["On track", "Flag", "High risk", "Done"],                  # clark
    ("use_cases", "commitment"): list(COMMITMENTS),                                      # #709: the store's own words; a blank is allowed (no flag)
    "priority": ["Urgent", "High", "Medium", "Low"],
    "type": ["Risk", "Assumption", "Issue", "Dependency"],
    "impact": ["High", "Medium", "Low"],
    "likelihood": ["High", "Medium", "Low"],
}

# clark (#85c): NOT NULL columns, whose drop-down does not allow a blank. The rest (and every other sheet's optional links) do.
NOT_BLANK = {("actions", "priority"), ("actions", "status"), ("raid", "type"), ("raid", "status"), ("milestones", "status"),
             ("decisions", "status"), ("use_cases", "status")}
PEOPLE = {"owner", "made_by"}              # free text until the people table exists (#115)
LISTS_NAME = "Lists"                       # the hidden sheet holding the project's own lists
LIST_ERROR_TITLE = "Not on the list"
LIST_ERROR = "Pick one of the values in the list."

INTERNAL_NOTE = ("INTERNAL: this workbook includes internal notes and Sensitive items. Never share it with a client.")
FIXED_NAME = "clark"                       # creator and last-modified-by: fixed and neutral, so the file never names a person
ZIP_TIME = (1980, 1, 1, 0, 0, 0)           # the earliest time a zip can hold: every member gets it

# Formatting (#85a). Brand colours come from excel_colours (the demo tokens); the layout rules are these.
HEADER = PatternFill("solid", fgColor=colours.HEADER_FILL)
OFFICE_FONT = look.office_font()           # the look's --font-office: one font on every sheet, a font Office has
HEADER_FONT = Font(name=OFFICE_FONT, bold=True, color=colours.HEADER_TEXT)
BODY_FONT = Font(name=OFFICE_FONT, size=11)  # the data cells (11 is the size a cell had before it named a font)
# The item's title column on each sheet: the column frozen beside the ID, so a row stays readable while scrolling across.
TITLE_OF = {"milestones": "name", "actions": "description", "raid": "description", "decisions": "decision",
            "use_cases": "title"}
SHORT_NAMES = {"owner", "made_by", "workstream", "labels"}      # people, streams and labels: a little wider than a status
NUMBERS = {"sort_order", "percent_complete"}
LOCKED = PatternFill("solid", fgColor=colours.TOKENS["grey-100"])      # the page's quiet grey, for a column the import never reads
# The default (committed, no brand) palette, which the constants above and the functions below use when no `pal` is given. An export
# builds its own with excel_palette.palette(branding=...) (item 711): the local brand's light values over the committed ones.
DEFAULT_PAL = excel_palette.committed()


class Styles:
    """The fills and fonts one workbook draws with, from its palette: the module constants for the default one."""
    def __init__(self, pal):
        self.pal = pal
        self.header = PatternFill("solid", fgColor=pal.header_fill)
        self.header_font = Font(name=pal.font, bold=True, color=pal.header_text)
        self.body_font = Font(name=pal.font, size=11)
        self.locked = PatternFill("solid", fgColor=pal.tokens["grey-100"])


def _pal(pal):
    return pal if pal is not None else DEFAULT_PAL
# The ID column (#85d, BRD FR-70d). Every sheet is protected with no password (item 727), so a locked cell is not changed by
# mistake; Excel then refuses to sort a protected range, and a person who needs to sort chooses Review, Unprotect Sheet.
# The protection is a convenience only: the import never reads it and is still the guard (a changed existing ID is refused for
# that row; a row with no ID is a new item and gets the next free ID). The ID column is shaded (LOCKED fill) and these words
# are pinned by a test.
ID_NOTE = ("IDs are given by clark. Don't change or move an ID, and don't sort the ID column on its own: an ID moved to "
           "another row takes that row's details with it when the file is imported. Leave the ID empty on a new row.")
ID_PROMPT_TITLE = "ID"
ID_PROMPT_EXISTING = "Don't change this ID: if it changes, this row's details go to another item when the file is imported."
ID_PROMPT_NEW = "Leave the ID empty for a new item. clark gives it an ID when the file is imported."




ALWAYS_LOCKED = {"id", "project"}      # on a data sheet, besides the sheet's own locked set and DERIVED (item 727)
# Protected sheets allow: the autofilter, resizing and formatting, and inserting rows. In openpyxl a True flag means the action
# is NOT allowed, so these are the ones set False. Sorting stays blocked (Excel does not sort a range with a locked cell), and
# rows are not deleted on a protected sheet (an item is never removed by deleting its row: the import does not delete).
ALLOWED_ON_PROTECTED = ("autoFilter", "formatCells", "formatColumns", "formatRows", "insertRows",
                        "selectLockedCells", "selectUnlockedCells")
UNLOCKED = Protection(locked=False)


def locked_fields(locked):
    """The fields of a data sheet that stay locked: its own locked set, what is worked out, the ID and the Project. Every
    other column is editable, including one added later."""
    return set(locked) | DERIVED | ALWAYS_LOCKED


def print_setup(ws):
    """Print setup (row 801): landscape, one page wide however many pages tall, so the Cover and the wide data sheets do not split across pages."""
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4                       # A4, as the PDF export is
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)


def protect_sheet(ws):
    """Protect the sheet with no password (so no hash is stored); the person unprotects it from the Review tab."""
    prot = SheetProtection(sheet=True)
    for name in ALLOWED_ON_PROTECTED:
        setattr(prot, name, False)
    ws.protection = prot


class Refused(Exception):
    """The export did not write the workbook; the message says why, in plain words, and names the file."""


class TooBig(Refused):
    """A workbook that is too big to open safely (a zip bomb, or the wrong file); the message says so in plain words."""


# What a workbook may be before clark opens it. A real export of a large project is far below all four. The sizes are those the
# .xlsx (a zip) declares for its members; Python's zip reader never gives back more than a member declares.
MAX_FILE_BYTES = 25 * 1024 * 1024          # the file as saved
MAX_UNPACKED_BYTES = 50 * 1024 * 1024      # all its members, unpacked
MAX_MEMBER_BYTES = 40 * 1024 * 1024        # any one member, unpacked
MAX_MEMBERS = 200                          # members in the zip
MAX_SNAPSHOT_BYTES = 20 * 1024 * 1024      # the per-row record in the state file; a bigger one is left out (the import copes)


def check_workbook_size(path):
    """Raise TooBig, before anything is unpacked, if the file is larger than the limits above (a small file that inflates to
    gigabytes is refused by its unpacked size, not just its ratio). A missing file, or one that is not a zip, passes: opening it
    says what is wrong with it."""
    path = Path(path)
    try:
        size = path.stat().st_size
    except OSError:
        return
    mb = lambda n: f"{n / 1048576:.0f} MB" if n >= 1048576 else f"{n / 1024:.0f} KB"
    if size > MAX_FILE_BYTES:
        raise TooBig(f"{path.name} is {mb(size)}, more than the {mb(MAX_FILE_BYTES)} clark will open. A clark export is far "
                     "smaller: check it is the right file.")
    try:
        with zipfile.ZipFile(path) as z:
            infos = z.infolist()
    except (zipfile.BadZipFile, OSError):
        return
    total, biggest = sum(i.file_size for i in infos), max((i.file_size for i in infos), default=0)
    if len(infos) > MAX_MEMBERS:
        raise TooBig(f"{path.name} holds {len(infos)} parts, more than the {MAX_MEMBERS} a workbook should have, so it was "
                     "not opened. Check it is the right file.")
    if biggest > MAX_MEMBER_BYTES or total > MAX_UNPACKED_BYTES:
        raise TooBig(f"{path.name} would unpack to about {mb(total)} (the most clark will open is {mb(MAX_UNPACKED_BYTES)}), "
                     "so it was not opened. A clark export is far smaller: check it is the right file.")


# ── Helpers ───────────────────────────────────────────────────────────────────

def clock():
    """The real time now, as UTC without a zone mark (#75). The one place the export reads the clock; tests replace it
    (excel.clock = ...) with a naive UTC datetime. UTC because the workbook's created/modified times are UTC in the file (Excel
    shows them in the user's zone) and the state file's exported_at is a machine value: neither depends on the machine's zone."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def moment(on=None):
    """The time the export is stamped with, to the second, in UTC (#75): midnight UTC at the start of day `on` (YYYY-MM-DD) when
    it is given, else the clock. It sets the workbook's created and modified times and the state file's exported_at, so the
    same rows with the same `on` always give the same bytes, in any zone."""
    if on:
        return datetime.combine(date.fromisoformat(str(on)), datetime.min.time())
    return clock().replace(microsecond=0)


def day(on=None):
    """The calendar day of the export, as a date: `on` when given, else today on the user's own calendar (the clock's moment
    seen in the local zone, #75). Dates are never shifted by a zone; only 'today' depends on where the user is."""
    if on:
        return date.fromisoformat(str(on))
    return moment().replace(tzinfo=timezone.utc).astimezone().date()


def exported_text(on=None):
    """'DD-MM-YYYY HH:MM (UTC+04:00)' in the user's local time (#75), for the cover (#85b). The zone is named by
    its UTC offset, not its name: zone names ('Gulf Standard Time', or just '+04') differ between systems, an offset does not.
    The moment is the export's own (moment(on): the clock, or midnight UTC at the start of `on`), shown through clark.timefmt,
    so it depends on the machine's zone by design: a cover carrying it differs between zones for the same data and clock."""
    stamp = moment(on).strftime("%Y-%m-%d %H:%M:%S")
    shown = local_text(stamp)
    offset = int(parse(stamp).astimezone().utcoffset().total_seconds() // 60)
    sign, offset = ("+" if offset >= 0 else "-"), abs(offset)
    return f"{shown[:10]} {shown[11:]} (UTC{sign}{offset // 60:02d}:{offset % 60:02d})"


def file_hash(path):
    """The SHA-256 of the workbook, or None when there is none (creaite excel_sync.file_hash)."""
    path = Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def hash_key(digest):
    """A workbook's entry in the state file when it is known by its bytes, not where it is (#147: the menu's export is
    downloaded by the browser, so clark never learns the path). Found only for a byte-identical file: a re-save or an edit
    changes the bytes. Kept as the fallback for a workbook exported before export ids, or one whose id was dropped."""
    return "sha256:" + digest


EXPORT_ID_NAME = "clark_export_id"     # the custom workbook property (docProps/custom.xml) that holds the export id; never a cell
EXPORT_ID_OK = re.compile(r"[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{15}")    # a random UUID (version 4) as 32 hex digits, nothing else
CUSTOM_PART = "docProps/custom.xml"    # the zip member that holds a workbook's custom properties
MAX_CUSTOM_BYTES = 64 * 1024           # a bigger custom-properties part is not read for an id
KEYED = ("sha256:", "id:")             # the state-file keys that are not paths


def new_export_id():
    """A fresh export id: a random UUID (version 4) as 32 hex digits. Random on purpose: it says nothing about the rows, the
    project or the person, and can't be worked out from them. The one place an id is made; tests replace it (excel.new_export_id
    = ...) when they need the same bytes twice."""
    return uuid.uuid4().hex


def id_key(project, token):
    """An export's entry in the state file when it is found by the id inside the workbook. Keyed by the project too, so an id
    copied into a workbook imported into another project looks up a key that project never wrote: it is no record there."""
    return f"id:{project}:{token}"


def export_id_of(path):
    """The export id inside the workbook at `path`, or None: no such file, no id, two of them, or a value that is not a random
    UUID as 32 hex digits (a long, odd or marked-up value, a NUL or a number is ignored, never looked up). Reads only the small
    custom-properties part of the zip, never the sheets."""
    try:
        with zipfile.ZipFile(path) as z:
            info = z.getinfo(CUSTOM_PART)
            if info.file_size > MAX_CUSTOM_BYTES:
                return None
            data = z.read(info)
        with warnings_lib.catch_warnings():
            warnings_lib.simplefilter("ignore")
            props = [p for p in CustomPropertyList.from_tree(fromstring(data)) if p.name == EXPORT_ID_NAME]
    except Exception:                       # not a zip, no such part, bad XML: no id
        return None
    value = props[0].value if len(props) == 1 else None
    return value if isinstance(value, str) and EXPORT_ID_OK.fullmatch(value) else None


def _key(path):
    """The workbook's entry in the state file: its full path, or an id_key() or hash_key() as it is. A path matches only that
    file; a hash_key() only its exact bytes; an id_key() the export id inside the workbook, which an edit or a re-save keeps."""
    if isinstance(path, str) and path.startswith(KEYED):
        return path
    return str(Path(path).resolve())


def _books(state_path):
    """{key: record} from the state file, or {} when there is none. Raises ValueError for text that is not JSON; a file of
    another shape gives {}, and an entry that is not a record is left out."""
    state_path = Path(state_path)
    if not state_path.exists():
        return {}
    whole = json.loads(state_path.read_text(encoding="utf-8"))
    books = whole.get("workbooks") if isinstance(whole, dict) else None
    return {k: v for k, v in books.items() if isinstance(v, dict)} if isinstance(books, dict) else {}


def _find(books, path, project=None):
    """(key, record) of this workbook's export record, or (None, {}). Tried in turn: the export id inside the file under this
    `project` (with no project, as the import always gives, under whichever project wrote it), the file's path, then its
    SHA-256. A record that names another project than `project` is passed over."""
    if isinstance(path, str) and path.startswith(KEYED):
        tries = [path]
    else:
        token = export_id_of(path)
        if token and project:
            tries = [id_key(project, token)]
        elif token:                           # no project to look under (not an import): the one record with this id, if one
            tries = [k for k in books if k.startswith("id:") and k.endswith(":" + token)][:1]
        else:
            tries = []
        tries.append(_key(path))
        digest = file_hash(path)
        if digest:
            tries.append(hash_key(digest))
    for k in tries:
        rec = books.get(k)
        if rec is not None and (project is None or rec.get("project") in (None, project)):
            return k, rec
    return None, {}


def find_state(state_path, path, project=None):
    """(key, record) as load_state finds it; the key is where mark_imported writes back (None when nothing was found)."""
    return _find(_books(state_path), path, project)


def load_state(state_path, path, project=None):
    """The last export's record for this workbook: its file hash, imported_hash and rows (creaite excel_sync.load_state).
    clark: one state file holds a record per workbook. Found by the export id inside the workbook, for the `project`
    being imported, so the record is found from any folder, and after the file was edited or saved again; else by the path;
    else by the file's SHA-256 (hash_key), which finds a workbook with no id (an older export) only while it is exactly what
    clark wrote. A workbook whose id was dropped (another program rewrote it without its properties) is no longer what clark
    wrote either, so it is found by neither and the import treats it as unrecorded (it fails safe). The record names the
    project it was exported from ("project"); one of another project is passed over, and the caller checks it again
    (excel_import.read_workbook)."""
    return find_state(state_path, path, project)[1]


KEEP_NEWEST = 10          # the most bytes- or id-keyed ("sha256:", "id:") records kept for one project (#181); the oldest go first
KEEP_TOTAL = 30           # and the most the state file holds in all, newest first, plus each project's newest (never cut), so more than 30 live projects keep more than 30 (#181)


def prune_hash_records(state_path, today, keep_days=30, keep_newest=KEEP_NEWEST, live=None, keep_total=KEEP_TOTAL, keep=None):
    """Remove the bytes-keyed ("sha256:") and id-keyed ("id:") records exported more than keep_days before `today`, so the
    state file does not grow for ever (each holds a copy of every row). The two kinds are counted together under each cap below.
    Path-keyed records are left alone. #147. An id-keyed record also carries what its imports did (imported_hash, created):
    mark_imported writes those back to it, and a short copy of them under the workbook's path, which is kept, so pruning it never
    lets a row an import made be made again. A record is aged by its export date only, on
    purpose: an import never writes to the bytes-keyed record (mark_imported writes under the workbook's path, which is kept),
    so the export date is the only date it has. Nor does an import need it afterwards: mark_imported copies the record it found
    by the bytes, with the export in it ("hash", "rows"), under that path, so dropping the bytes-keyed one loses nothing for a
    file that was imported. A file still byte for byte the export, kept unimported for over keep_days, then imports as
    unrecorded: every difference is staged for the person to check, and nothing is lost. #181: also, no project keeps more than
    `keep_newest` of them (the newest by export time), at most `keep_total` stay in all (plus each project's newest, which the total never cuts: with more than `keep_total` live projects the file holds one per project and no more than ten of each), and, when `live` (a set of project codes) is
    given, none of a project outside it (an archived or removed one keeps no snapshot at all). The age rule is not the only brake on
    the file's size; an older export then imports as unrecorded, which stages every difference for checking (fails safe).
    `keep` is the record just written: the caps never cut it, and nor does each project's newest, so the total cap cannot take
    the snapshot a person has just made. An export date after today (a clock set back) ranks at the start of today, below every real export made today."""
    state_path = Path(state_path)
    with STATE_LOCK:
        if not state_path.exists():
            return
        whole = json.loads(state_path.read_text(encoding="utf-8"))
        books, cutoff = whole.get("workbooks", {}), str(date.fromisoformat(str(today)[:10]) - timedelta(days=keep_days))
        now = str(today)[:10]
        old = [k for k, v in books.items() if k.startswith(KEYED) and str(v.get("exported_at") or "9")[:10] < cutoff]
        # #181: none of a project that is not live; no more than `keep_newest` for any one project; no more than `keep_total` in all.
        # Newest by export time, then by the order they were saved in (two exports in one second), so the same records go every time: a hundred exports in one day must not make a state
        # file of a hundred copies of every row.
        left = {}
        for at, (k, v) in enumerate(books.items()):                  # `at` is the order they were saved in: the tie-break for two in one second
            if k.startswith(KEYED) and k not in old:
                if live is not None and v.get("project") not in live:
                    old.append(k)
                else:
                    when = str(v.get("exported_at") or "")
                    left.setdefault(str(v.get("project") or ""), []).append((min(when, now + " 00:00:00"), at, k))     # a future date ranks at the start of today
        must = {keep} if keep else set()
        kept, capped = [], []
        for mine in left.values():
            mine.sort(reverse=True)
            must.add(mine[0][2])                                     # each project's newest is exempt from the total cap
            kept += mine[:max(keep_newest, 1)]
            capped += [k for _, _, k in mine[max(keep_newest, 1):]]
        if keep_total and len(kept) > max(keep_total, 1):
            kept.sort(reverse=True)
            capped += [k for _, _, k in kept[max(keep_total, 1):]]
        old += [k for k in capped if k not in must]
        if old:
            for k in old:
                del books[k]
            platform.write_file(state_path, json.dumps(whole, indent=1, ensure_ascii=False))


def save_state(state_path, path, record):
    """Write this workbook's export record into the state file (creaite excel_sync.save_state), safely (platform.write_file).
    clark: the read, change and write are one step under STATE_LOCK, so a record written at the same time is not lost."""
    state_path = Path(state_path)
    with STATE_LOCK:
        whole = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        if whole.get("workbooks", {}).get(_key(path)) == record:
            return                                                    # #181: the same record again (the same bytes): nothing to write
        whole.setdefault("workbooks", {})[_key(path)] = record
        state_path.parent.mkdir(parents=True, exist_ok=True)
        platform.write_file(state_path, json.dumps(whole, indent=1, ensure_ascii=False))


def has_unimported_edits(path, state_path):
    """True if the workbook exists and differs from both the last export and the last import
    (creaite excel_sync.has_unimported_edits). A workbook clark has no record of counts as edited: it is never overwritten."""
    h = file_hash(path)
    if h is None:
        return False
    state = load_state(state_path, path)
    return h not in (state.get("hash"), state.get("imported_hash"))


MAX_CREATED = 5000     # fingerprints of the rows an import created, kept per workbook; the oldest are dropped past this


def add_created(record, created):
    """Append `created` ([{"fp", "id", "step", "db_id", "at"}, ...]; the last three say which step made it) to a workbook record's "created" list, keeping the newest MAX_CREATED."""
    if created:
        keep = ("fp", "id", "step", "db_id", "at")
        record["created"] = (list(record.get("created") or []) + [{k: c[k] for k in keep if k in c} for c in created])[-MAX_CREATED:]
    return record


def created_for(state_path, path, project):
    """[{"fp", "id"}] the imports made that a read of `path` must not make again: this workbook's own record first, then those of
    other workbooks of the same project in the state file (a copy of a workbook, or the same one saved elsewhere, has no record of
    its own). clark addition (#38). An import of a workbook found by its export id is recorded twice (under the id and, shortly,
    under the path: mark_imported), so a row made once is listed once."""
    books = _books(state_path)
    own_key, own = _find(books, path, project)
    own_key = own_key or _key(path)
    out, seen = [], set()
    for rec in [own] + [r for k, r in books.items() if k != own_key and r.get("project") == project]:
        for c in rec.get("created") or []:
            if not isinstance(c, dict):
                continue
            mark = (c.get("fp"), c.get("id"), c.get("step"), c.get("db_id"), c.get("at"))
            if mark not in seen:
                seen.add(mark)
                out.append(c)
    return out


def _write_back(state_path, path, project, change):
    """Apply `change` (a function that edits a record in place) to this workbook's record and save it, as one step under
    STATE_LOCK. A record found by the export id is changed where it is, and the same change is made to a short record under the
    workbook's path too (what was imported and made, never the export's rows), which pruning never removes; any other record is
    saved under the path, as before export ids (so one found by its bytes is copied there)."""
    with STATE_LOCK:                              # the record read and written back as one step
        key, record = find_state(state_path, path, project)
        if project:
            record.setdefault("project", project)
        change(record)
        if key and key.startswith("id:"):
            save_state(state_path, key, record)
            short = {k: v for k, v in _books(state_path).get(_key(path), {}).items()}
            short.setdefault("project", record.get("project"))
            change(short)
            save_state(state_path, path, short)
        else:
            save_state(state_path, path, record)


def mark_imported(path, state_path, created=None, project=None, step=None):
    """Record the workbook as it is now as imported, so the next export may overwrite it (what creaite's cmd_import does to
    the state at its end). For the import (#38). clark: `created` is the fingerprints of the rows this import made
    (record_created), written in the same save; `project` is kept if the record has none; `step` is the stamp of the step
    that applied the import ({"step", "db_id", "at"}), so "already imported" holds only while that step is in force. Written
    back to the record the import found (_write_back): by the export id, so the next import of the same workbook finds it."""
    digest = file_hash(path)

    def change(record):
        if step:
            record["imported_step"] = step
        record["imported_hash"] = digest
        add_created(record, created)
    _write_back(state_path, path, project, change)


def record_created(path, state_path, created, project=None):
    """Record only the fingerprints of the rows an import created, without marking the file as imported (for a workbook saved
    again after it was read: its new rows must still not be made twice). clark addition (#38)."""
    if created:
        _write_back(state_path, path, project, lambda record: add_created(record, created))


def lock_file(path):
    """The file Excel keeps beside a workbook it has open (creaite excel_sync.LOCK)."""
    path = Path(path)
    return path.with_name("~$" + path.name)


def choices(table, field):
    """The drop-down values for a field, for this table first, then for the field anywhere (creaite excel_sync.choices)."""
    return CHOICES.get((table, field)) or CHOICES.get(field)


# The characters an .xlsx can't hold (XML 1.0 refuses them): the C0 controls but tab, line feed and carriage return, lone
# surrogates, and U+FFFE and U+FFFF (creaite excel_sync.NOT_XML).
NOT_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff￾￿]")


def cell_text(value):
    """A value as a cell may hold it: text without NOT_XML's characters (a vertical tab, form feed or separator becomes a
    space); anything else as it is (creaite excel_sync.cell_text). clark: a carriage return (or CR LF) becomes a line feed,
    which is what an XML file gives back anyway (XML 1.0 reads CR as LF), so the round trip is exact."""
    if not isinstance(value, str):
        return value
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    return NOT_XML.sub(lambda m: " " if m.group() in "\x0b\x0c\x1c\x1d\x1e" else "", value)


# A text cell that starts with one of these could be taken for a formula by Excel (a CSV/formula injection). Such text is stored
# as a text cell (protect_text_cell), so it shows exactly as typed, with no apostrophe, and is never a formula. A line feed
# first is also given the style's quotePrefix, as a cheap extra guard.
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")
QUOTE_PREFIX_START = FORMULA_START + ("\n",)
APOSTROPHE = "'"


def escape_text(text):
    """Text as it goes in a cell. Text is shown exactly as typed: protect_text_cell (not an apostrophe) is what keeps text that
    starts with = + - @ TAB CR from running as a formula. The one case that still takes an apostrophe: text that starts with an
    apostrophe and then one of those characters or another apostrophe ('=1 becomes ''=1), because a v0.1.0 file wrote =1 as '=1
    and unescape_text takes that one apostrophe off again; this keeps unescape_text(escape_text(t)) == t for every text.
    Call it after cell_text, which can remove characters from the front."""
    return APOSTROPHE + text if text.startswith(APOSTROPHE) and text[1:].startswith(FORMULA_START + (APOSTROPHE,)) else text


def unescape_text(text):
    """Cell text to the stored text: removes exactly one leading apostrophe when what follows starts with = + - @ TAB CR or
    another apostrophe (the inverse of escape_text). Text typed in Excel, with no such apostrophe, comes back as typed."""
    if text.startswith(APOSTROPHE) and text[1:].startswith(FORMULA_START + (APOSTROPHE,)):
        return text[1:]
    return text


def protect_text_cell(cell):
    """Make `cell` a text cell, as a string, never a formula (openpyxl would make a string that starts with = a formula, and
    "#N/A" an error). When the text starts with = + - @ TAB CR or a line feed, the cell's style also gets quotePrefix, which
    Excel shows with no apostrophe and which makes a person's later edit of the cell stay text. Other styling is kept."""
    if isinstance(cell.value, str):
        cell.data_type = "s"
        cell.quotePrefix = cell.value.startswith(QUOTE_PREFIX_START)
    return cell


def to_cell(field, value):
    """A stored value as it goes in a cell: dates as real dates (before 1900 as dd-mm-yyyy text), flags as Yes or No,
    text without the characters a workbook can't hold (creaite excel_sync.to_cell). clark: no link fields, and the
    cell is made text by protect_text_cell
    (escape_text only handles text that starts with an apostrophe). Numbers and dates are never touched."""
    if value is None:
        return None
    if field in DATES:
        try:
            day = date.fromisoformat(value)
            if day.year < 1900:       # Excel has no date before 1900 (shows ####): dd-mm-yyyy text
                return "%02d-%02d-%04d" % (day.day, day.month, day.year)
            return day
        except (TypeError, ValueError):
            return escape_text(cell_text(value))   # not a date: text as typed, which must not be a formula
    if field in YES_NO:
        return "Yes" if int(value) else "No"
    value = cell_text(value)
    return escape_text(value) if isinstance(value, str) else value


def from_cell(field, value):
    """Workbook value to stored value: dates YYYY-MM-DD, Yes/No to 1/0, blanks to None (creaite excel_sync.from_cell).
    clark: text has its escape apostrophe removed (unescape_text), and a formula is only ever its text, never run."""
    if value is None:
        return None
    if not isinstance(value, (str, int, float, bool, date, datetime)):
        value = str(getattr(value, "text", None) or value)     # an array formula object: its formula as text
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        if value.strip() == "":
            return None
        value = unescape_text(value)
        if field in DATES:
            m = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", value.strip())     # as excel_import.read_date: - / or .
            try:
                if m:
                    return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
            except ValueError:
                pass
            return value  # left as typed; the store's checks report it
    if field in YES_NO:
        if str(value).lower() in ("yes", "y", "1", "true"):
            return 1
        if str(value).lower() in ("no", "n", "0", "false"):
            return 0
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def add_list(ws, col, n_rows, values, allow_blank=True, source=None):
    """Add a drop-down to column `col`, rows 2 to `n_rows` (creaite excel_sync.add_list). The values are written in the rule
    itself, or `source` (a range such as Lists!$A$2:$A$9) is used when given. clark (#85c): the rule is a list, its error style
    is stop (anything else is refused), and the error is in plain words.

    The rule covers rows 2 to `n_rows` only, that is the last data row + EXTRA_ROWS, not the whole column: a row typed further
    down has no drop-down. A range source (Lists!...) is matched by Excel without regard to case, so "high" is accepted where
    "High" is listed (not verified in Excel); a literal list in the rule is case-sensitive. The import checks the value either way."""
    formula = source or '"' + ",".join(values) + '"'
    dv = DataValidation(type="list", formula1=formula, allow_blank=allow_blank, errorStyle="stop",
                        showErrorMessage=True, errorTitle=LIST_ERROR_TITLE, error=LIST_ERROR)
    dv.add(f"{col}2:{col}{n_rows}")
    ws.add_data_validation(dv)


def add_note(ws, col, n_rows, title, text):
    """A prompt that shows when a cell in column `col` is selected, and checks nothing (free text with a note)."""
    dv = DataValidation(showInputMessage=True, promptTitle=title, prompt=text)
    dv.add(f"{col}2:{col}{n_rows}")
    ws.add_data_validation(dv)


def id_prompt(ws, col, first, last, text):
    """An input message (no rule) on the ID cells `col`{first}:`col`{last}; it refuses nothing."""
    if last < first:
        return
    dv = DataValidation(allow_blank=True, showInputMessage=True, promptTitle=ID_PROMPT_TITLE, prompt=text)
    dv.add(f"{col}{first}:{col}{last}")
    ws.add_data_validation(dv)


def lock_column(ws, col, n_rows, label, message=None):
    """Refuse edits in column `col` (rows 2 to `n_rows`): `label` is set by clark (creaite excel_sync.lock_column).
    The message says what to do next."""
    dv = DataValidation(type="custom", formula1="FALSE", showErrorMessage=True, errorTitle="Not editable",
                        error=message or "This column is filled in by clark. Leave it as it is.")
    dv.add(f"{col}2:{col}{n_rows}")
    ws.add_data_validation(dv)


def _dxf(name, pal=None):
    """The look of a colour name as a conditional format: the token's light fill and dark text."""
    fill, text = _pal(pal).hexes(name)
    return DifferentialStyle(font=Font(color=text), fill=PatternFill(fill_type="solid", start_color=fill, end_color=fill))


def add_colour_rules(ws, col, n_rows, values, pal=None):
    """One rule per value: a cell equal to the word gets that word's colour, so a value changed in Excel recolours itself. The
    word is a fixed literal from excel_colours, never data."""
    for value, name in values.items():
        rule = Rule(type="cellIs", operator="equal", formula=['"' + value + '"'], dxf=_dxf(name, pal))
        ws.conditional_formatting.add(f"{col}2:{col}{n_rows}", rule)


def add_late_status_rule(ws, col, n_rows, date_col, open_states, pal=None):
    """Row 1021: an open item past its date reads Overdue (red) on the page and in Word, so its Status cell is red here too, ahead of the
    green Open rule (stop if true). A formula rule evaluated by Excel against today's date; the sheet's words are unchanged."""
    rule = Rule(type="expression", formula=[late_formula(date_col, col, open_states)], dxf=_dxf("red", pal), stopIfTrue=True)
    ws.conditional_formatting.add(f"{col}2:{col}{n_rows}", rule)


def late_formula(date_col, status_col, open_states):
    """The overdue rule for row 2 (it applies down the column): a real date before today on a row whose status is open."""
    is_open = ",".join(f'${status_col}2="{s}"' for s in sorted(open_states))
    return f"AND(ISNUMBER(${date_col}2),${date_col}2<TODAY(),OR({is_open}))"


def add_late_rule(ws, col, n_rows, date_col, status_col, open_states, pal=None):
    """Red text on the date of an open item past its date. A formula rule, evaluated by Excel against today's date."""
    rule = FormulaRule(formula=[late_formula(date_col, status_col, open_states)], font=Font(color=_pal(pal).late_text))
    ws.conditional_formatting.add(f"{col}2:{col}{n_rows}", rule)


REF_CELL_LIMIT = 250        # characters a Milestone or Use case cell holds ("ID: name"); the name is cut, never the ID
REF_TABLES = {"milestone": ("milestones", "name"), "use_case": ("use_cases", "title")}
OPEN_TABLES = (("actions", "milestone"), ("raid", "milestone"), ("decisions", "milestone"),
               ("actions", "use_case"), ("raid", "use_case"), ("decisions", "use_case"))


def ref_text(item_id, name):
    """What a Milestone or Use case cell shows: 'ID: name' (just the ID when there is no name). A very long name is cut with an
    ellipsis so the cell stays under REF_CELL_LIMIT; the ID is never cut."""
    name = " ".join(str(name or "").split())
    if not name:
        return item_id
    room = REF_CELL_LIMIT - len(item_id) - 2
    if len(name) > room:
        name = name[:max(room - 1, 0)].rstrip() + "\u2026"
    return f"{item_id}: {name}"


def _ref_names(rows_by_table):
    """{"milestone": {id: 'ID: name'}, "use_case": {id: 'ID: name'}} from the milestone and use case rows."""
    return {f: {r["id"]: ref_text(r["id"], r.get(nf)) for r in rows_by_table.get(t, [])}
            for f, (t, nf) in REF_TABLES.items()}


def _open_items(rows_by_table):
    """{(field, id): 'ID, ID'}: the open actions, risks and issues and decisions under each milestone and use case (glance.is_open:
    status not Closed, Cancelled, Made or Withdrawn), in ID order."""
    found = {}
    for table, field in OPEN_TABLES:
        for r in rows_by_table.get(table, []):
            if r.get(field) and glance.is_open(r):
                found.setdefault((field, r[field]), []).append(r["id"])
    return {k: ", ".join(sorted(v)) for k, v in found.items()}


def writer_ids(text):
    """The ids in a use case row's `milestones` value (the canonical form the export keeps: 'ID, ID')."""
    return [i for i in (text or "").split(", ") if i]


def column_width(table, field):
    """A column's width by its kind: ID 10; the title 40 (48 when it is a long-text column); other long text 48; dates 12;
    flags and numbers 10; the Updated stamp 24 (it is text such as 2030-01-10 09:30:00.000); people, streams and labels 18;
    anything else 12."""
    if field == "id" or field in YES_NO or field in NUMBERS:
        return 10
    if field in REF_TABLES and table not in ("milestones", "use_cases"):
        return 40
    if field in ("open_items", "milestones"):
        return 30
    if field in WIDE:
        return 48
    if field == TITLE_OF.get(table):
        return 40
    if field in DATES:
        return 12
    if field == "updated_at":
        return 24
    return 18 if field in SHORT_NAMES else 12


def wraps(table, field):
    """Whether a column's text wraps: long text, the title column, and the "ID: name" Milestone and Use case columns of the other sheets."""
    return (field in WIDE or field == TITLE_OF.get(table) or field in ("open_items", "milestones")
            or (field in REF_TABLES and table not in ("milestones", "use_cases")))


def freeze_cell(table, cols):
    """Where the panes freeze: below the header row, and after the ID and the item's title (C2 on every sheet)."""
    fields = [f for _, f in cols]
    return f"{get_column_letter(fields.index(TITLE_OF[table]) + 2)}2"


def _ordered(table, rows):
    """A sheet's rows in order: by sort_order then ID for milestones and use cases, by ID for the rest (as the page lists
    them; creaite orders every sheet by its key)."""
    if table in ("milestones", "use_cases"):
        return sorted(rows, key=lambda r: (r.get("sort_order") or 0, r["id"]))
    return sorted(rows, key=lambda r: r["id"])


def _project_lists(project, rows_by_table):
    """The project's own lists for the drop-downs: {"workstream": [...names], "milestone": [...IDs], "use_case": [...IDs]}.
    Workstreams are those of the project (rows_by_table["workstreams"]), or, when that is not given, those the rows use.
    An empty list is left out (a drop-down with nothing in it would refuse everything). So a project with no milestones, or no
    use cases, has no list rule on those columns: they stay free text, and any ID typed there is checked on import instead."""
    streams = rows_by_table.get("workstreams")
    if streams is None:
        names = {r.get("workstream") for t in TABLES for r in rows_by_table.get(t, []) if r.get("workstream")}
    else:
        names = {r.get("name") for r in streams if r.get("name") and not r.get("archived")}
    out = {"workstream": sorted(names, key=lambda n: (n.lower(), n)),
           "milestone": [v for _, v in sorted(_ref_names(rows_by_table)["milestone"].items())],
           "use_case": [v for _, v in sorted(_ref_names(rows_by_table)["use_case"].items())]}
    return {k: [to_cell(k, v) for v in vs] for k, vs in out.items() if vs}


LIST_HEADS = {"workstream": "Workstreams", "milestone": "Milestones", "use_case": "Use cases"}


HISTORY_NAME = "History"
HISTORY_COLUMNS = (("When", "when_text", 22), ("Who", "who", 18), ("How", "how", 26), ("Item", "item", 34), ("Field", "field", 20),
                   ("From", "from", 44), ("To", "to", 44))
HISTORY_NOTE = "This sheet is read-only and for internal use. Do not send it to a client."
HISTORY_CELL_LIMIT = 5000                  # characters a history cell holds (design note, section 3)
HISTORY_FONT = OFFICE_FONT


def history_cell(value):
    """A history value as a cell holds it: text only, cut at HISTORY_CELL_LIMIT with an ellipsis."""
    if value is None:
        return None
    text = cell_text(str(value))      # protection is the string cell type (data_type "s"), as c27c96b: no visible apostrophe
    return text if len(text) <= HISTORY_CELL_LIMIT else text[:HISTORY_CELL_LIMIT - 1] + "\u2026"


# ── The Gantt sheet (row 926) ────────────────────────────────────────────────

# (column label, line field), the page's own labels and order (gantt/logic/grid.js). "_days" and "_status" are worked out, never stored.
GANTT_SHEET_COLUMNS = (
    ("ID", "id"), ("Line", "name"), ("Type", "type"), ("Parent", "parent"), ("Start", "start"), ("End", "end"), ("Days", "_days"),
    ("Done %", "pct"), ("Status", "_status"), ("Health", "health"), ("Depends on", "depends"), ("Owner", "owner"),
    ("Workstream", "workstream"), ("Priority", "priority"), ("Baseline start", "baseline_start"), ("Baseline end", "baseline_end"),
    ("Effort (days)", "effort"), ("Budget", "budget"), ("Deliverable", "deliverable"), ("On dashboard", "show"), ("Notes", "note"))
GANTT_DATES = {"start", "end", "baseline_start", "baseline_end"}
GANTT_WIDTHS = {"id": 18, "name": 32, "type": 12, "parent": 18, "_days": 8, "pct": 10, "_status": 14, "depends": 30, "owner": 18, "workstream": 18,
                "deliverable": 30, "show": 14, "note": 40}
GANTT_DEFAULT_NAME = "Gantt"
CLIENT_COPY_NAME = "clark_client_copy"       # row 926: the hidden workbook-level defined name only the client workbook carries (it points at the client Gantt sheet)
GANTT_BAD_SHEET_CHARS = re.compile(r"[\\/*?:\[\]]")


def gantt_days(line):
    """Days a line spans, both ends counted; blank for a milestone or a line without both dates (the page's Days column, grid.js)."""
    try:
        if line.get("type") == "milestone":
            return None
        return (date.fromisoformat(line["end"]) - date.fromisoformat(line["start"])).days + 1
    except (KeyError, TypeError, ValueError):
        return None


def gantt_status(line, today):
    """Done, Late, In progress or Not started, from the dates and Done % as of `today` (YYYY-MM-DD); the page's rule (grid.js statusOf)."""
    pct = line.get("pct") or 0
    if pct >= 100:
        return "Done"
    milestone = line.get("type") == "milestone"
    end = (line.get("start") if milestone else line.get("end")) or ""
    if today and end and end < today:
        return "Late"
    if pct > 0 or (today and not milestone and line.get("start") and line["start"] <= today):
        return "In progress"
    return "Not started"


def gantt_sheet_name(name, taken=()):
    """The tab's name as a sheet name: no character a sheet name cannot hold, at most 31 characters, not one already used; else 'Gantt'."""
    clean = " ".join(GANTT_BAD_SHEET_CHARS.sub(" ", name).split())[:31] if isinstance(name, str) else ""
    reserved = {LISTS_NAME, HISTORY_NAME, COVER_NAME, *taken}       # the sheets written after the Gantt one are named already
    if not clean or clean.lower() in {t.lower() for t in reserved}:
        clean = GANTT_DEFAULT_NAME
    return clean


def gantt_cell(line, field, today):
    """One cell of the Gantt sheet from a line (the editor's stored line or the client's gated copy)."""
    if field == "_days":
        return gantt_days(line)
    if field == "_status":
        return gantt_status(line, today)
    v = line.get(field)
    if field == "show":
        return "Yes" if v else "No"
    if field == "type":
        return cell_text(str(v).capitalize()) if v else None
    if field == "depends":
        v = ", ".join(v) if isinstance(v, (list, tuple)) else ", ".join(n.strip() for n in str(v or "").split(",") if n.strip())
        return escape_text(cell_text(v)) if v else None
    if v is None or v == "":
        return None
    if field in GANTT_DATES:
        return to_cell("due_date", v)           # a real date in dd-mm-yyyy, as every other sheet's dates
    return to_cell(field, v)


def write_gantt(wb, lines, fields, name, today, pal=None):
    """The Gantt sheet: `fields` are the GANTT_SHEET_COLUMNS fields to write, `lines` in the order to write them. Read-only (locked), a
    header row, frozen after the Line column."""
    st = Styles(_pal(pal))
    ws = wb.create_sheet(gantt_sheet_name(name, wb.sheetnames))
    cols = [(label, f) for label, f in GANTT_SHEET_COLUMNS if f in fields]
    ws.append([label for label, _ in cols])
    for line in lines:
        ws.append([gantt_cell(line, f, today) for _, f in cols])
        for c in ws[ws.max_row]:
            c.font = st.body_font
            protect_text_cell(c)
    for i, (_, f) in enumerate(cols, start=1):
        head = ws.cell(row=1, column=i)
        head.font, head.fill = st.header_font, st.header
        head.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(i)].width = GANTT_WIDTHS.get(f, 12)
        for (c,) in ws[f"{get_column_letter(i)}2:{get_column_letter(i)}{len(lines) + 1}"]:
            c.alignment = Alignment(wrap_text=f in ("name", "note", "deliverable", "depends"), vertical="top")
            if f in GANTT_DATES:
                c.number_format = DATE_FORMAT
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{len(lines) + 1}"
    protect_sheet(ws)
    return ws


def write_history(wb, view, pal=None):
    """The History sheet (#123), after the data sheets: `view` is exactly what history.view_for_project returns, so the sheet and
    the Activity tab show the same rows. Row 1 is the internal note and the footnote, row 2 the header (frozen with it), then the
    rows newest first, then the closing line (or the empty words). Every cell is a text cell in the look's office font; the import never reads it."""
    st = Styles(_pal(pal))
    ws = wb.create_sheet(HISTORY_NAME)

    def put(row, values, **kw):
        for i, v in enumerate(values, start=1):
            c = ws.cell(row=row, column=i, value=v)
            protect_text_cell(c)            # text is text: a value starting "=" is never a formula
            c.font = Font(name=st.pal.font, **kw)
            c.alignment = Alignment(wrap_text=i in (6, 7), vertical="top")

    put(1, [history_cell(HISTORY_NOTE + " " + view["footnote"])], italic=True)
    ws.append([label for label, _, _ in HISTORY_COLUMNS])
    for i, (label, _, width) in enumerate(HISTORY_COLUMNS, start=1):
        head = ws.cell(row=2, column=i)
        head.font, head.fill = Font(name=st.pal.font, bold=True, color=st.pal.header_text), st.header
        head.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(i)].width = width
    for r in view["rows"]:
        put(ws.max_row + 1, [history_cell(r[key]) for _, key, _ in HISTORY_COLUMNS])
    last = view["closing"] or (view["empty"] if not view["rows"] else "")
    if last:
        put(ws.max_row + 1, [history_cell(last)], italic=True)
    ws.freeze_panes = "A3"
    protect_sheet(ws)
    return ws


def write_lists(wb, lists, pal=None):
    """The hidden Lists sheet: one column per project list, a header in row 1 (the ranges the drop-downs point at are those of
    `workbook`, in the same order). Hidden, not very hidden, so a person can unhide it; the import reads sheets by name and never opens it."""
    st = Styles(_pal(pal))
    ws = wb.create_sheet(LISTS_NAME)
    for i, field in enumerate(lists, start=1):
        col = get_column_letter(i)
        head = ws.cell(row=1, column=i, value=LIST_HEADS[field])
        head.font, head.fill = st.header_font, st.header
        head.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[col].width = 24
        for n, v in enumerate(lists[field], start=2):
            c = ws.cell(row=n, column=i, value=v)
            protect_text_cell(c)
            c.font = st.body_font
    ws.sheet_state = "hidden"
    protect_sheet(ws)
    return ws


# ── Export ────────────────────────────────────────────────────────────────────

COVER_NAME = "Cover"
COVER_LABELS = {"exported": "Exported", "caution": "Caution", "return": "Sending changes back",
                "where": "Where to make changes", "ids": "IDs", "locked": "Locked cells"}
COVER_FONT = OFFICE_FONT
COVER_COLUMNS = 12                  # the Cover's grid: 12 equal columns, text and tiles in merged cells
COVER_SIZE = 10                     # body text, in points
COVER_TITLE_SIZE = 22               # the title band: the report title, in points
COVER_SUBTITLE_SIZE = 12            # and its subtitle line
COVER_CHARS = 1.05                  # characters of body text to a column-width unit, a little under what Arial 10 fits
TILE_BAR = {"red": "status-red", "amber": "status-amber-text", "green": "status-green-text"}     # a tile's left bar: the status tokens


def _cover_cell(value):
    """Cover text as a cell holds it: the same cell_text as the data (the cell itself is made text by protect_text_cell, which
    is what keeps text starting = + - @ from being a formula), so no cell can be a formula or hold a character XML can't. No
    escape_text: the import never reads the Cover, so text that starts '= needs no extra apostrophe."""
    return cell_text(excel_cover.cut(value))


def _cover_font(pal, **kw):
    kw.setdefault("size", COVER_SIZE)
    return Font(name=pal.font, **kw)


def _span_chars(first, last, size=COVER_SIZE):
    """About how many characters of `size` point text fit in columns first..last."""
    return (last - first + 1) * excel_picture.COVER_COL_WIDTH * COVER_CHARS * COVER_SIZE / size


def _put(pal, ws, row, first, last, value="", font=None, fill=None, align=None, top=None, bottom=None, left=None):
    """Fill columns first..last of `row` as one merged cell holding `value`: the fill and the borders go on every cell of the
    range (a merged cell draws from them), the text on the first. The text is a text cell, never a formula."""
    if last > first:
        ws.merge_cells(start_row=row, start_column=first, end_row=row, end_column=last)
    for col in range(first, last + 1):
        c = ws.cell(row=row, column=col)
        if fill:
            c.fill = PatternFill("solid", fgColor=fill)
        c.border = Border(top=top, bottom=bottom, left=left if col == first else None)
        c.font = font or _cover_font(pal)
    c = ws.cell(row=row, column=first)
    c.value = _cover_cell(value) if value != "" else None
    protect_text_cell(c)
    c.alignment = align or Alignment(wrap_text=True, vertical="top")
    return c


def _tile_widths(n):
    """The grid columns for each of n tiles side by side: health (first) twice as wide as the others when there are three."""
    return {1: [12], 2: [6, 6], 3: [6, 3, 3]}.get(n) or [12 // n] * (n - 1) + [12 - 12 // n * (n - 1)]


def _heading(pal, ws, row, first, last, text):
    """A section heading: the brand-blue square, the title and a grey rule under it."""
    t = pal.tokens
    square = TextBlock(InlineFont(rFont=pal.font, sz=12, b=True, color=t["brand-blue"]), "\u25a0  ")
    words = TextBlock(InlineFont(rFont=pal.font, sz=12, b=True, color=t["brand-ink"]), cell_text(excel_cover.cut(text, 200)))
    c = _put(pal, ws, row, first, last, "", _cover_font(pal, size=12, bold=True), None,
             Alignment(vertical="center"), bottom=Side(style="thin", color=t["grey-300"]))
    c.value = CellRichText(square, words)
    ws.row_dimensions[row].height = 22


def write_cover(wb, cover, mark=False, pal=None, wave=False):
    """The Cover sheet, first in the workbook and the one it opens on (item 85b): a 12-column grid with the gridlines off, text
    blocks and tiles in merged cells, laid out as Option A of the signed mockup: the navy title band (the logo at its left when
    `mark`, the INTERNAL tag at its right, a subtitle line under the title), Current state, At a glance tiles side by side, the
    Summary, This week and Next week side by side, and a quiet About this export block. Excel does not fit a merged cell's height
    to its text, so every row's height is estimated from the text (excel_cover.height). Frozen below the band. The look's office
    font throughout. `cover` is excel_cover.lines(). Not a table: the import never reads it."""
    ws = wb.create_sheet(COVER_NAME, 0)
    ws.sheet_view.showGridLines = False
    for col in range(1, COVER_COLUMNS + 1):
        ws.column_dimensions[get_column_letter(col)].width = excel_picture.COVER_COL_WIDTH
    pal = _pal(pal)
    t = pal.tokens
    navy, white, ink = t["brand-navy"], t["white"], t["brand-ink"]
    grey_fill, grey_text, rule = t["grey-50"], t["grey-700"], t["grey-300"]
    last = COVER_COLUMNS
    band_edge = Side(style="thick", color=t["brand-blue"])       # a distinct edge under the dark band
    row = 0
    start = 1
    for line in cover:
        kind, text = line["kind"], line["text"]
        if kind == "title":
            row += 1
            start = excel_picture.LOGO_COLUMNS + 1 if mark else 1
            tag = line.get("tag", "")
            end = last - 2 if tag else last
            for col in range(1, last + 1):
                ws.cell(row=row, column=col).fill = PatternFill("solid", fgColor=navy)
            _put(pal, ws, row, start, end, text, _cover_font(pal, bold=True, size=COVER_TITLE_SIZE, color=white), navy,
                 Alignment(wrap_text=True, vertical="center"))
            if tag:
                _put(pal, ws, row, last - 1, last, tag, _cover_font(pal, bold=True, size=11, color=white), t["status-red"],
                     Alignment(horizontal="center", vertical="center"))
            ws.row_dimensions[row].height = max(excel_picture.COVER_ROW_POINTS,
                                                excel_cover.height(text, _span_chars(start, end, COVER_TITLE_SIZE), 20, 30))
        elif kind == "subtitle":
            row += 1
            for col in range(1, last + 1):
                ws.cell(row=row, column=col).fill = PatternFill("solid", fgColor=navy)
            edge = None if wave else band_edge
            for col in range(1, start):
                ws.cell(row=row, column=col).border = Border(bottom=edge)
            _put(pal, ws, row, start, last, text, _cover_font(pal, size=COVER_SUBTITLE_SIZE, color=t["grey-100"]), navy,
                 Alignment(wrap_text=True, vertical="top"), bottom=edge)
            ws.row_dimensions[row].height = excel_cover.height(text, _span_chars(start, last, COVER_SUBTITLE_SIZE), 20, 17)
            if wave:        # the brand's cover picture sits in a dark row of its own under the subtitle (drawn after the save)
                row += 1
                for col in range(1, last + 1):
                    c = ws.cell(row=row, column=col)
                    c.fill = PatternFill("solid", fgColor=navy)
                    c.border = Border(bottom=band_edge)
                ws.row_dimensions[row].height = excel_picture.WAVE_ROW_POINTS
            ws.freeze_panes = ws.cell(row=row + 1, column=1)
        elif kind == "heading":
            row += 2                           # a short blank row first
            ws.row_dimensions[row - 1].height = 8
            _heading(pal, ws, row, 1, last, text)
        elif kind == "text":
            row += 1
            _put(pal, ws, row, 1, last, text)
            ws.row_dimensions[row].height = excel_cover.height(text, _span_chars(1, last))
        elif kind == "pair":
            left_end, right_start = last // 2 - 1, last // 2 + 2      # columns 1-5 and 8-12: a two column gutter (6-7) with no rule across it
            row += 2
            ws.row_dimensions[row - 1].height = 8
            _heading(pal, ws, row, 1, left_end, line["left"]["title"])
            _heading(pal, ws, row, right_start, last, line["right"]["title"])
            row += 1
            _put(pal, ws, row, 1, left_end, line["left"]["text"])
            _put(pal, ws, row, right_start, last, line["right"]["text"])
            ws.row_dimensions[row].height = max(excel_cover.height(line["left"]["text"], _span_chars(1, left_end)),
                                                excel_cover.height(line["right"]["text"], _span_chars(right_start, last)))
        elif kind == "tiles":
            tiles = line["tiles"]
            first = 1
            rows = (row + 1, row + 2, row + 3)
            sub = 15
            for tile, w in zip(tiles, _tile_widths(len(tiles))):
                end = first + w - 1
                bar = Side(style="thick", color=t[TILE_BAR.get(tile["colour"], "grey-300")])
                _put(pal, ws, rows[0], first, end, tile["title"], _cover_font(pal, color=grey_text), grey_fill, left=bar)
                health = tile["tile"] == "health"
                if health:       # the pill: the page's colour for the status, with the words in it, so it reads in black and white too
                    pill_end = min(end, first + 1)
                    fill, pen = pal.hexes(tile["colour"]) if tile["colour"] in pal.colours else (grey_fill, ink)
                    _put(pal, ws, rows[1], first, pill_end, tile["value"], _cover_font(pal, bold=True, size=12, color=pen), fill,
                         Alignment(horizontal="center", vertical="center"), left=bar)
                    if end > pill_end:
                        _put(pal, ws, rows[1], pill_end + 1, end, "", None, grey_fill)
                else:
                    _put(pal, ws, rows[1], first, end, tile["value"], _cover_font(pal, bold=True, size=22, color=ink), grey_fill,
                         Alignment(horizontal="left", vertical="center", indent=1), left=bar)
                _put(pal, ws, rows[2], first, end, tile["detail"], _cover_font(pal, color=ink if health else grey_text), grey_fill, left=bar)
                sub = max(sub, excel_cover.height(tile["detail"], _span_chars(first, end) - 1))
                first = end + 1
            ws.row_dimensions[rows[0]].height = 18
            ws.row_dimensions[rows[1]].height = 32
            ws.row_dimensions[rows[2]].height = sub
            row += 3
        elif kind == "about":                  # the About this export block: a quiet grey panel
            row += 2
            ws.row_dimensions[row - 1].height = 14
            _put(pal, ws, row, 1, last, text, _cover_font(pal, bold=True, color=ink), grey_fill, Alignment(vertical="center"))
            ws.row_dimensions[row].height = 20
        else:                                  # one row of that block: its label at the left, its words beside it
            row += 1
            edge = Side(style="thin", color=rule)
            _put(pal, ws, row, 1, 3, COVER_LABELS.get(kind, ""), _cover_font(pal, bold=True, color=grey_text), grey_fill, top=edge)
            _put(pal, ws, row, 4, last, text, _cover_font(pal, color=grey_text), grey_fill, top=edge)
            ws.row_dimensions[row].height = excel_cover.height(text, _span_chars(4, last))
    wb.active = 0
    protect_sheet(ws)
    return ws


def workbook(project, rows_by_table, on=None, cover=None, mark=False, history=None, pal=None, wave=False, gantt_tab=None):
    """The workbook for one project, from {table: [row, ...]} (creaite excel_sync.cmd_export, the sheet part). Rows are dicts
    with the table's columns; labelled rows may carry `labels` (comma-separated) and milestones `original_date`. A missing
    table is an empty sheet. `on` is the day Shown state is worked out for (today by default). `cover` (excel_cover.lines) adds
    the Cover as the first sheet (#85b); without it the workbook is as it was. `history` (history.view_for_project's result) adds
    the History sheet (#123) after the data sheets and before Lists."""
    pal = _pal(pal)
    st = Styles(pal)
    lists = _project_lists(project, rows_by_table)
    names, open_of = _ref_names(rows_by_table), _open_items(rows_by_table)
    ranges = {f: f"{LISTS_NAME}!${get_column_letter(i)}$2:${get_column_letter(i)}${len(vs) + 1}"
              for i, (f, vs) in enumerate(lists.items(), start=1)}
    wb = Workbook()
    wb.remove(wb.active)
    stamp = moment(on)
    props = wb.properties
    props.created = props.modified = stamp
    props.creator = props.lastModifiedBy = FIXED_NAME
    props.title = f"{project} work items" if project else "clark import template"
    props.description = INTERNAL_NOTE
    for name, table, cols, locked in SHEETS:
        ws = wb.create_sheet(name)
        rows = _ordered(table, rows_by_table.get(table, []))
        ws.append([label for label, _ in cols])
        for r in rows:
            if table == "milestones":
                r = {**r, "shown_state": milestone_state(r, on), "original_date": r.get("original_date") or r.get("baseline_date")}
            if table == "use_cases":      # row 1107: the milestones linked straight to the use case, one "ID: name" per line (the ids are in the row; the import reads them back)
                r = {**r, "milestones": "\n".join(names["milestone"].get(i, i) for i in writer_ids(r.get("milestones"))) or None}
            if table in ("milestones", "use_cases"):
                r = {**r, "open_items": open_of.get(("milestone" if table == "milestones" else "use_case", r["id"]))}
            else:
                r = {**r, **{f: names[f].get(r.get(f), r.get(f)) for f in REF_TABLES}}
            r = {**r, **{f: sanitise.rich_plain_text(r[f]) for t, f in RICH_WORDS if t == table and isinstance(r.get(f), str)}}
            ws.append([to_cell(f, r.get(f)) for _, f in cols])
            for c in ws[ws.max_row]:
                c.font = st.body_font
                protect_text_cell(c)        # text is text: openpyxl would make a string starting "=" a formula, "#N/A" an error
        n_rows = len(rows) + 1 + EXTRA_ROWS
        for i, (label, field) in enumerate(cols, start=1):
            col = get_column_letter(i)
            head = ws.cell(row=1, column=i)
            head.font, head.fill = st.header_font, st.header
            head.alignment = Alignment(wrap_text=True, vertical="center")
            ws.column_dimensions[col].width = column_width(table, field)
            ws.column_dimensions[col].font = st.body_font        # the empty rows below the data, which a person fills in
            for c in ws[f"{col}2:{col}{n_rows}"]:
                c[0].font = st.body_font           # the data and the spare rows, so typed entries match (#85)
            for c in ws[f"{col}2:{col}{len(rows) + 1}"]:
                c[0].alignment = Alignment(wrap_text=wraps(table, field), vertical="top")
            if field in DATES:
                for c in ws[f"{col}2:{col}{n_rows}"]:
                    c[0].number_format = DATE_FORMAT
            if field not in locked_fields(locked):        # editable: the data rows and the blank rows for new items
                for c in ws[f"{col}2:{col}{n_rows}"]:
                    c[0].protection = UNLOCKED
            if field == "id":
                id_prompt(ws, col, 2, len(rows) + 1, ID_PROMPT_EXISTING)
                id_prompt(ws, col, len(rows) + 2, n_rows, ID_PROMPT_NEW)
                head.comment = Comment(ID_NOTE, FIXED_NAME)
                head.comment.width, head.comment.height = 280, 60
            if field in locked:
                if field != "id":       # the ID is not refused by a rule: the import guards it (#129)
                    lock_column(ws, col, n_rows, label, "Priority follows Impact and Likelihood. Change those instead."
                                if (table, field) == ("raid", "priority") else None)
            if field in locked_fields(locked):      # item 1157: every locked column is grey, the Project and the worked-out ones too
                for c in ws[f"{col}2:{col}{len(rows) + 1}"]:
                    c[0].fill = st.locked
            blank = field not in YES_NO and (table, field) not in NOT_BLANK
            if field == "project":
                if project:         # the import template (project None) is for any project: no code in it, and the cell stays free
                    add_list(ws, col, n_rows, [project], allow_blank=False)
            elif field in ranges and field not in locked:
                add_list(ws, col, n_rows, None, allow_blank=True, source=ranges[field])   # the project's own list
            elif field in YES_NO:
                add_list(ws, col, n_rows, ["Yes", "No"], allow_blank=False)
            elif field not in locked and choices(table, field):
                add_list(ws, col, n_rows, choices(table, field), allow_blank=blank)
            elif field in PEOPLE:
                add_note(ws, col, n_rows, "Owner" if field == "owner" else "Made by",
                         "Type the person's name.")
            if field == "status" and (table, "due_date") in colours.LATE:
                add_late_status_rule(ws, col, n_rows, get_column_letter([f for _, f in cols].index("due_date") + 1),
                                     colours.LATE[(table, "due_date")][1], pal)
            if (table, field) in colours.BY_FIELD:      # clark (#85c): colour follows the value, by conditional format
                add_colour_rules(ws, col, n_rows, colours.BY_FIELD[(table, field)], pal)
            if (table, field) in colours.LATE:
                status_field, open_states = colours.LATE[(table, field)]
                add_late_rule(ws, col, n_rows, col, get_column_letter([f for _, f in cols].index(status_field) + 1),
                              open_states, pal)
        if table == "milestones":      # the internal note and the ID note stay on Milestones A1, whatever the sheet order
            note = Comment(INTERNAL_NOTE + "\n\n" + ID_NOTE, FIXED_NAME)    # one note per cell: both go on Milestones A1
            note.width, note.height = 320, 120
            ws["A1"].comment = note
        ws.freeze_panes = freeze_cell(table, cols)
        ws.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{len(rows) + 1}"
        protect_sheet(ws)
    gantt = rows_by_table.get("gantt_lines") or []
    if gantt:           # row 926: every line the author has, eye-off included (this is the editor's own copy); no lines, no sheet
        write_gantt(wb, sorted(gantt, key=lambda r: (r.get("sort_order") or 0, r["id"])), {f for _, f in GANTT_SHEET_COLUMNS},
                    gantt_tab, day(on).isoformat(), pal)
    if history is not None:
        write_history(wb, history, pal)
    if lists:
        write_lists(wb, lists, pal)
    if cover:
        write_cover(wb, cover, mark, pal, wave)
    for ws in wb.worksheets:
        print_setup(ws)
    return wb


def fixed_zip(data, replace=None, add=None):
    """The same .xlsx with every member given one fixed date, in sorted order, deflated: openpyxl stamps each member with the
    time it was saved, so two saves in different seconds would differ. `replace` maps a member's name to the bytes to use, and `add` maps the name of a new member to its bytes."""
    replace = replace or {}
    add = add or {}
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as src, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for name in sorted(set(src.namelist()) | set(add)):
            info = zipfile.ZipInfo(name, ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            dst.writestr(info, add[name] if name in add else replace[name] if name in replace else src.read(name))
    return out.getvalue()


def latest_export(state_path, project):
    """(export id, file hash) of `project`'s newest export recorded by its id, or None; for export(reuse=...)."""
    try:
        books = _books(state_path)
    except (OSError, ValueError):
        return None
    mine = [(str(r.get("exported_at") or ""), k, r) for k, r in books.items()
            if k.startswith(f"id:{project}:") and r.get("project") == project]
    if not mine:
        return None
    _, k, r = max(mine)
    token = k[len(f"id:{project}:"):]
    return (token, r.get("hash")) if EXPORT_ID_OK.fullmatch(token) and r.get("hash") else None


def export(path, project, rows_by_table, state_path, on=None, cover=None, branding=None, warnings=None, history=None, reuse=None, gantt_tab=None):
    """Write the workbook at `path` for `project` from {table: [row, ...]} and record what was written in `state_path`
    (creaite excel_sync.cmd_export). Returns {table: rows written}.

    Each workbook carries a fresh export id. `reuse` (latest_export's (id, hash)) lets an export that comes out byte for
    byte the same as that one keep its id, so the same rows exported again the same day are the same file and the same record
    (so the record file does not grow by a click); any other export gets a fresh id, so two different files never share one.
    Without `reuse`, the record already kept for `path` (if any) is offered.

    Raises Refused, and leaves the file as it is, while the workbook is open in Excel or has edits not yet imported. clark: the
    workbook is saved with platform.write_file (a temporary file, then a safe replace with retry)."""
    path = Path(path)
    if lock_file(path).exists():
        raise Refused(f"{path.name} is open in Excel. Close it, then export again ({path}).")
    if has_unimported_edits(path, state_path):
        if load_state(state_path, path):
            raise Refused(f"{path.name} has edits that haven't been imported. Import it first; the workbook was not "
                          f"overwritten ({path}).")
        raise Refused(f"{path.name} already exists and wasn't written by an export from this store, so it was not "
                      f"overwritten ({path}). Import it, or choose another file name.")
    buf = io.BytesIO()
    logo = excel_picture.load(branding, warnings) if cover else None     # #133: the local brand logo, if there is one and it is safe
    pal = excel_palette.palette(branding=branding)      # item 711: the local brand's light values, else the committed look
    for note in pal.warnings:           # the palette's notes are for the log only: no one is shown them
        logging.getLogger("clark.excel").warning("%s", note)
    wave = excel_picture.load_wave(branding, warnings) if cover else None     # the brand's cover picture: only from the branding folder
    wb = workbook(project, rows_by_table, on, cover, mark=bool(logo), history=history, pal=pal, wave=bool(wave), gantt_tab=gantt_tab)
    if reuse is None:                      # the same unchanged workbook exported again to its own path keeps its id
        try:
            mine = _books(state_path).get(_key(path)) or {}
        except (OSError, ValueError):
            mine = {}
        reuse = (mine.get("export_id"), mine.get("hash")) if mine.get("hash") else None
    reuse = reuse if isinstance(reuse, tuple) and len(reuse) == 2 and EXPORT_ID_OK.fullmatch(str(reuse[0])) else None
    token = reuse[0] if reuse else new_export_id()
    # The export id, so an import finds this record after an edit or a re-save. A workbook property only (custom.xml),
    # never a cell or the Cover; it is random, so it holds nothing of the project's rows or of the person.
    wb.custom_doc_props.append(StringProperty(name=EXPORT_ID_NAME, value=token))
    wb.save(buf)
    # openpyxl sets "modified" to the real time as it saves, so core.xml is written again with the export's own stamp.
    wb.properties.modified = wb.properties.created
    replace, add = {"docProps/core.xml": tostring(wb.properties.to_tree())}, {}
    if logo or wave:
        # The logo and the cover picture go in after openpyxl has saved, by editing the zip's members (standard library only); the write below is
        # the atomic one. If the saved file is not laid out as expected the Cover goes without a mark.
        try:
            with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as z:
                files = {n: z.read(n) for n in z.namelist()}
            more, add = excel_picture.embed(files, logo[0] if logo else None, COVER_NAME, wave[0] if wave else None)
            replace.update(more)
        except excel_picture.PictureRefused as e:
            text = excel_picture.NOT_USED.format(why=e)         # the same plain sentence as a refused logo file
            excel_picture.LOG.warning("%s", text)
            if warnings is not None:
                warnings.append(text)
    data = fixed_zip(buf.getvalue(), replace, add)
    if reuse and hashlib.sha256(data).hexdigest() != reuse[1]:
        # not the same file as the export whose id was offered: it gets a fresh id of its own (the same part, written the same way)
        token = new_export_id()
        wb.custom_doc_props = CustomPropertyList()
        wb.custom_doc_props.append(StringProperty(name=EXPORT_ID_NAME, value=token))
        replace[CUSTOM_PART] = tostring(wb.custom_doc_props.to_tree())
        data = fixed_zip(buf.getvalue(), replace, add)
    platform.write_file(path, data)
    snapshot = {t: {r["id"]: {k: v for k, v in r.items() if k not in DERIVED} for r in rows_by_table.get(t, [])}
                for t in TABLES}
    # clark: "rows" is what each row held when it was exported, {table: {id: row}}: the import compares a workbook with it to
    # tell the person's own edits from changes made in clark since. Left out (None) if it would be very large.
    if len(json.dumps(snapshot, default=str)) > MAX_SNAPSHOT_BYTES:
        snapshot_rows = None
    else:
        snapshot_rows = snapshot
    save_state(state_path, path, {"exported_at": moment(on).strftime("%Y-%m-%d %H:%M:%S"),
                                  "hash": hashlib.sha256(data).hexdigest(), "imported_hash": None, "project": project,
                                  "export_id": token, "rows": snapshot_rows})
    return {t: len(snapshot[t]) for t in TABLES}


TEMPLATE_NAME = "clark import template.xlsx"


def template_bytes(on=None):
    """The import template (#454): the workbook of an export with no rows at all, the same sheets (SHEETS) and column labels,
    so the import reads it unchanged. It is made from nothing but SHEETS: no store, project, person, item, Cover, History or
    export id, so it names nothing and records nothing (an import finds no record of it, as of any workbook clark did not
    export). Returns the .xlsx bytes."""
    buf = io.BytesIO()
    wb = workbook(None, {}, on)
    wb.save(buf)
    wb.properties.modified = wb.properties.created        # as export(): the stamp is the workbook's own, not the time of saving
    return fixed_zip(buf.getvalue(), {"docProps/core.xml": tostring(wb.properties.to_tree())})


def export_name(project):
    """The file name clark gives a project's workbook, made safe (platform.safe_name)."""
    return platform.safe_name(f"{project} work items.xlsx")


def export_project(store, project, path=None, state_path=None, on=None, exported_by=None, owner=None, owner_email=None,
                   branding=None, warnings=None, reuse=None):
    """Export one project from the store (#31): each table's rows with Store.read(kind, project), archived rows left out (as
    creaite's hide_archived), labels from item_labels and each milestone's Original date from its history. `path` defaults
    to export_name() beside clark.db; the record goes in STATE_FILE beside clark.db. Returns the path written."""
    from clark import history
    folder = Path(store.path).parent
    path = Path(path) if path is not None else folder / export_name(project)
    state_path = Path(state_path) if state_path is not None else folder / STATE_FILE
    rows = {t: [r for r in store.read(t, project) if not r.get("archived")] for t in TABLES}
    rows["workstreams"] = [r for r in store.read("workstreams", project) if not r.get("archived")]   # for the drop-downs only
    ids = {r["id"] for t in LABELLED for r in rows[t]}
    have = {}
    for r in sorted(store.read("item_labels"), key=lambda r: r["label"].lower()):
        if r["item_id"] in ids:
            have.setdefault(r["item_id"], []).append(r["label"])
    for t in LABELLED:
        for r in rows[t]:
            r["labels"] = ", ".join(have.get(r["id"], [])) or None
    from clark import store as clark_store
    for r in rows["use_cases"]:      # row 1107: the direct links (canonical 'ID, ID'), kept in the export's record too
        r["milestones"] = ", ".join(clark_store.use_case_milestone_ids(store.con, r["id"])) or None
    for r in rows["milestones"]:
        r["original_date"] = history.original_date(store.con, r["id"], r.get("baseline_date"))
    # The Cover is worked out from what the published page shows (excel_cover.from_store), so the two can't disagree; the person
    # named as exporting and the owner are the caller's to give (Settings are not read here).
    cover = excel_cover.from_store(store, project, exported_text(on), exported_by, owner, owner_email, INTERNAL_NOTE,
                                   day(on).isoformat())
    view = history.view_for_project(store.con, project, "all", history.ROW_LIMIT)       # the one source the Activity tab shares
    rows["gantt_lines"] = [r for r in store.read("gantt_lines", project)]      # row 926: only the sheet reads these; the import does not (TABLES)
    tab = (store.read("projects", ref=project) or {}).get("gantt_tab_name")
    export(path, project, rows, state_path, on, cover, branding, warnings, history=view, reuse=reuse, gantt_tab=tab)
    return path


# ── Reading back ──────────────────────────────────────────────────────────────

def read_sheet(ws, table, cols):
    """Rows as {field: stored value}; header labels map to fields, so column order may change (creaite excel_sync.read_sheet).
    clark: worked-out columns are left out, and a blank cell in a NOT NULL text column reads as ""."""
    header = [c.value for c in ws[1]]
    by_label = {label: field for label, field in cols if field not in DERIVED}
    index = {i: by_label[h] for i, h in enumerate(header) if h in by_label}
    rows = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        rec = {index[i]: from_cell(index[i], v) for i, v in enumerate(row) if i in index}
        if any(v is not None for v in rec.values()):
            for f in rec:
                if rec[f] is None and (table, f) in EMPTY_TEXT:
                    rec[f] = ""
            rows.append(rec)
    return rows


def read_workbook(path):
    """{table: [row, ...]} as stored values, from an exported workbook (for the import, #38, and the round trip)."""
    check_workbook_size(path)
    wb = load_workbook(Path(path))
    return {table: read_sheet(wb[name], table, cols) if name in wb.sheetnames else [] for name, table, cols, _ in SHEETS}
