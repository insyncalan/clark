"""People (#115): the rules and the plain words for the people list, as code with no database (BRD FR-43a, FR-43c, FR-99b).

The design note is docs/handoff/design-115-people-table.md; the owner's six answers are in
plan item #115 (all yes, 29-10-2026). This module reads nothing and writes nothing: the store takes a person's fields, the
people already on the list and a name as plain values, and gets back a verdict or a sentence. Standard library only.

What is here:
- the one email rule (also the Draft email builder's, #50): `clean_email`;
- the matching key and the resolver: `name_key`, `resolve` (exact match on a name or an alias, never fuzzy, never a guess);
- the fields of a person: `check_person` (name, label, kind, aliases, email; the Needs details flag clears when an email is added);
- how two people with the same name are told apart on screen: `show_name`;
- pasted rows for the import box: `parse_rows`, and the plan lines the import shows before anything is saved: `plan_lines`;
- the staged line a change from anyone but the owner shows (Q3): `staged_line`, `staged_buttons`, `accepted_line`;
- the prompts, toasts, refusals and history lines (FR-43a: who, what, where, when).
"""
import csv
import io
import re
import unicodedata

from clark import confusables

EMAIL_MAX = 254
LOCAL_MAX = 64
LABEL_MAX = 30
NAME_MAX = 120
KINDS = ("person", "group")
NO_PERSON = ("", "tbc")           # an owner text that is blank or TBC maps to no person and never raises the Add prompt
ID_SHAPE = re.compile(r"\AP-(\d{3})\Z")
ID_LIMIT = 999
EMAIL_BAD = set(" ,;<>()[]\"'\\?#%`")
ROW_LIMIT = 500                   # the most rows one import box takes at once
TEXT_LIMIT = 200000               # the most characters one import box takes at once (checked before the text is read as rows)

EMAIL_REFUSED = ("That email can't be used: it holds more than one address or a character that isn't allowed. "
                 "Check the address and try again.")
EMAIL_INCOMPLETE = "That email is not complete (no dot after the @). Check the address and try again."
EMAIL_TOO_LONG = "That email is too long. Check the address and try again."


def _squash(text):
    return " ".join(unicodedata.normalize("NFKC", str(text or "")).split())


# ---- the one email rule ------------------------------------------------------------------------------------------------

def clean_email(value):
    """(address, problem). The address is trimmed and lower-cased; '' (blank) is allowed, which is what Needs details is for.
    problem is '' or a plain sentence. Exactly one address: no space, comma, semicolon, angle bracket, bracket, quote, backslash,
    question mark, hash, percent or backtick; no control, invisible or direction-mark character; exactly one @; a local part of
    1 to 64 characters; a domain with a dot, no empty label and no label that starts or ends with a hyphen; 254 characters at most.
    Both the people list and the Draft email builder call this, never a check of their own."""
    raw = "" if value is None else str(value)
    text = raw.strip().lower()
    if not text:
        return "", ""
    for ch in text:
        if ch in EMAIL_BAD or ch.isspace() or unicodedata.category(ch) in ("Cc", "Cf", "Cs", "Co", "Cn", "Zs", "Zl", "Zp"):
            return "", EMAIL_REFUSED
    if len(text) > EMAIL_MAX:
        return "", EMAIL_TOO_LONG
    if text.count("@") != 1:
        return "", EMAIL_REFUSED
    local, domain = text.split("@")
    if not local or len(local) > LOCAL_MAX or not domain:
        return "", EMAIL_REFUSED
    if "." not in domain:
        return "", EMAIL_INCOMPLETE
    labels = domain.split(".")
    if any(not lab or lab.startswith("-") or lab.endswith("-") for lab in labels):
        return "", EMAIL_REFUSED
    return text, ""


def email_row_problem(row_number, problem):
    """The same refusal for a pasted row: 'Row 7: ...' with the same next step."""
    if not problem:
        return ""
    return f"Row {row_number}: {problem[0].lower()}{problem[1:]}"


# ---- matching ----------------------------------------------------------------------------------------------------------

def name_key(text):
    """The key a name or alias is matched on: NFKC, casefold, whitespace collapsed, then the repo's reading of text
    (confusables.skeleton) so accents and look-alike letters are treated as everywhere else. '' for blank."""
    return confusables.skeleton(_squash(text).casefold()).casefold()


def aliases_of(person):
    """A person's aliases as a list (';'-separated text, like workstreams.aliases), without blanks or repeats."""
    seen, out = set(), []
    for part in str(person.get("aliases") or "").split(";"):
        part = _squash(part)
        if part and name_key(part) not in seen:
            seen.add(name_key(part))
            out.append(part)
    return out


def join_aliases(aliases):
    out, seen = [], set()
    for a in aliases:
        a = _squash(a)
        if a and name_key(a) not in seen:
            seen.add(name_key(a))
            out.append(a)
    return ";".join(out)


def keys_of(person):
    """Every key a person answers to: the name and each alias."""
    return {k for k in [name_key(person.get("name"))] + [name_key(a) for a in aliases_of(person)] if k}


def resolve(text, people):
    """What a typed owner name points at. Returns a dict with status and ids:
      'blank'    - blank or TBC: no person, and no prompt;
      'one'      - exactly one live person; id is theirs;
      'many'     - two or more live people (ids): no link, and the sentence from `two_matches`;
      'archived' - no live person but an archived one (ids): the prompt offers Restore;
      'none'     - no one: the text stays as typed.
    Exact match on the key of the name or any alias. Never fuzzy. Never a guess."""
    key = name_key(text)
    if key in NO_PERSON:
        return {"status": "blank", "id": None, "ids": []}
    live = [p["id"] for p in people if not p.get("archived") and key in keys_of(p)]
    if len(live) == 1:
        return {"status": "one", "id": live[0], "ids": live}
    if live:
        return {"status": "many", "id": None, "ids": live}
    gone = [p["id"] for p in people if p.get("archived") and key in keys_of(p)]
    if gone:
        return {"status": "archived", "id": None, "ids": gone}
    return {"status": "none", "id": None, "ids": []}


def alias_holders(alias, people, own_id=None):
    """The other live people who already have this alias (or this name): the alias clash warning is shown when it is not empty."""
    key = name_key(alias)
    return [p for p in people if not p.get("archived") and p["id"] != own_id and key in keys_of(p)]


def show_name(person, people):
    """The name as shown in a list or a picker: followed by the label, or the email if there is no label, whenever another live
    person has the same name. Otherwise just the name."""
    name = _squash(person.get("name"))
    same = [p for p in people if not p.get("archived") and p["id"] != person["id"] and name_key(p.get("name")) == name_key(name)]
    if not same:
        return name
    extra = _squash(person.get("label")) or (person.get("email") or "")
    return f"{name} ({extra})" if extra else name


# ---- a person's fields -------------------------------------------------------------------------------------------------

def check_person(fields, people=(), own_id=None):
    """Check a person before the store writes them. fields: name, email, organisation, role, label, aliases, kind. Returns
    (clean, problems): clean is the fields as they will be stored (email lower-cased, needs_details cleared when an email is
    there, aliases joined), problems is a list of plain sentences (empty when fine). A name need not be unique; an email is."""
    problems = []
    name = _squash(fields.get("name"))
    if not name:
        problems.append("Give the person a name.")
    elif len(name) > NAME_MAX:
        problems.append(f"The name is too long (at most {NAME_MAX} characters).")
    label = _squash(fields.get("label"))
    if len(label) > LABEL_MAX:
        problems.append(f"The label is too long (at most {LABEL_MAX} characters).")
    kind = fields.get("kind") or "person"
    if kind not in KINDS:
        problems.append("Choose person or team.")
    email, bad = clean_email(fields.get("email"))
    if bad:
        problems.append(bad)
    elif email:
        for p in people:
            if p["id"] != own_id and (p.get("email") or "").strip().lower() == email:
                problems.append(duplicate_email(p.get("name")))
                break
    aliases = aliases_of({"aliases": fields.get("aliases") if not isinstance(fields.get("aliases"), (list, tuple))
                          else ";".join(fields["aliases"])})
    clean = {"name": name, "email": email or None, "organisation": _squash(fields.get("organisation")) or None,
             "role": _squash(fields.get("role")) or None, "label": label or None, "aliases": join_aliases(aliases) or None,
             "kind": kind, "needs_details": 0 if email else (1 if fields.get("needs_details") else 0)}
    return clean, problems


def next_person_id(ids):
    """P-001 style: one more than the largest number over every person ever made (archived ones included, so a number is never
    reused). Raises ValueError past P-999."""
    top = 0
    for i in ids:
        m = ID_SHAPE.match(str(i))
        if m:
            top = max(top, int(m.group(1)))
    if top >= ID_LIMIT:
        raise ValueError("There is no room for another person on the list.")
    return f"P-{top + 1:03d}"


# ---- the import box ----------------------------------------------------------------------------------------------------

COLUMNS = ("name", "email", "organisation", "role", "aliases", "label", "kind")
HEAD_WORDS = {"name": "name", "email": "email", "e-mail": "email", "organisation": "organisation", "organization": "organisation",
              "role": "role", "aliases": "aliases", "alias": "aliases", "label": "label", "kind": "kind", "type": "kind"}


def parse_rows(text):
    """Rows pasted from Excel (tab-separated) or a CSV file. A first row that names columns sets the order; otherwise the order
    is COLUMNS. Returns (rows, problems): each row a dict with its 'row' number (1 is the first row of data), the checked fields
    ('clean') and its problems; problems is a list of 'Row n: ...' sentences naming the row. A refused row is named, the other
    rows still stand (the plan decides). Dedupe is the store's: on email, then on name or alias."""
    raw = str(text or "")
    if not raw.strip():
        return [], ["Paste at least one row."]
    if len(raw) > TEXT_LIMIT:
        return [], [f"That is too much text to import at once. Paste at most {ROW_LIMIT} rows at a time."]
    dialect = csv.excel_tab if raw.count("\t") >= raw.count(",") else csv.excel
    lines = [r for r in csv.reader(io.StringIO(raw), dialect) if any(c.strip() for c in r)]
    order = list(COLUMNS)
    if lines and {HEAD_WORDS.get(c.strip().lower()) for c in lines[0]} - {None}:
        order = [HEAD_WORDS.get(c.strip().lower()) for c in lines[0]]
        lines = lines[1:]
    if len(lines) > ROW_LIMIT:
        return [], [f"That is more than {ROW_LIMIT} rows. Paste fewer rows at a time."]
    rows, problems, seen_emails = [], [], set()
    for n, cells in enumerate(lines, start=1):
        fields = {col: cells[i] for i, col in enumerate(order) if col and i < len(cells)}
        clean, bad = check_person(fields)
        msgs = [email_row_problem(n, b) if b in (EMAIL_REFUSED, EMAIL_INCOMPLETE, EMAIL_TOO_LONG) else f"Row {n}: {b}" for b in bad]
        if clean["email"] and clean["email"] in seen_emails:
            msgs.append(f"Row {n}: that email is already on an earlier row. Check the address and try again.")
        if clean["email"]:
            seen_emails.add(clean["email"])
        rows.append({"row": n, "clean": clean, "problems": msgs})
        problems.extend(msgs)
    return rows, problems


def plan_lines(matched=0, many=(), unmatched=()):
    """The plan an Excel import of work items shows before anything is saved. many and unmatched are lists of what was typed
    (for many, (typed, [shown names])). Each line only when its count is above 0."""
    out = []
    if matched:
        out.append(f"{matched} item{'s' if matched != 1 else ''} now point{'' if matched != 1 else 's'} at a person.")
    if many:
        names = ", ".join(f"{t} ({', '.join(who)})" for t, who in many)
        out.append(f"{len(many)} owner name{'s' if len(many) != 1 else ''} match{'' if len(many) != 1 else 'es'} more than one "
                   f"person and will be saved as typed: {names}.")
    if unmatched:
        out.append(f"{len(unmatched)} owner name{'s are' if len(unmatched) != 1 else ' is'} not on the people list and will be "
                   f"saved as typed: {', '.join(unmatched)}.")
    if unmatched or many:
        out.append("Pick a choice beside a name if you want one: Same person as …, Add as new person, or Keep the name only.")
    out.append("Nothing is saved until you press Import. Reply Import or Cancel.")
    return out


# ---- prompts, refusals and toasts --------------------------------------------------------------------------------------

def _n(count, one, many=None):
    return f"{count} {one if count == 1 else (many or one + 's')}"


def add_prompt(name):
    return f"Add {name} as a new person?"


ADD_BUTTONS = ("Add person", "Keep the name only")


def archived_prompt(name):
    return f"{name} is archived. Restore {name} and use this name?"


def archived_buttons(name):
    return (f"Restore {name}", "Keep the name only")


def two_matches(typed, shown):
    """The sentence under the owner box when a name matches two or more people; shown is their names as show_name gives them."""
    return (f"{typed} matches {_listed(shown)}. The name is saved as typed and not tied to either person." if len(shown) == 2
            else f"{typed} matches {_listed(shown)}. The name is saved as typed and not tied to any of them.")


TWO_MATCH_BUTTONS = ("Use this one", "Keep the name only")


def _listed(names):
    names = list(names)
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def merge_prompt(source, target, items):
    return (f"Merge {source} into {target}? {_n(items, 'item')} will show {target}, and {source} will be archived. "
            "You can undo this.")


def rename_prompt(old, new, items, projects):
    return f"Rename {old} to {new}? {_n(items, 'item')} in {_n(projects, 'project')} will show {new}. You can undo this."


def archive_prompt(name, open_items):
    owns = f" {name} still owns {_n(open_items, 'open item')} and they keep the name too." if open_items else ""
    return f"Archive {name}? Old items keep the name.{owns} You can restore {name} later."


def match_prompt(linked, many, none):
    return (f"This will link {_n(linked, 'item')} to a person. {_n(many, 'item')} match{'es' if many == 1 else ''} more than one "
            f"person and {none} match{'es' if none == 1 else ''} no one; they are left as typed. Nothing else changes, and you can undo it.")


def alias_clash(alias, holder, other):
    return (f"{alias} is already an alias of {holder}. Use it for {other} as well? Then \"{alias}\" will match both and will be "
            "saved as typed until the user picks one.")


def duplicate_email(owner):
    return f"That email already belongs to {owner}. Check the address, or open {owner} to change it."


def restore_without_email(name, email, holder):
    return (f"{name} is restored without an email: {email} now belongs to {holder}. Add a new email on the People list.")


def rename_toast(new, items, projects, archived=0):
    left = f" (and left {_n(archived, 'archived item')} as they were)" if archived else ""
    return f"Renamed to {new} on {_n(items, 'item')} in {_n(projects, 'project')}{left}. Undo."


def merge_toast(source, target, items):
    return f"Merged {source} into {target}. {_n(items, 'item')} now show{'s' if items == 1 else ''} {target}. Undo."


def archive_toast(name, open_items):
    owns = f" {name} still owns {_n(open_items, 'open item')}; they keep the name." if open_items else ""
    return f"{name} archived.{owns} Restore from the Archived list. Undo."


UNDO_BUTTON = "Undo last people change"


def undo_refused_later(kind, name):
    return f"Can't undo the {kind} of {name}: the person was changed again afterwards. Undo that change first."


def merged_away(source, target):
    return f"{source} was merged into {target}. Undo the merge first."


OWNER_RENAMED_AFTER = "The owner was renamed after this change. Undo the rename first."
PRIVACY_NOTE = "Saving a person's email sends nothing and needs no login; clark only drafts mail and never sends it."


# ---- history lines (FR-43a: who, how, when) ----------------------------------------------------------------------------

def stamp(at):
    """'YYYY-MM-DD HH:MM[:SS]' as '29-10-2026 at 14:05'; '' when it is not a date and time."""
    m = re.match(r"\A(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})", str(at or ""))
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)} at {m.group(4)}:{m.group(5)}" if m else ""


def _made(by, at, place="on the People list"):
    return f"Made by {by}, {place}, {stamp(at)}."


def history_line(kind, name, by, at, new=None, items=0, projects=0, aliases=0, source=None):
    """One history line for a people step. kind: add, edit, rename, merge, archive, restore, undo-rename, undo-merge, import,
    match. `by` is the user's full name."""
    made = _made(by, at)
    if kind == "rename":
        return f"{name} renamed to {new}. {made} {_n(items, 'item')} in {_n(projects, 'project')} now show {new}."
    if kind == "merge":
        return f"{name} merged into {new}. {made} {_n(items, 'item')} now show{'s' if items == 1 else ''} {new}; {_n(aliases, 'alias', 'aliases')} moved."
    if kind == "archive":
        return f"{name} archived. {made} Old items keep the name."
    if kind == "restore":
        return f"{name} restored. {made}"
    if kind == "add":
        return f"{name} added. {made}"
    if kind == "edit":
        return f"{name} changed. {made}"
    if kind.startswith("undo-"):
        return f"{kind[5:].capitalize()} of {name} undone. {made}"
    if kind == "match":
        return f"{_n(items, 'item')} matched to people. {made}"
    raise ValueError(kind)


def owner_line(old, new, by, at, why="renamed", target=None):
    """The line on an item whose owner text a rename or merge changed. why: 'renamed' or 'merged' (then target names the person)."""
    reason = "the person was renamed" if why == "renamed" else f"{old} was merged into {target or new}"
    return f"Owner changed from {old} to {new} because {reason}. {_made(by, at)}"


# ---- a change from anyone but the owner (the owner's answer to question 3): staged, never applied ------------------------------------

STAGED_FIELDS = ("name", "email", "organisation", "role", "label", "aliases", "kind")
FIELD_WORDS = {"name": "name", "email": "email", "organisation": "organisation", "role": "role", "label": "label",
               "aliases": "aliases", "kind": "kind"}


def staged_line(proposer, person, field, old, new):
    """What the owner is shown for one staged change: who proposed it, what it changes, from to. Nothing has changed yet."""
    was = old if old else "nothing"
    now = new if new else "nothing"
    return f"{proposer} proposes to change {person}'s {FIELD_WORDS.get(field, field)} from {was} to {now}. Nothing has changed yet."


def staged_new_line(proposer, name):
    return f"{proposer} proposes to add {name} to the people list. Nothing has changed yet."


STAGED_BUTTONS = ("Accept", "Reject")


def staged_buttons():
    return STAGED_BUTTONS


def accepted_line(proposer, accepter, how, at, rejected=False, what=""):
    """The history line for a staged change: who proposed it, who accepted (or rejected) it, how and when (FR-43a). how is where it
    reached the owner, e.g. 'in a teammate's changes file' or 'on the People list'."""
    verb = "rejected" if rejected else "accepted"
    proposed = f"proposed {what}" if what else "proposed it"
    return f"{proposer} {proposed}; {accepter} {verb} it {how}, {stamp(at)}."


def may_apply_directly(by, owner):
    """True only for the owner. Anyone else's people change is staged (Q3). Until #61 and #62 exist the owner is the only
    one who can change the list in practice."""
    return bool(by) and by == owner
