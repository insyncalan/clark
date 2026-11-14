"""Excel import (#38, FR-71): compare a workbook with the database by id, stage the differences, apply only the accepted ones.

Kept in its own file beside the export (`excel.py`, #37); it takes the export's sheet names and header labels from there. Reads with the vendored openpyxl; writes only through the store's Step (`Store.step`, `Step.create`,
`Step.update`, `Step.cancel`), so the writer's rules, the history and Undo all apply. Never edits the store.

THE WORKBOOK THE IMPORT READS (the one the export, #37, writes; its sheet names and labels are imported from excel.py):
- Sheets: "Actions", "Risks & Issues" (also read as "Risks and issues" or "RAID"), "Decisions", "Milestones", "Use cases". Sheets are
  matched by name, never by position, in any case and with any spacing. A sheet that is missing is not compared, so nothing in its table is staged as removed. The old and the new names are both
  read (#143): the sheet "Risks & Issues", "Risks and issues" or "RAID"; the headers "Client messaging" or "Client wording", "Baseline" or "Agreed".
  Two sheets or two columns that mean the same thing refuse the whole workbook, in words.
- Row 1 is the header. A header is the export's label for the column (excel.COLUMN_OF: Agreed, Achieved on, % complete, Client
  wording, State set by you ...), or a database column name (schema.sql, as `store.columns()` lists them): id, project, description,
  due_date and so on; case, spaces and hyphens do not matter ("Due date" reads as due_date). "Labels" is read too, on actions,
  RAID items and decisions. The export's worked-out columns (Original, Shown state) are never read. A column the table does not
  have is ignored and said so. A column that is absent is not compared; a column that is present but blank is a cleared value. The id
  column must be there, or the sheet is skipped and reported.
- Dates are real Excel dates, shown DD-MM-YYYY. Text dates DD-MM-YYYY (or with / or .) and YYYY-MM-DD are read too (YYYY-MM-DD
  may be followed by a space or T and a time, HH:MM, HH:MM:SS or with a fraction, and nothing else).
  Yes/No (or 1/0) for client_visible, active and state_set.
- Columns the import never changes: id, project, source, updated_at, archived, closed, state_set, and a RAID item's priority.
  The writer works these out (state_set follows from State). `updated_at` is used only to spot a clash.

THE EXPORT'S RECORD (excel.STATE_FILE, beside clark.db; read with excel.load_state):
- It holds, per workbook, the SHA-256 of what the export wrote ("hash"), of what was last imported ("imported_hash"), and a
  snapshot of every row as it was exported ("rows": {table: {id: row}}). The import uses all three:
  * the same file again (its hash is imported_hash) is not read at all: "already imported", no changes staged, but ONLY while
    the step that imported it is still in force (see UNDO AND RESTORE below);
  * a row that changed in clark since the export is a clash, and only the cells the person edited (those that differ from the
    snapshot) are staged; what is newer in clark is left alone and listed;
  * a row in the database that was not in the export (added in clark afterwards, or by an earlier import) is never "removed from
    the workbook": the workbook could not have held it;
  * a row with no id that an earlier import already made is not made again (see NEW ROWS ARE NOT MADE TWICE below).
- The record is found by the export id inside the workbook (excel.load_state): each export writes a random id into the
  workbook's custom properties (never a cell or the Cover) and keeps its record under that id and the project. So the exported
  file finds its record from any folder, and still after it was edited, sorted or opened and saved again, and an import of it
  writes back to that same record (excel.mark_imported). Only an unrecorded file loses it: a workbook with no id (exported
  before ids, or another program's file) is found by its path, or by its SHA-256 only while it is exactly what clark wrote; a
  program that rewrites the file without its custom properties drops the id, and then nothing finds the record (fails safe).
  An id that is not a random UUID as 32 hex digits is ignored, never looked up.
- A record that names another project is no record: an id is looked up under the project being imported only, so a workbook of
  project A carrying B's id (copied, or forged) finds nothing, and a byte-identical workbook exported from A and imported into B
  is passed over too; read_workbook treats the workbook as unrecorded for B.
- A workbook with no export record (not written by an export from this store, or saved again or edited since) is "unrecorded": creaite refuses it; clark
  reads it and stages it, but accept_all accepts nothing and apply_import refuses until the person confirms it
  (read_workbook(..., allow_unrecorded=True) or plan.confirm_unrecorded()). Without a snapshot the database is what it is
  compared with, every difference is staged, and a clash says so.
- Formulas are never read: a cell typed as a formula is left out of the comparison (not taken as blank) and a note names the sheet and rows.
- A file bigger than excel's limits (excel.check_workbook_size) is refused before it is opened.

HOW A ROW IS READ:
- A row with an id is matched to the database row of that id. A row with no id is new (clark gives it its id). An id that is not
  in this project, is the wrong shape for its sheet, or is not in the database is reported and left out; the same for a second row
  with the same id.
- Blank cell, database has a value: a change to empty if the column can be empty; for a column that must hold text but whose
  default is empty (client_message, headline ...) the change is to ''; for any other column (owner, status, raised ...) it is a
  reported problem, never a change. Blank cell and nothing in the database is no change.
- A row in the database for the project, in the export, but missing from the workbook is staged as "removed from the workbook". Nothing is
  deleted (#126, BRD FR-43c), so applying it archives the item: it is hidden, its status is unchanged and Undo or Restore
  brings it back. Only an open item is staged; items that are already finished (Closed, Cancelled, Withdrawn, Done) are left alone. Use cases have no closed state, so one missing from the workbook is only mentioned in the notes. accept_all never
  accepts these (it could be the wrong file or a deleted row by mistake): each is accepted by number, plan.accept(n), and the
  report says how many are waiting.
- A milestone's agreed date (baseline_date) is never changed by an import: moving it is a rebaseline that records a decision.
  The change is dropped and a note says so (creaite excel_sync.cmd_import).

NEW ROWS ARE NOT MADE TWICE: when an import creates rows (rows with no id), the same record keeps, per workbook ("created"), a
fingerprint of each one and the id clark gave it. The fingerprint is a SHA-256 over the row as the importer reads it (the table
and every importable cell value after normalising, sorted by column name; never the workbook's file hash), so it survives
Excel saving the same content as different bytes, or a copy of the workbook. A later read of a no-id row with a recorded
fingerprint does not stage it: it is left as it is, with a note ("Already imported as ABC-A-004: left as it is.") and counted in
plan.already_created. Rules:
  * the fingerprints are written only after the step has committed, in the same save as mark_imported (or, if the file was saved
    again after it was read, on their own); a refused or rolled-back import records none; only the rows actually accepted and made;
  * each recorded fingerprint covers ONE row: two identical no-id rows in one import are both made (and recorded twice); a later
    read lets as many identical rows go as were made, and stages any extra one as new;
  * editing a pending new row in the workbook after it was imported changes its fingerprint, so it is a different new row and is
    staged as new (the earlier one stays in clark: change it there);
  * a fingerprint counts only while the step that made its row is in force (UNDO AND RESTORE below): after an Undo of the import,
    the same unchanged workbook makes those rows again; a fresh export starts a new record anyway;
  * the list is capped at excel.MAX_CREATED (5000) per workbook, the oldest dropped.

UNDO AND RESTORE: the state file outlives the database's steps, so the record keeps, with "imported_hash" and with each
fingerprint, a stamp of the step that did it: its apply_id, the database's meta.db_id and the step's `at` time. A stamp is in
force only if the database has that step (an applies row with the same id and time, in a database with that db_id) and not all of
its changes (for a fingerprint: its row's creation) have been put back by an Undo that is itself still in force. After an Undo,
or in a database restored from an older copy, the same unchanged workbook is read in full again and can be imported. A record
without a stamp (written before this rule) is taken as in force. Reads the store's `meta` and `applies` rows (read only; the
store has no call for db_id) and uses store.reverted_rowids.

DEPARTURES FROM CREAITE (also in the reuse record): it compares a row with the database, and only a clash is compared with
the export snapshot (creaite diffs every row against the snapshot); it reads a workbook with no export record, only after a
confirmation (creaite refuses); it short-circuits the same file only by hash, as creaite does, but a row added in clark since the
export is never "removed"; the whole import is one step (creaite saves per item); a missing item is archived, not closed (#126).

STAGING: the database's `staged_changes` table belongs to the team and client change files (it needs a change_files row) and the
store has no calls for it, so the import's staged changes are kept in memory, in an ImportPlan. States are those of that table:
'clean', 'clash' (the row changed in clark after the workbook was made: its updated_at cell differs), 'accepted', 'rejected'.
Rows with no difference are counted as unchanged ('same'). Nothing is applied until it is accepted.

AFTER APPLYING: the workbook is recorded as imported (excel.mark_imported), so the next export may overwrite it; the export refuses
while a workbook has edits that were never imported. Not recorded if nothing was applied, or the file was saved again after the
plan read it.

APPLYING (the half-apply design): every accepted change goes into ONE step. Each is tried; if any breaks a rule, all the broken
ones are reported together (naming the id and the field) and the step is rolled back, so nothing at all is applied. Chosen
because Store.step rolls the whole step back on any error, so one Undo always reverses exactly one import, and because a
workbook with one bad row is more likely wrong than half right. The person rejects or fixes the bad row and imports again.
"""
import hashlib
import json
import re
import sqlite3
import unicodedata
import zipfile
import zlib
from html import unescape
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from pathlib import Path

from openpyxl import load_workbook

from clark import backup, excel, sanitise
from clark import store as writer
from clark.store import Invalid

# The sheet names and header labels are the export's own (excel.SHEET_OF, excel.COLUMN_OF), so the two cannot drift apart.
SHEET_NAMES = dict(excel.SHEET_OF)                                  # table → the sheet the export writes
SHEET_TABLES = {name.lower(): table for table, name in SHEET_NAMES.items()}     # sheet name (lower case) → table
SHEET_TABLES["risks and issues"] = "raid"          # the earlier name of the sheet (now "Risks & Issues"); still read (#143)
SHEET_TABLES["raid"] = "raid"                      # the oldest name, written out so workbooks exported before the rename still import (#143)
# Header names the export has used or will use (#143): the old and the new read as the same column. They are written out here
# and not taken from excel.COLUMN_OF, so a rename in the export can never stop an older workbook from importing.
HEADER_ALIASES = {"client messaging": "client_message", "client wording": "client_message",
                  "baseline": "baseline_date", "agreed": "baseline_date"}
TABLE_ORDER = ("milestones", "use_cases", "actions", "raid", "decisions")     # the order changes are written in
GANTT = "gantt_lines"          # row 926: the Gantt sheet (named for the project's Gantt tab, else 'Gantt'); read by gantt_sheet(), not by the generic reader
WRITE_ORDER = TABLE_ORDER + (GANTT,)                                         # the Gantt lines are written after the rest
GANTT_HEADERS = {label.lower(): f for label, f in excel.GANTT_SHEET_COLUMNS}      # the export's own labels (Days and Status are worked out: never read)
GANTT_TEXT = {"name": 200, "owner": 200, "workstream": 200, "deliverable": 500, "note": 2000}     # the data layer's limits (store.GANTT_TEXT_LIMITS)
WORDS = {"actions": "action", "raid": "RAID item", "decisions": "decision", "milestones": "milestone",
         "use_cases": "use case", GANTT: "line"}
LOCKED = {"id", "project", "source", "updated_at", "archived", "closed", "state_set"}
LOCKED_IN = {"raid": {"priority"}}                       # worked out from impact and likelihood
LABELS = "labels"      # not a column: an item's labels, as the export writes them (comma-separated); the store keeps them apart
UC_MILESTONES = "milestones"      # row 1107: not a use_cases column: the milestones a use case is linked to directly, as ids ('ID, ID'); the store keeps them in use_case_milestones
FLAGS = {"client_visible", "state_set", "active"}
# what applying "removed from the workbook" does (#126: nothing is deleted or closed; the row is archived, status unchanged)
REMOVED_BY = {"actions": "archived", "raid": "archived", "decisions": "archived", "milestones": "archived"}
FINISHED = {"actions": ("Closed", "Cancelled"), "raid": ("Closed", "Cancelled"), "decisions": ("Withdrawn",),
            "milestones": ("Done", "Cancelled")}
NOT_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff￾￿]")   # (creaite excel_sync.NOT_XML)
A_WORD = {"actions": "an action", "raid": "a RAID item", "decisions": "a decision", "milestones": "a milestone",
          "use_cases": "a use case", GANTT: "a line"}
# RICH TEXT: fields that hold HTML (schema.sql "-- HTML"; docs: the editor writes it, publish.clean_html cleans it on output):
# use_cases.standing is the only one the workbook carries ("Where it stands"); projects.current_state is HTML too but is not in
# the workbook. The import writes what the cell holds, so this is the write-side seam.
RICH_FIELDS = {"standing"}
TITLE_OF = {"actions": "description", "raid": "description", "decisions": "decision", "milestones": "name",
            "use_cases": "title", GANTT: "name"}                  # the column that says what an item is (a row's "other values" are matched on it)
MAX_SHEET_ROWS, MAX_SHEET_COLUMNS = 5000, 100        # the area a sheet may span, empty cells included: checked before any cell is built
MAX_SHEET_CELLS, MAX_TOTAL_CELLS = 200000, 400000     # rows times columns, empty cells included: one sheet, and all the sheets read together
MAX_TEXT = 10000                                    # characters in one text cell; a longer one is refused (a hostile file can hold megabytes)
MAX_ROWS = 2000                                     # rows with something in them, per sheet; a bigger sheet is refused whole
OVER_LIMIT = MAX_ROWS + 1                           # what list_sheets gives a sheet read_workbook would refuse: the page says "more than 2,000 rows"


def clean_rich(field, text):
    """
    is staged or compared. A no-op today: the text is stored as typed, and publishing cleans it on output (publish.clean_html).
    Once #66a merges, call its cleaner here and nowhere else. Do not write a sanitiser in this file."""
    return text


_FORMULA = object()        # a cell typed as a formula: not read (it is neither blank nor a value)


def virtual_columns(table):
    """The columns of a sheet that are not columns of its table: labels (actions, risks, decisions) and a use case's direct milestones."""
    return [LABELS] if table in writer.LABELLED else [UC_MILESTONES] if table == "use_cases" else []


def milestone_ids(text, refs=None):
    """(ids, bad): a Linked milestones cell as the sorted, distinct milestone ids it names. The export writes one 'ID: name' per line (item 1150 left this column as it was);
    a line with no ': ' may hold several ids split by commas. `bad` is the first piece that is not a milestone id."""
    found, bad = set(), ""
    for line in str(text).replace("\r", "\n").split("\n"):
        if not line.strip():
            continue
        head = resolve_ref("milestone", line, refs)
        pieces = [head] if (": " in line or "," not in line) else [p.strip() for p in line.split(",") if p.strip()]
        for piece in pieces:
            m = writer.ITEM_ID.fullmatch(piece)
            if m and m.group(2) == "M":
                found.add(piece)
            elif not bad:
                bad = piece
    return sorted(found), bad


def _label(table, f):
    """A column as the person sees it: the export's header label (Due, Agreed, Client wording ...)."""
    for label, field_ in (excel.COLUMN_OF.get(table, {}).items() if table != GANTT else ((l, g) for l, g in excel.GANTT_SHEET_COLUMNS)):
        if field_ == f:
            return label
    return f.replace("_", " ").capitalize()


def plain(table, msg):
    """The store's refusal in the words of the workbook's own column headings (no field names, no raw timestamps)."""
    m = re.fullmatch(r"missing required field\(s\): (.+)", msg)
    if m:
        names = [_label(table, f.strip()) for f in m.group(1).split(",")]
        return (names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]) + (" is needed" if len(names) == 1 else " are needed")
    m = re.fullmatch(r"unknown label (.+?) (\(labels: .*)", msg, re.S)
    if m:
        return f"There is no label {m.group(1)} {m.group(2)}"
    m = re.match(r"([a-z_]+) (must be|is not) ", msg)
    if m and m.group(1) == "review_after_days":
        msg = "Not reviewed after (days)" + msg[len(m.group(1)):]
    elif m and m.group(1) in excel.COLUMN_OF.get(table, {}).values():
        msg = _label(table, m.group(1)) + msg[len(m.group(1)):]
    m = re.fullmatch(r"(.*) \(got (.*)\)", msg, re.S)
    if m:
        cell = m.group(2)
        if len(cell) >= 2 and cell[0] == cell[-1] and cell[0] in "'\"":
            cell = cell[1:-1]
        msg = f"{m.group(1)} (the cell says {cell})"
    return re.sub(r"\b(\d{4})-(\d{2})-(\d{2}) 00:00:00\b", lambda x: f"{x.group(3)}-{x.group(2)}-{x.group(1)}", msg)


def _names(table, fields):
    return ", ".join(_label(table, f) for f in fields) or "nothing"


def _short(text, n=40):
    """`text` clean (no control or direction characters) and at most `n` characters, for echoing something a cell holds."""
    t = " ".join(_clean(text).split())
    return (t[:n].rstrip() + "...") if len(t) > n else t


def _got(value):
    """A cell's value as a person would say it, for 'got ...' (dates as DD-MM-YYYY, long text cut short)."""
    if isinstance(value, datetime):
        return writer.shown(value.date().isoformat()) + (value.strftime(" %H:%M") if value.hour or value.minute else "")
    if isinstance(value, date):
        return writer.shown(value.isoformat())
    if isinstance(value, time):
        return value.strftime("%H:%M")
    return repr(_short(value, 60)) if isinstance(value, str) else repr(value)


def _shown(f, v):
    if v is None or v == "":
        return "empty"
    if f == "show":
        return "Yes" if v else "No"
    return writer.shown(v) if f in writer.DATE_FIELDS else _short(v, 120)


@dataclass
class Problem:
    """Something in the workbook that is reported and not imported."""
    message: str
    sheet: str = ""
    row: int = 0              # the workbook row (1 = the header); 0 when it is about the whole sheet
    id: str = ""
    field: str = ""

    def __str__(self):
        return self.message


def _clean(text):
    """`text` without control and direction-changing characters (they could make a plan line read differently from what it says)."""
    return "".join(ch for ch in str(text) if unicodedata.category(ch) not in ("Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"))


def _title_of(c):
    t = " ".join(_clean(c.after.get(TITLE_OF[c.table]) or "").split())
    return (t[:80].rstrip() + "...") if len(t) > 80 else (t or f"{A_WORD[c.table]} with no title")


@dataclass
class StagedChange:
    """One difference between the workbook and the database, waiting for a decision."""
    n: int
    kind: str                 # 'new' | 'changed' | 'removed'
    table: str
    sheet: str
    row: int                  # workbook row
    id: str = ""              # the database id (empty for a new row)
    before: dict = field(default_factory=dict)     # changed: field → the database value
    after: dict = field(default_factory=dict)      # changed: field → the workbook value; new: all the values given
    state: str = "clean"      # 'clean' | 'clash' | 'accepted' | 'rejected'
    clash: bool = False       # the row changed in clark after the workbook was made
    kept: dict = field(default_factory=dict)       # clash: field → the newer value in clark that is left alone (the person did not edit it)
    from_snapshot: bool = False                    # clash: only the person's own edits are staged (the export's record was there)
    problem: str = ""         # why the writer would refuse it (found when staged; checked again when applied)
    seen_at: str = ""         # the database row's updated_at when staged
    fp: str = ""              # new: the row's fingerprint (fingerprint()), recorded once the row has been made
    preview: str = ""         # new: the ID it would get if the plan were applied as it stands (the real one is given at apply)
    typed: str = ""           # a new Gantt line: the id its row carried (not taken: the lines that name it in Parent or Depends on get the real one)

    @property
    def label(self):
        if self.table == GANTT:             # row 926: the row is said with every Gantt line, as the refusal is read beside the workbook
            return f"{self.id or 'new line'} (row {self.row} of {self.sheet})"
        return self.id or f"new {WORDS[self.table]} (row {self.row} of {self.sheet})"

    def detail(self):
        """A new row's other values in plain words (the plan's second line for it)."""
        return "; ".join(f"{_label(self.table, f)} {_shown(f, v)}" for f, v in self.after.items()
                         if f not in ("source", TITLE_OF[self.table]))

    def describe(self):
        """The change in plain words, dates as DD-MM-YYYY."""
        if self.kind == "removed":
            return (f"{self.id}: No longer in the workbook. Accepting this archives it: it is hidden, not deleted. Undo brings it back.")
        if self.kind == "new":
            where = f" (row {self.row} of {self.sheet})" if self.table == GANTT else ""
            return f"New: {_title_of(self)}{where} → {self.preview or 'a new ID'}"
        return f"{self.label}: " + "; ".join(f"{_label(self.table, f)} {_shown(f, self.before.get(f))} -> {_shown(f, v)}"
                                          for f, v in self.after.items())


@dataclass
class ImportResult:
    applied: bool
    step_id: object = None            # the step to hand to Store.undo, or None if nothing was written
    counts: dict = field(default_factory=lambda: {"new": 0, "changed": 0, "removed": 0})
    problems: list = field(default_factory=list)
    message: str = ""
    marked: bool = False              # the workbook was recorded as imported, so the export may overwrite it
    created: list = field(default_factory=list)    # [{"fp", "id"}] for each new row made (recorded in the export's record)


@dataclass
class ImportPlan:
    """What the workbook differs by: staged changes, the rows that were reported, and notes. Decide with accept / reject."""
    file: str
    project: str
    changes: list = field(default_factory=list)
    problems: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    unchanged: int = 0
    already_created: int = 0          # rows with no id that an earlier import made from this content: left as they are
    path: str = ""                    # the workbook's full path
    file_hash: object = None          # its SHA-256 when it was read (excel.file_hash)
    state_path: object = None         # the export's record that was used (apply_import records the import there)
    already_imported: bool = False    # this very file was imported before: nothing is staged
    partial: bool = False             # only some of the workbook's sheets were read (#655): it is never marked as imported as a whole
    unrecorded: bool = False          # no export record of this workbook: accept_all accepts nothing, apply_import refuses...
    unrecorded_ok: bool = False       # ...until the person has confirmed it (confirm_unrecorded)
    store: object = field(default=None, repr=False)     # read only: to work out the IDs new rows would get

    def refresh_ids(self):
        """Work out, for each new row still wanted, the ID it gets if the plan is applied as it stands: row order within each
        type, in the order the import writes them, from the store's own next free number (so an archived or undone item's number is
        never reused). A row left out gets none. A type that has run out of numbers leaves its rows without one."""
        for c in self.changes:
            c.preview = ""
        if self.store is None:
            return
        nxt = {}
        for c in self.changes:
            if c.kind != "new" or c.state == "rejected" or c.problem:
                continue
            group = "shared" if c.table in writer.SHARED_NUMBERS else c.table
            if group not in nxt:
                try:
                    nxt[group] = int(writer.next_id(self.store.con, c.table, self.project)[-3:])
                except Invalid:
                    nxt[group] = 1000
            n = nxt[group]
            nxt[group] = n + 1
            if n <= 999:
                c.preview = f"{self.project}{writer.ID_PREFIX[c.table]}{n:03d}"

    def get(self, n):
        for c in self.changes:
            if c.n == n:
                return c
        raise Invalid(f"There is no staged change {n}.")

    def confirm_unrecorded(self):
        """The person says: yes, import this workbook though clark has no record of exporting it."""
        self.unrecorded_ok = True

    def accept(self, *numbers):
        for n in numbers:
            self.get(n).state = "accepted"
        self.refresh_ids()

    def reject(self, *numbers):
        for n in numbers:
            self.get(n).state = "rejected"
        self.refresh_ids()

    def accept_all(self):
        """Accept every new and changed row that has no problem and no clash; a clash or a problem has to be accepted by number,
        and so does every "removed from the workbook" row (accept(n) archives that one item): a row that is only missing from
        the workbook is easily a mistake, so it is never accepted in bulk. A workbook with no export record accepts nothing
        until confirm_unrecorded()."""
        if self.unrecorded and not self.unrecorded_ok:
            return
        for c in self.changes:
            if not c.problem and not c.clash and c.kind != "removed":
                c.state = "accepted"
        self.refresh_ids()

    def reject_all(self):
        for c in self.changes:
            c.state = "rejected"
        self.refresh_ids()

    def accepted(self):
        return [c for c in self.changes if c.state == "accepted"]

    def counts(self, changes=None):
        changes = self.changes if changes is None else changes
        return {k: sum(c.kind == k for c in changes) for k in ("new", "changed", "removed")}

    def report(self):
        """The whole plan as plain lines, for a person to read before deciding."""
        k = self.counts()
        out = [f"{self.file} into {self.project}: {k['new']} new, {k['changed']} changed, {k['removed']} no longer in the "
               f"workbook, {self.unchanged} unchanged, "
               + (f"{self.already_created} already imported as new rows, " if self.already_created else "")
               + f"{len(self.problems)} reported."]
        if k["removed"]:
            out.append(f"  {k['removed']} {'row is' if k['removed'] == 1 else 'rows are'} no longer in the workbook. Accept each one to "
                       "archive it (nothing is deleted); Accept all leaves them alone.")
        if self.unrecorded and not self.unrecorded_ok:
            out.append("  There is no record of exporting this workbook from clark, so nothing is accepted for you and it will not be "
                       "applied until you confirm it.")
        for c in self.changes:
            tag = ""
            if c.clash:
                if c.from_snapshot:
                    left = "; ".join(f"{_label(c.table, f)} (now {_shown(f, v)})" for f, v in c.kept.items())
                    tag = (f" [changed in clark since the workbook was made. You edited {_names(c.table, c.after)}."
                           + (f" Newer in clark and left alone: {left}.]" if left else "]"))
                else:
                    tag = (" [changed in clark since the workbook was made. clark has no record of what you edited, so this lists "
                           "every field that differs, including ones you did not edit: applying it puts the workbook's values back]")
            bad = f" [would be refused: {c.problem}]" if c.problem else ""
            out.append(f"  {c.n}. {c.state}: {c.describe()}{tag}{bad}")
            if c.kind == "new" and c.detail():
                out.append(f"       {c.detail()}")
        out += [f"  Not imported: {p.message}" for p in self.problems]
        out += [f"  Note: {n}" for n in self.notes]
        return "\n".join(out)


# ── Reading cells ─────────────────────────────────────────────────────────────

def _key(header):
    return re.sub(r"[\s\-]+", "_", str(header).strip().lower())


def cell_text(value):
    """A value without the characters a workbook can't hold (creaite excel_sync.cell_text)."""
    if not isinstance(value, str):
        return value
    return NOT_XML.sub(lambda m: " " if m.group() in "\x0b\x0c\x1c\x1d\x1e" else "", value)


def same(a, b):
    """Equal once blanks and trailing spaces are ignored (creaite excel_sync.same, without the labels case)."""
    def norm(x):
        x = cell_text(x)
        return None if x is None or str(x).strip() == "" else "\n".join(line.rstrip() for line in str(x).rstrip().splitlines())
    return norm(a) == norm(b)


def read_date(value):
    """A date cell as YYYY-MM-DD: a real Excel date, DD-MM-YYYY text (also / or .), or YYYY-MM-DD text. Raises ValueError."""
    if isinstance(value, date):
        if (value.date() if isinstance(value, datetime) else value) < date(1900, 3, 1):
            raise ValueError(value)        # Excel's day 60 (a 29 February 1900 that never was) reads as 28 February, and a negative day as 1899: neither is a date
        return value.isoformat()[:10]
    s = str(value).strip()
    if not s.isascii():                      # \d also takes other scripts' digits; refuse them like check_id does
        raise ValueError(s)
    m = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", s)
    if m:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?)?", s)
    if m:
        h, mi, sec = (int(x or 0) for x in m.group(4, 5, 6))
        if h > 23 or mi > 59 or sec > 59:
            raise ValueError(s)
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    raise ValueError(s)


REF_FIELDS = ("milestone", "use_case")


class RefClash(ValueError):
    """Item 1150: a Milestone or Use case cell's text matches more than one item."""
    def __init__(self, kind, text, names):
        super().__init__(text)
        self.kind, self.text, self.names = kind, text, names


def _ref_key(text):
    return " ".join(str(text or "").split()).casefold()


class RefLookup:
    """Item 1150: finds the milestone or use case a cell's text names, now that the drop-downs carry no id. `items` is
    {"milestone": [row, ...], "use_case": [row, ...]} (rows with id, name or title, and a use case's ref); `then` is the same for the
    rows as the export held them, so a cell written before an item was renamed still finds it. A use case is found by the text the
    export shows ('UC 1.5 Title'), then by its reference, then by its title; a milestone by the text shown, then its name. The first
    of those that matches anything decides: one item is the answer, more than one is a RefClash (never a guess), none is None."""
    def __init__(self, items, then=None):
        self.tiers, self.rows = {}, {}
        for field, (_, nf) in excel.REF_TABLES.items():
            rows = list(items.get(field, ()))
            self.rows[field] = {r["id"]: r for r in rows}
            old = [r for r in (then or {}).get(field, ()) if r["id"] in self.rows[field]]      # an item still here, as the export held it
            self.tiers[field] = [(r["id"], self._keys(field, nf, r)) for r in rows + old]

    @staticmethod
    def _keys(field, nf, r):
        if field == "use_case":
            ref = r.get("ref")
            return [_ref_key(excel.ref_text(r["id"], r.get(nf), ref)), _ref_key(ref), _ref_key(r.get(nf))]
        return [_ref_key(excel.ref_text(r["id"], r.get(nf))), _ref_key(r.get(nf)), ""]

    def shown(self, field, item_id):
        r = self.rows[field].get(item_id) or {}
        return excel.ref_text(item_id, r.get(excel.REF_TABLES[field][1]), r.get("ref") if field == "use_case" else None)

    def names(self, field, item_id, text):
        """Whether `text` is the text the export shows for this item (now, or as the export held it)."""
        key = _ref_key(text)
        return any(i == item_id and key and key in keys[:2 if field == "milestone" else 3] for i, keys in self.tiers.get(field, ()))

    def find(self, field, text, own=()):
        key = _ref_key(text)
        for i in own:                                  # a cell that still shows the item the row has is no change, whoever else shares the name
            if self.names(field, i, text):
                return i
        for n in range(3):
            hits = []
            for item_id, keys in self.tiers.get(field, ()):
                if keys[n] and keys[n] == key and item_id not in hits:
                    hits.append(item_id)
            if len(hits) == 1:
                return hits[0]
            if hits:
                names = []
                for i in hits:
                    t = self.shown(field, i)
                    if t not in names:
                        names.append(t)
                raise RefClash("use case" if field == "use_case" else "milestone", " ".join(str(text).split()), names)
        return None


def resolve_ref(field, text, refs=None, own=()):
    """A Milestone or Use case cell as the id it names. An older export wrote 'ID: name' (item 710): if the text holds ': ' and what
    comes before the first ': ' is an item id, that is the id (the name after it is only a label, so
    a renamed milestone still resolves and is no change). A bare id is also fine. Otherwise (item 1150) `refs`, a RefLookup, finds
    the item by the text the export shows (first the item the row already has, `own`); text matching nothing stays as it is and the
    store refuses it as it always did; text matching more than one item raises RefClash. A name that itself contains ': ' is fine:
    only an id before the first one counts."""
    text = text.strip()
    head, sep, _ = text.partition(": ")
    if sep and writer.ITEM_ID.fullmatch(head.strip()):
        return head.strip()
    if refs is not None and not writer.ITEM_ID.fullmatch(text):
        found = refs.find(field, text, own)
        if found:
            return found
    return text


OLD_COMMITMENT = "Candidate"                                    # row 1061: the word the flag had before Planned 2026


def from_cell(name, value, kind, label=None, stored=(), table=None, refs=None):
    """(stored value, None) or (None, why not); see _from_cell. `refs` (a RefLookup) lets a Milestone or Use case cell be read by its
    name (item 1150); a name that matches more than one item is refused, naming the clash."""
    try:
        return _from_cell(name, value, kind, label, stored, table, refs)
    except RefClash as e:
        return None, f"{label or name}: {e.text} matches more than one {e.kind} ({', '.join(e.names)}). Pick one from the list."


def _from_cell(name, value, kind, label=None, stored=(), table=None, refs=None):
    """(stored value, None) or (None, why not). A blank cell is (None, None). (creaite excel_sync.from_cell: dates to
    YYYY-MM-DD, Yes/No to 1/0, blank to None; departure: it refuses what it can't read instead of passing it on.) `label` is
    the column's name as the person sees it, for the reason given; it defaults to `name`. `stored` is what the item holds now
    (and held at the export): a long text that is that text, or that text cut to what Excel keeps, is not a change, so it is not
    refused and comes back as the stored text."""
    label = label or name
    if value is None or (isinstance(value, str) and not value.strip()):
        return None, None
    if isinstance(value, str) and len(value) > MAX_TEXT:
        for old in stored:
            if isinstance(old, str) and value in (old, excel.cell_text(old), excel.cell_text(old)[:MAX_CELL_TEXT]):
                return old, None
        return None, f"{label} is too long ({len(value):,} characters; the most clark will take is {MAX_TEXT:,})"
    if name in writer.DATE_FIELDS:
        try:
            return read_date(value), None
        except (ValueError, OverflowError):
            return None, f"{label} must be a date, shown DD-MM-YYYY (got {_got(value)})"
    if name == UC_MILESTONES:                                   # row 1107: the ids, in the one form the export keeps ('ID, ID')
        ids, bad = milestone_ids(value)
        if bad:
            return None, f"{label} must be milestone IDs, one per line (got {_got(bad)})"
        return ", ".join(ids) or None, None
    if name == "commitment":                                    # #709: the owner's words, case exact (spaces round the word are not part of it); never guessed
        word = str(value).strip()
        if word == OLD_COMMITMENT:                              # row 1061: a workbook exported before the rename still says Candidate; it is Planned 2026 (exact word only)
            word = writer.COMMITMENTS[0]
        if word in writer.COMMITMENTS:
            return word, None
        return None, f"{label} must be one of {', '.join(writer.COMMITMENTS[:-1])} or {writer.COMMITMENTS[-1]}, or left empty (got {_got(value)})"
    if name in FLAGS:
        s = str(value).strip().lower()
        if s in ("yes", "y", "1", "true", "1.0"):
            return 1, None
        if s in ("no", "n", "0", "false", "0.0"):
            return 0, None
        return None, f"{label} must be Yes or No (got {_got(value)})"
    if kind.upper() == "INTEGER":
        if isinstance(value, bool):
            return None, f"{label} must be a whole number (got {_got(value)})"
        if isinstance(value, float) and value.is_integer():
            return int(value), None
        if isinstance(value, int):
            return value, None
        if isinstance(value, str) and re.fullmatch(r"-?\d+", value.strip()):
            return int(value.strip()), None
        return None, f"{label} must be a whole number (got {_got(value)})"
    if isinstance(value, float) and value.is_integer():
        return str(int(value)), None
    if isinstance(value, (datetime, date)):
        return None, f"{label} is text, but the cell holds a date ({_got(value)})"
    text = excel.unescape_text(str(cell_text(value)))
    if table == "use_cases" and name == "owner":                # row 875: the change route's checks on a use case's owner (plain one line, 200 characters)
        from clark import changes
        if not changes._plain_text(text) or len(unicodedata.normalize("NFC", text).strip()) > changes.UC_OWNER_LIMIT:
            return None, f"{label} must be plain text of at most {changes.UC_OWNER_LIMIT} characters, with no hidden characters"
    if table == "use_cases" and name == "ref":                  # the change route's checks on a use case's "Shown as": plain, 1 to 20 characters
        from clark import changes
        shown = unicodedata.normalize("NFC", text).strip()
        if text.strip() and (not changes._plain_text(shown) or len(shown) > changes.UC_REF_LIMIT):
            return None, f"{label} must be plain text of at most {changes.UC_REF_LIMIT} characters, with no hidden characters"
    if name in REF_FIELDS:
        text = resolve_ref(name, text, refs, [x for x in stored if isinstance(x, str)])
    return (clean_rich(name, text) if name in RICH_FIELDS else text), None      # as typed: no strip (spaces round-trip); undo #37's apostrophe


_QUIET = ("note", "updated_at")      # change_log fields that are history only: an Undo does not put them back


def _db_id(store):
    row = store.con.execute("SELECT v FROM meta WHERE k = 'db_id'").fetchone()
    return row[0] if row else None


def stamp_of(store, apply_id, db_id=None):
    """{"step", "db_id", "at"} for step `apply_id`: what the record keeps to tell later whether that step is still in force."""
    row = store.con.execute("SELECT at FROM applies WHERE apply_id = ?", (apply_id,)).fetchone()
    return {"step": apply_id, "db_id": db_id or _db_id(store), "at": row[0] if row else None}


def in_force(store, stamp, item=None, db_id=None):
    """Whether the step in `stamp` ({"step", "db_id", "at"}) is still in force in this database: it has that step (same id and
    time, same db_id) and some change it made (for `item`: the creation of that row) has not been put back by an Undo that is
    itself in force. No stamp (a record from before this rule): True."""
    if not stamp or stamp.get("step") is None:
        return True
    con = store.con
    if stamp.get("db_id") != (db_id or _db_id(store)):
        return False
    row = con.execute("SELECT at FROM applies WHERE apply_id = ?", (stamp["step"],)).fetchone()
    if row is None or row[0] != stamp.get("at"):
        return False
    if item is None:
        rows = con.execute("SELECT rowid, field FROM change_log WHERE apply_id = ?", (stamp["step"],)).fetchall()
    else:
        rows = con.execute("SELECT rowid, field FROM change_log WHERE apply_id = ? AND item_id = ? AND op = 'insert'",
                           (stamp["step"], item)).fetchall()
    reverted = writer.reverted_rowids(con)
    return any(r[1] not in _QUIET and r[0] not in reverted for r in rows)


def fingerprint(table, values):
    """SHA-256 of a new row's content: the table and the importable cell values as the importer reads them (blank cells left
    out), sorted by column name. Not the workbook's file hash, so the same content saved again gives the same fingerprint."""
    canon = json.dumps([table, sorted((k, v) for k, v in values.items())], ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _title_key(v):
    """A title as compared between rows: blanks collapsed, case ignored."""
    return " ".join(str(v or "").split()).casefold()


def _six_digit_fraction(text):
    """Python 3.9's fromisoformat takes a fraction of exactly 3 or 6 digits (3.11 takes any): pad or cut the fraction to 6."""
    return re.sub(r"(\d\d:\d\d:\d\d)\.(\d+)", lambda m: m.group(1) + "." + (m.group(2) + "000000")[:6], text, count=1)


def _naive(when):
    """A date-time with any timezone suffix taken to UTC and then dropped, so two of them can always be subtracted."""
    if when.tzinfo is not None:
        when = when.astimezone(timezone.utc).replace(tzinfo=None)
    return when


def _read_when(text):
    """Text as a naive date-time: a trailing Z or an offset is read and stripped. Raises ValueError when it is not a date-time."""
    text = text.strip().replace("T", " ")
    if text[-1:] in ("Z", "z"):
        text = text[:-1] + "+00:00"
    return _naive(datetime.fromisoformat(_six_digit_fraction(text)))


def _moved(cell, stored):
    """Whether an updated_at cell (an Excel date-time, or text) differs from the database's updated_at by more than the cell can
    hold: 2 milliseconds for a date-time, a second for text without a fraction. Unreadable text says nothing, so is no clash.
    A timezone suffix (Z or an offset) is read and dropped; this never raises."""
    try:
        if isinstance(cell, datetime):
            then, slack = _naive(cell), 0.002
        else:
            text = str(cell)
            then = _read_when(text)
            slack = 0.002 if "." in text else 1.0
        now = _read_when(str(stored))
        return abs((now - then).total_seconds()) > slack
    except (ValueError, TypeError, OverflowError):
        return False


# ── Reading the workbook ──────────────────────────────────────────────────────

_SCHEMA_INFO = {}


def _table_info(store, table):
    """{column: (type, not null, default)} for a table, read from schema.sql's own text (the writer is the only code that may
    build SQL, so this asks the schema file, not the database). The test checks it against store.columns()."""
    if not _SCHEMA_INFO:
        text = Path(writer.SCHEMA).read_text(encoding="utf-8")
        for m in re.finditer(r"TABLE IF NOT EXISTS (\w+) \((.*?)\n\);", text, re.S):
            cols = {}
            for line in m.group(2).splitlines():
                line = line.split("--")[0]
                c = re.match(r"\s{2}([a-z_]+)\s+(TEXT|INTEGER|REAL)\b(.*)", line)
                if c:
                    rest = c.group(3)
                    d = re.search(r"DEFAULT\s+('[^']*'|[^\s,]+)", rest)
                    cols[c.group(1)] = (c.group(2), "NOT NULL" in rest or "PRIMARY KEY" in rest, d.group(1) if d else None)
            _SCHEMA_INFO[m.group(1)] = cols
    return _SCHEMA_INFO[table]


def _is_blank_default(info):
    """A column that must hold text but whose default is empty: a cleared cell means ''."""
    return info[1] and info[2] in ("''", '""')


def _differs(v, old, f=""):
    """Whether a value (None for a blank cell) differs from a stored one, as the import sees it: blanks and trailing spaces
    are ignored, and labels are the same in any order or case."""
    if f == LABELS:
        return sorted(n.lower() for n in writer.label_names(v)) != sorted(n.lower() for n in writer.label_names(old))
    if v is None:
        return not (old is None or old == "")
    if old is None:
        return True
    return not (v == old or (isinstance(v, str) and same(v, old)))


def _gantt_blank(v):
    return v is None or (isinstance(v, str) and not v.strip())


def gantt_cell_value(f, v):
    """One Gantt sheet cell as the change route takes it (row 926). A blank is what the column holds when it is empty; a cell that
    cannot be read is passed on as it is, so the data layer refuses it in its own words. Dates become YYYY-MM-DD, Yes/No become 1/0
    (None: blank, the eye is left alone), a text is cleaned of the characters a workbook can't hold."""
    blank = _gantt_blank(v)
    if f == "show":
        if blank:
            return None
        s_ = str(v).strip().lower()
        return 1 if s_ in ("yes", "y", "1", "true", "1.0") else 0 if s_ in ("no", "n", "0", "false", "0.0") else str(v)
    if f in excel.GANTT_DATES:
        if blank:
            return None
        try:
            return read_date(v)
        except (ValueError, OverflowError):
            return v if isinstance(v, str) else str(v)
    if f == "pct":
        if blank:
            return 0
        if isinstance(v, float) and v.is_integer():
            return int(v)
        if isinstance(v, str) and re.fullmatch(r"\d{1,3}", v.strip()):
            return int(v.strip())
        return v
    if f in ("effort", "budget"):
        return None if blank else v
    if f == "parent":
        return None if blank else (v.strip() if isinstance(v, str) else v)
    if f == "type":
        return "" if blank else (v.strip().lower() if isinstance(v, str) else v)
    if f in ("health", "priority"):
        if blank:
            return ""
        if not isinstance(v, str):
            return v
        return next((a for a in writer.ALLOWED[(GANTT, f)] if a.lower() == v.strip().lower()), v.strip())
    if blank:
        return ""
    if f == "depends":
        return ",".join(writer.gantt_list(v if isinstance(v, str) else str(v)))
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return str(int(v)) if float(v).is_integer() else str(v)
    if isinstance(v, str):
        return excel.unescape_text(str(cell_text(v)))
    return v


def gantt_differs(f, new, old):
    """Whether a cell's value differs from the stored line's, as the data layer would store it (a text is compared after the data
    layer's own tidying; a text it would refuse always differs, so the check names it)."""
    if f in GANTT_TEXT:
        try:
            return writer.gantt_plain(new, GANTT_TEXT[f], writer.GANTT_NO_NAME if f == "name" else writer.GANTT_BAD_TEXT,
                                      blank_ok=f != "name", lines=f == "note") != (old or "")
        except Invalid:
            return True
    if f == "depends":
        return writer.gantt_list(new) != writer.gantt_list(old)
    if f in ("effort", "budget"):
        if new is None or old is None:
            return new is not old
        return not (isinstance(new, (int, float)) and not isinstance(new, bool) and float(new) == float(old))
    return new != old


class _Reader:
    def __init__(self, store, project, filename, record=None, created=()):
        self.store, self.project, self.filename = store, project, filename
        self.plan = ImportPlan(filename, project)
        self.n = 0
        self.today = writer.today()
        self.snapshot = (record or {}).get("rows") or {}     # the export's record of each row: {table: {id: row}}
        self._refs = None
        self.made = {}                                       # fingerprint → ids an earlier import made from it (used up as rows match)
        for c in created:
            self.made.setdefault(c.get("fp"), []).append(c.get("id"))
        self.fp_rows = {}                                    # fingerprint → the first workbook row that carried it
        self.held = set()                                    # items whose row was skipped for a changed ID: not "removed"
        self.given = {}                                      # a new row's change number → the values its cells gave (no defaults)
        self.formulas = {}                                   # sheet → workbook rows holding a formula cell
        self.errors = {}                                     # sheet → workbook rows holding an error cell in a column the import reads
        self.err_cols = {}                                   # (sheet, workbook row) → the column positions holding an error cell
        self.unplaced = set()                                # sheets with a row whose ID and title are both errors: no item can be told missing there

    @property
    def refs(self):
        """Item 1150: the RefLookup for this project's milestones and use cases (and the rows as the export held them)."""
        if self._refs is None:
            items = {f: self.store.read(t, project=self.project) for f, (t, _) in excel.REF_TABLES.items()}
            then = {f: [{**r, "id": i} for i, r in (self.snapshot.get(t) or {}).items()] for f, (t, _) in excel.REF_TABLES.items()}
            self._refs = RefLookup(items, then)
        return self._refs

    def rows_of(self, ws, min_row, cols=None):
        """(row number, [cell values]) for each row from `min_row`; a formula cell is _FORMULA (it is not read, and is noted). `cols` are the
        column positions the import reads: an error cell in any other column says nothing."""
        for rn, row in enumerate(ws.iter_rows(min_row=min_row), start=min_row):
            vals = []
            for k, c in enumerate(row):
                if c.data_type == "f":
                    self.formulas.setdefault(ws.title, set()).add(rn)
                    vals.append(_FORMULA)
                elif c.data_type == "e":                     # an error value (#REF!, #N/A): not text the person typed
                    if cols is None or k in cols:
                        self.errors.setdefault(ws.title, set()).add(rn)
                        self.err_cols.setdefault((ws.title, rn), set()).add(k)
                    vals.append(_FORMULA)
                else:
                    vals.append(c.value)
            yield rn, vals

    def problem(self, msg, sheet="", row=0, id="", field=""):
        self.plan.problems.append(Problem(msg, sheet, row, id, field))

    def stage(self, **kw):
        self.n += 1
        c = StagedChange(n=self.n, **kw)
        self.plan.changes.append(c)
        return c

    def sheet(self, ws, table):
        """Stage one sheet's differences. The header-to-column reading is (creaite excel_sync.read_sheet); the id match, the
        removed rows and the clash check follow (creaite excel_sync.cmd_import), with clark's departures noted in the module."""
        sheet = ws.title
        cols = writer.columns(self.store.con, table)
        info = dict(_table_info(self.store, table))
        if table in writer.LABELLED:
            cols = cols + [LABELS]
            info[LABELS] = ("TEXT", False, None)
        if table == "use_cases":
            cols = cols + [UC_MILESTONES]
            info[UC_MILESTONES] = ("TEXT", False, None)
        header, named, ignored = header_map(next(ws.iter_rows(min_row=1, max_row=1, values_only=True), ()), table, cols, sheet)
        if "id" not in header:
            self.problem(f"{sheet}: there is no id column, so the sheet was skipped (every row would look new)", sheet)
            return
        if ignored:
            self.plan.notes.append(f"{sheet}: column(s) {', '.join(ignored)} are not columns the import knows for this sheet and "
                                   "were ignored")
        editable = [c for c in cols if c in header and c not in LOCKED and c not in LOCKED_IN.get(table, ())]
        db = {r["id"]: r for r in self.store.read(table, project=self.project)}
        for r in db.values():
            if LABELS in cols:
                r[LABELS] = ", ".join(writer.labels_of(self.store.con, r["id"])) or None
            if UC_MILESTONES in cols:
                r[UC_MILESTONES] = ", ".join(writer.use_case_milestone_ids(self.store.con, r["id"])) or None
        seen, rows = set(), 0
        self.typed_rows = 0
        self.row_titles = {}                      # id → the title the workbook gives it (to tell a swap from a title edit)
        for _, row in self.rows_of(ws, 2, set(header.values())):
            i, t = (row[header["id"]] if header["id"] < len(row) else None), None
            if TITLE_OF[table] in header and header[TITLE_OF[table]] < len(row):
                t = row[header[TITLE_OF[table]]]
            if isinstance(i, str) and i.strip() and isinstance(t, str):
                self.row_titles.setdefault(i.strip(), _title_key(t))
        snap = self.snapshot.get(table)           # None: no record of what was exported for this sheet
        for rn, row in self.rows_of(ws, 2, set(header.values())):
            cell = {c: (row[i] if i < len(row) else None) for c, i in header.items()}
            raw_id = cell["id"]
            if raw_id is _FORMULA:
                self.held.add(self.other_item(table, cell, db, ""))      # its item is not "removed": only its ID cell is unreadable
                bad = self.err_cols.get((sheet, rn), ())
                if header["id"] in bad:
                    if TITLE_OF[table] in header and header[TITLE_OF[table]] in bad:      # nothing says which item this row is: none on the sheet is offered for archiving
                        self.unplaced.add(sheet)
                        self.problem(f"{sheet}, row {rn}: the ID and the title are error values; the row was left out and no item on this sheet is offered for archiving", sheet, rn, "", "id")
                    else:
                        self.problem(f"{sheet}, row {rn}: the ID is an error value; the row was left out", sheet, rn, "", "id")
                else:
                    self.problem(f"{sheet}, row {rn}: the ID is a formula, which is not read; the row was left out", sheet, rn, "", "id")
                continue
            rid = "" if raw_id is None else str(raw_id).strip()
            placeholder = ""
            if rid and not any(ch.isdigit() for ch in rid):    # TBD, new, n/a, -, ?: no number in it, so it says "no ID yet"
                placeholder, rid = rid, ""
            if not rid and all(v is None or (isinstance(v, str) and not v.strip()) for c, v in cell.items() if c != "id"):
                continue                                   # an empty row
            rows += 1
            if rows > MAX_ROWS:
                raise Invalid(f"The {sheet} sheet has more than {MAX_ROWS:,} rows, which is more than clark will import in one go. "
                              "Check this is the right file. Nothing was changed.")
            if rid:
                self.existing_row(table, sheet, rn, rid, cell, editable, info, db, seen, snap)
            else:
                made = len(self.plan.changes)
                self.new_row(table, sheet, rn, cell, editable, info)
                if placeholder and len(self.plan.changes) > made:
                    self.plan.notes.append(f"{sheet}, row {rn}: “{_short(_clean(placeholder))}” isn't an ID, so the item gets a new ID.")
        if not rows and db:
            self.plan.notes.append(f"{sheet} has no rows, so every {WORDS[table]} of {self.project} is no longer in the workbook: "
                                   "check this is the right file")
        removed_before = sum(1 for c in self.plan.changes if c.kind == "removed" and c.sheet == sheet)
        for rid, r in db.items():
            if rid in seen or rid in self.held or r["archived"] or sheet in self.unplaced:
                continue
            if snap is not None and rid not in snap:
                self.plan.unchanged += 1             # added in clark after the export: the workbook could not have held it
                continue
            if table == "use_cases":
                self.plan.notes.append(f"{rid} is not in the workbook; an import never archives a use case, so it stays")
            elif r["status"] in FINISHED[table]:
                self.plan.unchanged += 1
            else:
                self.stage(kind="removed", table=table, sheet=sheet, row=0, id=rid, seen_at=r["updated_at"])
        gone = [c for c in self.plan.changes if c.kind == "removed" and c.sheet == sheet][removed_before:]
        if gone and (self.typed_rows or self.looks_edited(table, gone, db)):
            self.plan.notes.append(f"{sheet}: This looks like an ID that was changed. The old item shows as no longer in the workbook: don't accept that line if you still want it.")

    def looks_edited(self, table, gone, db):
        """True if a new row of this sheet carries what a missing item holds (two or more of its other values, and none that
        differs): its ID was probably blanked or retyped, not a new item added."""
        for c in self.plan.changes:
            given = self.given.get(c.n) if c.kind == "new" and c.sheet == gone[0].sheet else None
            if not given:
                continue
            rest = {f: v for f, v in given.items() if f not in ("project", "source", TITLE_OF[table], LABELS)}
            for g in gone:
                old = db[g.id]
                title = given.get(TITLE_OF[table])
                if isinstance(title, str) and title.strip() and _title_key(title) == _title_key(old.get(TITLE_OF[table])):
                    return True                 # the same words as a missing item, whatever else was edited
                if len(rest) >= 2 and all(old.get(f) is not None and (old[f] == v or (isinstance(v, str) and same(v, old[f])))
                                          for f, v in rest.items()):
                    return True
        return False

    def check_id(self, table, sheet, rn, rid):
        """None if `rid` can be matched in this project's table, else the reason (already reported)."""
        m = writer.ITEM_ID.fullmatch(rid)
        if not m or not rid.isascii() or writer.item_table(rid) != table:          # \d in ITEM_ID also takes other scripts' digits
            self.problem(f"{sheet}, row {rn}: “{_short(rid)}” isn't {A_WORD[table]} id (for example "
                         f"{self.project}{writer.ID_PREFIX[table]}001); the row was left out", sheet, rn, _short(rid), "id")
            return False
        if m.group(1) != self.project:
            self.problem(f"{sheet}, row {rn}: {_short(rid)} belongs to project {m.group(1)}, but this import is for "
                         f"{self.project}; the row was left out", sheet, rn, _short(rid), "id")
            return False
        return True

    def existing_row(self, table, sheet, rn, rid, cell, editable, info, db, seen, snap=None):
        other = self.other_item(table, cell, db, rid, editable, info)
        if other and rid not in db and any(other in ids for ids in self.made.values()):
            other = ""                              # a typed id imported before: its row is the item made then ("Already imported")
        if other:                                   # the row's own words are another item's: its id was typed over or edited
            self.held.update((other, rid))          # that item is not missing from the workbook, only its id was altered
            self.problem(f"{sheet}, row {rn}: the ID was changed. IDs can't be edited; the row was skipped.", sheet, rn, _short(rid), "id")
            return
        if not self.check_id(table, sheet, rn, rid):
            return
        if rid in seen:
            self.problem(f"{sheet}, row {rn}: {rid} appears twice; this second row was left out", sheet, rn, rid, "id")
            return
        seen.add(rid)
        cur = db.get(rid)
        t = cell.get(TITLE_OF[table])
        if cur is not None and isinstance(t, str) and t.strip() and _title_key(t) != _title_key(cur.get(TITLE_OF[table])):
            dup = next((i for i, r in db.items() if i != rid and _title_key(r.get(TITLE_OF[table])) == _title_key(t)), "")
            if dup:
                self.plan.notes.append(f"{sheet}, row {rn}: {rid}'s new title is the same as {dup}'s.")
        if cur is None:
            self.new_row(table, sheet, rn, cell, editable, info, typed=rid)
            return
        if cell.get("project") not in (None, "") and cell["project"] is not _FORMULA and str(cell["project"]).strip() != self.project:
            self.problem(f"{sheet}, row {rn}: {rid} has project {cell['project']}, but it belongs to {self.project} and an "
                         "import doesn't move items; the row was left out", sheet, rn, rid, "project")
            return
        # What the row held when it was exported, if the export's record has it. A row that changed in clark since then is a
        # clash, and only what the person edited (the cells that differ from the export) is staged.
        was = snap.get(rid) if snap else None
        if was is not None:
            clash = was.get("updated_at") != cur["updated_at"]
        else:
            clash = ("updated_at" in cell and cell["updated_at"] not in (None, "", _FORMULA)
                     and _moved(cell["updated_at"], cur["updated_at"]))
        before, after, kept, bad = {}, {}, {}, False
        for f in editable:
            label = _label(table, f)
            if cell[f] is _FORMULA:
                continue                                # a formula is not read: neither a value nor a cleared cell
            v, err = from_cell(f, cell[f], info[f][0], label, (cur[f], was.get(f) if was else None), table=table, refs=self.refs)
            if err:
                self.problem(f"{sheet}, row {rn}, {rid}: {err}; the row was left out", sheet, rn, rid, f)
                bad = True
                continue
            if f == "commitment" and v is None:
                continue                                # #709: an empty Commitment cell leaves the flag as it is (never clears it)
            old = cur[f]
            basis = (lambda x: sanitise.rich_plain_text(x) if isinstance(x, str) else x) if (table, f) in excel.RICH_WORDS else (lambda x: x)   # row 1005: the sheet holds the words of a rich field, so that is what a cell is compared with
            if f == LABELS and sorted(n.lower() for n in writer.label_names(v)) == sorted(n.lower() for n in writer.label_names(old)):
                continue                                # the same labels, in any order or case
            if clash and was is not None:               # the person's own edit is what differs from the export
                then = basis(was.get(f))
                if not _differs(v, then, f):
                    if _differs(then, basis(old), f):
                        kept[f] = old                   # newer in clark: left alone
                    continue
            if v is None:
                if old is None or old == "":
                    continue
                if not info[f][1]:
                    v = None                            # a cleared value, in a column that can be empty
                elif _is_blank_default(info[f]):
                    v = ""
                else:
                    self.problem(f"{sheet}, row {rn}, {rid}: {label} is blank in the workbook, but it can't be empty; "
                                 "the row was left out", sheet, rn, rid, f)
                    bad = True
                    continue
            elif old is not None and (v == basis(old) or (isinstance(v, str) and same(v, basis(old)))):
                continue
            if table == "milestones" and f == "baseline_date" and old:
                self.plan.notes.append(f"{sheet}: {rid}'s change to the agreed date ({label}) was ignored: moving an "
                                       "agreed date is a rebaseline, which records a decision; do it in clark")
                continue
            before[f], after[f] = old, v
        if not bad and table == "use_cases" and isinstance(after.get("ref"), str):      # the change route refuses a "Shown as" another use case already has
            mine = after["ref"].strip().casefold()
            taken = [r.get("ref") for i, r in db.items() if i != rid] + [c.after.get("ref") for c in self.plan.changes if c.table == table and c.id != rid]
            if any(isinstance(x, str) and x.strip().casefold() == mine for x in taken):
                self.problem(f"{sheet}, row {rn}, {rid}: {_label(table, 'ref')} is already used by another use case; the row was left out", sheet, rn, rid, "ref")
                bad = True
        if bad:
            return
        if not after:
            self.plan.unchanged += 1
            return
        if cur["archived"]:                              # #126: an archived row can't be edited; said here, once, in plain words
            self.problem(f"{sheet} row {rn}: {rid} is archived, so its changes were left out. Restore it in clark first, "
                         "then import again.", sheet, rn, rid)
            return
        self.stage(kind="changed", table=table, sheet=sheet, row=rn, id=rid, before=before, after=after,
                   state="clash" if clash else "clean", clash=clash, seen_at=cur["updated_at"],
                   kept=kept if clash else {}, from_snapshot=bool(clash and was is not None))

    def _agree(self, table, cell, row, editable, info):
        """How many of the row's other cells (not the title) hold what `row`, an item of the database, holds."""
        n = 0
        for f in editable:
            if f == TITLE_OF[table] or cell.get(f) is _FORMULA or cell.get(f) is None:
                continue
            v, err = from_cell(f, cell[f], info[f][0], f, refs=self.refs)
            old = row.get(f)
            if not err and v is not None and old is not None and (v == old or (isinstance(v, str) and same(v, old))):
                n += 1
        return n

    def other_item(self, table, cell, db, rid, editable=(), info=None):
        """The id of a DIFFERENT item whose title the row carries (a pasted-over or edited ID), else ''. A row whose title is its
        own item's (unchanged), blank or a formula says nothing."""
        t = cell.get(TITLE_OF[table])
        if not isinstance(t, str) or not t.strip():
            return ""
        key = _title_key(t)
        if rid in db and _title_key(db[rid].get(TITLE_OF[table])) == key:
            return ""
        m = next((i for i, r in db.items() if i != rid and _title_key(r.get(TITLE_OF[table])) == key), "")
        if m and rid in db and self.row_titles.get(m) != _title_key(db[rid].get(TITLE_OF[table])):
            return ""                    # a title edit: the other item's row does not hold this one's title, so nothing was swapped
        if m and rid in db and info and self._agree(table, cell, db[rid], editable, info) > self._agree(table, cell, db[m], editable, info):
            return ""                    # two descriptions swapped, the IDs kept: the rest of the row still belongs to its own item
        return m

    def new_row(self, table, sheet, rn, cell, editable, info, typed=""):
        values, bad = {}, False
        for f in editable:
            if cell[f] is _FORMULA:
                continue
            v, err = from_cell(f, cell[f], info[f][0], _label(table, f), table=table, refs=self.refs)
            if err:
                self.problem(f"{sheet}, row {rn} (new): {err}; the row was left out", sheet, rn, "", f)
                bad = True
            elif v is not None:
                values[f] = v
        if cell.get("project") not in (None, "", _FORMULA) and str(cell["project"]).strip() != self.project:
            self.problem(f"{sheet}, row {rn} (new): project is {cell['project']}, but this import is for {self.project}; "
                         "the row was left out", sheet, rn, "", "project")
            bad = True
        if bad:
            return
        if not values:
            return
        given = dict(values)
        fp = fingerprint(table, values)
        if self.made.get(fp):
            rid = self.made[fp].pop(0)             # one recorded row covers one workbook row
            self.held.add(rid)                     # and its item is not "missing from the workbook": this row is it
            self.plan.already_created += 1
            self.plan.notes.append(f"{sheet}, row {rn}: Already imported as {rid}: left as it is.")
            return
        if fp in self.fp_rows:
            self.plan.notes.append(f"{sheet}, row {rn} is the same as row {self.fp_rows[fp]}, so two items will be made. Delete one row "
                                   "first if that isn't what you want.")
        self.fp_rows.setdefault(fp, rn)
        values["project"] = self.project
        if table in ("actions", "raid"):
            values.setdefault("raised", self.today)
        values["source"] = f"Excel import, {writer.shown(self.today)}, {self.filename}"
        if typed:
            self.typed_rows += 1
            self.plan.notes.append(f"{sheet}, row {rn}: the ID {_short(typed)} isn't one clark knows, so the item gets a new ID.")
        self.given[self.stage(kind="new", table=table, sheet=sheet, row=rn, after=values, fp=fp).n] = given


def _gantt_sheet(self, ws):
    """Row 926: stage the Gantt sheet's differences from the project's Gantt lines. A stored id that exists changes only the fields
    that differ; an empty id, or one that is not a line of this project yet, makes a new line (the data layer gives the id; the one
    typed is only the name the Parent and Depends on cells of the sheet use for it). Days and Status are worked out and never read.
    A line missing from the sheet is left alone. The rules are the page's, applied when the plan is checked and again when it is applied."""
    sheet = ws.title
    if excel.CLIENT_COPY_NAME in ws.parent.defined_names:      # the client workbook's mark (excel_client.write_gantt_sheet): a client copy is never imported, whatever row its header is in
        self.problem(f"{sheet}: this is the copy made for the client, not a workbook to import, so the sheet was skipped.", sheet)
        return
    first = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), ())
    header, ignored = {}, []
    for i, h in enumerate(first):
        if h is None or h is _FORMULA or not str(h).strip():
            continue
        f = GANTT_HEADERS.get(str(h).strip().lower())
        if f is None:
            ignored.append(str(h).strip())
        elif not f.startswith("_") and f not in header:
            header[f] = i
        elif f.startswith("_"):
            pass                                          # Days and Status: worked out
    if "id" not in header or "name" not in header:       # also a client copy: its title band is row 1 and its header row 4
        self.problem(f"{sheet}: there is no id column, so the sheet was skipped (every row would look new)", sheet)
        return
    if ignored:
        self.plan.notes.append(f"{sheet}: column(s) {', '.join(ignored)} are not columns the import knows for this sheet and were ignored")
    editable = [f for f in header if f != "id"]
    db = {r["id"]: r for r in self.store.read(GANTT, project=self.project)}
    seen, rows = set(), 0
    for rn, row in self.rows_of(ws, 2, set(header.values())):
        cell = {f: (row[i] if i < len(row) else None) for f, i in header.items()}
        raw_id = cell["id"]
        if raw_id is _FORMULA:
            what = "an error value" if header["id"] in self.err_cols.get((sheet, rn), ()) else "a formula, which is not read"
            self.problem(f"{sheet}, row {rn}: the ID is {what}; the row was left out", sheet, rn, "", "id")
            continue
        rid = "" if raw_id is None else str(raw_id).strip()
        placeholder = ""
        if rid and not any(ch.isdigit() for ch in rid):
            placeholder, rid = rid, ""
        if not rid and all(_gantt_blank(v) for f, v in cell.items() if f != "id"):
            continue
        rows += 1
        if rows > MAX_ROWS:
            raise Invalid(f"The {sheet} sheet has more than {MAX_ROWS:,} rows, which is more than clark will import in one go. "
                          "Check this is the right file. Nothing was changed.")
        if rid:
            m = writer.GANTT_ID.fullmatch(rid)
            if not m or not rid.isascii():
                self.problem(f"{sheet}, row {rn}: “{_short(rid)}” isn't {A_WORD[GANTT]} id (for example "
                             f"{self.project}{writer.ID_PREFIX[GANTT]}001); the row was left out", sheet, rn, _short(rid), "id")
                continue
            if rid[:-8] != self.project:
                self.problem(f"{sheet}, row {rn}: {_short(rid)} belongs to project {_short(rid[:-8])}, but this import is for "
                             f"{self.project}; the row was left out", sheet, rn, _short(rid), "id")
                continue
            if rid in seen:
                self.problem(f"{sheet}, row {rn}: {rid} appears twice; this second row was left out", sheet, rn, rid, "id")
                continue
            seen.add(rid)
        values = {f: gantt_cell_value(f, cell[f]) for f in editable if cell[f] is not _FORMULA}
        cur = db.get(rid) if rid else None
        if cur is not None:
            before, after = {}, {}
            for f, v in values.items():
                if f == "show" and v is None:
                    continue
                if gantt_differs(f, v, cur[f]):
                    before[f], after[f] = cur[f], v
            if not after:
                self.plan.unchanged += 1
            else:
                self.stage(kind="changed", table=GANTT, sheet=sheet, row=rn, id=rid, before=before, after=after, seen_at=cur["updated_at"])
            continue
        new = {f: v for f, v in values.items() if not (v is None and f not in ("start", "end"))}
        for f in ("start", "end", "type", "name"):
            if f in header and f not in values:
                new[f] = "" if f in ("type", "name") else None       # a formula there is not read: the line still needs it
        fp = fingerprint(GANTT, new)
        if self.made.get(fp):
            made_id = self.made[fp].pop(0)
            self.held.add(made_id)
            self.plan.already_created += 1
            self.plan.notes.append(f"{sheet}, row {rn}: Already imported as {made_id}: left as it is.")
            continue
        if fp in self.fp_rows:
            self.plan.notes.append(f"{sheet}, row {rn} is the same as row {self.fp_rows[fp]}, so two items will be made. Delete one row "
                                   "first if that isn't what you want.")
        self.fp_rows.setdefault(fp, rn)
        new["project"] = self.project
        if rid:
            self.plan.notes.append(f"{sheet}, row {rn}: the ID {_short(rid)} isn't one clark knows, so the item gets a new ID.")
        self.stage(kind="new", table=GANTT, sheet=sheet, row=rn, after=new, fp=fp, typed=rid)


_Reader.gantt_sheet = _gantt_sheet


def header_map(first_row, table, cols, sheet):
    """(header, named, ignored) for a sheet's first row: header[column] = its position, named[column] = the heading as written,
    ignored = headings the import does not know. read_workbook and list_sheets read the heading row the same way (issue 737)."""
    labels = {label.lower(): f for label, f in excel.COLUMN_OF[table].items()}
    for alias, f in HEADER_ALIASES.items():
        if f in labels.values():
            labels[alias] = f
    header, named = {}, {}
    ignored = []
    for i, h in enumerate(first_row):
        if h is None or h is _FORMULA or not str(h).strip():
            continue
        k = labels.get(str(h).strip().lower()) or _key(h)       # the export's label first, then a column name
        if k in excel.DERIVED:
            continue                                  # worked out by the export (Original, Shown state): never read back
        if k in cols and k in header:
            raise Invalid(f"The {sheet} sheet has two columns for the same thing: “{named[k]}” and “{str(h).strip()}”. Keep one of "
                          "them and import again. Nothing was changed.")
        if k in cols:
            header[k], named[k] = i, str(h).strip()
        else:
            ignored.append(str(h).strip())
    return header, named, ignored


CHOICE_ORDER = ("actions", "raid", "decisions", "milestones", "use_cases")     # the order the person is offered the sheets in (#655)


def _blank(v):
    return v is None or (isinstance(v, str) and not v.strip())


def _rows_counted(ws, table, cols):
    """How many rows read_workbook would count against MAX_ROWS in this sheet, stopping once it is past the limit: a row counts when
    its ID cell has something in it, or any column the import reads does (a formula cell counts; a row whose ID is a formula is
    left out; cells under a heading the import does not know are not looked at). `cols` None (no store to name the columns) counts
    every row with anything in it, which is never fewer."""
    first = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), ())
    header = None
    if cols is not None:
        try:
            header = header_map(first, table, cols, ws.title)[0]
        except Invalid:
            header = None                         # two columns for one thing: the check says so; here every cell is looked at
    if header is not None and "id" not in header:
        return 0                                  # no id column: the sheet is skipped
    rows = 0
    for row in ws.iter_rows(min_row=2, max_row=MAX_SHEET_ROWS + 2, max_col=MAX_SHEET_COLUMNS):
        if header is None:
            used = any(not _blank(c.value) for c in row)
        else:
            at = {k: (row[i] if i < len(row) else None) for k, i in header.items()}
            if at["id"] is not None and at["id"].data_type in ("f", "e"):
                continue
            used = any(c is not None and (c.data_type in ("f", "e") or not _blank(c.value)) for c in at.values())
        if used:
            rows += 1
            if rows > MAX_ROWS:
                break
    return rows


def _gantt_listed(ws, store):
    """Row 926: the rows of a sheet the import can read as the Gantt sheet (the editor's export layout: a header row 1 with the ID and Line
    columns), None when it is not one (the client workbook's Gantt sheet has a title band in row 1, so it is never offered). Over the limits,
    OVER_LIMIT, as for the other sheets."""
    first = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), ())
    fields = {GANTT_HEADERS.get(str(h).strip().lower()) for h in first if isinstance(h, str)}
    if "id" not in fields or "name" not in fields:
        return None
    reach_rows, reach_cols = ws.max_row or 0, ws.max_column or 0
    if reach_rows > MAX_SHEET_ROWS or reach_cols > MAX_SHEET_COLUMNS or reach_rows * reach_cols > MAX_SHEET_CELLS:
        return OVER_LIMIT
    rows = 0
    for row in ws.iter_rows(min_row=2, max_row=MAX_SHEET_ROWS + 2, max_col=MAX_SHEET_COLUMNS, values_only=True):
        if any(not _blank(v) for v in row):
            rows += 1
            if rows > MAX_ROWS:
                break
    return min(rows, OVER_LIMIT)


def list_sheets(path, store=None, project=None):
    """The sheets of the workbook at `path` that clark imports, for the person to choose from (issue 655): [{"table", "name", "rows"}]
    in CHOICE_ORDER, "rows" being the rows below the header read_workbook would count. A sheet the file does not have is not listed;
    row 926: after them comes the Gantt sheet ({"table": GANTT, "name": the sheet's own name}) when the file has one the import can read;
    a History sheet (or any other) is never listed. Nothing is compared or written.
    A sheet that read_workbook would refuse for its size is given "rows" = OVER_LIMIT (MAX_ROWS + 1), whatever its real size: the
    box says "more than 2,000 rows", so the list never promises what ticking would refuse. That is every refusal read_workbook makes
    of one sheet: more than MAX_ROWS rows counted as the reader counts them (with `store`, exactly; without, never fewer), a reach
    past row MAX_SHEET_ROWS or column MAX_SHEET_COLUMNS, or more than MAX_SHEET_CELLS cells (empty ones included). (The total across
    sheets, MAX_TOTAL_CELLS, is not shown here.) The reach is the workbook's own dimension record, as read_workbook uses it; a
    workbook whose record understates the sheet is counted only as far as row MAX_SHEET_ROWS + 2 (cheap, about 0.2 s) and is not
    corrected: the check still refuses it in words. The sheet is not read (ticking it is what makes the check refuse it, in words)."""
    path = Path(path)
    try:
        excel.check_workbook_size(path)
    except excel.TooBig as e:
        raise Invalid(str(e))
    check_sheets_early(path, lambda title: False)             # row 966: only the shared-strings text scan, no sheet is counted; a text no Excel could hold is refused before the load
    try:
        wb = load_workbook(str(path), read_only=True)
    except Exception:
        raise Invalid(f"{path.name} can't be read as an Excel workbook (.xlsx).")
    try:
        found, gantt = {}, None
        gantt_names = {excel.GANTT_DEFAULT_NAME.lower()}
        if store is not None and project is not None:
            gantt_names.add(excel.gantt_sheet_name((store.read("projects", ref=project) or {}).get("gantt_tab_name")).lower())
        for ws in wb.worksheets:
            table = SHEET_TABLES.get(re.sub(r"[\s_]+", " ", ws.title.strip().lower()))
            if table is None:
                if ws.title.strip().lower() in gantt_names:
                    n = _gantt_listed(ws, store)
                    if n is not None:
                        if gantt is not None:
                            raise Invalid(f"The workbook has two sheets for the same thing: “{gantt[0]}” and “{ws.title}”. Keep one of them and "
                                          "import again. Nothing was changed.")
                        gantt = (ws.title, n)
                continue
            if table in found:
                raise Invalid(f"The workbook has two sheets for the same thing: “{found[table][0]}” and “{ws.title}”. Keep one of them and "
                              "import again. Nothing was changed.")
            reach_rows, reach_cols = ws.max_row or 0, ws.max_column or 0
            if reach_rows > MAX_SHEET_ROWS or reach_cols > MAX_SHEET_COLUMNS or reach_rows * reach_cols > MAX_SHEET_CELLS:
                rows = OVER_LIMIT                                 # the reader's size tests, before any row is looked at
            else:
                cols = None
                if store is not None:
                    cols = writer.columns(store.con, table) + virtual_columns(table)
                rows = min(_rows_counted(ws, table, cols), OVER_LIMIT)
            found[table] = (ws.title, rows)
        listed = [{"table": t, "name": SHEET_NAMES[t], "rows": found[t][1]} for t in CHOICE_ORDER if t in found]
        if gantt is not None:
            listed.append({"table": GANTT, "name": gantt[0], "rows": gantt[1]})
        return listed
    except Invalid:
        raise
    except Exception:                                        # cells that point at a shared-strings table the file does not have, and the like
        raise Invalid(f"{path.name} can't be read as an Excel workbook (.xlsx).")
    finally:
        wb.close()


MAX_CELL_TEXT = 32767                                # the most characters Excel itself keeps in a cell: a longer text is not from Excel
_SCAN_CHUNK = 65536
_TAG = re.compile(rb"<(?:[A-Za-z_][\w.-]*:)?(row|c|t)(?![\w:.-])")   # one tag (cut out by _scan_member), matched by local name: <row>, <x:row>, <ns:c>, <x:t>
_ATTR_R = re.compile(rb"\sr=\"([A-Za-z]*)(\d*)\"")
_SHEET_TAG = re.compile(rb"<sheet\b[^>]*>")
_REL_TAG = re.compile(rb"<Relationship\b[^>]*>")


class _TextTooLong(Exception):
    pass


def _attr(tag, name):
    m = re.search(rb"[\s:]" + name + rb"=\"([^\"]*)\"", tag)
    return unescape(m.group(1).decode("utf-8", "replace")) if m else None


def _column_number(letters):
    n = 0
    for ch in letters.upper():
        n = n * 26 + ord(ch) - 64
    return n


def _small_member(z, name, limit=1 << 20):
    try:
        member = z.open                                  # a zip member is read as bytes, never as text
        with member(name) as f:
            data = f.read(limit + 1)
    except (KeyError, OSError, RuntimeError, zipfile.BadZipFile):
        return None
    return data if len(data) <= limit else None


def _too_large(title, rows, cols):
    return (f"The {title} sheet is too large ({max(rows, 1):,} rows by {max(cols, 1)} columns, most of it empty), "
            "which is more than clark will import in one go. Check this is the right file. Nothing was changed.")


def _scan_member(z, member, title):
    """Stream one part of the zip (never whole), counting the cells a worksheet really holds: (rows reached, columns reached).
    The workbook's own dimension record is not trusted (a sheet can say A1:B2 and hold 300,000 rows). Raises Invalid at once,
    with the words the loaded sheet would get, when it reaches past row MAX_SHEET_ROWS or column MAX_SHEET_COLUMNS or holds more
    cells than the limits allow at all; raises _TextTooLong for a text longer than Excel can keep. Memory is one chunk and one
    tag; the read stops at what the zip declares (excel.MAX_MEMBER_BYTES)."""
    max_row = max_col = cells = row = col = read = tags = 0
    buf = b""
    text = None                                          # the bytes of a <t> node read so far (it can run over a chunk cut), else None
    opener = z.open                                      # a zip member is read as bytes, never as text
    with opener(member) as f:
        while True:
            chunk = f.read(_SCAN_CHUNK)
            read += len(chunk)
            buf += chunk
            pos = 0
            while True:                                  # one pass over buf: each byte is looked at a bounded number of times
                if text is not None:                     # inside a text node: it ends at the next '<', which may be in a later chunk
                    lt = buf.find(b"<", pos)
                    text += buf[pos:] if lt < 0 else buf[pos:lt]
                    if len(text) > 8 * MAX_CELL_TEXT:    # a text node this long is not a cell
                        raise _TextTooLong()
                    if lt < 0:
                        pos = len(buf)
                        break
                    if len(text) > MAX_CELL_TEXT and len(unescape(text.decode("utf-8", "replace"))) > MAX_CELL_TEXT:
                        raise _TextTooLong()
                    text, pos = None, lt
                lt = buf.find(b"<", pos)
                if lt < 0:
                    pos = len(buf)
                    break
                gt = buf.find(b">", lt)
                if gt < 0:                               # the tag goes on in the next chunk: keep it from its '<'
                    pos = lt
                    break
                tag, pos = buf[lt:gt + 1], gt + 1
                m = _TAG.match(tag)
                if m is None:
                    continue
                if m.group(1) == b"t":
                    if not tag.endswith(b"/>"):
                        text = b""
                    continue
                at = _ATTR_R.search(tag)
                if m.group(1) == b"row":
                    row = int(at.group(2)) if at and at.group(2) else row + 1
                    col = 0
                    tags += 1                                    # an empty row does not move max_row (its number is only where the next cell
                    if tags > MAX_SHEET_ROWS:                    # without an r lands), but row tags are still counted, so a flood of them is refused
                        raise Invalid(f"The {title} sheet reaches past row {MAX_SHEET_ROWS:,} or column {MAX_SHEET_COLUMNS}, which is more than "
                                      "clark will import in one go. Check this is the right file. Nothing was changed.")
                    continue
                cells += 1
                if at and at.group(1) and at.group(2):
                    col, row = _column_number(at.group(1).decode()), int(at.group(2))
                else:
                    col += 1
                max_row, max_col = max(max_row, row), max(max_col, col)
                if max_row > MAX_SHEET_ROWS or max_col > MAX_SHEET_COLUMNS:
                    raise Invalid(f"The {title} sheet reaches past row {MAX_SHEET_ROWS:,} or column {MAX_SHEET_COLUMNS}, which is more than "
                                  "clark will import in one go. Check this is the right file. Nothing was changed.")
                if cells > MAX_SHEET_ROWS * MAX_SHEET_COLUMNS:
                    raise Invalid(_too_large(title, max_row, max_col))
            buf = buf[pos:]
            if len(buf) > 8 * MAX_CELL_TEXT:             # a tag this long is not a cell
                raise _TextTooLong()
            if not chunk or read > excel.MAX_MEMBER_BYTES:
                return max_row, max_col


def check_sheets_early(path, wanted):
    """Refuse a hostile workbook BEFORE openpyxl loads it whole (a full load of a sheet that says A1:B2 and holds 300,000 rows
    took 7.6 s and 216 MB before it was refused). `wanted(title)` says whether a sheet is one the import reads; only those are
    streamed, one part at a time (_scan_member), against the same limits and with the same words as the loaded check in
    read_workbook, which stays as it was. A text longer than Excel can keep (MAX_CELL_TEXT), in the shared strings or a sheet,
    refuses the file. A part that is damaged inside the zip
    (cut short, or not what the zip says it is) is refused in the same words as a file that is not a workbook. A file that is not a zip, or has no readable sheet list, passes: opening it says what is wrong with it."""
    path = Path(path)
    try:
        z = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError):
        return
    with z:
        area = 0
        try:
            book, rels = _small_member(z, "xl/workbook.xml"), _small_member(z, "xl/_rels/workbook.xml.rels")
            if book is None or rels is None:
                return
            target = {_attr(r, b"Id"): _attr(r, b"Target") for r in _REL_TAG.findall(rels)}
            if "xl/sharedStrings.xml" in z.NameToInfo:
                _scan_member(z, "xl/sharedStrings.xml", "shared strings")
            for tag in _SHEET_TAG.findall(book):
                title, part = _attr(tag, b"name"), target.get(_attr(tag, b"id"))
                if not title or not part or not wanted(title):
                    continue
                part = part.lstrip("/") if part.startswith("/") else "xl/" + part
                if part not in z.NameToInfo:
                    continue
                rows, cols = _scan_member(z, part, title)
                if rows * cols > MAX_SHEET_CELLS:
                    raise Invalid(_too_large(title, rows, cols))
                area += rows * cols
                if area > MAX_TOTAL_CELLS:
                    raise Invalid("The sheets in this workbook are too large together (most of the space is empty), which is more than "
                                  "clark will import in one go. Check this is the right file. Nothing was changed.")
        except (_TextTooLong, zipfile.BadZipFile, zlib.error, EOFError, OSError, ValueError, RuntimeError):   # ValueError: a digit run too long to be a number
            raise Invalid(f"{path.name} can't be read as an Excel workbook (.xlsx).")


def read_workbook(store, path, project, state_path=None, allow_unrecorded=False, sheets=None):
    """Compare the workbook at `path` with `project`'s rows in the database; returns an ImportPlan of staged changes (all waiting
    for a decision), the rows that were reported, and notes. Writes nothing. Raises Invalid if the file isn't a workbook, is too
    big to open (excel.check_workbook_size) or the project isn't there.

    `state_path` is the export's record (default: excel.STATE_FILE beside clark.db). A file whose hash is the last one imported
    is not read again (plan.already_imported). A workbook with no export record is plan.unrecorded: nothing is accepted for the
    person and apply_import refuses it until it is confirmed (`allow_unrecorded=True`, or plan.confirm_unrecorded()).

    `sheets` (#655): None reads every sheet; otherwise the tables (CHOICE_ORDER) whose sheets are read. A sheet that is not in it
    is NOT READ: its dimensions are not checked, its rows are not looked at (a broken row in it blocks nothing), nothing in it is
    staged as new, changed or "no longer in the workbook" (so nothing of it can be archived), and no note is made of it. The
    plan is then `partial`: applying it does not mark the file as imported as a whole."""
    if sheets is not None:
        sheets = {t for t in sheets if t in CHOICE_ORDER or t == GANTT}      # row 926: the Gantt sheet is read when asked for (or when `sheets` is None)
    project_row = store.read("projects", ref=project)
    if project_row is None:
        raise Invalid(f"There is no project {project}.")
    gantt_names = {excel.gantt_sheet_name(project_row.get("gantt_tab_name")).lower(), excel.GANTT_DEFAULT_NAME.lower()}
    path = Path(path)
    try:
        excel.check_workbook_size(path)
    except excel.TooBig as e:
        raise Invalid(str(e))
    seen_hash = excel.file_hash(path)
    state_path = Path(state_path) if state_path is not None else Path(store.path).parent / excel.STATE_FILE
    try:
        record = excel.load_state(state_path, path, project)
    except (OSError, ValueError):
        record = {}
    if record.get("project") not in (None, project):
        record = {}          # #147: a record of another project's export (the same bytes, found by SHA-256) is no record for this one
    same_file = seen_hash is not None and record.get("imported_hash") == seen_hash
    undone = same_file and not in_force(store, record.get("imported_step"))
    if same_file and not undone:
        plan = ImportPlan(path.name, project, path=str(path), file_hash=seen_hash, state_path=state_path, already_imported=True)
        plan.notes.append(f"{path.name} was already imported as it is now, so there is nothing to compare. Edit and save it "
                          "again, or export a fresh workbook, to import more.")
        return plan
    def wanted(title):
        table = SHEET_TABLES.get(re.sub(r"[\s_]+", " ", title.strip().lower()))
        if table is None and title.strip().lower() in gantt_names:
            table = GANTT
        return table is not None and (sheets is None or table in sheets)
    check_sheets_early(path, wanted)                   # row 966: a hostile sheet is refused while streamed, before the full load below
    try:
        wb = load_workbook(str(path))                  # not data_only: a formula is seen as one, and not read
    except Exception:
        raise Invalid(f"{path.name} can't be read as an Excel workbook (.xlsx).")
    try:
        try:
            created = excel.created_for(state_path, path, project)
        except (OSError, ValueError):
            created = []
        db_id = _db_id(store)
        created = [c for c in created if in_force(store, c, item=c.get("id"), db_id=db_id)]      # UNDO AND RESTORE
        rd = _Reader(store, project, path.name, record, created)
        if undone:
            rd.plan.notes.append(f"{path.name} was imported before, but that import has been undone (or this is another copy of "
                                 "the database), so it is read again.")
        rd.plan.path, rd.plan.file_hash, rd.plan.state_path = str(path), seen_hash, state_path
        rd.plan.unrecorded = not record.get("hash")
        rd.plan.unrecorded_ok = bool(allow_unrecorded)
        if rd.plan.unrecorded:
            rd.plan.notes.append(f"There is no record of exporting {path.name} from this store (a workbook with no export id is recorded only while it is exactly what clark wrote), so clark can't say what you edited "
                                 "or what was in the export: every difference is staged and rows no longer in the "
                                 "workbook are offered for archiving (nothing is deleted). Check it is the right file, then confirm it to apply anything.")
        found, to_read, area = set(), [], 0
        for ws in wb.worksheets:
            table = SHEET_TABLES.get(re.sub(r"[\s_]+", " ", ws.title.strip().lower()))
            if table is None and ws.title.strip().lower() in gantt_names:
                table = GANTT                                                  # row 926: the sheet named for the Gantt tab, else 'Gantt'
            if table is None or (sheets is not None and table not in sheets):
                continue
            if table in found:
                first = next(w.title for w, t in to_read if t == table)
                raise Invalid(f"The workbook has two sheets for the same thing: “{first}” and “{ws.title}”. Keep one of them and "
                              "import again. Nothing was changed.")
            found.add(table)
            if ws.max_row > MAX_SHEET_ROWS or ws.max_column > MAX_SHEET_COLUMNS:       # one far-off cell would build the whole grid
                raise Invalid(f"The {ws.title} sheet reaches past row {MAX_SHEET_ROWS:,} or column {MAX_SHEET_COLUMNS}, which is more than "
                              "clark will import in one go. Check this is the right file. Nothing was changed.")
            cells = ws.max_row * ws.max_column
            if cells > MAX_SHEET_CELLS:
                raise Invalid(f"The {ws.title} sheet is too large ({ws.max_row:,} rows by {ws.max_column} columns, most of it empty), "
                              "which is more than clark will import in one go. Check this is the right file. Nothing was changed.")
            area += cells
            to_read.append((ws, table))
        if area > MAX_TOTAL_CELLS:                    # all the sheets together are checked before any one is read
            raise Invalid("The sheets in this workbook are too large together (most of the space is empty), which is more than "
                          "clark will import in one go. Check this is the right file. Nothing was changed.")
        for ws, table in to_read:
            rd.gantt_sheet(ws) if table == GANTT else rd.sheet(ws, table)
        rd.plan.partial = sheets is not None and any(
            (SHEET_TABLES.get(re.sub(r"[\s_]+", " ", w.title.strip().lower())) or (GANTT if w.title.strip().lower() in gantt_names else None))
            not in (None, *sheets) for w in wb.worksheets)
        if not found:
            rd.problem("The workbook has none of the sheets Actions, Risks & Issues, Decisions, Milestones, Use cases or "
                       f"{excel.gantt_sheet_name(project_row.get('gantt_tab_name'))}, so there is nothing to compare.")
        else:
            for t in TABLE_ORDER:
                if t not in found and (sheets is None or t in sheets):
                    rd.plan.notes.append(f"There is no {SHEET_NAMES[t]} sheet, so {WORDS[t]}s were not compared")
        for sheet_name, rows_ in rd.formulas.items():
            shown = ", ".join(str(r) for r in sorted(rows_)[:10]) + (" and more" if len(rows_) > 10 else "")
            rd.plan.notes.append(f"{sheet_name}: a formula cell was ignored in row {shown}; clark reads typed values, not "
                                 "formulas, so type the value instead")
        for sheet_name, rows_ in rd.errors.items():
            shown = ", ".join(str(r) for r in sorted(rows_)[:10]) + (" and more" if len(rows_) > 10 else "")
            rd.plan.notes.append(f"{sheet_name}: an error cell was ignored in row {shown}; type the value instead")
        rd.plan.changes.sort(key=lambda c: (WRITE_ORDER.index(c.table), ("changed", "new", "removed").index(c.kind), c.row))
        for i, c in enumerate(rd.plan.changes, start=1):
            c.n = i
        rd.plan.store = store
        rd.plan.refresh_ids()
        if any(c.kind == "new" and not c.preview for c in rd.plan.changes):
            raise Invalid(f"The workbook adds more new items than {project} has numbers left (each kind of item stops at 999). "
                          "Import fewer rows at a time, or check this is the right file. Nothing was changed.")
    finally:
        wb.close()
    lines = [c for c in rd.plan.changes if c.table == GANTT]
    for c in rd.plan.changes:                  # which would the writer refuse? (each tried alone and rolled back)
        if c.table != GANTT:
            errs, _, refused = _try(store, [c], "Import check", commit=False)
            c.problem = errs[0].message.split(": ", 1)[-1] if errs else refused
    if lines:                                  # row 926: the Gantt lines are tried together (a line may name another new one), each refusal kept with its row
        errs, _, refused = _try(store, lines, "Import check", commit=False)
        for c in lines:
            c.problem = next((e.message.split(": ", 1)[-1] for e in errs if e.row == c.row), refused)
        if any(c.problem == writer.GANTT_TOO_MANY for c in lines):    # a count over the limit is the whole sheet's: no line of it is taken alone (the 501st keeps its row)
            for c in lines:
                c.problem = writer.GANTT_TOO_MANY
    rd.plan.refresh_ids()
    return rd.plan


# ── Applying ──────────────────────────────────────────────────────────────────

class _Rollback(Exception):
    """Raised inside the step to roll all of it back."""


def _gantt_ref(ids, text):
    """A Parent or Depends on cell with the ids the sheet typed for its new lines put as the ids they were given."""
    return ",".join(ids.get(d, d) for d in writer.gantt_list(text))


def _write(st, store, c, ctx=None):
    """Write one staged change through the step."""
    if c.table == GANTT:                     # row 926: through the page's own change route (changes.gantt_import_write)
        from clark import changes
        after = dict(c.after)
        if c.kind == "changed":
            now = store.read(GANTT, ref=c.id)
            if now is None or now["updated_at"] != c.seen_at:
                raise Invalid(f"{c.id} was changed in clark after this import was checked; run the import again")
            return changes.gantt_import_write(store, st, now["project"], c.id, after)
        later = {k: after.pop(k) for k in ("parent", "depends") if k in after}
        ref = changes.gantt_import_write(store, st, after["project"], None, {k: v for k, v in after.items() if k != "project"})
        if c.typed:
            ctx["ids"][c.typed] = ref
        if later:
            ctx["later"].append((c, ref, later, after["project"]))
        return ref
    after = dict(c.after)
    text = writer.OWNER_TEXT.get(c.table)
    if text in after and c.kind != "removed":      # row 873: the owner text and the person it links to are written together, as an owner edit does, else a later rename or merge puts the old name back
        found = store.resolve_owner(after[text]) if after[text] else {"status": "blank"}
        if found["status"] == "one" or c.kind == "changed":
            after["owner_id"] = found["id"] if found["status"] == "one" else None
    wanted = after.pop(UC_MILESTONES, False) if c.table == "use_cases" and c.kind != "removed" else False      # row 1107: False = the cell was not part of this change
    if c.kind == "new":
        ref = st.create(c.table, after)
        _write_milestone_links(st, ref, wanted)
        return ref
    now = store.read(c.table, ref=c.id)
    if now is None:
        raise Invalid(f"{c.id} is no longer in clark; run the import again")
    if now["updated_at"] != c.seen_at:
        raise Invalid(f"{c.id} was changed in clark after this import was checked; run the import again")
    if c.kind == "changed":
        ref = st.update(c.table, c.id, after) if after else c.id
        _write_milestone_links(st, c.id, wanted)
        return ref
    return st.archive(c.table, c.id)


def _write_milestone_links(st, use_case, wanted):
    """Make a use case's direct milestone links the ones the cell names (row 1107): missing ones are added, ones the cell no longer names
    are ended (their rows are kept). `wanted` is the cell as milestone_ids' text, None for an emptied cell, False when not part of the change."""
    if wanted is False:
        return
    want = set(wanted.split(", ")) if wanted else set()
    have = set(writer.use_case_milestone_ids(st.con, use_case))
    for m in sorted(want - have):
        writer.link_use_case_milestone(st, use_case, m)
    for m in sorted(have - want):
        writer.unlink_use_case_milestone(st, use_case, m)


def _try(store, changes, by_user, commit, src_ref=None, made=None, route="excel", place="excel"):
    """(problems, step id, refused): try `changes` in one step. If any breaks a rule, every broken one is returned and the step is
    rolled back; with commit False it is rolled back whatever happens (a dry run through the writer's own checks). `refused` is
    the plain reason when the store would not open the step (it is busy, or a check before a step such as the backup refused) or
    would not commit it: nothing was written, and it is "" otherwise. `route` and `place` are the step's (a Word import, #48,
    passes "word" and None: the Head's ruling on Q6 is that it uses this refuse-and-rollback rather than another). `made`, if
    given, is filled with {change number: the id the store gave a new row}; it is only to be trusted when the step committed
    (no problems, nothing refused)."""
    problems, step_id, refused = [], None, ""
    ctx = {"ids": {}, "later": []}               # row 926: the ids the sheet typed for new Gantt lines → the ids they got; their Parent and Depends on cells, written once every line is there

    def broke(c, e):
        f = next((f for f in list(c.after) if re.search(rf"\b{re.escape(f)}\b", str(e))), "")
        problems.append(Problem(f"{c.label}: {plain(c.table, str(e))}", c.sheet, c.row, c.id, f))
    try:
        with store.step(route, by_user, place=place, src_ref=src_ref, dry=not commit) as st:   # #86: a preview takes no backup
            for c in changes:
                try:
                    ref = _write(st, store, c, ctx)
                    if made is not None and c.kind == "new":
                        made[c.n] = ref
                except (Invalid, sqlite3.IntegrityError) as e:
                    broke(c, e)
            if not problems:
                from clark import changes as route_changes
                for c, ref, later, project in ctx["later"]:
                    try:
                        route_changes.gantt_import_write(store, st, project, ref, {k: (_gantt_ref(ctx["ids"], v) or None) if k == "parent" else _gantt_ref(ctx["ids"], v)
                                                                                    for k, v in later.items()})
                    except (Invalid, sqlite3.IntegrityError) as e:
                        broke(c, e)
            if problems or not commit:
                raise _Rollback()
            step_id = st.peek_apply_id()
    except _Rollback:
        pass
    except (Invalid, sqlite3.Error) as e:          # the step was refused on entry, or could not be committed: nothing is written
        reason = str(e) if isinstance(e, Invalid) else writer._busy(e)       # a database error in the store's plain words
        problems, step_id, refused = [], None, reason or e.__class__.__name__
    return problems, step_id, refused


def _mark_imported(store, plan, state_path, created=(), stamp=None):
    """Record the workbook as imported (excel.mark_imported) so the next export may overwrite it, with the fingerprints of the
    rows just made (`created`). Returns (done, note). Not marked when the file has changed since it was read (those edits were
    never read) or can't be recorded; the import stands either way, and the fingerprints are still recorded where they can be."""
    if not plan.path or plan.file_hash is None:
        return False, ""
    if plan.partial:             # #655: the sheets left unticked were never read, so the file is not "imported as it is"; only its new rows are recorded
        try:
            excel.record_created(plan.path, state_path, created, plan.project)
        except (OSError, ValueError):
            pass
        return False, ""
    if excel.file_hash(plan.path) != plan.file_hash:
        try:
            excel.record_created(plan.path, state_path, created, plan.project)
        except (OSError, ValueError):
            pass
        return False, (f" {plan.file} was saved again after it was read, so it is not marked as imported: import it again "
                       "before exporting.")
    try:
        excel.mark_imported(plan.path, state_path, created, plan.project, stamp)
    except (OSError, ValueError) as e:
        return False, f" {plan.file} could not be marked as imported ({e}), so the next export will refuse until it is."
    return True, ""


def apply_import(store, plan, by_user, state_path=None):
    """Apply the accepted changes as ONE step (one Undo reverses the lot). If any accepted change breaks a rule, all the broken
    ones are reported and nothing at all is applied. Returns an ImportResult; its step_id is what Store.undo takes.

    Once applied, the workbook is recorded as imported (excel.mark_imported) in `state_path`, by default the one the plan was read
    with (the export's state file beside clark.db), so the next export may overwrite it and the same file is not imported twice.
    Nothing is recorded when nothing was applied, or when the import was refused or rolled back. The rows it made are recorded by
    fingerprint too (see NEW ROWS ARE NOT MADE TWICE at the top: editing a pending new row after importing it makes a new
    row, and Undo of the import keeps the fingerprints). A plan of a workbook with no export record is refused until it is confirmed."""
    state_path = Path(state_path) if state_path is not None else (plan.state_path or Path(store.path).parent / excel.STATE_FILE)
    if plan.already_imported:
        return ImportResult(False, message=f"{plan.file} was already imported as it is now, so nothing was changed.")
    if plan.unrecorded and not plan.unrecorded_ok:
        return ImportResult(False, message=f"There is no record of exporting {plan.file} from this store (a workbook with no export id is recorded only while it is exactly what clark wrote), so nothing was "
                            "applied. Check it is the right file, confirm it, and import again.")
    if plan.path and plan.file_hash is not None:
        try:
            now = excel.load_state(state_path, plan.path, plan.project)
            if now.get("imported_hash") == plan.file_hash and in_force(store, now.get("imported_step")):
                return ImportResult(False, message=f"{plan.file} has been imported since this plan was made, so nothing "
                                    "was changed.")
        except (OSError, ValueError):
            pass
    accepted = plan.accepted()
    if not accepted:
        return ImportResult(False, message="Nothing was accepted, so nothing was changed.")
    src = "by Excel import (" + re.sub(r"\s+", " ", plan.file)[:250] + ")"
    made = {}
    problems, step_id, refused = _try(store, accepted, by_user, commit=True, src_ref=src, made=made)
    if refused:
        if backup.is_refusal(refused):             # #86: the safety copy could not be made; its own words say nothing was imported
            return ImportResult(False, message=refused)
        return ImportResult(False, message=f"Nothing was applied, because clark could not start the import: {refused}")
    if problems:
        names = "; ".join(p.message for p in problems)
        return ImportResult(False, problems=problems, message=f"Nothing was applied, because {len(problems)} accepted "
                            f"change(s) break a rule: {names}. Reject or fix them in the workbook and import again.")
    counts = plan.counts(accepted)
    stamp = stamp_of(store, step_id) if step_id is not None else None
    created = [{"fp": c.fp, "id": made[c.n], **stamp} for c in accepted if c.kind == "new" and c.fp and c.n in made] if stamp else []
    marked, note = _mark_imported(store, plan, state_path, created, stamp)      # only now that the step has committed
    given = [made[c.n] for c in accepted if c.kind == "new" and c.n in made]
    ids = (f" New items: {', '.join(given[:10])}{f' and {len(given) - 10} more' if len(given) > 10 else ''}." if given else "")
    return ImportResult(True, step_id, counts, marked=marked, created=created, message=f"Imported {counts['new']} new, {counts['changed']} "
                        f"changed and {counts['removed']} archived because they are no longer in the workbook (nothing was deleted), as one step you can undo.{ids}{note}")
