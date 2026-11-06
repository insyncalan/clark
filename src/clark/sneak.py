"""Sneak peek's reader (#42): typed words about one work item become from → to changes, by plain code. No model, no network, no
process, no store: it reads one project's data (the rows the page already has) and the words, and writes nothing. Applying what it
finds is a separate step that goes through the change route (#65, #68), never here.

Written for clark; the idea (words in, from → to out, a confirm for the changes that matter) follows creaite's sneak_peek.py at
v2.6.9, with none of its code.

Reads: a due date ("Friday", "tomorrow", "30-10-2026", "2026-10-30"), an owner ("owner Jo Ellis", "assign to Jo Ellis"), a priority
("high priority") and a status ("done", "cancel", "reopen", "delayed"), for an action, a risk, an issue or a decision. A date that
is not a real day is refused in plain words and nothing is offered.

Also reads a milestone (its forecast date, its achieved date and its status: Achieved or Planned) and a use case (its status, its
headline and its commitment word), by the same rules: nothing is written here, a change that is final asks first, and the words a
person reads that are new for these are all in WORDS.
"""
import os
import re
import unicodedata
from datetime import date, datetime, timedelta

from clark.changes import (ACHIEVED_DATE, ARCHIVED_MILESTONE, ARCHIVED_USE_CASE, NO_PROJECT, UC_COMMITMENTS, UC_COMMITMENT_WORDS,
                           UC_HEADLINE_WORDS, Refused, _checked_use_case_changes)
from clark.edit_ai import unseen

TABLES = (("actions", "action"), ("raid", None), ("decisions", "decision"))
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
PRIORITIES = {"urgent": "Urgent", "high": "High", "medium": "Medium", "low": "Low"}
LABELS = {"due_date": "Due", "needed_by": "Needed by", "date": "Date", "owner": "Owner", "priority": "Priority", "status": "Status"}
CONFIRM_STATUS = {"Cancelled", "Closed", "Made", "Withdrawn"}          # creaite's list, as far as it applies here (Open 1 on #42)
MAX_WORDS = 400
NUMERIC_DATE = re.compile(r"\b(\d{1,2})-(\d{1,2})-(\d{4})\b|\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
OWNER = re.compile(r"\b(?:owner(?:\s+is)?|assign(?:ed)?\s+to|owned\s+by|give\s+(?:it\s+)?to)\s+([^,;.]+?)(?=\s+(?:and|with|due|by|priority|(?:urgent|high|medium|low)\s+priority)\b|[,;]|\.\s|\.$|$)", re.I)
BAD_DATE = "That date isn't a real day, so nothing was changed. Check the day and month."
NOTHING = ("I couldn't find a change in that. Here I can change the due date, the owner, the priority and the status. "
           "Try, for example, “move to Friday, owner Jo Ellis, high priority”.")
ARCHIVE = re.compile(r"\barchiv\w*\b", re.I)
DELETE = re.compile(r"\bdelet\w*\b", re.I)
NO_ARCHIVE = "An item can't be archived from here. Archiving isn't available from the page yet. Nothing was changed."
NO_DELETE = "Nothing is removed here. To take an item out of the lists, archive it from its row. Nothing was changed."
BAD_NAME = "I can't use that as a person's name, so nothing was changed. Type a name, for example “owner Jo Ellis”."
UNSURE_STATUS = "I can't tell which status you mean, so nothing was changed. Say one status, without “not”, for example “done” or “reopen”."
NEEDS_DATE = "A decision that is made needs the day it was made. Add a date, for example “made on 30-10-2026”."
BAD_YEAR = "That year looks wrong, so nothing was changed. Type a year between 2000 and 2100."
# Every sentence a person reads that is new for a milestone or a use case (the rest are the work items' own, or changes.py's).
WORDS = {
    "hidden": "That {what} is hidden from the client (its eye is off), so nothing was changed. Turn its eye on first.",
    "nothing_milestone": "I couldn't find a change in that. Here I can change a milestone's forecast date, achieved date and status. "
                         "Try, for example, “forecast Friday” or “achieved yesterday”.",
    "nothing_use_case": "I couldn't find a change in that. Here I can change a use case's status, headline and commitment. "
                        "Try, for example, “flag, committed” or “headline: Go-live is on plan”.",
    "agreed_date": "Moving the agreed date needs who agreed it and why, so it can't be done here. Nothing was changed.",
    "no_cancel": "A milestone can't be cancelled from here. Nothing was changed.",
    "owner_left_out": "A milestone's owner can't be changed here, so it was left out.",
    "labels": {"forecast_date": "Forecast", "actual_date": "Achieved date", "headline": "Headline", "commitment": "Commitment"},
    "achieved": "Achieved",
    "no_flag": "No flag",
}
NEGATION = re.compile(r"\b(not|never|no|nothing|neither|nor|without|unless|cannot|ain'?t|\w+n't|(?:don|doesn|didn|isn|wasn|aren|weren|won|can|couldn|shouldn|wouldn|mustn|hasn|haven|hadn)t)\b", re.I)
NOT_NAMES = {"is", "to", "by", "tbc", "tba", "tbd", "none", "nobody", "unknown", "n/a", "na", "null", "nil"}
ITEM_ID = re.compile(r"[A-Z][A-Z0-9]{0,6}-(?:[A-Z]-)?\d+", re.I)
TWO_DATES = "I can't tell which day you mean, so nothing was changed. Give one day."
TOO_LONG = "That is too long. Use a sentence or two."


def today():
    """Today's date: CLARK_NOW (a date, or a date and time) when set, else the real day."""
    text = (os.environ.get("CLARK_NOW") or "").strip()[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return date.today()


def find_item(data, item_id):
    """(kind, row) for a work item in one project's data, or (None, None)."""
    for table, fixed in TABLES:
        for row in data.get(table) or []:
            if row.get("id") == item_id:
                return (fixed or str(row.get("type", "")).lower()), row
    return None, None


def _day(y, m, d):
    try:
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def dates_in(words, now):
    """([date, ...] found, True if one of them is not a real day). Numeric dates (DD-MM-YYYY or YYYY-MM-DD) and day words."""
    found, bad = [], False
    for m in NUMERIC_DATE.finditer(words):
        d = _day(m.group(3), m.group(2), m.group(1)) if m.group(1) else _day(m.group(4), m.group(5), m.group(6))
        if d is None:
            bad = True
        else:
            found.append(d)
    plain = NUMERIC_DATE.sub(" ", words.lower())
    if re.search(r"\btoday\b", plain):
        found.append(now)
    if re.search(r"\byesterday\b", plain):
        found.append(now - timedelta(days=1))
    if re.search(r"\btomorrow\b", plain):
        found.append(now + timedelta(days=1))
    for i, name in enumerate(DAYS):
        if re.search(r"\b" + name + r"\b", plain):
            found.append(now + timedelta(days=(i - now.weekday()) % 7 or 7))        # the next one, never today
    return found, bad


def clean_name(text):
    """A typed name with every character a reader cannot see gone (controls, direction marks, zero-width and line separators:
    Cc, Cf, Zl, Zp), spaces made single, at most 60 characters; "" when nothing usable is left (no letter or digit, a word like
    "is" or "TBC", or an item ID)."""
    kept = "".join(c for c in unseen(text) if unicodedata.category(c) not in ("Cc", "Cf", "Zl", "Zp"))
    name = " ".join(kept.split())[:60].strip()
    while name and unicodedata.category(name[0])[0] in "PS":            # quotes, symbols and emoji around the name
        name = name[1:].lstrip()
    while name and unicodedata.category(name[-1])[0] in "PS":
        name = name[:-1].rstrip()
    if not any(c.isalnum() for c in name) or name.lower().strip(". ") in NOT_NAMES or any(ITEM_ID.fullmatch(w) for w in name.split()):
        return ""
    return name


def _dmy(iso):
    m = re.fullmatch(r"(\d{4})-(\d\d)-(\d\d)", iso or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else (iso or "—")


def _statuses_for(words, kind):
    """The set of statuses the words ask for (empty: none)."""
    w = words.lower()
    got = set()
    if kind == "decision":
        if re.search(r"\b(withdraw|withdrawn)\b", w):
            got.add("Withdrawn")
        if re.search(r"\b(made|decided|approve[d]?)\b", w):
            got.add("Made")
        if re.search(r"\b(pending|reopen|re-open)\b", w):
            got.add("Pending")
        return got
    if re.search(r"\b(cancel|cancelled|canceled)\b", w):
        got.add("Cancelled")
    if re.search(r"\b(done|close|closed|complete|completed|finished)\b", w):
        got.add("Closed")
    if re.search(r"\b(reopen|re-open|open again)\b", w):
        got.add("Open")
    if re.search(r"\bdelayed\b", w):
        got.add("Delayed")
    return got


def _owners(data):
    """Everyone who owns something in the project's data: action and RAID owners, who made each decision, milestone owners."""
    names = set()
    for table, field in (("actions", "owner"), ("raid", "owner"), ("decisions", "made_by"), ("milestones", "owner")):
        names.update(str(r.get(field)).strip().casefold() for r in data.get(table) or [] if isinstance(r, dict) and r.get(field))
    return names


def read(data, item_id, words, now=None, known_owners=None, archived=None):
    """Read `words` about one item. Returns {"ok": True, "id", "changes": [{field, label, from, to, from_text, to_text, confirm,
    new_name}], "confirm": bool, "note": text} or {"ok": False, "message": plain words}. Nothing is written. `archived` is a function giving the
    project's archived rows (the same shape as `data`), asked only when the item is not among the live ones."""
    now = now or today()
    if not isinstance(words, str) or not words.strip():
        return {"ok": False, "message": NOTHING}
    if len(words) > MAX_WORDS:
        return {"ok": False, "message": TOO_LONG}
    data = data if isinstance(data, dict) else {}
    kind, row = find_item(data, item_id)
    if row is None:
        for table, kind_, reader in (("milestones", "milestone", read_milestone), ("use_cases", "use case", read_use_case)):
            mine = next((r for r in data.get(table) or [] if isinstance(r, dict) and r.get("id") == item_id), None)
            if mine is not None:
                if table == "milestones" and item_id in (data.get("report_hidden") or []) or table == "use_cases" and not mine.get("client_visible", 1):
                    return {"ok": False, "message": WORDS["hidden"].format(what=kind_)}
                return reader(data, mine, words, now)
        gone = archived() if callable(archived) else None
        if gone and any(isinstance(r, dict) and r.get("id") == item_id for r in gone.get("milestones") or []):
            return {"ok": False, "message": ARCHIVED_MILESTONE}
        if gone and any(isinstance(r, dict) and r.get("id") == item_id for r in gone.get("use_cases") or []):
            return {"ok": False, "message": ARCHIVED_USE_CASE}
        return {"ok": False, "message": "That item isn't in this project any more. Reload the page."}
    changes, notes, same = [], [], []

    def add(field, new, text=None, confirm=False, new_name=False):
        old = row.get(field)
        if new == old:
            same.append(f"The {LABELS[field].lower()} is already {text or new}.")
            return
        changes.append({"field": field, "label": LABELS[field], "from": old, "to": new,
                        "from_text": _dmy(old) if field in ("due_date", "needed_by", "date") else (old or "—"),
                        "to_text": text or new, "confirm": confirm, "new_name": new_name})

    m = OWNER.search(words)
    rest = (words[:m.start()] + " " + words[m.end():]) if m else words        # the owner's name is not scanned for dates, statuses or priorities
    found, bad = dates_in(rest, now)
    if bad:
        return {"ok": False, "message": BAD_DATE}
    if any(not 2000 <= d.year <= 2100 for d in found):
        return {"ok": False, "message": BAD_YEAR}
    statuses = _statuses_for(rest, kind)
    if len(statuses) > 1 or (statuses and NEGATION.search(rest.replace("’", "'"))):
        return {"ok": False, "message": UNSURE_STATUS}
    status = next(iter(statuses), None)
    current = row.get("status")
    if status == "Pending" and current == "Made":
        return {"ok": False, "message": "A decision that has been made can't go back to pending. Record a new decision that replaces it."}
    if status == "Delayed" and kind != "action":
        return {"ok": False, "message": "Only an action can be delayed."}
    if len(set(found)) > 1:
        return {"ok": False, "message": TWO_DATES}
    if found:
        when = found[0]
        text = _dmy(when.isoformat())
        if kind == "decision" and (status or current) == "Made":
            if status == "Made":
                if when > now:
                    notes.append(f"{text} hasn't come yet. Check it is the day the decision was made.")
                add("date", when.isoformat(), text)               # the day it was made
            else:
                notes.append("A decision that is made has no due date, so the date was left out.")
        elif kind == "decision" and (status or current) == "Withdrawn":
            notes.append("A withdrawn decision has no due date, so the date was left out.")
        else:
            add("needed_by" if kind == "decision" else "due_date", when.isoformat(), text)
        if when < now and status != "Made":
            notes.append(f"{text} is in the past.")
        elif re.search(r"\b(today|yesterday|tomorrow|" + "|".join(DAYS) + r")\b", NUMERIC_DATE.sub(" ", rest.lower())):
            notes.append(f"Read as {text}.")
    if status == "Made" and kind == "decision" and not row.get("date") and not any(c["field"] == "date" for c in changes):
        return {"ok": False, "message": NEEDS_DATE}
    if m:
        name = clean_name(m.group(1))
        if not name:
            return {"ok": False, "message": BAD_NAME}
        if kind == "decision":
            notes.append("A decision's owner is who made it; that is not changed here.")
        else:
            known = known_owners if known_owners is not None else _owners(data)
            add("owner", name, name, new_name=name.casefold() not in {str(k).casefold() for k in known})
    p = re.search(r"\b(urgent|high|medium|low)\s+priority\b|\bpriority\s+(?:is\s+|to\s+)?(urgent|high|medium|low)\b", rest.lower())
    if p:
        if kind not in ("action", "decision"):
            notes.append("A risk's, issue's or other register item's priority comes from its impact and likelihood, so it was left out.")
        elif kind == "decision":
            notes.append("A decision has no priority, so it was left out.")
        else:
            add("priority", PRIORITIES[p.group(1) or p.group(2)])
    if status:
        add("status", status, confirm=status in CONFIRM_STATUS)
    if DELETE.search(rest):
        if not changes:
            return {"ok": False, "message": NO_DELETE}
        notes.append("Nothing is removed here (archive the item from its row instead), so that part was left out.")
    if ARCHIVE.search(rest):
        if not changes:
            return {"ok": False, "message": NO_ARCHIVE}
        notes.append("An item can't be archived from here, so that part was left out. Archiving isn't available from the page yet.")
    if not changes:
        return {"ok": False, "message": " ".join(notes + same + ([] if notes or same else [NOTHING]))}
    return {"ok": True, "id": item_id, "changes": changes, "confirm": any(c["confirm"] for c in changes), "note": " ".join(notes)}


def _line(row, field, new, text=None, confirm=False, from_text=None):
    """One from → to line for a milestone or a use case, or None when the value is already that."""
    old = row.get(field)
    if new == old:
        return None
    label = WORDS["labels"].get(field) or LABELS.get(field) or field.capitalize()
    dated = field in ("forecast_date", "actual_date")
    return {"field": field, "label": label, "from": old, "to": new, "from_text": from_text if from_text is not None else (_dmy(old) if dated else (old or "—")),
            "to_text": text or (_dmy(new) if dated else new), "confirm": confirm, "new_name": False}


def _prepare(words, now):
    """The checks both new readers start with: (message or None, the owner match, the words without the owner's name, the days found)."""
    if not isinstance(words, str) or not words.strip():
        return None, None, "", []
    if len(words) > MAX_WORDS:
        return TOO_LONG, None, "", []
    m = OWNER.search(words)
    rest = (words[:m.start()] + " " + words[m.end():]) if m else words
    found, bad = dates_in(rest, now)
    if bad:
        return BAD_DATE, m, rest, []
    if any(not 2000 <= d.year <= 2100 for d in found):
        return BAD_YEAR, m, rest, []
    if len(set(found)) > 1:
        return TWO_DATES, m, rest, []
    return None, m, rest, found


def _done(out, notes, same, key):
    if not out:
        return {"ok": False, "message": " ".join(notes + same + ([] if notes or same else [WORDS[key]]))}
    return {"ok": True, "changes": out, "confirm": any(c["confirm"] for c in out), "note": " ".join(notes)}


def read_milestone(data, row, words, now):
    """Words about one milestone: its forecast date, achieved date and status. The agreed date and the owner are not changed here."""
    if not isinstance(words, str) or not words.strip():
        return {"ok": False, "message": WORDS["nothing_milestone"]}
    bad, owner, rest, found = _prepare(words, now)
    if bad:
        return {"ok": False, "message": bad}
    low = rest.lower()
    if re.search(r"\b(agreed|baseline|rebaseline)\b", low):
        return {"ok": False, "message": WORDS["agreed_date"]}
    if re.search(r"\b(cancel|cancelled|canceled)\b", low):
        return {"ok": False, "message": WORDS["no_cancel"]}
    got = set()
    if re.search(r"\b(done|achieved|complete|completed|finished|reached)\b", low):
        got.add("Done")
    if re.search(r"\b(reopen|re-open|open again|planned)\b", low):
        got.add("Planned")
    if len(got) > 1 or (got and NEGATION.search(rest.replace("’", "'"))):
        return {"ok": False, "message": UNSURE_STATUS}
    status = next(iter(got), None)
    current = row.get("status") or "Planned"
    target = status or current
    out, notes, same = [], [], []
    target_is_forecast = bool(re.search(r"\bforecast\b", low))

    def put(line, said):
        if line is None:
            same.append(said)
        else:
            out.append(line)
    if found:
        when, text = found[0], _dmy(found[0].isoformat())
        if target == "Done" and not re.search(r"\bforecast\b", low):
            if when > now:
                return {"ok": False, "message": ACHIEVED_DATE}
            put(_line(row, "actual_date", when.isoformat()), f"The achieved date is already {text}.")
        else:
            put(_line(row, "forecast_date", when.isoformat()), f"The forecast is already {text}.")
            if when < now:
                notes.append(f"{text} is in the past.")
        if re.search(r"\b(today|yesterday|tomorrow|" + "|".join(DAYS) + r")\b", NUMERIC_DATE.sub(" ", low)):
            notes.append(f"Read as {text}.")
    if status and status != current:                    # the store fills or clears the achieved date with the status; it is said here so the lines show it
        shown = {"Done": WORDS["achieved"], "Planned": "Planned"}
        out.append(_line(row, "status", status, shown[status], confirm=status == "Done" or current == "Done", from_text=shown.get(current, current)))
        if status == "Done" and not found and not row.get("actual_date"):
            fc = row.get("forecast_date")
            out.append(_line(row, "actual_date", fc if fc and fc <= now.isoformat() else now.isoformat()))
        elif status == "Done" and found and target_is_forecast and not row.get("actual_date"):
            out.append(_line(row, "actual_date", now.isoformat()))      # "done, forecast Friday": the store still sets the achieved date, so the lines show it
        elif status == "Planned" and row.get("actual_date"):
            out.append(_line(row, "actual_date", None, "—"))
    elif status:
        same.append(f"The status is already {WORDS['achieved'] if status == 'Done' else status}.")
    if owner:
        notes.append(WORDS["owner_left_out"])
    r = _done([c for c in out if c], notes, same, "nothing_milestone")
    if r["ok"]:
        r["id"] = row.get("id")
    return r


COMMIT_WORDS = (("Planned 2027", re.compile(r"\bplanned\s+(?:for\s+)?2027\b", re.I)), ("Candidate", re.compile(r"\bcandidate\b", re.I)),
                ("Committed", re.compile(r"\bcommitted\b", re.I)))
NO_COMMIT = re.compile(r"\bno\s+(?:flag|commitment)\b|\b(?:clear|remove|drop|unset)\s+(?:the\s+)?(?:flag|commitment)\b", re.I)
HEADLINE_QUOTED = re.compile(r"\bheadline\b\s*(?:\b(?:is|to|as)\b|[:=])?\s*(?:\"([^\"]*)\"|“([^”]*)”)", re.I)
HEADLINE_PLAIN = re.compile(r"\bheadline\b\s*(?:\b(?:is|to|as)\b|[:=])\s*(.+)$", re.I | re.S)
USE_CASE_STATUS = (("High risk", r"\bhigh[- ]risk\b|\bred\b"), ("On track", r"\bon[- ]track\b|\bgreen\b"),
                   ("Flag", r"\b(?:flag|flagged|amber)\b"), ("Done", r"\b(?:done|complete|completed|finished)\b"))


def read_use_case(data, row, words, now):
    """Words about one use case: its status (On track, Flag, High risk, Done), its headline and its commitment word."""
    if not isinstance(words, str) or not words.strip():
        return {"ok": False, "message": WORDS["nothing_use_case"]}
    if len(words) > MAX_WORDS:
        return {"ok": False, "message": TOO_LONG}
    rest, head = words, None
    for rx in (HEADLINE_QUOTED, HEADLINE_PLAIN):
        h = rx.search(rest)
        if h:
            head = next((g for g in h.groups() if g is not None), "").strip()
            rest = rest[:h.start()] + " " + rest[h.end():]
            break
    marks = [word for word, rx in COMMIT_WORDS if rx.search(rest)]
    clear = bool(NO_COMMIT.search(rest))
    if len(marks) + clear > 1:
        return {"ok": False, "message": UC_COMMITMENT_WORDS}
    for _, rx in COMMIT_WORDS:
        rest = rx.sub(" ", rest)
    rest = NO_COMMIT.sub(" ", rest)
    low = rest.lower()
    got = {name for name, rx in USE_CASE_STATUS if re.search(rx, low)}
    if got == {"Flag", "High risk"}:                    # "flag it as high risk": the risk is the status, the flag is the verb
        got.discard("Flag")
    if len(got) > 1 or (got and NEGATION.search(rest.replace("’", "'"))):
        return {"ok": False, "message": UNSURE_STATUS}
    values = {}
    if head:
        values["headline"] = head
    if got:
        values["status"] = next(iter(got))
    if marks or clear:
        values["commitment"] = marks[0] if marks else None
    try:
        values = _checked_use_case_changes(values)
    except Refused as e:
        return {"ok": False, "message": e.message}
    out, same = [], []
    for field in ("status", "headline", "commitment"):
        if field not in values:
            continue
        new = values[field]
        none = WORDS["no_flag"]
        line = _line(row, field, new, new or none, confirm=field == "status" and new == "Done",
                     from_text=(row.get(field) or (none if field == "commitment" else "—")))
        if line is None:
            same.append(f"The {WORDS['labels'].get(field, field).lower()} is already {new or none}.")
        else:
            out.append(line)
    r = _done(out, [], same, "nothing_use_case")
    if r["ok"]:
        r["id"] = row.get("id")
    return r


def make_read(data_for):
    """The seam the server calls for POST /api/sneak/read: `read(req)` -> (status, body). `data_for(code)` is the store's read of
    one project (None when there is none). The server has checked the request's shape."""
    def seam(req):
        data = data_for(req["project"])
        if data is None:
            return 404, {"ok": False, "message": NO_PROJECT, "code": "project_not_found"}
        return 200, read(data, req["id"], req["text"], archived=lambda: data_for(req["project"], "only"))
    return seam
