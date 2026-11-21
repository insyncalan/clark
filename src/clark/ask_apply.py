"""ask clark's dry run and Apply (#47e part 1). Unguarded; it never opens the database for writing.

A change the answer suggests (ask.read_reply's `changes`: one flat object each, from the model) is only a suggestion. Here it is
turned into a request in /api/change's form, checked against the saved data, and shown as a dry run: the row before and after,
both read from the data by changes.make_ask_change inside a step that is always rolled back. The model's words are never shown
as the before or the after. Apply saves exactly what the dry run showed, as one undoable step (route "assistant", actor
"clark", "via ask clark" in history), through the same changes.py path as a hand edit.

THE SUGGESTION'S FORM. {"op": "new" | "change", "kind": "action" | "risk" | "issue" | "assumption" | "dependency" | "decision" |
"milestone", "id": "ABC-A-001", "current_title": ..., "current_owner": ..., "source": "P3", <fields>}. `kind` is needed for a
new item; a change takes its kind from the ID. `current_title` and `current_owner` are what the model says the item is now:
when given, each must match the data, or the suggestion is refused as one that may be about another item. `source` names the
passage the change came from. The fields are the plain names in FIELDS (a field not there, or not one the item can take, is
refused with its name). "archive", "delete", "remove" and more than MAX_AT_ONCE changes at once are refused: not yet (part 1).

THE OFFER. A dry run that passes is kept here, in memory only, under a random offer ID for OFFER_MINUTES, with the project, the
request, the `before` it showed and whether it came from a source passage. Apply takes only the offer ID: the page can't send a
different change, drop the source mark or send its own before. A change from a source passage needs `confirm` to be exactly
True, a separate press from the one that asks for Apply. If the row has changed since the dry run, nothing is saved.

Nothing about a question, a passage or a value is logged or kept beyond the offer.
"""
import re
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from clark import ask, ask_data, ask_words, changes, edit_ai, platform
from clark.store import CODE_RE, Store, connect

MAX_AT_ONCE = ask.MAX_CHANGES   # FR-62a: more than five items at once asks first and lists them; part 1 refuses it (not yet). One constant with the reply reader (Row 1293)
OFFER_MINUTES = 30
MAX_OFFERS = 50
OP_NEW, OP_CHANGE = "new", "change"
NOT_YET_OPS = tuple("archive remove restore".split()) + (changes.DELETE,)      # made, not spelt: a lone delete string reads as SQL to the writer test
CLAIMS = ("current_title", "current_owner")
MAX_WHY = 300                     # row 1292 step S4: the card's one-line reason, plain text
FORM = ("op", "kind", "id", "project", "source", "why") + CLAIMS
KINDS = {"action": ("actions", None), "risk": ("raid", "Risk"), "issue": ("raid", "Issue"),
         "assumption": ("raid", "Assumption"), "dependency": ("raid", "Dependency"), "decision": ("decisions", None),
         "milestone": ("milestones", None), "use case": ("use_cases", None)}
TITLE = {"actions": "description", "raid": "description", "decisions": "decision", "milestones": "name", "use_cases": "title"}
OWNER = {"actions": "owner", "raid": "owner", "decisions": "made_by", "milestones": "owner"}
# The plain names a suggestion may use, per table, and the column each one is. A column must also be in changes.CHANGE_KINDS for
# the op, and in ASK_FIELDS: so no archive flag, no use case link, no client wording, no agreed date moved (that is a rebaseline).
FIELDS = {
    "actions": {"title": "description", "owner": "owner", "priority": "priority", "due": "due_date", "due_date": "due_date",
                "status": "status", "workstream": "workstream", "milestone": "milestone"},
    "raid": {"title": "description", "owner": "owner", "due": "due_date", "due_date": "due_date", "status": "status",
             "workstream": "workstream", "milestone": "milestone", "impact": "impact", "likelihood": "likelihood"},
    "decisions": {"title": "decision", "made_by": "made_by", "owner": "made_by", "status": "status", "date": "date",
                  "needed_by": "needed_by"},
    "milestones": {"title": "name", "name": "name", "owner": "owner", "agreed_date": "baseline_date", "workstream": "workstream",
                   "forecast_date": "forecast_date", "achieved_date": "actual_date", "status": "status"},
    "use_cases": {"headline": "headline", "standing": "standing", "status": "status"},   # issue 729: the commitment flag is read by the model, never changed by it
}
ASK_FIELDS = {t: {OP_NEW: tuple(f for f in ops[changes.NEW] if f != "type"), OP_CHANGE: ops[changes.UPDATE]}
              for t, ops in changes.ASK_FIELDS.items()}      # changes.ASK_FIELDS is the list; it is checked again there
ID_KINDS = (("actions", r"-A-\d{3}"), ("decisions", r"-D-\d{3}"), ("milestones", r"-M-\d{3}"), ("use_cases", r"-U-\d{3}"), ("raid", r"-\d{3}"))
ANY_ITEM = re.compile(r"[A-Z][A-Z0-9]{2,6}-(?:[ADMU]-)?\d{3}")
SOURCE_ID = re.compile(r"P[1-9]\d{0,2}")

NOT_A_CHANGE = "That suggestion isn't in a form clark can use. Nothing was changed. Ask again, or make the change yourself."
NOT_YET = "Archiving or deleting by asking isn't available yet. Nothing was changed. Do it yourself on the board."
TOO_MANY = (f"Changing more than {MAX_AT_ONCE} items at once by asking isn't available yet. Nothing was changed. "
            f"Ask for {MAX_AT_ONCE} or fewer at a time.")
OTHER_PROJECT = "That suggestion is for another project. Only the open project can be changed here. Nothing was changed."
WRONG_KIND = "That suggestion's ID and kind don't match. Nothing was changed. Ask again."
UNKNOWN_ID = "That suggestion names {ref}, which isn't in this project. Nothing was changed. Check the ID and ask again."
WRONG_TITLE = "That suggestion gave the wrong title for {ref}, so it may be about another item. Nothing was changed. Check {ref} and ask again."
WRONG_OWNER = "That suggestion gave the wrong owner for {ref}, so it may be about another item. Nothing was changed. Check {ref} and ask again."
NOT_ALLOWED = "Asking can't set the {name} of this item. Nothing was changed. Change it yourself in the item's details."
NOTHING = "That suggestion doesn't say what to change. Nothing was changed. Ask again."
NEEDS_CONFIRM = ("This change comes from one of your files. Read the passage, then press Confirm to save it. "
                 "Nothing was changed yet.")
NO_OFFER = "That change is no longer waiting to be saved. Nothing was changed. Ask again."
ASKING_OFF = changes.ASK_OFF
BUSY = "The saved data could not be opened just now. Wait a moment and try again. Nothing was changed."
NO_PROJECT = "That project isn't here. Nothing was changed."


class Refusal(Exception):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def fail(code, message, status=400):
    return status, {"ok": False, "code": code, "message": message}


def _fold(text):
    return " ".join(edit_ai.normal(ask_data.plain(text or "")).casefold().split())      # #1293 A: the saved text may hold HTML; the model was shown it plain


def _blank_tbc(owner):
    """Row 1293 (b): an item with no owner is stored as "TBC", so a folded TBC owner counts as blank (it matches any owner)."""
    return "" if owner == "tbc" else owner


def _plain_name(name):
    """A field name from a suggestion, safe to say back: letters, digits and spaces only, short."""
    return re.sub(r"[^A-Za-z0-9 ]", " ", str(name).replace("_", " "))[:30].strip() or "field"


def _kind_word(table, row):
    """The word for a new item's kind in a sentence: action, risk, issue, assumption, dependency, decision, milestone ("" if none)."""
    if table == "raid":
        return str(row.get("type") or "").casefold()
    return {"actions": "action", "decisions": "decision", "milestones": "milestone"}.get(table, "")


def table_of(ref, project):
    """The table an item ID of `project` is in, or None."""
    for table, tail in ID_KINDS:
        if re.fullmatch(re.escape(project) + tail, ref):
            return table
    return None


@dataclass(frozen=True)
class Plan:
    """A suggestion turned into a request for changes.make_ask_change, before any data is read."""
    table: str
    op: str
    ref: object
    request: dict
    claims: dict
    from_source: bool
    why: object = None


def read_suggestion(project, change, from_source=False):
    """`change` (one of ask.Reply.changes) as a Plan for `project`, or Refusal. Only the form is checked here; nothing is read."""
    if not isinstance(project, str) or not re.fullmatch(CODE_RE, project):
        raise Refusal("bad_project_code", NO_PROJECT)
    if not isinstance(change, dict) or not change:
        raise Refusal("not_a_change", NOT_A_CHANGE)
    op = change.get("op")
    if isinstance(op, str) and op.strip().casefold() in NOT_YET_OPS:
        raise Refusal("not_yet", NOT_YET)
    if "archived" in change:
        raise Refusal("not_yet", NOT_YET)
    if op not in (OP_NEW, OP_CHANGE):
        raise Refusal("not_a_change", NOT_A_CHANGE)
    named = change.get("project", project)
    if named != project:
        raise Refusal("other_project", OTHER_PROJECT)
    source = change.get("source")
    if source is not None and not (isinstance(source, str) and SOURCE_ID.fullmatch(source)):
        raise Refusal("not_a_change", NOT_A_CHANGE)
    why = change.get("why")
    if why is not None and not isinstance(why, str):
        raise Refusal("not_a_change", NOT_A_CHANGE)
    if why is not None:
        why = " ".join("".join(c for c in why if c >= " " and c != "\x7f").split())[:MAX_WHY] or None
    claims = {k: change[k] for k in CLAIMS if change.get(k) is not None}
    if any(not isinstance(v, str) for v in claims.values()):
        raise Refusal("not_a_change", NOT_A_CHANGE)
    word = change.get("kind")
    if word is not None and (not isinstance(word, str) or word.strip().casefold() not in KINDS):
        raise Refusal("not_a_change", NOT_A_CHANGE)
    kind = KINDS[word.strip().casefold()] if word is not None else None
    ref = change.get("id")
    if op == OP_NEW:
        if kind is None or ref is not None or claims:
            raise Refusal("not_a_change", NOT_A_CHANGE)
        table, raid_type = kind
        if table == "use_cases":                     # issue 729: a use case can be changed, not added, by asking
            raise Refusal("not_a_change", NOT_A_CHANGE)
    else:
        if not isinstance(ref, str) or not ANY_ITEM.fullmatch(ref):
            raise Refusal("not_a_change", NOT_A_CHANGE)
        table = table_of(ref, project)
        if table is None:
            raise Refusal("other_project", OTHER_PROJECT)
        if kind is not None and kind[0] != table:
            raise Refusal("wrong_kind", WRONG_KIND)
        if table == "use_cases" and "current_owner" in claims:      # a use case has no owner to claim
            raise Refusal("not_a_change", NOT_A_CHANGE)
        raid_type = None
    fields = {}
    for name, value in change.items():
        if name in FORM:
            continue
        column = FIELDS[table].get(name) if isinstance(name, str) else None
        if column is None or column not in ASK_FIELDS[table][op] or column in fields:
            raise Refusal("field_not_allowed", NOT_ALLOWED.format(name=_plain_name(name)))
        if isinstance(value, bool) or not (value is None or isinstance(value, str)):
            raise Refusal("not_a_change", NOT_A_CHANGE)
        fields[column] = value
    if raid_type is not None:
        fields["type"] = raid_type
    if not fields:
        raise Refusal("nothing", NOTHING)
    if op == OP_NEW:
        request = {"project": project, "kind": table, "op": changes.NEW, "values": fields}
    else:
        request = {"project": project, "kind": table, "op": changes.UPDATE, "id": ref, "changes": fields}
    return Plan(table, op, ref, request, claims, bool(from_source) or source is not None, why)


@dataclass
class Offer:
    project: str
    request: dict
    expect: object
    from_source: bool
    at: float
    ref: object = None            # Row 1293: the item a change is about (None for a new item)
    stale: str = ""               # Row 1293: the sentence to give when another change to the same item has been saved first ("" when not)


def _owner_shown(before, plan):
    """The owner the card shows beside the title: the stored owner of a changed item; none for a new item, a use case, or a blank owner. TBC is shown as stored (ruling 20-11)."""
    if plan.op != OP_CHANGE or plan.table not in OWNER:
        return None
    owner = (before or {}).get(OWNER[plan.table])
    return owner if isinstance(owner, str) and owner.strip() else None


class AskApply:
    """`db_path` the database; `ask_change` changes.make_ask_change's function (made here when not given); `clock` for tests."""

    def __init__(self, db_path, onedrive_roots=None, by_user=None, ask_change=None, clock=time.monotonic):
        self.db_path = Path(db_path)
        self.onedrive_roots = list(platform.onedrive_roots() if onedrive_roots is None else onedrive_roots)
        self.ask_change = ask_change or changes.make_ask_change(self.db_path, self.onedrive_roots, by_user)
        self.clock = clock
        self.offers = {}
        self.lock = threading.Lock()

    def reader(self):
        """The store, opened read-only (a write through it fails in SQLite itself)."""
        return Store(connect(self.db_path, readonly=True), self.db_path, self.onedrive_roots)

    def check_data(self, plan):
        """The switch, the project and, for a change, the item and the model's claims about it, read from the data (read-only)."""
        try:
            store = self.reader()
        except (sqlite3.Error, OSError, TypeError):
            raise Refusal("busy", BUSY, 409) from None
        try:
            try:
                on = store.ask_enabled() is True
            except Exception:  # noqa: BLE001  a switch that can't be read is off
                on = False
            if not on:
                raise Refusal("asking_off", ASKING_OFF, 409)
            project = plan.request["project"]
            if store.read("projects", ref=project) is None:
                raise Refusal("project_not_found", NO_PROJECT, 404)
            if plan.op != OP_CHANGE:
                return
            row = store.read(plan.table, ref=plan.ref)
            if row is None or row.get("project") != project or row.get("archived"):
                raise Refusal("unknown_id", UNKNOWN_ID.format(ref=plan.ref))
            title = plan.claims.get("current_title")
            if title is None or not _fold(title):      # #1293: a change must name the title it is about, so the card can show it
                raise Refusal("no_title", NOT_A_CHANGE)
            if _fold(title) != _fold(row.get(TITLE[plan.table])):
                raise Refusal("wrong_title", WRONG_TITLE.format(ref=plan.ref))
            owner = plan.claims.get("current_owner")
            if owner is not None and _fold(owner) != _fold(row.get(OWNER[plan.table])):
                raise Refusal("wrong_owner", WRONG_OWNER.format(ref=plan.ref))
        finally:
            store.close()

    def keep(self, offer):
        with self.lock:
            now = self.clock()
            for k in [k for k, o in self.offers.items() if now - o.at > OFFER_MINUTES * 60]:
                del self.offers[k]
            while len(self.offers) >= MAX_OFFERS:
                del self.offers[next(iter(self.offers))]
            key = secrets.token_urlsafe(16)
            self.offers[key] = offer
            return key

    def duplicate_of(self, plan, after, earlier):
        """Row 1293 (b): the warning sentence when a new item has the same kind, project and title (capitals and extra spaces ignored)
        as one already there or one the same reply offered before it, and the same owner (a blank owner on either side matches any);
        else "". `earlier` is the list of (kind word, title, owner) the reply's earlier new items made. Read-only; never refuses."""
        table = plan.table
        word = _kind_word(table, after)
        title, owner = _fold(after.get(TITLE[table])), _blank_tbc(_fold(after.get(OWNER[table])))
        if not word or not title:
            return ""
        shown = ask_data.plain(after.get(TITLE[table]) or "").strip()
        same = lambda o: not owner or not o or o == owner      # noqa: E731
        if any(w == word and t == title and same(o) for w, t, o in earlier):
            return ask_words.duplicate(word, shown)
        try:
            store = self.reader()
        except (sqlite3.Error, OSError, TypeError):
            return ""
        try:
            rows = store.read(table, plan.request["project"], archived=False)
        except Exception:  # noqa: BLE001  a warning is only a help: when the data can't be read there is none
            return ""
        finally:
            store.close()
        for row in rows:
            if table == "raid" and str(row.get("type") or "").casefold() != word:
                continue
            if _fold(row.get(TITLE[table])) == title and same(_blank_tbc(_fold(row.get(OWNER[table])))):
                return ask_words.duplicate(word, shown)
        return ""

    def plan(self, project, change, from_source=False, earlier=()):
        """The dry run of one suggestion: (status, {ok, offer, kind, ref, before, after, fields, needs_confirm}) or a refusal.
        `before` and `after` come from the data (changes.make_ask_change, rolled back); `fields` the shown fields that differ."""
        try:
            plan = read_suggestion(project, change, from_source)
            self.check_data(plan)
        except Refusal as r:
            return fail(r.code, r.message, r.status)
        status, body = self.ask_change(plan.request, dry=True)
        if status != 200 or not body.get("ok"):
            return status, {"ok": False, "code": body.get("code", "refused"), "message": body.get("message", NOT_A_CHANGE)}
        before, after = body["before"], body["after"]
        if after is None:                              # nothing would change
            return fail("nothing", NOTHING)
        fields = [k for k in after if k != "id" and (after[k] is not None if before is None else before.get(k) != after[k])]
        if not fields:
            return fail("nothing", NOTHING)
        offer = self.keep(Offer(plan.request["project"], plan.request, before, plan.from_source, self.clock(),
                                plan.ref if plan.op == OP_CHANGE else None))
        out = {"ok": True, "offer": offer, "kind": body["kind"], "ref": body["ref"] if plan.op == OP_CHANGE else None,
               "new": plan.op == OP_NEW, "before": before, "after": after, "fields": fields,
               "title": (before or {}).get(TITLE[plan.table]) if plan.op == OP_CHANGE else None,
               "owner": _owner_shown(before, plan), "why": plan.why,
               "needs_confirm": plan.from_source}
        if plan.op == OP_NEW:
            said = self.duplicate_of(plan, after, earlier)
            if said:
                out["duplicate"] = said                # Row 1293: a warning above Apply; it never blocks
        return 200, out

    def plan_all(self, project, suggested, from_source=False):
        """The dry runs of a reply's changes: more than MAX_AT_ONCE is refused whole (not yet); else one result each."""
        if not isinstance(suggested, (list, tuple)):
            return fail("not_a_change", NOT_A_CHANGE)
        if len(suggested) > MAX_AT_ONCE:
            return fail("too_many", TOO_MANY)
        plans, earlier = [], []
        for c in suggested:
            made = self.plan(project, c, from_source, tuple(earlier))[1]
            plans.append(made)
            if made.get("ok") and made.get("new"):      # Row 1293 (b): a later new item matching this one is warned about
                after = made["after"]
                table = made["kind"]
                word = _kind_word(table, after)
                earlier.append((word, _fold(after.get(TITLE[table])), _blank_tbc(_fold(after.get(OWNER[table])))))
        return 200, {"ok": True, "plans": plans}

    def restore(self, offer, held):
        """Put an offer back after a save that did not happen (its own time still runs, so it expires when it would have)."""
        with self.lock:
            self.offers[offer] = held

    def apply(self, offer, project, confirm=False):
        """Save one offer as one undoable step. A change from a source passage needs `confirm` exactly True. The offer is used
        once: it is gone once it is saved or refused; a save that could not be made (busy or unusable data, or a fault) keeps it."""
        if not isinstance(offer, str) or not isinstance(project, str):
            return fail("no_offer", NO_OFFER)
        with self.lock:
            held = self.offers.get(offer)
            if held is None or held.project != project or self.clock() - held.at > OFFER_MINUTES * 60:
                return fail("no_offer", NO_OFFER, 409)
            if held.stale:                             # Row 1293: the first change to this item was saved; nothing is written for this one
                del self.offers[offer]
                return fail("changed", held.stale, 409)
            if held.from_source and confirm is not True:
                return fail("needs_confirm", NEEDS_CONFIRM, 409)
            del self.offers[offer]                     # taken while it is saved, so a second Apply at the same moment finds nothing
        try:
            status, body = self.ask_change(held.request, dry=False, expect=held.expect)
        except BaseException as e:                     # row 1293 line 10: an unexpected fault saved nothing, so the offer stays
            committed = getattr(e, "committed", False) is True       # unless the save had been committed: then it is used up
            if not committed:
                self.restore(offer, held)
            raise
        if status == 503 and body.get("committed") is not True:                              # row 1293 line 10: a busy or unusable database saved nothing: the offer is kept for the next Apply
            self.restore(offer, held)
        if status != 200 or not body.get("ok"):
            return status, {"ok": False, "code": body.get("code", "refused"), "message": body.get("message", NOT_A_CHANGE)}
        stale = self.mark_stale(held, body)
        return 200, {"ok": True, "kind": body["kind"], "ref": body["ref"], "apply_id": body["apply_id"],
                     "undoable": body["undoable"], "before": body["before"], "after": body["after"], "stale": stale}

    def mark_stale(self, saved, body):
        """Row 1293 (a): the other offers still waiting for the item just changed (they were made from the item as it was) are
        marked stale. Returns [{"offer", "message"}] for the page to show on those cards in place of Apply; nothing is written for them."""
        if saved.ref is None or not isinstance(body.get("before"), dict) or not isinstance(body.get("after"), dict):
            return []
        moved = [k for k in body["after"] if body["before"].get(k) != body["after"][k]]
        out = []
        with self.lock:
            for key, other in self.offers.items():
                if other.ref != saved.ref or other.project != saved.project or other.stale:
                    continue
                mine = [c for c in other.request.get("changes", {}) if c in moved]
                other.stale = ask_words.stale((mine or moved or list(other.request.get("changes", {})) or ["item"])[0])
                out.append({"offer": key, "message": other.stale})
        return out
