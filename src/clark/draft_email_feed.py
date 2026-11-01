"""The Draft email route's seam (#50, FR-44, FR-45): turns a request from the editor into the builder's answer. Read only.

server.py stays small: its POST /api/draft-email hands the request here and sends the (status, body) that comes back. This module
reads one project's open items through the store's read (`data_for`), asks draft_email.py for the ticks and the email, and returns
both. It writes nothing, sends nothing and makes no Outlook draft; there is no model. The page copies the email and the user
pastes it.

Request (JSON; every key but `project` is optional; a key not listed is refused):
    project         the project code
    mode            "update_request", "chase" or "decision" (default: from the item for a peek, else "update_request")
    picked          the item IDs ticked (default: draft_email.default_picked)
    reply_by        YYYY-MM-DD
    unblocks        what a decision or a chase holds up (one line, 200 characters)
    include_update  true to put each item's latest update under it
    item            one item's ID (the peek's); or
    owner           a person's name (their open items); not both
    email, name     who the email is for (an address decides which items start ticked: internal ones start unticked for any
                    address that is not on one of your own domains, and for no address)
Answer: {"ok": true, "project", "mode", "items": [{id, text, kind, due, owner, internal}], "picked": [ids], "draft": build()}.

Settings that do not exist yet (your own domains, your name from Settings > Profile) come from `profile`, a callable returning
{"name": "", "own_domains": []}; the safe defaults are no name (the email says to add one) and no own domains (every address
counts as outside, so internal items start unticked). `chased(code)` (how often each item has been asked about) is built from the "I sent it"
records (chase_counts_of); it is empty with none. Standard library only, Python 3.9.
"""
import re
import threading
import unicodedata
from datetime import datetime

from clark import draft_email as de
from clark import publish
from clark.changes import Refused, _call

CODE = re.compile(r"[A-Z][A-Z0-9]{2,6}")
ID = re.compile(r"[A-Z][A-Z0-9]{2,6}-(?:[AD]-)?[0-9]{3}")        # the shape of an action, risk or decision ID
DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
ADDRESS = re.compile(r"[^@\s<>?,;:\"()\[\]\\]+@[^@\s<>?,;:\"()\[\]\\]+\.[^@\s<>?,;:\"()\[\]\\]+")      # no brackets, query, quotes or separators
HIDDEN_IN_TEXT = frozenset({"Cf", "Co", "Cs"})            # a bidi override or a zero-width mark: one_line leaves these, an address may not have them
KEYS = ("project", "mode", "picked", "reply_by", "unblocks", "include_update", "item", "owner", "email", "name")
MAX_PICKED, MAX_UNBLOCKS, MAX_NAME, MAX_EMAIL = 200, 200, 100, 254

SAFE_PROFILE = {"name": "", "own_domains": []}
BAD_REQUEST = "That could not be read. Reload the page and try again."
NO_PROJECT = "There is no project with that code. Check the code in the address, or choose a project from the list."
BAD_CODE = "Use a project code of 3 to 7 capital letters or digits."
BAD_ITEM = "That item could not be found in this project. Reload the page and choose it again."
NOT_FOR_EMAIL = "One of those items can't go in an email. Reload the page and choose again."
BAD_PICK = "One of the ticked items is not in this project. Reload the page and tick again."
BAD_DATE = "Choose the reply-by date from the calendar, or leave it empty."
BAD_ADDRESS = "That email address is not complete. Check it, or leave it empty."
BAD_TEXT = "One of the fields is too long or is not text. Shorten it and try again."
BAD_BOTH = "Choose one item or one person, not both."
ARCHIVED = "That project is archived, so no email can be drafted for it. Restore it first."


def refuse(status, code, message):
    return status, {"ok": False, "message": message, "code": code}


def text_of(value, limit):
    """One line of text, or None when it is not text or is longer than `limit` (flattened as the Subject and To are)."""
    if value is None:
        return ""
    if not isinstance(value, str) or len(value) > limit:
        return None
    return de.one_line(value)


def rules_from_inputs(inputs):
    """{"hidden": ids, "excluded": label names (lower case)} from publish.read_inputs' shape: the two rules publish.select uses to
    keep a row out of the client's file (report_hidden; Sensitive and any label that excludes), taken from publish itself so the
    email and the file cannot drift apart."""
    return {"hidden": list(inputs.get("hidden") or ()), "excluded": sorted(publish._excluded_labels(inputs.get("label_rules")))}


def items_of(data, rules=None):
    """The project's open items as the builder reads them (draft_email's words). An action, a risk or issue, and a decision still
    pending; a made or withdrawn decision is not asked for. The one place the store's columns are named for the builder. A row in
    the report's hidden list is marked `hidden` (never in an email), and one with an excluding label (Sensitive always, so it is
    barred even when no rules are given) is marked `sensitive` (never in an email, to anyone)."""
    rules = rules or {}
    hidden = set(rules.get("hidden") or ())
    excluded = {"sensitive"} | {str(n).casefold() for n in rules.get("excluded") or ()}
    labels = data.get("labels") or {}

    def marks(row):
        return {"hidden": row["id"] in hidden, "sensitive": any(str(n).casefold() in excluded for n in labels.get(row["id"]) or ())}
    out = []
    for r in data.get("actions") or []:
        out.append({"id": r["id"], "project": r["project"], "kind": "actions", "text": r.get("description") or "",
                    "due": r.get("due_date"), "priority": r.get("priority"), "owner": r.get("owner"), "status": r.get("status"),
                    de.LATEST: r.get("latest_update"), "client_visible": bool(r.get("client_visible")), **marks(r)})
    for r in data.get("raid") or []:
        out.append({"id": r["id"], "project": r["project"], "kind": "raid", "text": r.get("description") or "",
                    "type": r.get("type"), "response": r.get("response_action"), "due": r.get("due_date"),
                    "priority": r.get("priority"), "owner": r.get("owner"), "status": r.get("status"),
                    "client_visible": bool(r.get("client_visible")), **marks(r)})
    for r in data.get("decisions") or []:
        if r.get("status") == "Pending":
            out.append({"id": r["id"], "project": r["project"], "kind": "decisions", "text": r.get("decision") or "",
                        "due": r.get("needed_by"), "owner": r.get("made_by"), "status": "Open",
                        "client_visible": bool(r.get("client_visible")), **marks(r)})
    return out


def make(data_for, profile=None, clock=None, chased=None, rules_for=None):
    """The seam for server.LocalServer(draft_email=...): `seam(req)` answers (status, body). `data_for(code)` is the store's read
    (None when there is no such project), `profile()` the settings, `clock()` the time as "YYYY-MM-DD HH:MM", `chased(code)` the
    {item ID: {n, last}} history, `rules_for(code)` the report's hidden ids and excluding labels (rules_from_inputs' shape; the
    launcher gives it from publish.read_inputs). All but data_for have safe defaults; without `rules_for` only the Sensitive label
    on a row is known, so the launcher must give it."""
    profile = profile or (lambda: SAFE_PROFILE)
    rules_for = rules_for or (lambda code: {})
    clock = clock or (lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))
    chased = chased or (lambda code: {})

    def seam(req):
        if not isinstance(req, dict) or any(k not in KEYS for k in req):
            return refuse(400, "bad_request", BAD_REQUEST)
        code = req.get("project")
        if not isinstance(code, str) or not CODE.fullmatch(code):
            return refuse(400, "bad_project_code", BAD_CODE)
        mode = req.get("mode")
        if mode is not None and (not isinstance(mode, str) or mode not in de.MODES):
            return refuse(400, "bad_mode", de.NO_SUCH_KIND)
        reply_by = req.get("reply_by") or ""
        if not isinstance(reply_by, str) or reply_by and not _day(reply_by):
            return refuse(400, "bad_date", BAD_DATE)
        unblocks, owner, name, email = (text_of(req.get(k), n) for k, n in
                                        (("unblocks", MAX_UNBLOCKS), ("owner", MAX_NAME), ("name", MAX_NAME), ("email", MAX_EMAIL)))
        if None in (unblocks, owner, name, email):
            return refuse(400, "bad_text", BAD_TEXT)
        if email and (not ADDRESS.fullmatch(email) or any(unicodedata.category(c) in HIDDEN_IN_TEXT for c in email)):
            return refuse(400, "bad_address", BAD_ADDRESS)
        include_update = req.get("include_update", False)
        item_id, picked = req.get("item"), req.get("picked")
        if not isinstance(include_update, bool) or item_id is not None and not (isinstance(item_id, str) and ID.fullmatch(item_id)):
            return refuse(400, "bad_request", BAD_REQUEST)
        if picked is not None and not (isinstance(picked, list) and len(picked) <= MAX_PICKED
                                       and all(isinstance(i, str) and ID.fullmatch(i) for i in picked)):
            return refuse(400, "bad_pick", BAD_PICK)
        if item_id is not None and owner:
            return refuse(400, "bad_request", BAD_BOTH)
        data = data_for(code)
        if data is None:
            return refuse(404, "project_not_found", NO_PROJECT)
        if (data.get("project") or {}).get("archived"):
            return refuse(409, "project_archived", ARCHIVED)
        items = items_of(data, rules_for(code))
        known = {i["id"] for i in items}
        if item_id is not None and item_id not in known:
            return refuse(404, "bad_item", BAD_ITEM)
        if picked is not None and not set(picked) <= known:
            return refuse(400, "bad_pick", BAD_PICK)
        # A Sensitive item never goes in an email, to anyone: a request that names one is refused (the list never offers it).
        if {i["id"] for i in items if i.get("sensitive")} & ({item_id} | set(picked or ())):
            return refuse(400, "not_for_email", NOT_FOR_EMAIL)
        now, who = clock(), profile()
        today, domains = now[:10], list(who.get("own_domains") or [])
        if item_id is not None:
            offer = de.item_for_peek(items, item_id, email, domains)
            mode = mode or (de.mode_for(offer[0], today) if offer else de.MODES[0])
        elif owner:
            mode = mode or de.MODES[0]
            offer = de.items_for_owner(items, owner, email, domains, mode, today)
        else:
            mode = mode or de.MODES[0]
            offer = de.sort_items(de.offered(items, email, domains)[0], today)
        offered_ids = {o["id"] for o in offer}
        ticks = [i for i in (picked if picked is not None else de.default_picked(offer, email, domains)) if i in offered_ids]
        outside = de.is_outside(email, domains)
        draft = de.build({"mode": mode, "items": offer, "picked": ticks, "name": name, "email": email, "own_domains": domains,
                          "from": who.get("name") or "", "now": now, "include_update": include_update, "reply_by": reply_by,
                          "unblocks": unblocks, "chased": chased(code), "project_names": {code: (data.get("project") or {}).get("name") or code}})
        shown = [{"id": i["id"], "text": i["text"], "kind": i["kind"], "due": i.get("due"), "owner": i.get("owner"),
                  "internal": bool(outside and de.is_internal(i))} for i in offer]
        return 200, {"ok": True, "project": code, "mode": mode, "items": shown, "picked": ticks, "draft": draft, "outside": bool(outside)}
    return seam


def _day(text):
    """Whether `text` is a real YYYY-MM-DD date."""
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return False
    return bool(DAY.fullmatch(text))


def chase_counts_of(records):
    """{item ID: {n, last}} for the tone, from Store.email_sent_for's rows (an update request does not count: draft_email.chase_counts)."""
    return de.chase_counts([{"kind": de.SENT_KIND, "ids": r["ids"], "date": r["day"], "mode": r["mode"]} for r in records])


# ---- "I sent it" (#50 item 5): the seam of POST /api/draft-email/sent -----------------------------------------------------------
SENT_KEYS = ("project", "ids", "mode", "day")
MAX_SENT = 50                                      # the ids one record can hold (Store.EMAIL_MAX_IDS)
BUSY_SENT = "That is already being recorded. Wait a moment and look at the history before you press again."
BAD_SENT = "That could not be recorded. Reload the page and try again."
SENT_BAD_DAY = "The date this page sent is not a real date. Reload the page and try again."     # the day comes from the page's clock, not from the person
SENT_BAD_PROJECT = "That project could not be found. Reload the page and choose it again."
SENT_BAD_PICK = "One of the ticked items is not in this project. Untick it, or reload the page."
SENT_TOO_MANY = f"At most {MAX_SENT} items can be recorded in one email. Send it in parts."
NOTHING_SAVED = "Nothing was saved."                # the last words of every refusal of "I sent it"


def said_nothing_saved(answer):
    """(status, body) with " Nothing was saved." added to the end of a refusal's message (once); an answer that was recorded, and the 409 "already being recorded" wait, are left as they are."""
    status, body = answer
    if isinstance(body, dict) and body.get("code") == "already_recording":
        return answer                                  # a wait, not a refusal: the first press is being saved
    if isinstance(body, dict) and body.get("ok") is False and isinstance(body.get("message"), str) and not body["message"].endswith(NOTHING_SAVED):
        body = dict(body, message=f"{body['message']} {NOTHING_SAVED}")
    return status, body


def make_sent(path, onedrive_roots=None, by_user=None, today=None):
    """The `draft_email_sent` seam for server.LocalServer: `seam(req)` records one press of "I sent it" and answers (status, body).
    The request holds the project code, the item ids ticked (1 to 50), the mode and the day (YYYY-MM-DD); a key not listed, anything
    that is not text of the right shape, or any words of the email is refused before the store is opened. Who pressed it comes from
    `by_user` (the login name unless one is given), never from the request. The store checks the rest (the project, that each id is
    one of its work items, the day) and writes one record in one transaction (Store.log_email_sent); nothing else is written.
    Answer: {"ok": true, "seq": n}, or a refusal in plain words."""
    gate, in_flight = threading.Lock(), set()           # #258: the same record while one is being written is refused, not written twice

    def work(store, who, req):
        seq = store.log_email_sent(req["project"], req["ids"], req["mode"], req["day"], who, today=today() if callable(today) else today)
        return 200, {"ok": True, "seq": seq}

    def check(req):
        if not isinstance(req, dict) or any(k not in SENT_KEYS for k in req) or any(k not in req for k in SENT_KEYS):
            return refuse(400, "bad_request", BAD_SENT)
        code, ids, mode, day = (req[k] for k in SENT_KEYS)
        if not isinstance(code, str) or not CODE.fullmatch(code):
            return refuse(400, "bad_project_code", SENT_BAD_PROJECT)
        if not isinstance(mode, str) or mode not in de.MODES:
            return refuse(400, "bad_mode", de.NO_SUCH_KIND)
        if isinstance(ids, list) and not ids:
            return refuse(400, "nothing_ticked", de.NOTHING_TO_RECORD)
        if isinstance(ids, list) and len(ids) > MAX_SENT:
            return refuse(400, "too_many", SENT_TOO_MANY)
        if not isinstance(ids, list) or not all(isinstance(i, str) and ID.fullmatch(i) for i in ids):
            return refuse(400, "bad_pick", SENT_BAD_PICK)
        if not isinstance(day, str) or not DAY.fullmatch(day) or not _day(day):
            return refuse(400, "bad_date", SENT_BAD_DAY)
        key = (code, tuple(sorted(set(ids))), mode, day)
        with gate:
            if key in in_flight:
                return refuse(409, "already_recording", BUSY_SENT)
            in_flight.add(key)
        try:
            return _call(path, onedrive_roots, by_user, work, {"project": code, "ids": ids, "mode": mode, "day": day})
        finally:
            with gate:
                in_flight.discard(key)

    def seam(req):
        return said_nothing_saved(check(req))
    return seam
