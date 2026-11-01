"""#97: the read behind GET /api/draft, the Draft email of the right-click menu. It drafts and sends nothing.

`make_read(read_inputs, profile, now)` gives the `draft` seam the server calls for GET /api/draft?project=<CODE>&item=<ID>. It reads one
project (the same read-only inputs a publish is made from, `publish.read_inputs`: only the columns a report may carry, so a working
note, the internal note and the source are not in what this module can see) and finds the ONE item asked for in that project. It
runs draft_email.build on it and returns what the Draft email dialog (components/DraftEmail.jsx) needs: the items on offer, the
dialog's starting state, the finished draft, today's date and the reason line.

What cannot reach the draft:
  - another project's item (the id must be a row of the project asked for), an archived item or a milestone or use case: not found;
  - an item left off the report, or labelled Sensitive (or any label that keeps a row out of a published file): the builder's own
    `barred` leaves it out, so the draft says there is nothing to put in an email;
  - a risk's response (a working note, not read here) and the item's internal text.
`To` is the person's address from the People list (#115). There is no People list yet, so it is left empty for the person to type,
and `reason` says so. Nothing here writes to the database, a file or the clipboard, and nothing is sent.

Standard library only, Python 3.9.
"""
import re
from datetime import datetime

from clark import draft_email, publish

KINDS = ("actions", "raid", "decisions")
TEXT = {"actions": "description", "raid": "description", "decisions": "decision"}
DUE = {"actions": "due_date", "raid": "due_date", "decisions": "needed_by"}
OWNER = {"actions": "owner", "raid": "owner", "decisions": "made_by"}
REASON = "There is no People list yet, so the To line is empty. Type the address in your mail app."
UNBLOCKS_LIMIT = 200
DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
BAD_MODE = draft_email.NO_SUCH_KIND
BAD_OPTION = "That email option could not be read. Close the Draft email and open it again."


def now_text():
    """Now as YYYY-MM-DD HH:MM on this machine's clock; a test passes its own."""
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _flag(value):
    return value in ("1", "true")


def _options(opts, item_id, today, default_mode):
    """The dialog's inputs, each checked: mode (one of draft_email.MODES), picked ("none", or the item's own id), reply_by (a day),
    unblocks (short plain text), include_update (0 or 1). Raises ValueError in plain words; nothing is passed on unchecked."""
    opts = opts or {}
    mode = opts.get("mode", default_mode)
    if mode not in draft_email.MODES:
        raise ValueError(BAD_MODE)
    picked = opts.get("picked", item_id)
    if picked not in (item_id, "none"):
        raise ValueError(BAD_OPTION)
    reply_by = opts.get("reply_by", "")
    if reply_by and (not DAY.fullmatch(reply_by) or draft_email._as_day(reply_by) is None):
        raise ValueError(BAD_OPTION)
    unblocks = opts.get("unblocks", "")
    if len(unblocks) > UNBLOCKS_LIMIT or draft_email.one_line(unblocks) != unblocks.strip():
        raise ValueError(BAD_OPTION)
    include = opts.get("include_update", "0")
    if include not in ("0", "1"):
        raise ValueError(BAD_OPTION)
    return {"mode": mode, "picked": [] if picked == "none" else [item_id], "replyBy": reply_by, "unblocks": unblocks.strip(),
            "includeUpdate": include == "1"}


def make_read(read_inputs, profile, now=now_text):
    """`read(code, item_id, opts)` for the server. read_inputs(code) is publish.read_inputs bound to the store (raises
    publish.PublishError for a project that is not there); profile is profile_settings.Profile (the sender's name and own domains).
    Returns the reply's parts, or raises LookupError("project") / LookupError("item"), or ValueError(plain words) for a bad option."""
    def read(code, item_id, opts=None):
        try:
            got = read_inputs(code)
        except publish.PublishError:
            raise LookupError("project") from None
        data = got["data"]
        kind = next((k for k in KINDS if any(r.get("id") == item_id for r in data.get(k) or ())), None)
        row = next((r for r in data[kind] if r["id"] == item_id), None) if kind else None
        if row is None or row.get("archived") or row.get("project", code) != code:
            raise LookupError("item")
        stamp = now()
        today = stamp[:10]
        labels = {str(n).casefold() for n in (data.get("labels") or {}).get(item_id, ())}
        item = {"id": row["id"], "project": code, "kind": kind, "text": row[TEXT[kind]] or "", "due": row.get(DUE[kind]),
                "priority": row.get("priority"), "owner": row.get(OWNER[kind]) or "", "status": row.get("status"),
                "client_visible": bool(row.get("client_visible")),
                "sensitive": bool(labels & publish._excluded_labels(got.get("label_rules"))),
                "hidden": item_id in set(got.get("hidden") or ())}
        if kind == "raid":
            item["type"] = row.get("type")
        if kind == "actions":
            item[draft_email.LATEST] = row.get("latest_update") or ""
        state = _options(opts, item_id, today, draft_email.mode_for(item, today))
        own = profile.own_domains()
        names = {code: (data.get("project") or {}).get("name") or code}
        offered, _ = draft_email.offered([item], "", own)
        built = draft_email.build({"mode": state["mode"], "items": [item], "picked": state["picked"], "name": "", "email": "",
                                   "own_domains": own, "from": profile.who(), "now": stamp, "project_names": names,
                                   "reply_by": state["replyBy"], "unblocks": state["unblocks"], "include_update": state["includeUpdate"]})
        return {"item": item_id, "items": [{"id": i["id"], "text": i["text"]} for i in offered], "state": state, "draft": built,
                "today": today, "reason": REASON}
    return read
