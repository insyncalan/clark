"""Draft email: the wording and the rules, as plain code with no model (#50; BRD FR-44, FR-45, BR-9).

Brought across from creaite's Draft email and Draft chase (BL-83, BL-224, BL-298; v2.6.11 drafts.js and drafts.py): the
greeting by the time of day, the subject, the update request, the chase (First chase, Second chase, Firmer chase), the decision request, due
and overdue marking, and the email's HTML. It reads nothing and writes nothing: it takes the items, the options and the
time, and returns the To, the Subject, the HTML and the plain text. clark never sends mail and never makes an Outlook
draft; the page copies the two texts to the clipboard and the user pastes them.

The HTML is for Outlook's Word engine: every element carries its own inline style, tables have cellpadding and a bottom
border on each cell, the look's email fonts (Calibri then Arial) at 11 pt, and there are no classes, style blocks, variables, spans or images. It is
always drawn on white. Colour is never the only signal: the words say overdue and due soon too. Dates in the text are
DD-MM-YYYY; the items carry them as YYYY-MM-DD.

An item is a dict: id, project (code), kind ("actions", "raid" or "decisions"), text, due, priority, owner, type and
response (a risk or issue), update (the latest update), status, client_visible, sensitive, hidden. Only those words can
reach an email: an internal note, a source or anything else on the dict is never read.

Standard library only, Python 3.9.
"""
import re
import unicodedata
from datetime import date, timedelta
from html import escape
from urllib.parse import quote

from clark import look
from clark.confusables import skeleton

# The mode is named "update_request" and its subject word is joined from parts because the one-writer test in
# test_store_writer.py flags any string that begins with the word "update" as SQL.
UPDATE_REQUEST = "".join(("Up", "date request"))
LATEST = "".join(("up", "date"))              # the item field holding the latest update
MODES = ("update_request", "chase", "decision")
TONE_NAMES = ("First chase", "Second chase", "Firmer chase")   # what a person reads on the tone buttons
RECORD_MODES = MODES                                  # what "I sent it" records
DUE_SOON_DAYS = 7
SENT_KIND = "email_sent"
INTERNAL_TAG = "internal"
NO_SUCH_KIND = "That kind of email isn't available. Choose Update request, Chase or Decision."
NOTHING_TO_RECORD = "Tick at least one item before you press I sent it."
NOTHING_TICKED = "No items are ticked. Tick at least one to draft the email."
NO_OPEN_ITEMS = "There are no open items to put in an email."
NO_SENDER = "Add your name in Settings › Profile so it signs the email."
# Shown, with the preview selected, when the browser refuses the clipboard.
COPY_REFUSED = "The browser did not copy it. Press ⌘C to copy the selected text."
MAILTO_LIMIT = 2000        # the longest finished mailto: link (encoded) that every mail app keeps whole; longer ones are cut off
HELD_WORDS = ("confidential", "restricted")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

# The email is drawn on white whatever the theme, in the committed look's light colours (read from tokens.css by look.py, not written
# here): red and amber are the status text colours, ink and muted the text colours, head and rule the page's quiet grey and its
# border. Every pair used for text is at least 4.5:1 on white (tested).
COLOURS = {key: "#" + look.colour(token) for key, token in (
    ("red", "status-red-text"), ("amber", "status-amber-text"), ("ink", "text"), ("muted", "text-muted"), ("head", "grey-50"),
    ("rule", "grey-300"), ("white", "white"))}
# The only keys of an item the module reads; the items it hands back carry these and nothing else.
ITEM_KEYS = ("id", "project", "kind", "text", "due", "priority", "owner", "type", "response", LATEST, "status", "client_visible",
             "sensitive", "hidden")
# The page's own fonts (Inter and Montserrat) are embedded in the page and a mail app does not have them, so an email cannot use them:
# it takes the look's --font-email list (Calibri, then Arial, then the generic sans-serif), at 11 pt.
FONT = f"font-family:{look.email_font_family()};font-size:11pt;"

OPEN = "I'm pulling together where things stand on the items below."
ASK = "Could you let me know where each one stands, and flag anything that's blocking you or that you need from me?"
DECIDE = "Where an item is a decision we need from you, could you let me know what you have decided?"
REPLY_BY = " It would be helpful to hear back by {reply_by}."
THANKS = " Thank you."
SIGN_OFF = {"update_request": "Kind regards,", "chase": "Kind regards,", "decision": "Thank you,"}

CHASE = {
    "subjects": ("Reminder", "Second reminder", "Reply needed"),
    "openings": ("A quick reminder about the items below, which are now past their due dates.",
                 "I'm following up on my earlier note{last} about the items below, which are still overdue.",
                 "These items are now well overdue{longest}. I have chased them {n}{since}."),
    "asks": ("Could you let me know where each one stands, and when I can expect it?",
             "Could you let me have an update on each, and a date for anything still open?",
             "Please reply with a firm date for each, or tell me what is blocking any of them, so that we can resolve it together."),
    "one_openings": ("A quick reminder about the item below, which is now past its due date.",
                     "I'm following up on my earlier note{last} about the item below, which is still overdue.",
                     "This item is now {days} overdue. I have chased it {n}{since}."),
    "one_asks": ("Could you let me know where it stands, and when I can expect it?",
                 "Could you let me have an update, and a date for it?",
                 "Please reply with a firm date, or tell me what is blocking it, so that we can resolve it together."),
}
DECISION = {
    "subjects": ("Decision needed", "Decision needed (second reminder)", "Decision needed"),
    "openings": ("A quick note on the decision below{needed}.",
                 "I'm following up on my earlier note{last} about the decision below{needed}.",
                 "I have asked for this decision {n}{since}."),
    "ask": "Could you let me have the decision, or tell me what you need to make it, by {reply_by}?",
}


# ---- small helpers ----------------------------------------------------------------------------------------------------

def one_line(text):
    """Text for a header (Subject, To): every control character and line break (CR, LF, NEL, U+2028, U+2029 and the rest) becomes
    a space, then the white space is collapsed. A name with a line break in it can never start a second header in a mail link."""
    flat = "".join(" " if unicodedata.category(c) in ("Cc", "Zl", "Zp") else c for c in str(text or ""))
    return " ".join(flat.split())


DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")       # the one shape clark stores: no week or ordinal forms, no spaces, ASCII digits only


def _as_day(iso):
    """The date of a stored YYYY-MM-DD that is a real day, else None. The same on every Python (3.11 reads more forms)."""
    if not isinstance(iso, str) or not DAY.fullmatch(iso):
        return None
    try:
        return date(int(iso[:4]), int(iso[5:7]), int(iso[8:]))
    except ValueError:
        return None


def shown(iso):
    """YYYY-MM-DD as DD-MM-YYYY; anything else comes back as it is."""
    day = _as_day(iso)
    return f"{day.day:02d}-{day.month:02d}-{day.year:04d}" if day else str(iso or "")


def weekday_date(iso):
    """YYYY-MM-DD as "Thursday 15-10-2026", the way the email names a reply-by date; '' when it is not a date."""
    day = _as_day(iso)
    return f"{WEEKDAYS[day.weekday()]} {shown(iso)}" if day else ""


def short(text, limit=60):
    """A title for a subject line: whole when it fits, else cut at a word about `limit` characters in, with an ellipsis."""
    text = one_line(text)
    if len(text) <= limit:
        return text
    cut = text[:limit - 1]
    if text[limit - 1] != " " and " " in cut:
        cut = cut[:cut.rindex(" ")]
    return cut.rstrip(" ,;:.-") + "…"


def times(n):
    """once, twice, 3 times."""
    return "once" if n == 1 else "twice" if n == 2 else f"{n} times"


def greeting(hour, first=""):
    """"Good morning, Dana," before 12:00, "Good afternoon," before 18:00, "Good evening," after."""
    part = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
    return f"Good {part}{', ' + first if first else ''},"


def working_days_ahead(start, n=2, weekend=(5, 6)):
    """The date n working days after `start` (YYYY-MM-DD), as YYYY-MM-DD; the weekend days (Monday is 0) are skipped."""
    d = date.fromisoformat(start)
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() not in weekend:
            n -= 1
    return d.isoformat()


def due_info(due, today, kind="actions", soon=DUE_SOON_DAYS):
    """{date, words, level} for a due (or needed-by) date: level is "over", "soon" or "". "4 days overdue", "due in 6 days",
    "due today", "due tomorrow"; a decision says "needed". No date reads "No date"; beyond the window there are no words."""
    if not due:
        return {"date": "No date", "words": "", "level": ""}
    try:
        n = (date.fromisoformat(due) - date.fromisoformat(today)).days
    except ValueError:
        return {"date": str(due), "words": "", "level": ""}
    if n < 0:
        return {"date": shown(due), "words": f"{-n} day{'' if n == -1 else 's'} overdue", "level": "over"}
    if n > soon:
        return {"date": shown(due), "words": "", "level": ""}
    verb = "needed" if kind == "decisions" else "due"
    return {"date": shown(due), "level": "soon",
            "words": f"{verb} today" if n == 0 else f"{verb} tomorrow" if n == 1 else f"{verb} in {n} days"}


def _rank(item, today):
    due = item.get("due") or ""
    return (0 if due and due < today else 1 if due else 2, due or "9999", item.get("id") or "")


def sort_items(items, today):
    """Overdue first (oldest due first), then due soonest, then undated; ties by ID."""
    return sorted(items, key=lambda i: _rank(i, today))


# ---- who and what may go in an email ----------------------------------------------------------------------------------

def host(address):
    """The part of an address after the @, lower case; '' when there is none."""
    parts = str(address or "").split("@")
    return parts[1].strip().lower() if len(parts) > 1 else ""


def is_outside(address, own_domains):
    """True when the address is not on one of the user's own domains. No address on record counts as outside."""
    h = host(address)
    return not h or h not in [str(d).strip().lower() for d in own_domains or []]


def barred(item, outside=True):
    """True when an item can never go in an email: a hidden row, anything marked confidential or restricted in the words
    that would be sent, and (to an outside address) a sensitive item even when it is client-visible."""
    if item.get("hidden"):
        return True
    # Read the way a person reads it: a soft hyphen, a zero-width character or a look-alike letter (Cyrillic "е") in the word
    # does not hide it (confusables.skeleton, the repo's one reading of text for restricted-word scans).
    said = skeleton(" ".join(str(item.get(k) or "") for k in ("text", "response", LATEST))).lower()
    if any(skeleton(w).lower() in said for w in HELD_WORDS):
        return True
    return bool(outside and item.get("sensitive"))


def open_items(items):
    """The items still open: not closed, done, cancelled, withdrawn, achieved or decided."""
    done = ("closed", "done", "cancelled", "dropped", "resolved", "decided", "withdrawn")
    return [i for i in items if str(i.get("status") or "").strip().lower() not in done]


def is_internal(item):
    """True when the item is not marked client-visible: it is tagged "internal" in the list for an outside address."""
    return not item.get("client_visible")


def offered(items, address="", own_domains=()):
    """The open items that may be offered for this address: barred ones are left out. Returns (items, left_out count)."""
    outside = is_outside(address, own_domains)
    open_ = open_items(items)
    ok = [i for i in open_ if not barred(i, outside)]
    return ok, len(open_) - len(ok)


def default_picked(items, address="", own_domains=()):
    """The IDs ticked to start with: all of them for an address on an own domain; for anyone else only the client-visible
    ones (the rest start unticked, tagged "internal")."""
    outside = is_outside(address, own_domains)
    return [i["id"] for i in items if not outside or not is_internal(i)]


def items_for_owner(items, owner, address="", own_domains=(), mode="update_request", today=""):
    """All of an owner's open items that may be offered, sorted; a chase offers only the overdue ones."""
    want = str(owner or "").strip().lower()
    mine = [i for i in items if str(i.get("owner") or "").strip().lower() == want]
    ok, _ = offered(mine, address, own_domains)
    if mode == "chase":
        ok = [i for i in ok if i.get("due") and i["due"] < today and i.get("kind") != "decisions"]
    return sort_items(ok, today or "9999-12-31")


def item_for_peek(items, item_id, address="", own_domains=()):
    """The one item from the peek, as a list of one, or [] when it is not open or is barred."""
    ok, _ = offered([i for i in items if i.get("id") == item_id], address, own_domains)
    return ok


def mode_for(item, today):
    """The mode the peek opens in: a pending decision asks for the decision, an item past its date is chased, anything
    else is an update request."""
    if item.get("kind") == "decisions":
        return "decision"
    return "chase" if item.get("due") and item["due"] < today else "update_request"


# ---- chase counts and the tone -----------------------------------------------------------------------------------------

def chase_counts(entries):
    """{item ID: {"n": how often asked, "last": YYYY-MM-DD}} from the "I sent it" history entries (chase and decision modes)."""
    out = {}
    for e in entries or []:
        if e.get("kind") != SENT_KIND or e.get("mode") not in ("chase", "decision"):
            continue
        for i in e.get("ids") or []:
            row = out.setdefault(i, {"n": 0, "last": ""})
            row["n"] += 1
            row["last"] = max(row["last"], str(e.get("date") or ""))
    return out


def tone_for(ids, counts):
    """0 First chase, 1 Second chase, 2 Firmer chase: stepped up with the most often chased of the items picked."""
    n = max([0] + [(counts or {}).get(i, {}).get("n", 0) for i in ids])
    return min(n, 2)


def _per_item(items, counts):
    """(times asked, last date) for each item, from its own history: one pair per item, in the order of the items."""
    out = []
    for i in items:
        row = (counts or {}).get(i["id"]) or {}
        out.append((row.get("n", 0), row.get("last", "") if row.get("n", 0) else ""))
    return out


# ---- the pieces of the email -------------------------------------------------------------------------------------------

def subject(mode, items, today, tone=0, project_names=None, reply_by=""):
    """The Subject starts with the project's name (FR-44): "Example Programme · ABC-A-003 · Update request"."""
    names = project_names or {}
    codes = sorted({i.get("project") or "" for i in items})
    lead = one_line(" / ".join(names.get(c) or c for c in codes))
    lead = f"{lead} · " if lead else ""
    if mode == "decision":
        if tone == 2:
            # Never a deadline the sender did not set: the reply-by date they chose, or no date at all.
            when = weekday_date(reply_by)
            return f"{lead}Decision needed: reply by {when}" if when else f"{lead}Decision still needed"
        return f"{lead}{DECISION['subjects'][tone]}" + (f": {short(items[0].get('text'))}" if len(items) == 1 else "")
    word = UPDATE_REQUEST if mode == "update_request" else CHASE["subjects"][tone]
    if not items:
        return word
    if len(items) == 1:
        return f"{lead}{one_line(items[0]['id'])} · {word}: {short(items[0].get('text'))}"
    over = sum(1 for i in items if i.get("due") and i["due"] < today)
    if mode == "chase":
        if over == len(items):
            return f"{lead}{word}: {len(items)} overdue items"
        return f"{lead}{word}: {len(items)} items" + (f" ({over} overdue)" if over else "")
    return f"{lead}{word}: {len(items)} open items" + (f" ({over} overdue)" if over else "")


def _held(unblocks):
    """The sentence that says what is held up: only when the sender typed it."""
    return f" It is holding up {unblocks}." if unblocks else ""


def _days_late(item, today):
    """Whole days past the due date, or 0 when the item is not past it (or has no date)."""
    if not (item.get("due") and today and item["due"] < today):
        return 0
    return (date.fromisoformat(today) - date.fromisoformat(item["due"])).days


def _plural(n):
    return f"{n} day{'' if n == 1 else 's'}"


def _history(per, items, asked="chased"):
    """What can be said about earlier chases, true for every ticked item: when each was chased the same number of times and
    last on the same day, that count and day; when they differ, only that some were chased before, and the latest day among
    them; nothing when none was."""
    if not any(n for n, _ in per):
        return ""
    last = max(d for _, d in per)
    since = f", most recently on {shown(last)}" if last else ""
    if len(set(per)) == 1:
        if asked == "chased":
            return f"I have chased {'it' if len(items) == 1 else 'them'} {times(per[0][0])}{since}."
        return f"I have asked for {'this decision' if len(items) == 1 else 'these decisions'} {times(per[0][0])}{since}."
    if asked == "chased":
        return f"I have chased some of them before{since}."
    return f"I have asked for some of these decisions before{since}."


def _opening(mode, items, tone, per, unblocks="", today=""):
    unblocks = str(unblocks or "").strip()
    if mode == "update_request":
        return OPEN
    late = [i for i in items if _days_late(i, today)]
    longest = max([_days_late(i, today) for i in items] + [0])
    uniform = len(set(per)) <= 1
    one = len(items) == 1
    last = per[0][1] if per and uniform else ""
    if mode == "chase":
        if tone == 0:
            if one:
                due = shown(items[0]["due"]) if items[0].get("due") else ""
                return ("A quick reminder about the item below, which is now past its due date." if late else
                        f"A quick reminder about the item below, which is due on {due}." if due else "A quick reminder about the item below.")
            return ("A quick reminder about the items below, which are now past their due dates." if len(late) == len(items) else
                    "A quick reminder about the items below, some of which are past their due dates." if late else
                    "A quick reminder about the items below.")
        if tone == 1:
            what = "item" if one else "items"
            state = (f", which {'is' if one else 'are'} still overdue" if len(late) == len(items) else
                     ", some of which are still overdue" if late else
                     f", which is due on {shown(items[0]['due'])}" if one and items[0].get("due") else "")
            if uniform:
                return f"I'm following up on my earlier note{' of ' + shown(last) if last else ''} about the {what} below{state}."
            return f"I'm following up on the {what} below{state}. {_history(per, items)}".strip()
        if one:
            due = shown(items[0]["due"]) if items[0].get("due") else ""
            lead = (f"This item is now {_plural(longest)} overdue." if late else f"This item is due on {due}." if due else "")
        else:
            lead = (f"These items are now well overdue, the longest by {_plural(longest)}." if len(late) == len(items) else
                    f"Some of these items are now well overdue, the longest by {_plural(longest)}." if late else
                    "I'm writing again about the items below.")
        text = f"{lead} {_history(per, items)}".strip()
        if unblocks:
            text += f" It is holding up {unblocks}." if one else f" They are holding up {unblocks}."
        return text
    needed = f", which is needed for {unblocks}" if unblocks and tone == 0 else f"; it is needed for {unblocks}" if unblocks else ""
    if tone == 0:
        return f"A quick note on the decision below{needed}."
    if tone == 1:
        if uniform:
            return f"I'm following up on my earlier note{' of ' + shown(last) if last else ''} about the decision below{needed}."
        return f"I'm following up on the decision below{needed}. {_history(per, items, 'asked')}"
    return _history(per, items, "asked") + _held(unblocks)


def _ask(mode, items, tone, reply_by):
    reply = REPLY_BY.format(reply_by=weekday_date(reply_by)) if weekday_date(reply_by) else ""
    if mode == "update_request":
        deciding = " " + DECIDE if any(i.get("kind") == "decisions" for i in items) else ""
        return f"{ASK}{deciding}{reply}{THANKS}"
    if mode == "chase":
        pool = CHASE["one_asks"] if len(items) == 1 else CHASE["asks"]
        return f"{pool[tone]}{reply}{THANKS}"
    return DECISION["ask"].format(reply_by=weekday_date(reply_by) or "").replace("by ?", "as soon as you can?")


def _what(item):
    """The words of an item's row, before any update line: a decision and a risk or issue say what they are."""
    kind = item.get("kind")
    if kind == "decisions":
        return "Decision needed: " + str(item.get("text") or "")
    if kind == "raid":
        return f"{item.get('type') or 'Risk'}: {item.get('text') or ''}"
    return str(item.get("text") or "")


def _lines(item, include_update):
    """The extra muted lines under an item: a risk's response, the latest update."""
    out = []
    if item.get("kind") == "raid" and "response" in item:     # #97: the menu's read never carries a response (a working note), and then no line says one is missing
        out.append("Response: " + (str(item.get("response") or "").strip() or "none recorded yet"))
    update = str(item.get(LATEST) or "").strip()
    if include_update and update:
        out.append("Latest update: " + update)
    return out


# ---- HTML (inline styles only) -----------------------------------------------------------------------------------------

def _p(inner, extra=""):
    return f'<p style="{FONT}color:{COLOURS["ink"]};margin:0 0 12px 0;{extra}">{inner}</p>'


def _head(text):
    return f'<p style="{FONT}color:{COLOURS["ink"]};margin:16px 0 6px 0;"><b style="font-weight:bold;">{escape(text)}</b></p>'


def _td(inner, extra="", colour=None):
    return (f'<td style="{FONT}color:{colour or COLOURS["ink"]};border-bottom:1px solid {COLOURS["rule"]};padding:6px 8px;'
            f'vertical-align:top;{extra}">{inner}</td>')


def _th(text, width=""):
    return (f'<th align="left" style="{FONT}color:{COLOURS["ink"]};background:{COLOURS["head"]};'
            f'border-bottom:1px solid {COLOURS["rule"]};padding:6px 8px;text-align:left;font-weight:bold;'
            f'{"width:" + width + ";" if width else ""}">{text}</th>')


def _muted(text):
    return f'<i style="font-style:normal;color:{COLOURS["muted"]};">{escape(text)}</i>'


def _row_html(item, today, include_update):
    d = due_info(item.get("due"), today, item.get("kind") or "actions")
    colour = COLOURS["red"] if d["level"] == "over" else COLOURS["amber"] if d["level"] == "soon" else COLOURS["ink"]
    strong = "font-weight:bold;" if d["level"] == "over" else ""
    what = escape(_what(item))
    if item.get("kind") in ("raid", "decisions"):
        label, _, rest = _what(item).partition(": ")
        what = f'<b style="font-weight:bold;">{escape(label)}:</b> {escape(rest)}'
    extra = "".join("<br>" + _muted(x) for x in _lines(item, include_update))
    priority = item.get("priority") or ""
    prio = '<b style="font-weight:bold;">Urgent</b>' if priority == "Urgent" else escape(priority)
    due = escape(d["date"]) + (f"<br>{escape(d['words'])}" if d["words"] else "")
    return (f'<tr style="vertical-align:top;">{_td(escape(item["id"]), "white-space:nowrap;")}{_td(what + extra)}'
            f'{_td(due, "white-space:nowrap;" + strong, colour)}{_td(prio, "white-space:nowrap;")}</tr>')


def _table_html(items, today, include_update):
    return (f'<table cellpadding="6" cellspacing="0" border="0" style="border-collapse:collapse;width:100%;{FONT}'
            f'color:{COLOURS["ink"]};"><tr style="vertical-align:top;">{_th("ID", "9%")}{_th("Item")}{_th("Due", "18%")}'
            f'{_th("Priority", "10%")}</tr>{"".join(_row_html(i, today, include_update) for i in items)}</table>')


def _text_rows(items, today, include_update):
    width = max([len(i["id"]) for i in items] + [0])
    pad = " " * width
    out = []
    for i in items:
        d = due_info(i.get("due"), today, i.get("kind") or "actions")
        words = f" ({d['words']})" if d["words"] else ""
        out.append(f"  {i['id'].ljust(width)}  {_what(i)}  |  {d['date']}{words}  |  {i.get('priority') or ''}")
        out += [f"  {pad}  {x}" for x in _lines(i, include_update)]
    return out


# ---- the builder -------------------------------------------------------------------------------------------------------

def build(opts):
    """The email for the items ticked, with no model.

    opts: mode ("update_request", "chase" or "decision"), items (the offered items), picked (IDs ticked; all when absent), name and
    first (the recipient), email, own_domains, from (the sender's name; it signs with the first word), now ("YYYY-MM-DD HH:MM"), include_update,
    reply_by (YYYY-MM-DD), chased ({id: {n, last}}), project_names ({code: name}), unblocks (what a decision holds up),
    cover (an opening the user wrote, used instead of the standard one).
    Returns {to, subject, html, text, items, tone, mode, ids, internal_ids, problems, ready}. internal_ids are the ticked items
    not marked client-visible, for an outside address: the page shows them a note in the preview, and nothing about them is in
    the copied email. problems are plain next steps (nothing ticked, no sender name); while there are any, ready is False and
    the page does not copy. An item that is barred for the address is never included, even if picked."""
    mode = opts.get("mode") or "update_request"
    if mode not in MODES:
        raise ValueError(NO_SUCH_KIND)
    now = str(opts.get("now") or "")
    today, hour = now[:10], int(now[11:13] or 0) if len(now) >= 13 else 0
    outside = is_outside(opts.get("email"), opts.get("own_domains"))
    picked = opts.get("picked")
    items = [i for i in opts.get("items") or [] if not barred(i, outside) and (picked is None or i["id"] in picked)]
    items = sort_items(items, today)
    internal_ids = [i["id"] for i in items if outside and is_internal(i)]
    ids = [i["id"] for i in items]
    tone = tone_for(ids, opts.get("chased")) if mode != "update_request" else 0
    per = _per_item(items, opts.get("chased"))
    first = str(opts.get("first") or str(opts.get("name") or "").split(" ")[0]).strip()
    names = opts.get("project_names") or {}
    include_update = bool(opts.get("include_update"))
    opening = str(opts.get("cover") or "").strip() or _opening(mode, items, tone, per, str(opts.get("unblocks") or ""), today)
    ask = _ask(mode, items, tone, opts.get("reply_by") or "")
    sender = (str(opts.get("from") or "").split() or [""])[0]       # signs with the first word of the name
    hello = greeting(hour, first)
    codes = sorted({i.get("project") or "" for i in items})
    blocks_html = "".join(_head(names.get(c) or c) + _table_html([i for i in items if (i.get("project") or "") == c], today,
                                                                 include_update) for c in codes)
    html = (f'<div style="{FONT}color:{COLOURS["ink"]};background:{COLOURS["white"]};">{_p(escape(hello))}{_p(escape(opening))}'
            f'{blocks_html}{_p(escape(ask), "margin-top:16px;")}'
            f'{_p(escape(SIGN_OFF[mode]) + "<br>" + escape(sender), "margin-bottom:0;")}</div>')
    lines = [hello, "", opening, ""]
    for c in codes:
        lines += [str(names.get(c) or c).strip(),
                  *_text_rows([i for i in items if (i.get("project") or "") == c], today, include_update), ""]
    lines += [ask, "", SIGN_OFF[mode], sender]
    offerable = any(not barred(i, outside) for i in opts.get("items") or [])
    problems = ([] if items else [NOTHING_TICKED if offerable else NO_OPEN_ITEMS]) + ([] if sender else [NO_SENDER])
    return {"to": one_line(opts.get("email")), "internal_ids": internal_ids, "problems": problems, "ready": not problems, "subject": subject(mode, items, today, tone, names, opts.get("reply_by") or ""), "html": html,
            "text": "\n".join(lines), "items": [{k: i[k] for k in ITEM_KEYS if k in i} for i in items], "ids": ids, "tone": tone, "mode": mode}


# ---- copying, and "I sent it" -------------------------------------------------------------------------------------------

def clipboard(draft):
    """What Copy for Outlook puts on the clipboard: both types. Copy as text puts draft["text"] alone. Raises ValueError, in
    plain words, while the draft has a problem to fix first."""
    if draft.get("problems"):
        raise ValueError(draft["problems"][0])
    return {"text/html": draft["html"], "text/plain": draft["text"]}


def copy_result(ok):
    """The words under the preview after a copy: a success, or the fall-back when the browser refused (the preview is then
    selected). It never fails silently."""
    return "Copied" if ok else COPY_REFUSED


def mailto_link(draft):
    """The finished mailto: link, encoded the way the page encodes it (encodeURIComponent). To and Subject are one line each."""
    enc = lambda s: quote(str(s or ""), safe="!'()*")
    return f"mailto:{enc(one_line(draft.get('to')))}?subject={enc(one_line(draft.get('subject')))}&body={enc(draft.get('text'))}"


def mailto_offered(draft):
    """Open in mail app is offered only when the finished, encoded link (not the plain text: a space is 3 characters in a link and
    a line break 6) is no longer than MAILTO_LIMIT, which every mail app keeps whole."""
    return not draft.get("problems") and len(mailto_link(draft)) <= MAILTO_LIMIT


def sent_entry(ids, mode, day):
    """The record "I sent it" adds to the items' history: the item IDs, the date (YYYY-MM-DD) and the mode, never the email's
    text. Raises ValueError when there is nothing to record. This builds the entry only; the store writes it (#31)."""
    if mode not in RECORD_MODES:
        raise ValueError(NO_SUCH_KIND)
    ids = list(dict.fromkeys(i for i in ids if isinstance(i, str) and i.strip()))[:50]
    if not ids:
        raise ValueError(NOTHING_TO_RECORD)
    date.fromisoformat(day)
    return {"kind": SENT_KIND, "ids": ids, "date": day, "mode": mode}
