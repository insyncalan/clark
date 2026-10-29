"""Stage the text of a Word file as NEW work items for the person to accept (#48; BRD FR-72, FR-43a; design-48-word.md section 4).

A pure function of `docx_read`'s blocks: `stage(read, file_name, imported_on, seen)` gives a `WordPlan`. It touches no database, no
file, no route and no page; the guarded step that writes the accepted rows (one step, one Undo, the history row "by Word import
(<file name>)") comes in a separate change and takes `WordPlan.accepted()`.

What it stages: new actions, new risks and issues (and the other two RAID types), and new decisions, nothing else. A paragraph or a
list item under a heading that reads Actions, Next steps, Risks, Issues, Decisions and so on becomes one row; a table under such a
heading becomes one row per line, its columns read by their headings. Everything else is listed in the plan's notes and left alone.
It never changes, closes or removes an item that is already there: a table line that carries an ID names an existing item and is
left alone, and a missing line means nothing. It reads no picture and no comment (the reader does not give them).

Text from a file is not an instruction. Every value is plain text for a plain field (control characters removed, blanks tidied,
at most MAX_VALUE characters). No rich field is seeded (RICH_FIELDS is empty): the day one is, its text goes through
`sanitise.clean_html`, as everywhere else. Each row is staged with `client_visible` off (Q3), so a file nobody has read closely
reaches the client only when the person turns that row on. Each row's `source` names the file, the day and the heading.

The same content twice makes the rows once: a row's fingerprint (SHA-256 of its table and values, not the file's bytes) is
compared with `seen` (the fingerprints already made, kept by the later step) and with the rows already staged from this file.

Standard library only, Python 3.9. Dates are given in and shown as DD-MM-YYYY and stored as YYYY-MM-DD. Every message is plain
words (no part, markup or file-format terms), and "clark" never starts a line.
"""
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

MAX_VALUE = 2000            # characters in one value
MAX_ITEMS = 500             # rows staged from one file; the rest are noted
MAX_HEADING = 80            # a heading longer than this is not one of HEADINGS' names, and is never copied whole into a row
MAX_NAME = 120              # characters of the file's name kept in a source line
RICH_FIELDS = frozenset()   # fields seeded from Word that hold rich text: none (use_cases.standing, current_state and text sections are not seeded)

# The headings that decide what a row is. Compared lower case, with trailing punctuation and extra spaces removed.
HEADINGS = {
    "actions": ("action", "actions", "action items", "action list", "actions register", "next steps", "next step", "next week",
                "next actions", "actions for next week"),
    "decisions": ("decision", "decisions", "decisions made", "decisions needed", "decisions required", "decision log"),
    "risks": ("risk", "risks"),
    "issues": ("issue", "issues"),
    "raid": ("risks and issues", "risks & issues", "issues and risks", "raid", "raid log", "raid items"),
}
WORD_OF = {"actions": "action", "decisions": "decision", "risks": "risk", "issues": "issue", "raid": "risk or issue"}
TABLE_OF = {"actions": "actions", "decisions": "decisions", "risks": "raid", "issues": "raid", "raid": "raid"}
RAID_TYPES = {"risk": "Risk", "assumption": "Assumption", "issue": "Issue", "dependency": "Dependency"}

# Table column headings (lower case) → the field they fill. The Excel export's own labels (excel.COLUMN_OF) and the headings the Word
# report writes (docx_build) are both here, so a table from either comes back. A heading not here is not read and is noted once.
COLUMNS = {
    "actions": {"description": "description", "action": "description", "item": "description", "task": "description",
                "owner": "owner", "priority": "priority", "due": "due_date", "due date": "due_date", "status": "status",
                "latest update": "latest_update"},
    "raid": {"description": "description", "item": "description", "risk": "description", "issue": "description",
             "type": "type", "owner": "owner", "response action": "response_action", "due": "due_date", "due date": "due_date",
             "impact": "impact", "likelihood": "likelihood", "status": "status"},
    "decisions": {"decision": "decision", "description": "decision", "status": "status", "made by": "made_by",
                  "needed by": "needed_by", "date": "date", "reasoning": "reasoning", "revisit": "revisit"},
}
ID_COLUMN = "id"
# The words a column may hold (the writer's own lists, schema.sql). A new row starts open or pending: Closed and Cancelled need a
# closing date and mean an item that is finished, which a Word table cannot be trusted to say.
CHOICES = {
    ("actions", "priority"): ("Urgent", "High", "Medium", "Low"),
    ("actions", "status"): ("Open", "Delayed"),
    ("raid", "impact"): ("High", "Medium", "Low"),
    ("raid", "likelihood"): ("High", "Medium", "Low"),
    ("raid", "status"): ("Open",),
    ("raid", "type"): tuple(RAID_TYPES.values()),
    ("decisions", "status"): ("Pending", "Made"),
}
DATE_FIELDS = {"due_date", "needed_by", "date", "revisit"}
REQUIRED = {"actions": "description", "raid": "description", "decisions": "decision"}
HIDDEN_FROM_CLIENT = "Not shown to the client until you turn it on."

CONTROLS = re.compile("[\x00-\x08\x0b-\x1f\x7f-\x9f​-‏‪-‮⁠-⁤﻿]")
BLANKS = re.compile(r"\s+")
DATE_DMY = re.compile(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$")
DATE_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
MARK = re.compile(r"^(risk|issue|assumption|dependency)\s*[:\-]\s*", re.I)


class WordImportError(ValueError):
    """A staging request that cannot be met, in words a person can act on."""


@dataclass
class Problem:
    """Something in the file that is reported and not staged."""
    message: str
    where: str = ""

    def __str__(self):
        return self.message


@dataclass
class StagedItem:
    """One new item waiting for a decision. Always new: there is no changed or removed row."""
    n: int
    table: str                    # 'actions' | 'raid' | 'decisions'
    where: str                    # where in the file it was read, in words
    values: dict = field(default_factory=dict)     # field → the value to write (dates stored YYYY-MM-DD)
    fp: str = ""                  # the row's fingerprint, recorded once it is made
    state: str = "waiting"        # 'waiting' | 'accepted' | 'rejected'
    kind: str = "new"

    @property
    def label(self):
        return f"new {_noun(self.table, self.values)} ({self.where})"

    def describe(self):
        """The row in plain words, dates as DD-MM-YYYY, and that it is hidden from the client."""
        body = "; ".join(f"{_LABEL.get(f, f)} {shown(f, v)}" for f, v in self.values.items() if f in _SHOWN)
        return f"New {_noun(self.table, self.values)} ({self.where}): {body}. {HIDDEN_FROM_CLIENT}"


_LABEL = {"description": "", "decision": "", "owner": "Owner", "priority": "Priority", "due_date": "Due", "status": "Status",
          "latest_update": "Latest update", "type": "Type", "response_action": "Response", "impact": "Impact",
          "likelihood": "Likelihood", "made_by": "Made by", "needed_by": "Needed by", "date": "Date", "reasoning": "Reasoning",
          "revisit": "Revisit"}
_SHOWN = set(_LABEL)


def _noun(table, values):
    if table == "raid":
        return (values.get("type") or "RAID item").lower() if values.get("type") else "risk or issue"
    return {"actions": "action", "decisions": "decision"}[table]


def shown(name, value):
    """A value as a person reads it: a date as DD-MM-YYYY."""
    if name in DATE_FIELDS and isinstance(value, str) and DATE_ISO.match(value):
        return f"{value[8:10]}-{value[5:7]}-{value[0:4]}"
    return str(value)


@dataclass
class WordPlan:
    """What the Word file would add: staged new items, what was reported, and notes. Decide with accept and reject."""
    file: str
    items: list = field(default_factory=list)
    problems: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    already_created: int = 0       # rows made from this content before, or repeated in this file: left as they are

    def get(self, n):
        for item in self.items:
            if item.n == n:
                return item
        raise WordImportError(f"There is no item {n} in this list.")

    def accept(self, *numbers):
        for n in numbers:
            self.get(n).state = "accepted"

    def reject(self, *numbers):
        for n in numbers:
            self.get(n).state = "rejected"

    def accept_all(self):
        for item in self.items:
            item.state = "accepted"

    def reject_all(self):
        for item in self.items:
            item.state = "rejected"

    def accepted(self):
        return [i for i in self.items if i.state == "accepted"]

    def counts(self):
        return {t: sum(i.table == t for i in self.items) for t in ("actions", "raid", "decisions")}

    def report(self):
        """The whole plan as plain lines, for a person to read before deciding."""
        k = self.counts()
        out = [f"{self.file}: {_count(len(self.items), 'new item')} found ({_count(k['actions'], 'action')}, "
               f"{_count(k['raid'], 'risk or issue', 'risks or issues')}, {_count(k['decisions'], 'decision')})"
               + (f", {self.already_created} left out because they were added before or repeat another line"
                  if self.already_created else "")
               + f", {len(self.problems)} not added. Nothing changes until you accept. {HIDDEN_FROM_CLIENT}"]
        out += [f"  {i.n}. {i.state}: {i.describe()}" for i in self.items]
        out += [f"  Not added: {p.message}" for p in self.problems]
        out += [f"  Note: {n}" for n in self.notes]
        return "\n".join(out)


# ===== Reading values =====
def clean_value(text):
    """`text` as one line of plain text: composed, control and invisible characters removed, blanks tidied."""
    return BLANKS.sub(" ", CONTROLS.sub("", unicodedata.normalize("NFC", str(text or "")))).strip()


def read_date(text):
    """YYYY-MM-DD for a day written DD-MM-YYYY (also with / or .) or YYYY-MM-DD; ValueError for anything else."""
    s = clean_value(text)
    m = DATE_DMY.match(s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = DATE_ISO.match(s)
        if not m:
            raise ValueError(s)
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return date(y, mo, d).isoformat()


def fingerprint(table, values):
    """SHA-256 of a new row's table and values (source and raised left out), sorted by name: the same content again gives the
    same fingerprint, whatever the file's bytes or name."""
    keep = sorted((k, v) for k, v in values.items() if k not in ("source", "raised", "client_visible"))
    canon = json.dumps([table, keep], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def file_label(name):
    """The file's name for a source line: the last part of a path, no control characters, at most MAX_NAME characters."""
    base = re.split(r"[\\/]", str(name or ""))[-1]
    base = clean_value(base) or "a Word file"
    return base if len(base) <= MAX_NAME else base[:MAX_NAME - 1] + "…"


def _count(n, one, many=None):
    """'1 action', '2 actions' (many defaults to the one with an s)."""
    return f"{n} {one if n == 1 else (many or one + 's')}"


def _heading_text(text):
    """A heading as kept in a row's source and where: tidied, and cut to MAX_HEADING characters."""
    t = clean_value(text)
    return t if len(t) <= MAX_HEADING else t[:MAX_HEADING - 1] + "…"


def _heading_kind(text):
    cleaned = clean_value(text)
    if len(cleaned) > MAX_HEADING:                          # none of the names is this long: decided by length, nothing scanned
        return None
    key = BLANKS.sub(" ", cleaned.lower().rstrip(" :.-–—"))   # rstrip, not a regex: a long run of dots cannot slow it down
    key = re.sub(r"^\d+[.)]?\s+", "", key)                  # "3. Actions"
    for kind, names in HEADINGS.items():
        if key in names:
            return kind
    return None


# ===== Staging =====
class _Stage:
    def __init__(self, file_name, imported_on, seen):
        self.file = file_label(file_name)
        self.on = imported_on
        self.seen = set(seen or ())
        self.plan = WordPlan(self.file)
        self.skipped_text = 0
        self.unread = set()
        self.has_id = 0
        self.over = 0

    def add(self, table, values, where, heading):
        values = {k: v for k, v in values.items() if v not in (None, "")}
        req = REQUIRED[table]
        if not values.get(req):
            self.plan.problems.append(Problem(f"{where}: there is no {req} to add, so nothing was added. Add a {req} and import again.", where))
            return
        fp = fingerprint(table, values)
        if fp in self.seen:
            self.plan.already_created += 1
            return
        if len(self.plan.items) >= MAX_ITEMS:
            self.over += 1
            return
        self.seen.add(fp)
        if table != "decisions":
            values["raised"] = self.on
        if table == "decisions":
            values.setdefault("status", "Pending")
            if values["status"] == "Made" and not values.get("date"):
                self.plan.problems.append(Problem(f"{where}: it says Made but has no date, so nothing was added. Add the date it was made and import again.", where))
                return
        values["client_visible"] = 0
        values["source"] = f"Word import, {shown('date', self.on)}, {self.file}, under {heading}"
        self.plan.items.append(StagedItem(len(self.plan.items) + 1, table, where, values, fp))

    def text_item(self, sec, block, heading):
        text = clean_value(block.get("text"))
        if not text:
            return
        kind, table = sec, TABLE_OF[sec]
        where = f"{block['kind'].replace('_', ' ')} under {heading}"
        values = {}
        if table == "raid":
            m = MARK.match(text)
            if m:
                values["type"] = RAID_TYPES[m.group(1).lower()]
                text = text[m.end():]
            elif kind == "risks":
                values["type"] = "Risk"
            elif kind == "issues":
                values["type"] = "Issue"
            else:
                self.plan.problems.append(Problem(f"{where}: it does not say whether this is a risk or an issue. Start it with "
                                                  f"\"Risk:\" or \"Issue:\". Nothing was added.", where))
                return
        if len(text) > MAX_VALUE:
            self.plan.problems.append(Problem(f"{where}: it is longer than {MAX_VALUE:,} characters, so nothing was added. Shorten it and import again.", where))
            return
        values[REQUIRED[table]] = text
        self.add(table, values, where, heading)

    def table_rows(self, sec, block, heading, index):
        table = TABLE_OF[sec]
        rows = block.get("rows") or []
        if len(rows) < 2:
            self.plan.notes.append(f"A table under {heading} has no lines below its headings, so nothing was read from it. Add the lines under the headings and import again.")
            return
        cols = COLUMNS[table]
        used = {}               # column number → the field it fills (the first column of a name wins)
        for i, cell in enumerate(rows[0]):
            name = clean_value(cell).lower()
            if name == ID_COLUMN:
                used[i] = ID_COLUMN
            elif name in cols and cols[name] not in used.values():
                used[i] = cols[name]
            elif name:
                self.unread.add(clean_value(cell))
        if REQUIRED[table] not in used.values():
            self.plan.notes.append(f"A table under {heading} has no column for the {REQUIRED[table]}, so nothing was read from it. Add a {REQUIRED[table].capitalize()} column and import again.")
            return
        for r, row in enumerate(rows[1:], start=2):
            where = f"table {index}, line {r - 1} under {heading}"
            cells = {i: clean_value(row[i]) if i < len(row) else "" for i in used}
            if not any(cells.values()):
                continue
            if ID_COLUMN in used.values():
                idc = next(i for i, f in used.items() if f == ID_COLUMN)
                if cells.get(idc):
                    self.has_id += 1
                    continue
            values, bad = {}, ""
            for i, f in used.items():
                v = cells.get(i, "")
                if f == ID_COLUMN or not v:
                    continue
                v, why = self._value(table, f, v)
                if why:
                    bad = why
                    break
                values[f] = v
            if bad:
                self.plan.problems.append(Problem(f"{where}: {bad} Nothing was added from this line.", where))
                continue
            if table == "raid" and "type" not in values:
                if sec == "risks":
                    values["type"] = "Risk"
                elif sec == "issues":
                    values["type"] = "Issue"
                else:
                    self.plan.problems.append(Problem(f"{where}: it does not say whether this is a risk or an issue. Add a Type "
                                                      "column or start the line with Risk or Issue. Nothing was added from this "
                                                      "line.", where))
                    continue
            self.add(table, values, where, heading)

    def _value(self, table, name, text):
        if len(text) > MAX_VALUE:
            return None, f"{name.replace('_', ' ').capitalize()} is longer than {MAX_VALUE:,} characters."
        if (table, name) in CHOICES:
            for choice in CHOICES[(table, name)]:
                if choice.lower() == text.lower():
                    return choice, None
            label = _LABEL.get(name) or name
            return None, f"{label} \"{text}\" is not one of {_join(CHOICES[(table, name)])}."
        if name in DATE_FIELDS:
            try:
                return read_date(text), None
            except (ValueError, OverflowError):
                return None, f"{_LABEL.get(name, name)} \"{text}\" is not a date. Write it as DD-MM-YYYY."
        return text, None


def _int(value):
    """value as a whole number, or 0 when it is not one (a hand-built block may carry anything)."""
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return 0


def _join(words):
    words = list(words)
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " or " + words[-1]


def stage(read, file_name, imported_on, seen=()):
    """The new items a Word file holds, as a WordPlan. `read` is `docx_read.read`'s result (or its list of blocks), `file_name` the
    file's name, `imported_on` today as YYYY-MM-DD, `seen` the fingerprints of rows already made from earlier files. Nothing is
    written anywhere and nothing is accepted: the person decides. Raises WordImportError only for a day that is not a day."""
    try:
        date.fromisoformat(imported_on)
    except (TypeError, ValueError):
        raise WordImportError("The day for this import is not a real day, so nothing was read. Choose a real date and try again.") from None
    blocks = getattr(read, "blocks", read)
    st = _Stage(file_name, imported_on, seen)
    if hasattr(read, "notes"):
        st.plan.notes.extend(read.notes)
    sec = None              # (kind, level, heading text)
    tables = 0
    for block in blocks:
        kind = block.get("kind")
        if kind == "heading":
            found = _heading_kind(block.get("text"))
            level = _int(block.get("level")) or 1
            if found:
                sec = (found, level, _heading_text(block.get("text")))
            elif sec and level <= sec[1]:
                sec = None
        elif kind == "table":
            tables += 1
            if sec:
                st.table_rows(sec[0], block, f"\"{sec[2]}\"", tables)
        elif kind in ("paragraph", "list_item"):
            if sec:
                st.text_item(sec[0], block, f"\"{sec[2]}\"")
            elif clean_value(block.get("text")):
                st.skipped_text += 1
    pl = st.plan
    if st.skipped_text:
        pl.notes.append(f"{_count(st.skipped_text, 'paragraph or list item', 'paragraphs or list items')} "
                        f"{'is' if st.skipped_text == 1 else 'are'} not under a heading for actions, risks, issues or "
                        "decisions, so " + ("it was" if st.skipped_text == 1 else "they were") + " not read.")
    if st.unread:
        pl.notes.append("These table headings are not read: " + ", ".join(sorted(st.unread)) + ".")
    if st.has_id:
        pl.notes.append(f"{_count(st.has_id, 'table line')} {'carries' if st.has_id == 1 else 'carry'} an ID, so "
                        f"{'it is an existing item' if st.has_id == 1 else 'they are existing items'}. An import never changes an "
                        f"existing item, so {'it was' if st.has_id == 1 else 'they were'} left alone.")
    if st.over:
        pl.notes.append(f"Only the first {MAX_ITEMS} items are shown; {st.over} more were not read. Put the rest in a second file.")
    if not pl.items and not pl.problems:
        pl.notes.append("Nothing new was found. Put actions, risks, issues or decisions under a heading with that name.")
    return pl
