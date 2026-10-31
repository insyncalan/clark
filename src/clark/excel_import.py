"""Excel import (#38, FR-71): compare a workbook with the database by id, stage the differences, apply only the accepted ones.

Kept in its own file beside the export (`excel.py`, #37); it takes the export's sheet names and header labels from there. Reads with the vendored openpyxl; writes only through the store's Step (`Store.step`, `Step.create`,
`Step.update`, `Step.cancel`), so the writer's rules, the history and Undo all apply. Never edits the store.

THE WORKBOOK THE IMPORT READS (the one the export, #37, writes; its sheet names and labels are imported from excel.py):
- Sheets: "Milestones", "Actions", "RAID" (also read as "Risks and issues"), "Decisions", "Use cases". Names are matched in any
  case. A sheet that is missing is not compared, so nothing in its table is staged as removed. The old and the new names are both
  read (#143): the RAID sheet or "Risks and issues"; the headers "Client messaging" or "Client wording", "Baseline" or "Agreed".
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
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook

from clark import backup, excel
from clark import store as writer
from clark.store import Invalid

# The sheet names and header labels are the export's own (excel.SHEET_OF, excel.COLUMN_OF), so the two cannot drift apart.
SHEET_NAMES = dict(excel.SHEET_OF)                                  # table → the sheet the export writes
SHEET_TABLES = {name.lower(): table for table, name in SHEET_NAMES.items()}     # sheet name (lower case) → table
SHEET_TABLES["risks and issues"] = "raid"          # the new name of the RAID sheet; both are read (#143)
SHEET_TABLES["raid"] = "raid"                      # the old name, written out so workbooks exported before the rename still import (#143)
# Header names the export has used or will use (#143): the old and the new read as the same column. They are written out here
# and not taken from excel.COLUMN_OF, so a rename in the export can never stop an older workbook from importing.
HEADER_ALIASES = {"client messaging": "client_message", "client wording": "client_message",
                  "baseline": "baseline_date", "agreed": "baseline_date"}
TABLE_ORDER = ("milestones", "use_cases", "actions", "raid", "decisions")     # the order changes are written in
WORDS = {"actions": "action", "raid": "RAID item", "decisions": "decision", "milestones": "milestone",
         "use_cases": "use case"}
LOCKED = {"id", "project", "source", "updated_at", "archived", "closed", "state_set"}
LOCKED_IN = {"raid": {"priority"}}                       # worked out from impact and likelihood
LABELS = "labels"      # not a column: an item's labels, as the export writes them (comma-separated); the store keeps them apart
FLAGS = {"client_visible", "state_set", "active"}
# what applying "removed from the workbook" does (#126: nothing is deleted or closed; the row is archived, status unchanged)
REMOVED_BY = {"actions": "archived", "raid": "archived", "decisions": "archived", "milestones": "archived"}
FINISHED = {"actions": ("Closed", "Cancelled"), "raid": ("Closed", "Cancelled"), "decisions": ("Withdrawn",),
            "milestones": ("Done", "Cancelled")}
NOT_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff￾￿]")   # (creaite excel_sync.NOT_XML)
A_WORD = {"actions": "an action", "raid": "a RAID item", "decisions": "a decision", "milestones": "a milestone",
          "use_cases": "a use case"}
# RICH TEXT: fields that hold HTML (schema.sql "-- HTML"; docs: the editor writes it, publish.clean_html cleans it on output):
# use_cases.standing is the only one the workbook carries ("Where it stands"); projects.current_state is HTML too but is not in
# the workbook. The import writes what the cell holds, so this is the write-side seam.
RICH_FIELDS = {"standing"}
TITLE_OF = {"actions": "description", "raid": "description", "decisions": "decision", "milestones": "name",
            "use_cases": "title"}                  # the column that says what an item is (a row's "other values" are matched on it)
MAX_SHEET_ROWS, MAX_SHEET_COLUMNS = 5000, 100        # the area a sheet may span, empty cells included: checked before any cell is built
MAX_SHEET_CELLS, MAX_TOTAL_CELLS = 200000, 400000     # rows times columns, empty cells included: one sheet, and all the sheets read together
MAX_TEXT = 10000                                    # characters in one text cell; a longer one is refused (a hostile file can hold megabytes)
MAX_ROWS = 2000                                     # rows with something in them, per sheet; a bigger sheet is refused whole


def clean_rich(field, text):
    """
    is staged or compared. A no-op today: the text is stored as typed, and publishing cleans it on output (publish.clean_html).
    Once #66a merges, call its cleaner here and nowhere else. Do not write a sanitiser in this file."""
    return text


_FORMULA = object()        # a cell typed as a formula: not read (it is neither blank nor a value)


def _label(table, f):
    """A column as the person sees it: the export's header label (Due, Agreed, Client wording ...)."""
    for label, field_ in excel.COLUMN_OF.get(table, {}).items():
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
    if m and m.group(1) in excel.COLUMN_OF.get(table, {}).values():
        msg = _label(table, m.group(1)) + msg[len(m.group(1)):]
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
    return repr(_short(value, 60)) if isinstance(value, str) else repr(value)


def _shown(f, v):
    if v is None or v == "":
        return "empty"
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

    @property
    def label(self):
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
            return f"New: {_title_of(self)} → {self.preview or 'a new ID'}"
        return f"{self.id}: " + "; ".join(f"{_label(self.table, f)} {_shown(f, self.before.get(f))} -> {_shown(f, v)}"
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
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    s = str(value).strip()
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


def from_cell(name, value, kind, label=None):
    """(stored value, None) or (None, why not). A blank cell is (None, None). (creaite excel_sync.from_cell: dates to
    YYYY-MM-DD, Yes/No to 1/0, blank to None; departure: it refuses what it can't read instead of passing it on.) `label` is
    the column's name as the person sees it, for the reason given; it defaults to `name`."""
    label = label or name
    if value is None or (isinstance(value, str) and not value.strip()):
        return None, None
    if isinstance(value, str) and len(value) > MAX_TEXT:
        return None, f"{label} is too long ({len(value):,} characters; the most clark will take is {MAX_TEXT:,})"
    if name in writer.DATE_FIELDS:
        try:
            return read_date(value), None
        except (ValueError, OverflowError):
            return None, f"{label} must be a date, shown DD-MM-YYYY (got {_got(value)})"
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


def _moved(cell, stored):
    """Whether an updated_at cell (an Excel date-time, or text) differs from the database's updated_at by more than the cell can
    hold: 2 milliseconds for a date-time, a second for text without a fraction. Unreadable text says nothing, so is no clash."""
    if isinstance(cell, datetime):
        then, slack = cell, 0.002
    else:
        text = str(cell).strip().replace("T", " ")
        try:
            then = datetime.fromisoformat(text)
        except ValueError:
            return False
        slack = 0.002 if "." in text else 1.0
    try:
        now = datetime.fromisoformat(str(stored).strip().replace("T", " "))
    except ValueError:
        return False
    return abs((now - then).total_seconds()) > slack


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


class _Reader:
    def __init__(self, store, project, filename, record=None, created=()):
        self.store, self.project, self.filename = store, project, filename
        self.plan = ImportPlan(filename, project)
        self.n = 0
        self.today = writer.today()
        self.snapshot = (record or {}).get("rows") or {}     # the export's record of each row: {table: {id: row}}
        self.made = {}                                       # fingerprint → ids an earlier import made from it (used up as rows match)
        for c in created:
            self.made.setdefault(c.get("fp"), []).append(c.get("id"))
        self.fp_rows = {}                                    # fingerprint → the first workbook row that carried it
        self.held = set()                                    # items whose row was skipped for a changed ID: not "removed"
        self.given = {}                                      # a new row's change number → the values its cells gave (no defaults)
        self.formulas = {}                                   # sheet → workbook rows holding a formula cell

    def rows_of(self, ws, min_row):
        """(row number, [cell values]) for each row from `min_row`; a formula cell is _FORMULA (it is not read, and is noted)."""
        for rn, row in enumerate(ws.iter_rows(min_row=min_row), start=min_row):
            vals = []
            for c in row:
                if c.data_type == "f":
                    self.formulas.setdefault(ws.title, set()).add(rn)
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
        labels = {label.lower(): f for label, f in excel.COLUMN_OF[table].items()}
        for alias, f in HEADER_ALIASES.items():
            if f in labels.values():
                labels[alias] = f
        header, named = {}, {}
        ignored = []
        for i, h in enumerate(next(ws.iter_rows(min_row=1, max_row=1, values_only=True), ())):
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
        seen, rows = set(), 0
        self.typed_rows = 0
        self.row_titles = {}                      # id → the title the workbook gives it (to tell a swap from a title edit)
        for _, row in self.rows_of(ws, 2):
            i, t = (row[header["id"]] if header["id"] < len(row) else None), None
            if TITLE_OF[table] in header and header[TITLE_OF[table]] < len(row):
                t = row[header[TITLE_OF[table]]]
            if isinstance(i, str) and i.strip() and isinstance(t, str):
                self.row_titles.setdefault(i.strip(), _title_key(t))
        snap = self.snapshot.get(table)           # None: no record of what was exported for this sheet
        for rn, row in self.rows_of(ws, 2):
            cell = {c: (row[i] if i < len(row) else None) for c, i in header.items()}
            raw_id = cell["id"]
            if raw_id is _FORMULA:
                self.held.add(self.other_item(table, cell, db, ""))      # its item is not "removed": only its ID cell is unreadable
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
            if rid in seen or rid in self.held or r["archived"]:
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
            v, err = from_cell(f, cell[f], info[f][0], label)
            if err:
                self.problem(f"{sheet}, row {rn}, {rid}: {err}; the row was left out", sheet, rn, rid, f)
                bad = True
                continue
            old = cur[f]
            if f == LABELS and sorted(n.lower() for n in writer.label_names(v)) == sorted(n.lower() for n in writer.label_names(old)):
                continue                                # the same labels, in any order or case
            if clash and was is not None:               # the person's own edit is what differs from the export
                then = was.get(f)
                if not _differs(v, then, f):
                    if _differs(then, old, f):
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
            elif old is not None and (v == old or (isinstance(v, str) and same(v, old))):
                continue
            if table == "milestones" and f == "baseline_date" and old:
                self.plan.notes.append(f"{sheet}: {rid}'s change to the agreed date ({label}) was ignored: moving an "
                                       "agreed date is a rebaseline, which records a decision; do it in clark")
                continue
            before[f], after[f] = old, v
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
            v, err = from_cell(f, cell[f], info[f][0], f)
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
            v, err = from_cell(f, cell[f], info[f][0], _label(table, f))
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


def read_workbook(store, path, project, state_path=None, allow_unrecorded=False):
    """Compare the workbook at `path` with `project`'s rows in the database; returns an ImportPlan of staged changes (all waiting
    for a decision), the rows that were reported, and notes. Writes nothing. Raises Invalid if the file isn't a workbook, is too
    big to open (excel.check_workbook_size) or the project isn't there.

    `state_path` is the export's record (default: excel.STATE_FILE beside clark.db). A file whose hash is the last one imported
    is not read again (plan.already_imported). A workbook with no export record is plan.unrecorded: nothing is accepted for the
    person and apply_import refuses it until it is confirmed (`allow_unrecorded=True`, or plan.confirm_unrecorded())."""
    if store.read("projects", ref=project) is None:
        raise Invalid(f"There is no project {project}.")
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
            if table is None:
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
            rd.sheet(ws, table)
        if not found:
            rd.problem("The workbook has none of the sheets Actions, RAID (or Risks and issues), Decisions, Milestones or Use cases, so there is "
                       "nothing to compare.")
        else:
            for t in TABLE_ORDER:
                if t not in found:
                    rd.plan.notes.append(f"There is no {SHEET_NAMES[t]} sheet, so {WORDS[t]}s were not compared")
        for sheet_name, rows_ in rd.formulas.items():
            shown = ", ".join(str(r) for r in sorted(rows_)[:10]) + (" and more" if len(rows_) > 10 else "")
            rd.plan.notes.append(f"{sheet_name}: a formula cell was ignored in row {shown}; clark reads typed values, not "
                                 "formulas, so type the value instead")
        rd.plan.changes.sort(key=lambda c: (TABLE_ORDER.index(c.table), ("changed", "new", "removed").index(c.kind), c.row))
        for i, c in enumerate(rd.plan.changes, start=1):
            c.n = i
        rd.plan.store = store
        rd.plan.refresh_ids()
        if any(c.kind == "new" and not c.preview for c in rd.plan.changes):
            raise Invalid(f"The workbook adds more new items than {project} has numbers left (each kind of item stops at 999). "
                          "Import fewer rows at a time, or check this is the right file. Nothing was changed.")
    finally:
        wb.close()
    for c in rd.plan.changes:                  # which would the writer refuse? (each tried alone and rolled back)
        errs, _, refused = _try(store, [c], "Import check", commit=False)
        c.problem = errs[0].message.split(": ", 1)[-1] if errs else refused
    rd.plan.refresh_ids()
    return rd.plan


# ── Applying ──────────────────────────────────────────────────────────────────

class _Rollback(Exception):
    """Raised inside the step to roll all of it back."""


def _write(st, store, c):
    """Write one staged change through the step."""
    if c.kind == "new":
        return st.create(c.table, dict(c.after))
    now = store.read(c.table, ref=c.id)
    if now is None:
        raise Invalid(f"{c.id} is no longer in clark; run the import again")
    if now["updated_at"] != c.seen_at:
        raise Invalid(f"{c.id} was changed in clark after this import was checked; run the import again")
    if c.kind == "changed":
        return st.update(c.table, c.id, dict(c.after))
    return st.archive(c.table, c.id)


def _try(store, changes, by_user, commit, src_ref=None, made=None):
    """(problems, step id, refused): try `changes` in one step. If any breaks a rule, every broken one is returned and the step is
    rolled back; with commit False it is rolled back whatever happens (a dry run through the writer's own checks). `refused` is
    the plain reason when the store would not open the step (it is busy, or a check before a step such as the backup refused) or
    would not commit it: nothing was written, and it is "" otherwise. `made`, if given, is filled with {change number: the id
    the store gave a new row}; it is only to be trusted when the step committed (no problems, nothing refused)."""
    problems, step_id, refused = [], None, ""
    try:
        with store.step("excel", by_user, place="excel", src_ref=src_ref, dry=not commit) as st:   # #86: a preview takes no backup
            for c in changes:
                try:
                    ref = _write(st, store, c)
                    if made is not None and c.kind == "new":
                        made[c.n] = ref
                except (Invalid, sqlite3.IntegrityError) as e:
                    f = next((f for f in list(c.after) if re.search(rf"\b{re.escape(f)}\b", str(e))), "")
                    problems.append(Problem(f"{c.label}: {plain(c.table, str(e))}", c.sheet, c.row, c.id, f))
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
