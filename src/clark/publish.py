"""Publish one HTML report for a project: Local, boxed layout (#39; BRD FR-80, FR-81, FR-83).

One UTF-8 file, {CODE}-report-{week_ending or date}.html: the committed page (clark/page, #35, so a local brand's tokens
are layered) plus three insertions and nothing else: a <meta> Content-Security-Policy straight after <meta charset>, the
report's data in <script type="application/json" id="clark-data"> before </body>, and the project's name as the <title>
with data-mode="view" on <html>. The page's own script finds that block and runs in view mode (no fetch, no token, no
Settings tab). The file has no clark-boot token block and refers to no outside address, and opens from file:// with no server.

What goes in is chosen BEFORE the file is made, by select(): allow-lists, never deny-lists. A row is published only if it is
not archived, its client_visible flag is on, it is not in report_hidden and it carries no label whose behaviour or default
choice is "exclude" (Sensitive always, names compared without case). Each table has a PUBLISH_FIELDS tuple of the columns the
view shows, and nothing else is ever copied, so internal_note, movement, source and the project's folders are not in the file.
select(), clean_html(), render(), csp_meta() and file_name() are pure; read_inputs() reads the database once, read-only.

- Q1 yes: a hidden section of type actions, raid, decisions, milestones or usecases drops that kind's rows and its tab (a hidden
  Milestones section also drops the Client Requested Report View's tab, whose figures are the milestones).
- Q2 yes (Head ruling on #39): publish() records the verified file with Store.log_publication, once, after the write is read
  back and compared: a `publications` row with the file's SHA-256 and nothing else (no step, no write to the project row). The
  folder to offer next time is read back from the latest publication (Store.last_publish_folder).
- Q3 no route and no button: the folder arrives as an argument; the Save dialog is a later route's job (platform.choose_save_file).
  `python3 -m clark.publish CODE FOLDER` is for manual runs.
- Q4 yes: a milestone's state_reason and the project's health_reason are published (the text the client reads under the
Not here: To client (#43), Word, comments (#40), spine and cover layouts (#46: they render boxed in v0.1), the editor's section UI (#65).

Standard library only, Python 3.9.
"""
import argparse
import base64
import bisect
import getpass
import hashlib
import heapq
from datetime import date
import html as htmllib
import json
import logging
import os
import re
import secrets
import stat
import sys
import unicodedata
from html.parser import HTMLParser
from pathlib import Path

from clark import doclinks, milestones, page, platform, section_bodies
from clark.store import (COMMITMENTS, GANTT_COLUMNS, GANTT_HIDEABLE, GANTT_DEFAULT_HIDDEN, GANTT_DEFAULT_TAB, GANTT_ID, GANTT_TAB_LIMIT, GANTT_TEXT_LIMITS, Invalid as StoreInvalid,
                         NumberTaken, check_section_body, excluded_label_names, gantt_list, open_store)
from clark.server import csp_hashes        # the one place the policy's hashes are worked out (#33); never copied

LOG = logging.getLogger("clark.publish")
MAX_BYTES = 5 * 1024 * 1024               # NFR-8: a file larger than this is refused
VERSION = 1                               # the data block's shape; the page refuses another
KINDS = ("milestones", "actions", "raid", "decisions", "use_cases")
SECTION_OF_KIND = {"milestones": "milestones", "actions": "actions", "raid": "raid", "decisions": "decisions",
                   "use_cases": "usecases"}
WORK_KINDS = ("actions", "raid", "decisions")
# What the editor offers when report_sections has no rows (#65 is not built): this order, none hidden.
DEFAULT_SECTIONS = tuple({"id": f"s-{t}", "type": t, "title": title, "body": "", "beside": 0, "hidden": 0, "sort_order": n}
                         for n, (t, title) in enumerate((("current", "Current state"), ("glance", "At a glance"),
                                                         ("usecases", "Use cases"), ("milestones", "Milestones"),
                                                         ("raid", "Risks and issues"), ("actions", "Actions"),
                                                         ("decisions", "Decisions")), 1))
SECTION_TYPES = ("current", "glance", "usecases", "milestones", "text", "raid", "actions", "decisions", "docs", "gantt") + section_bodies.BODY_TYPES      # row 926: gantt carries no data of its own
BUILT_IN_SECTIONS = ("current", "glance", "usecases", "milestones", "raid", "actions", "decisions", "docs")      # row 906: the sections whose data lives elsewhere


def hidden_types(sections, deleted=False):
    """The built-in section types the published file carries nothing of (row 906). A section left out (hidden) is one; so is a
    built-in with no section row, when the project HAS section rows or has had them all deleted (`deleted`). No rows and none ever
    (a project made before #65): the default sections, none hidden, so the set is empty."""
    if not sections and not deleted:
        return set()
    have = {s.get("type") for s in sections or ()}
    return {s.get("type") for s in sections or () if s.get("hidden")} | {t for t in BUILT_IN_SECTIONS if t not in have}
# "docs" (#74): only while it has a document to show (documents()); needs, tracker and the section templates (#96) carry content: a section of those types stays in only when its
# body checks again and its published fields are not empty (_content; a template stub is never in the file)

# The columns the view shows, per table. Anything not named here is never copied into the file.
PUBLISH_FIELDS = {
    "projects": ("code", "name", "sponsor", "phase", "health", "health_reason", "client_name", "current_state", "week_ending", "layout"),
    "milestones": ("id", "name", "description", "baseline_date", "forecast_date", "status", "sort_order", "percent_complete",
                   "state_reason", "owner", "actual_date", "client_message", "workstream"),
    "workstreams": ("id", "name", "status"),
    "actions": ("id", "description", "workstream", "owner", "priority", "due_date", "status", "raised", "closed",
                "latest_update", "client_message", "milestone", "use_case"),
    "raid": ("id", "type", "workstream", "description", "owner", "due_date", "impact", "likelihood",
             "priority", "status", "raised", "closed", "client_message", "milestone", "use_case"),
    "decisions": ("id", "decision", "made_by", "client_message", "date", "status", "needed_by",
                  "revisit", "replaces", "use_case"),
    "use_cases": ("id", "ref", "title", "status", "headline", "standing", "sort_order", "commitment"),   # #709: the flag goes with the use case
    "links": ("from_item", "to_item", "kind"),
    "documents": ("title", "kind", "url", "date"),        # #74: never its id, place or archive flag
    "gantt_lines": ("id", "name") + tuple(c for c in GANTT_COLUMNS if c != "show"),   # row 926: every column a client may ever see; the line's eye (`show`) only decides, and gantt_hidden_columns takes columns out of the copy (gantt_for_client)
}
RICH = {"projects": ("current_state",), "use_cases": ("standing",)}     # HTML the editor wrote: through clean_html
# Read from the database as well, only to decide (never copied): the gates, and what a milestone's state is worked out from.
GATES = {"milestones": ("client_visible", "archived", "state", "state_set"), "workstreams": ("archived",),
         "actions": ("client_visible", "archived", "client_action"), "raid": ("client_visible", "archived", "client_action"),   # row 811: client_action only decides, it is never copied
         "decisions": ("client_visible", "archived"), "use_cases": ("client_visible", "archived"),
         "gantt_lines": ("show", "project"),      # row 926: a line with show 0 is dropped before anything is copied
         "projects": ("show_gantt_client", "gantt_tab_name", "gantt_title", "gantt_hidden_columns", "gantt_default_rows")}     # row 926: decide whether the Gantt tab is in the file and what it is called; none is copied as a project field
ORDER = {"milestones": "sort_order, id", "workstreams": "id", "actions": "id", "raid": "id", "decisions": "id",
         "use_cases": "sort_order, id"}
CODE = re.compile(r"[A-Z][A-Z0-9]{2,6}")


class PublishError(RuntimeError):
    """The file was not made, in words a person can act on."""


# ===== A budget for the scan (#112): a scan that would take too long is a refusal, never a hang =====
# Every loop of the scan spends one unit per step on a Work. A text that costs more than SCAN_BUDGET is not read to the end: the
# scan stops and says so as a finding (outside_addresses) or an error (check_brand), so the file is not published or copied.
# The real page costs about 14,700 steps (tests/test_publish_scan_budget.py measures it and keeps the budget at least
# 20 times that). A count of steps, not a clock: it is the same on every machine and needs no signal or thread.
# The budget grows with the text: SCAN_BUDGET plus SCAN_PER_CHAR steps for each character, never more than SCAN_CEILING (a big
# hand-made page or stylesheet passes; a shape that costs far more per character than ordinary markup still refuses).
SCAN_BUDGET = 400_000
SCAN_PER_CHAR = 1
SCAN_CEILING = 4_000_000
TOO_BIG_FOUND = "text too long or too tangled to check for outside addresses"


class ScanTooBig(Exception):
    """The scan went over its budget. Caught inside this module, where it becomes a finding or a PublishError."""


class Work:
    """A count of scan steps. spend() raises ScanTooBig once more than `limit` have been spent."""
    __slots__ = ("n", "limit")

    def __init__(self, limit=None, size=0):
        self.n = 0
        self.limit = min(SCAN_BUDGET + SCAN_PER_CHAR * size, max(SCAN_CEILING, SCAN_BUDGET)) if limit is None else limit

    def spend(self, steps=1):
        self.n += steps
        if self.n > self.limit:
            raise ScanTooBig()


# ===== Rich text: an allow-list cleaner (creaite's clean_markup, cut down) =====
DROP_WITH_TEXT = {"script", "style", "iframe", "object", "embed", "form", "template", "noscript", "svg", "math", "textarea",
                  "select"}                                   # these and everything inside them; link, meta... just go
VOID = {"br", "hr", "img"}
ALLOWED_TAGS = {"p", "br", "hr", "b", "strong", "i", "em", "u", "s", "sub", "sup", "code", "pre", "blockquote", "span", "div",
                "ul", "ol", "li", "h2", "h3", "h4", "a", "img", "table", "thead", "tbody", "tr", "th", "td"}
ALLOWED_ATTRS = {"a": ("href", "title"), "img": ("src", "alt", "title"), "td": ("colspan", "rowspan"),
                 "th": ("colspan", "rowspan")}
DATA_IMAGE = re.compile(r"data:image/(png|jpeg|gif|webp);base64,[A-Za-z0-9+/=]*", re.I)
SPAN = re.compile(r"[0-9]{1,3}")


def safe_href(value):
    """True for a link a reader may follow: https:, mailto: or a link within the page. Anything else (javascript:, data:, a
    relative or protocol-relative address) is not."""
    v = re.sub(r"[\x00-\x20]+", "", value or "").lower()
    return v.startswith(("https://", "mailto:", "#"))


class _Cleaner(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.open, self.skip, self.depth = [], [], None, 0

    def handle_starttag(self, tag, attrs):
        if self.skip:
            self.depth += tag == self.skip
            return
        if tag in DROP_WITH_TEXT:
            self.skip, self.depth = tag, 1
            return
        if tag not in ALLOWED_TAGS:
            return                                                # unwrapped: its text stays
        keep, given = [], dict(attrs)
        for name in ALLOWED_ATTRS.get(tag, ()):
            value = given.get(name)
            if value is None:
                continue
            if name == "href" and not safe_href(value):
                continue
            if name == "src" and not DATA_IMAGE.fullmatch(value.strip()):
                return                                            # an image that isn't embedded is dropped whole
            if name in ("colspan", "rowspan") and not SPAN.fullmatch(value.strip()):
                continue
            keep.append(f' {name}="{htmllib.escape(value.strip() if name == "src" else value, quote=True)}"')
        if tag == "img" and not any(a.startswith(" src=") for a in keep):
            return
        if tag == "a":
            keep.append(' rel="noopener noreferrer"')
        self.out.append(f"<{tag}{''.join(keep)}>")
        if tag not in VOID:
            self.open.append(tag)

    def handle_endtag(self, tag):
        if self.skip:
            if tag == self.skip:
                self.depth -= 1
                if self.depth == 0:
                    self.skip = None
            return
        if tag in self.open:
            while self.open:
                done = self.open.pop()
                self.out.append(f"</{done}>")
                if done == tag:
                    break

    def handle_data(self, data):
        if not self.skip:
            self.out.append(htmllib.escape(data, quote=False))

    def close_all(self):
        self.close()
        while self.open:
            self.out.append(f"</{self.open.pop()}>")


def clean_html(text):
    """`text` (HTML the editor wrote) reduced to the allow-list: no script, style, iframe, object, form, link or meta, no
    on* or style attributes, an img only if it is embedded (data:image/png, jpeg, gif or webp), a link only to https:,
    mailto: or this page. Text is always escaped again, so what comes back is well formed and can't reach outside."""
    if not isinstance(text, str) or not text:
        return ""
    c = _Cleaner()
    c.feed(text)
    c.close_all()
    return "".join(c.out)


# ===== Choosing what is published (pure) =====
def _excluded_labels(rules):
    """The label names (lower case) that keep a row out: Sensitive, and any label whose behaviour or default choice is
    exclude."""
    return excluded_label_names(rules)


REASON_LIMIT = 2000                                             # the writer's cap on a project's health reason (store.REASON_LIMIT)
_UNSEEN = frozenset({"Cc", "Cf", "Cs", "Co", "Zl", "Zp"})


def reason_text(value):
    """clark (#45 review): a project's health reason as the file carries it, whatever is stored (an old row, or one written
    around the writer): line breaks kept (a Windows one made plain), every other control, format, surrogate, private-use or
    separator character dropped (a bidi override, a zero-width space), cut at REASON_LIMIT characters. None stays None."""
    if value is None:
        return None
    text = str(value).replace("\r\n", "\n")
    return "".join(c for c in text if c == "\n" or unicodedata.category(c) not in _UNSEEN)[:REASON_LIMIT]


def _pick(row, fields):
    return {f: row.get(f) for f in fields}


def _content(s, ctx=None):
    """For a needs, tracker or section template section: what its body adds to its entry in the file (a dict, {} when the base
    publishes nothing of it), or None when the section is left out: its body is empty, or does not check, or (a template) its
    module has nothing to publish. `ctx` (section_bodies.Context) is what select already kept, for a template's live parts. The stored text is checked AGAIN here
    (store.check_section_body, the same checker a write meets), never trusted, so a body that is bad for any reason (written
    by an older or another clark, or by hand) never reaches the file. What is published is fields picked by name from the
    CHECKED value (section_bodies.published), never the stored text, and never passed through clean_html."""
    try:
        text = check_section_body(s["type"], s.get("body"))
    except StoreInvalid:
        return None
    return section_bodies.published(s["type"], json.loads(text), ctx) if text else None


def _keeper(d, code, hidden_ids, blocked):
    """keep(row, table): whether a row may be published. The one test of the gates (archived, the eye, the project, the
    report-hidden list, the exclude labels), shared by select and client_use_cases."""
    item_labels = d.get("labels") or {}

    def keep(row, table):
        return (row.get("archived") == 0 and ("client_visible" not in GATES[table] or row.get("client_visible") == 1)
                and row.get("project", code) == code and row.get("id") not in hidden_ids
                and not any(str(n).casefold() in blocked for n in item_labels.get(row.get("id"), ())))
    return keep


def _document(row):
    """#74: one document as the file carries it, or None to leave it out. Every field is checked again here, never trusted: the
    link must pass doclinks.check_link (the one link rule; a bad one drops the document, it is never repaired) and the title must
    not read as the address of another site; the title is text with hidden characters dropped (doclinks.link_label) and must hold
    something; a kind not in doclinks.KINDS drops the document (it is refused, never published as an empty kind) and a date that is not a real day is carried as nothing."""
    try:
        url = doclinks.check_link(row.get("url"))
        title = doclinks.link_label(row.get("title"), url) if str(row.get("title") or "").strip() else ""
        if not title or doclinks.looks_like_other_place(title, url):
            return None
    except doclinks.LinkError:
        return None
    day = row.get("date")
    try:
        day = day if isinstance(day, str) and re.fullmatch(r"\d{4}-\d\d-\d\d", day) and date.fromisoformat(day) else None
    except ValueError:
        day = None
    kind = row.get("kind")
    if kind not in doclinks.KINDS:
        return None
    return {"title": title, "kind": kind, "url": url, "date": day}


def documents(rows, code, hidden_ids, hidden_types):
    """#74: the documents a client may see, in their order: live (not archived), this project's, not hidden by the eye
    (report_hidden), and only while the Supporting documents section is not hidden; each through _document."""
    if "docs" in hidden_types:
        return []
    live = [r for r in sorted(rows or (), key=lambda r: (r.get("sort_order") or 0, str(r.get("id"))))
            if r.get("archived") == 0 and r.get("project", code) == code and r.get("id") not in hidden_ids]
    out = []
    for r in live:
        c = _document(r)
        if c:
            out.append(_pick(c, PUBLISH_FIELDS["documents"]))
        else:                          # issue 610: a live document that cannot be published is logged (its id only: no title, no address)
            LOG.warning("Document %s is not in the published file: its link, title or kind cannot be used.", r.get("id"))
    return out


OPEN_STEPS = ("Open", "Delayed")                                # an action's statuses that are still to do


def client_use_cases(data, code, hidden_ids=(), label_rules=(), hidden_types=()):
    """The single place for "what a client may see of a use case". Given `data` (as Store.data_for gives it), the project
    `code`, the report-hidden ids, the label rules and the hidden section types, returns a list, in the data's order, of
    {"id", "next_steps": [action ids], "milestones": [milestone ids]}, one per use case the client may see, and nothing else.

    A use case is in the list when it is not archived, is on the dashboard (client_visible, the eye), belongs to the project,
    is not report-hidden, has no Sensitive or exclude label, and the Use cases section is not hidden. Its next steps are
    the actions that point at it that pass the same gates and are still open (and the Actions section is not hidden). Its
    milestones are the milestones named by those next steps that pass the gates (and the Milestones section is not hidden).
    Ids only: the rows are published once, by select, and an id can only name a row that was published. The caller (the
    published file, or a route that tells the editor what the client sees) never repeats this rule."""
    hidden_types = set(hidden_types or ())
    keep = _keeper(data, code, set(hidden_ids or ()), _excluded_labels(label_rules))

    def shown(kind):
        return [] if SECTION_OF_KIND[kind] in hidden_types else [r for r in data.get(kind) or () if keep(r, kind)]
    steps = [a for a in shown("actions") if a.get("status") in OPEN_STEPS]
    milestone_ids = {m["id"] for m in shown("milestones")}
    pages = []
    for u in shown("use_cases"):
        mine = [a for a in steps if a.get("use_case") == u["id"]]
        named = {a.get("milestone") for a in mine}
        pages.append({"id": u["id"], "next_steps": [a["id"] for a in mine],
                      "milestones": sorted(named & milestone_ids)})
    return pages


def flagged_needs(rows):
    """Row 811b: the rows the 'Needs from you' list gains from work items flagged client_action. `rows` is select's own kept rows
    (the gates already met: client_visible, not archived, not report-hidden, no Sensitive or exclude label, section not hidden), so
    this adds no second rule of what a client may see. Only an action or a risk/issue that is flagged AND still open (OPEN_STEPS;
    a risk or issue is only Open) is listed; a decision never (it has no flag). Actions first, then risks and issues, each in the
    order select kept them (by id), so the order is the same every time. A row is {what, kind, from, by} as a hand-typed one is:
    what is the item's client wording (client_message) when set, else its description, which is the item's title and is published as its name in the Work rows already (hidden characters out, cut at 300), kind 'information', from always blank (an owner here is one of our own people; a typed row's From is who at the client owes it, which is not known), by its due date written DD-MM-YYYY."""
    out = []
    for k in ("actions", "raid"):
        for r in rows[k]:
            if r.get("client_action") != 1 or r.get("status") not in OPEN_STEPS:
                continue
            what = next((t for t in (reason_text(" ".join(str(r.get(f) or "").split())).strip() for f in ("client_message", "description")) if t), "")[:section_bodies.NEEDS_WHAT_MAX].strip()
            if not what:
                continue
            due = r.get("due_date")
            due = f"{due[8:10]}-{due[5:7]}-{due[:4]}" if isinstance(due, str) and re.fullmatch(r"\d{4}-\d\d-\d\d", due) else ""
            out.append({"what": what, "kind": "information", "from": "", "by": due})
    return out


# ===== The Gantt (row 926): the client's copy of a project's lines =====
GANTT_TYPES = ("phase", "task", "milestone")
GANTT_HEALTHS, GANTT_PRIORITIES = ("Green", "Amber", "Red"), ("High", "Medium", "Low")
GANTT_ONE_LINE = {"owner": GANTT_TEXT_LIMITS["owner"], "workstream": GANTT_TEXT_LIMITS["workstream"], "deliverable": GANTT_TEXT_LIMITS["deliverable"]}


def _gantt_day(v):
    """`v` when it is a real YYYY-MM-DD day, else None."""
    try:
        return v if isinstance(v, str) and re.fullmatch(r"\d{4}-\d\d-\d\d", v) and date.fromisoformat(v) else None
    except ValueError:
        return None


def _gantt_amount(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and 0 <= v < float("inf") else None


def _gantt_hidden(project):
    """The columns this project keeps out of the client's copy: gantt_hidden_columns as stored, only names that are columns. Exactly
    empty text hides nothing (the person chose that; blanks and commas alone are not a choice, so they hide the default). Anything else that cannot be read as a list of known names hides the default seven,
    never fewer: not text, an unknown name ('NOTE', '["note"]'), or text that names no column that can be hidden."""
    raw = project.get("gantt_hidden_columns")
    if not isinstance(raw, str):
        return set(GANTT_DEFAULT_HIDDEN)
    if raw == "":                                    # exactly the empty text, which is all the editor writes for "hide nothing"; ' ', ',' and ',,' are not a choice
        return set()
    names = gantt_list(raw)
    known = set(GANTT_COLUMNS) | {"id", "name"}      # id, name and the four chart columns are tolerated in a list written before they were un-hideable
    if any(n not in known for n in names):
        return set(GANTT_DEFAULT_HIDDEN)
    hidden = {n for n in names if n in GANTT_HIDEABLE}
    return hidden or set(GANTT_DEFAULT_HIDDEN)


def _gantt_line(row, code):
    """One Gantt line as the client may have it before columns are chosen, or None to leave it out. Every value is checked again
    here, never trusted (a row written around the writer): a line that fails (an id that is not this project's, a type that is not
    one of the three, no name, a date that is not a real day, an end before its start, a milestone on two days) is left out, never
    repaired, and its id only is logged."""
    ident = row.get("id")
    start, end = _gantt_day(row.get("start")), _gantt_day(row.get("end"))
    name = " ".join(reason_text(row.get("name")).split())[:GANTT_TEXT_LIMITS["name"]] if isinstance(row.get("name"), str) else ""
    ok = (isinstance(ident, str) and GANTT_ID.fullmatch(ident) and ident.startswith(code + "-GNT-") and row.get("type") in GANTT_TYPES
          and name and start and end and start <= end and (row["type"] != "milestone" or start == end))
    if not ok:
        LOG.warning("Gantt line %s is not in the published file: it cannot be used.", ident if isinstance(ident, str) and GANTT_ID.fullmatch(ident) else "?")
        return None
    pct = row.get("pct")
    c = {"id": ident, "name": name, "type": row["type"], "start": start, "end": end,
         "pct": pct if type(pct) is int and 0 <= pct <= 100 else 0,
         "health": row.get("health") if row.get("health") in GANTT_HEALTHS else "",
         "priority": row.get("priority") if row.get("priority") in GANTT_PRIORITIES else "",
         "baseline_start": _gantt_day(row.get("baseline_start")), "baseline_end": _gantt_day(row.get("baseline_end")),
         "effort": _gantt_amount(row.get("effort")), "budget": _gantt_amount(row.get("budget")),
         "note": reason_text(row.get("note"))[:GANTT_TEXT_LIMITS["note"]] if isinstance(row.get("note"), str) else "",
         "parent": row.get("parent"), "depends": gantt_list(row.get("depends")) if isinstance(row.get("depends"), str) else []}
    for f, limit in GANTT_ONE_LINE.items():
        c[f] = " ".join(reason_text(row.get(f)).split())[:limit] if isinstance(row.get(f), str) else ""
    return c


def gantt_for_client(d, code, project_name):
    """The Gantt tab's data for the published file, or None when there is no tab: the project's show_gantt_client is not 1, or no
    line is left (the tab needs at least one line with its eye on). The ONE place a client's Gantt is decided, and it runs before
    anything is copied: only a line whose `show` is exactly 1 and which belongs to this project is read at all; a dependency on a
    line that is not in the copy is dropped; a parent that is not in the copy (or is not a phase) reads as no parent; a dependency that
    would close a circle is dropped. The columns in the project's gantt_hidden_columns are not in the copy at all (not hidden by a
    style): the copy holds the line's id and name and every column not on that list. Returns {"tab_name", "title", "columns",
    "lines"}; `columns` names the columns a line carries."""
    project = d.get("project") or {}
    if type(project.get("show_gantt_client")) is not int or project["show_gantt_client"] != 1:      # exactly the whole number 1: True, 1.0 and "1" are not
        return None
    eyed = [r for r in d.get("gantt_lines") or () if type(r.get("show")) is int and r["show"] == 1 and r.get("project", code) == code]
    eyed.sort(key=lambda r: (r["sort_order"] if type(r.get("sort_order")) is int else 0, str(r.get("id"))))
    lines = {}
    for r in eyed:
        c = _gantt_line(r, code)
        if c and c["id"] not in lines:
            lines[c["id"]] = c
    if not lines:
        return None
    reach = {}                                                   # the dependencies kept so far: id -> ids

    def reaches(start, goal):
        seen, todo = set(), [start]
        while todo:
            n = todo.pop()
            if n == goal:
                return True
            if n not in seen:
                seen.add(n)
                todo.extend(reach.get(n, ()))
        return False
    for c in lines.values():
        kept = []
        for dep in c["depends"]:
            if dep in lines and dep != c["id"] and dep not in kept and not reaches(dep, c["id"]):
                kept.append(dep)
        reach[c["id"]] = kept
        c["depends"] = kept
        up = lines.get(c["parent"]) if isinstance(c["parent"], str) else None
        c["parent"] = up["id"] if up is not None and up["type"] == "phase" and c["type"] != "phase" else None
    hidden = _gantt_hidden(project)
    shown = [f for f in PUBLISH_FIELDS["gantt_lines"] if f in ("id", "name") or f not in hidden]
    tab = " ".join(reason_text(project.get("gantt_tab_name")).split())[:GANTT_TAB_LIMIT] if isinstance(project.get("gantt_tab_name"), str) else ""
    title = " ".join(reason_text(project.get("gantt_title")).split())[:120] if isinstance(project.get("gantt_title"), str) else ""
    rows = project.get("gantt_default_rows")
    return {"tab_name": tab or GANTT_DEFAULT_TAB, "title": title or project_name, "columns": shown,
            "default_rows": rows if type(rows) is int and 1 <= rows <= 500 else None,
            "lines": [{f: c[f] for f in shown} for c in lines.values()]}



def select(inputs):
    """What goes in the file, from `inputs` (read_inputs' shape: data as Store.data_for gives it, and hidden, sections,
    label_rules, changes, undone, as_at). Returns {"data", "sections", "tabs", "as_at", "needs_dropped"} (the count of flagged items the 100-row cap left out; build() takes it out and logs it). Everything not allowed is absent,
    not hidden: dropped rows, fields outside PUBLISH_FIELDS, and what only they reach (links, labels, workstreams)."""
    d, as_at = inputs["data"], inputs["as_at"]
    project = d.get("project") or {}
    code = project.get("code")
    if not code:
        raise PublishError("There is no project to publish.")
    given, deleted = inputs.get("sections"), bool(inputs.get("sections_deleted"))      # row 906: every section deleted is not "no sections yet"
    sections = sorted(given or ([] if deleted else DEFAULT_SECTIONS), key=lambda s: (s.get("sort_order", 0), str(s.get("id"))))
    hidden_types = globals()["hidden_types"](given, deleted)
    hidden_ids = set(inputs.get("hidden") or ())
    blocked = _excluded_labels(inputs.get("label_rules"))
    item_labels = d.get("labels") or {}

    keep = _keeper(d, code, hidden_ids, blocked)

    rows = {k: ([r for r in d.get(k) or () if keep(r, k)] if SECTION_OF_KIND[k] not in hidden_types else [])
            for k in KINDS}
    ids = {k: {r["id"] for r in rows[k]} for k in KINDS}
    linkable = ids["milestones"] | ids["actions"] | ids["raid"] | ids["decisions"]

    def ref(c, field, kind):
        """A pointer at a row that isn't published reads as nothing."""
        if field in c and c[field] not in ids[kind]:
            c[field] = None

    out = {}
    for k in KINDS:
        out[k] = []
        for r in rows[k]:
            c = _pick(r, PUBLISH_FIELDS[k])
            for f in RICH.get(k, ()):
                c[f] = clean_html(c[f])
            if k == "use_cases":                              # plain text the editor wrote: hidden characters out, cut at a limit
                for f in ("ref", "title", "headline"):
                    c[f] = reason_text(c[f])
                if c.get("commitment") not in COMMITMENTS:         # #709: only the owner's words reach the file; anything else reads as no flag
                    c["commitment"] = None
            ref(c, "milestone", "milestones")
            ref(c, "use_case", "use_cases")
            ref(c, "replaces", "decisions")
            if k == "milestones":
                mine = [x for x in inputs.get("changes") or () if x.get("item_id") == r["id"]]
                state = milestones.milestone_state(r, as_at)
                c.update(state=state, state_word=milestones.client_word(state), slip_days=milestones.slip_days(r, as_at),
                         original_date=milestones.original_date(mine, r["id"], r.get("baseline_date"),
                                                                inputs.get("undone") or ()))
            out[k].append(c)
    used = {str(r.get("workstream")).casefold() for k in ("milestones", "actions", "raid") for r in rows[k] if r.get("workstream")}
    out["workstreams"] = [_pick(w, PUBLISH_FIELDS["workstreams"]) for w in d.get("workstreams") or ()
                          if w.get("archived") == 0 and (str(w.get("name")).casefold() in used or w.get("id") in used)]
    out["links"] = [_pick(x, PUBLISH_FIELDS["links"]) for x in d.get("links") or ()
                    if x.get("from_item") in linkable and x.get("to_item") in linkable]
    out["labels"] = {i: list(item_labels[i]) for i in sorted(linkable) if item_labels.get(i)}
    proj = _pick(project, PUBLISH_FIELDS["projects"])
    proj["health_reason"] = reason_text(proj["health_reason"])
    proj["current_state"] = "" if "current" in hidden_types else clean_html(proj["current_state"])
    out["project"] = proj
    out["documents"] = documents(inputs.get("documents"), code, hidden_ids, hidden_types) if any(
        s.get("type") == "docs" and not s.get("hidden") for s in sections) else []          # #74: carried only with a section to draw them

    gantt = gantt_for_client(d, code, proj["name"])               # row 926: decided here, from the rows as read, before anything of it is copied
    if gantt:
        out["gantt"] = gantt
        proj["gantt_tab_name"], proj["gantt_title"] = gantt["tab_name"], gantt["title"]       # row 926: the project block carries the tab's name and the page's title, only when the tab is in the file
        proj["gantt_default_rows"] = gantt["default_rows"]
    shown = []
    pairs = set()                  # ids that open a row of two whose halves BOTH show: rows are read from every section, then the hidden are left out
    ctx = section_bodies.Context({k: out[k] for k in KINDS}, as_at)          # #96: only what is already kept, as the file carries it
    extra = {s["id"]: _content(s, ctx) for s in sections if s.get("type") in section_bodies.CHECKERS and not s.get("hidden")}   # a needs, tracker or template section's published fields; None: left out
    dropped = 0
    listed = flagged_needs(rows)         # row 811b: the flagged open items, as rows of the 'Needs from you' list
    if listed:
        needs_sections = [x for x in sections if x.get("type") == section_bodies.NEEDS]
        if not needs_sections:           # no such section at all: one is made for the file (an owner who has hidden theirs is respected: it is not made again)
            sections = sections + [{"id": "s-needs-flagged", "type": section_bodies.NEEDS, "title": "Needs from you", "body": "",
                                    "beside": 0, "hidden": 0, "sort_order": 1 << 30}]
            extra["s-needs-flagged"] = {}
            needs_sections = sections[-1:]
        mine = next((x for x in needs_sections if not x.get("hidden")), None)
        if mine is not None:
            typed = list((extra.get(mine["id"]) or {}).get("rows") or [])
            room = max(0, section_bodies.NEEDS_MAX_ROWS - len(typed))
            dropped = max(0, len(listed) - room)           # said by build() only, as a count (see the end of select)
            extra[mine["id"]] = {**(extra.get(mine["id"]) or {}), "rows": typed + listed[:room]}   # typed rows win: the section never holds more than a typed list may
    out_of_file = lambda x: (x.get("hidden") or x.get("type") not in SECTION_TYPES or (x.get("type") in section_bodies.CHECKERS and extra.get(x["id"]) is None)
                             or (x.get("type") == "docs" and not out["documents"])       # #74: no document to show, no section
                             or (x.get("type") == "gantt" and not gantt))                # row 926: no Gantt tab in the file, no Gantt section; the lines are data.gantt's, gated in gantt_for_client
    i = 0
    while i < len(sections):
        if sections[i].get("beside") and i + 1 < len(sections):
            if all(not out_of_file(x) for x in sections[i:i + 2]):
                pairs.add(sections[i]["id"])
            i += 1
        i += 1
    for s in sections:
        if out_of_file(s):
            continue
        c = {"id": s["id"], "type": s["type"], "title": s.get("title") or "", "beside": 1 if s["id"] in pairs else 0}
        if s["type"] == "text":
            c["body"] = clean_html(s.get("body"))
        elif s["type"] in section_bodies.CHECKERS:
            c.update({k: v for k, v in extra[s["id"]].items() if k not in c})     # never over id, type, title or beside
        shown.append(c)
    out["use_case_pages"] = client_use_cases(d, code, hidden_ids, inputs.get("label_rules"), hidden_types)
    tabs = ["dashboard"]
    if any(SECTION_OF_KIND[k] not in hidden_types for k in WORK_KINDS):
        tabs.append("work")
    if "milestones" not in hidden_types:
        tabs.append("milestones")
    if out["use_case_pages"]:
        tabs.append("usecases")
    if "milestones" not in hidden_types:      # the Client Requested Report View (#192) reads only what the file already holds; its figures are the milestones
        tabs.append("clientreport")
    if gantt:
        tabs.append("gantt")                  # row 926: only with the client switch on and at least one line with its eye on
    return {"data": out, "sections": shown, "tabs": tabs, "as_at": as_at, "needs_dropped": dropped}     # row 811b: build() takes needs_dropped out and logs it; no other caller does


# ===== The file (pure) =====
def _once(text, old, new):
    if text.count(old) < 1:
        raise PublishError("The page clark builds has changed shape, so no report could be made from it. Rebuild the page "
                           f"(python3 dev/tools/build_page.py). Missing: {old[:40]}")
    return text.replace(old, new, 1)


# A <style> start or end tag as the HTML parser reads it: the name must be followed by white space, / or >, and the letters are
# ASCII only (re.A: U+017F and U+212A are not s and k in a tag, so the scan and the page agree).
STYLE_START = re.compile(r"<style(?=[\t\n\f\r />])", re.I | re.A)
STYLE_END = re.compile(r"</style(?=[\t\n\f\r />])", re.I | re.A)


def style_texts(text, work=None):
    """The text inside each <style>...</style>, in order, as a list. Linear in the length of `text`: each step is a plain
    search forward that never goes back, and every search that finds nothing ends the scan (a lazy regex with an open-ended
    tail is quadratic on <style></style </style ...). As a browser does, a style with no end tag runs to the end of the text
    and is read in full, so a missing </style> hides nothing; a start tag with no > is not a tag and ends the scan."""
    work = work or Work()
    found, pos = [], 0
    while True:
        work.spend()
        start = STYLE_START.search(text, pos)
        if start is None:
            return found
        opened = text.find(">", start.end())
        if opened < 0:
            return found
        end = STYLE_END.search(text, opened + 1)
        if end is None:
            found.append(text[opened + 1:])
            return found
        found.append(text[opened + 1:end.start()])
        closed = text.find(">", end.end())
        if closed < 0:
            return found
        pos = closed + 1


# Foreign content (#112 H1): inside <svg> and <math> a browser reads <style> text by other rules, and a CDATA section hides
# anything inside it from a scan that reads style text as HTML does (a "</style>" in a comment or CDATA ends the style for the
# scan, not for the browser). The scan cannot read both ways at once, so it refuses all three, anywhere, whatever the spelling
# of the letters (ASCII case only). The real page has none; the data block (which writes every < as \u003c) is left out first.
FOREIGN = re.compile(r"<svg(?=[\t\n\f\r />])|<math(?=[\t\n\f\r />])|<!\[CDATA\[", re.I | re.A)
FOREIGN_FOUND = "an svg, math or CDATA section"


# #321: a picture embedded as data in the page's style is refused, so the page's cards stay plain CSS and text. What is spared:
# an embedded font (font/* and the older font types below; application/octet-stream only as an @font-face src), clark's named
# logo (build_page.py writes it as exactly this rule, alone, at the top level of a style), and the three pictures an own look may
# set (docs/DESIGN-SYSTEM.md: a home banner and a cover), each as `--name: url(data:image/...)` and nothing else in the value.
# Only a data: that is a URL counts: after url( or inside an image function's string argument. `.metadata:hover` and
# content:"Data: " are no URL. A data:font/ is trusted on its label, not on its bytes (a catch-the-accident check, not a sniffer).
LOGO_RULE = re.compile(r"\s*\.logo-icon\s*\{\s*background-image:\s*url\(\s*[\"']?data:image/svg\+xml;base64,[A-Za-z0-9+/=]+[\"']?\s*\)\s*;?\s*\}", re.I)
OLD_FONT_TYPES = frozenset(("application/font-woff", "application/font-woff2", "application/x-font-ttf", "application/x-font-otf",
                            "application/vnd.ms-fontobject"))
LOOK_PICTURES = re.compile(r"\s*--(?:art-home|image-cover|image-fade)\s*:\s*\Z")
LOOK_PICTURE_TYPE = re.compile(r"image/(?:png|jpeg|gif|webp|svg\+xml)\Z")
_DATA_URL = re.compile(r"[\"'\s]*data:([^;,\"')]*)", re.I)
_PROPERTY = re.compile(r"\s*([\w-]+)\s*:")
# The pieces of _CSS_PIECE, except that a run of words and punctuation with no string or bracket in it is one piece, not one per
# word (a function name before its ( is still its own piece). The walk below reads only brackets, strings, { } ; and the end of a
# piece, so it costs a step per bracket or string, not per word: an embedded font is a handful of steps, not thousands.
_PICTURE_PIECE = re.compile(r"""(?s:\"[^"\\\n\r\f]*(?:\\.[^"\\\n\r\f]*)*"?|'[^'\\\n\r\f]*(?:\\.[^'\\\n\r\f]*)*'?)|(-?[A-Za-z_][\w-]*)\s*\(|\(|\)|(?:[\w-]+(?![\w-])(?!\s*\()|(?s:\\.|\\)|[^"'()\w\\-])+|[\w-]+""")


def _escape_places(css, plain, gap=" "):
    """Where, in plain (= css_plain(css)), each escape of the style as typed put its character: two sorted lists, the starts and
    the ends. One pass. None if the places cannot be told (an escape built a comment: plain is then shorter than the decoded
    text). Used to ask whether a piece of the read text is spelled out as typed, with no escape in it."""
    typed = _without_comments(css.replace("\x00", "\ufffd"), gap)
    starts, ends, shift = [], [], 0
    for m in _CSS_ESCAPE.finditer(typed):
        put = len(_css_escape(m))
        starts.append(m.start() + shift)
        ends.append(m.start() + shift + put)
        shift += put - (m.end() - m.start())
    if len(typed) + shift != len(plain):
        return None
    return starts, ends


# The still circle picture a person's own brand may put on the top bar: `.logo { background: url(data:image/png;base64,...) ... }`,
# a rule on exactly `.logo` at the top level (no media query around it), setting `background` or `background-image`, with one
# embedded picture of an image type in the declaration, written out as base64 and no longer than CIRCLE_MAX characters. The words
# before and after the url( are plain keywords and lengths (no bracket, string or escape). It is data, so it reaches nothing.
CIRCLE_MAX = 262144
_CIRCLE_HEAD = re.compile(r"\s*background(?:-image)?\s*:[^;{}()\"'\\]*\Z", re.I)
_CIRCLE_TAIL = re.compile(r"\s*[\"']?\s*\)[^;{}()\"'\\]*(?:;|\}|\Z)")
_CIRCLE_DATA = re.compile(r"\s*[\"']?\s*data:(image/[a-z+]+);base64,([A-Za-z0-9+/=]+)", re.I)


def _circle_picture(plain, decl, start, blocks, mime, spelled_out):
    """True if the data: picture whose url( begins at plain[start] is the circle picture described above."""
    if len(blocks) != 1 or blocks[0][0] != ".logo" or not LOOK_PICTURE_TYPE.match(mime.strip().lower()):
        return False
    if not _CIRCLE_HEAD.match(plain[decl:start]):
        return False
    d = _CIRCLE_DATA.match(plain, plain.index("(", start) + 1)
    if d is None or len(d.group(2)) > CIRCLE_MAX:
        return False
    tail = _CIRCLE_TAIL.match(plain, d.end())
    return bool(tail) and spelled_out(blocks[0][1], tail.end())


def _picture_as_data(css, work=None):
    """True if _picture_as_data_read finds one, read with a comment as a break between tokens and with a comment cut out (so the
    two sides join): a comment is read both ways, as css_findings reads it."""
    if "/*" not in css:
        return _picture_as_data_read(css, work, " ")
    work = work or Work()
    return _picture_as_data_read(css, work, " ") or _picture_as_data_read(css, work, "")


def _picture_as_data_read(css, work, gap):
    """True if style text has a data: URL that is not a font, the logo rule or one of the look's named pictures. Read as a browser
    reads it (css_plain), with the same pieces css_findings reads: url( and the string arguments of image functions. A running
    note of the block it is in (@font-face, a top-level rule) and of where its declaration began says which is spared."""
    if "\\" not in css and "data:" not in css.lower():
        return False                                    # no escape and no data: in it: nothing to find
    work = work or Work()
    plain = css_plain(css, gap)
    escaped = "\\" in css                              # an escape could make the text read differently from a browser: ask of each spared piece
    stack, blocks, images, argument_start, decl = [], [], 0, False, 0

    places = []

    def spelled_out(begin, end):
        """True if plain[begin:end] has no escape in it. An escape elsewhere in the style (the page's content:"\\2713" tick) says
        nothing about a spared piece: only one inside the piece itself (a selector, a name, the value) takes its exception away."""
        if not escaped:
            return True
        if not places:
            places.append(_escape_places(css, plain, gap))
        if places[0] is None or "\\" in plain[begin:end]:
            return False
        starts, ends = places[0]
        i = bisect.bisect_left(ends, begin)             # the first escape that ends at or after the piece begins
        return i >= len(starts) or starts[i] > end

    def refused(mime, start, via_url):
        mime = mime.strip().lower()
        if mime.startswith("font/") or mime in OLD_FONT_TYPES:
            return False
        head = plain[decl:start]
        if mime == "application/octet-stream":
            prop = _PROPERTY.match(head)
            return not (blocks and blocks[-1][0] == "@font-face" and prop and prop.group(1).lower() == "src")
        if not via_url:
            return True
        if LOOK_PICTURES.match(head) and LOOK_PICTURE_TYPE.match(mime):
            close = plain.find(")", start)
            if spelled_out(decl, len(plain) if close < 0 else close + 1):       # its name and its url(...), each as typed
                return False
        logo = LOGO_RULE.match(plain, blocks[0][1]) if len(blocks) == 1 else None      # the rule's own block, nothing around it
        if logo and start < logo.end() and spelled_out(blocks[0][1], logo.end()):
            return False
        return not _circle_picture(plain, decl, start, blocks, mime, spelled_out)

    for m in _PICTURE_PIECE.finditer(plain):
        work.spend()
        piece = m.group(0)
        if m.group(1) is not None:
            is_image = bool(_IMAGE_FUNCTION.match(m.group(1)))
            stack.append(is_image)
            images += is_image
            argument_start = True
            if m.group(1).lower() == "url":
                argument_start = False                  # its string, if any, is its address, read here
                d = _DATA_URL.match(plain, m.end())
                if d and refused(d.group(1), m.start(), True):
                    return True
        elif piece == "(":
            stack.append(False)
            argument_start = True
        elif piece == ")":
            images -= stack.pop() if stack else 0
            argument_start = False
        elif piece[0] in "\"'":
            if images and argument_start:
                d = _DATA_URL.match(piece)
                if d and refused(d.group(1), m.start(), False):
                    return True
            argument_start = False
        else:
            if not stack:
                for i, ch in enumerate(piece, m.start()):
                    if ch == "{":
                        blocks.append((plain[decl:i].strip().lower(), decl))     # what it is, and where it began
                    elif ch == "}" and blocks:
                        blocks.pop()
                    if ch in ";{}":
                        decl = i + 1
            argument_start = piece.rstrip().endswith(",") or (argument_start and not piece.strip())
    return False


def check_brand(page_text):
    """Refuse a brand that reaches outside the file: an @import, or a url() that isn't data:. A font has to be embedded in
    tokens.css as data. (The policy would block it too, but a report with a missing font is refused, not published.) Also
    (#321) refuse a picture embedded as data in a style, other than the logo: a data: image is no address, but it would put a
    picture on a card, and only a test of the published cards would have caught it."""
    if FOREIGN.search(page_text):
        raise PublishError("The brand's tokens.css, or the page, has a drawing or formula section, which the check for "
                           "addresses outside the file cannot read: take it out.")
    work = Work(size=len(page_text))
    try:
        styles = style_texts(page_text, work)
        finds = [css_findings(css, work) for css in styles]
        pictures = any(_picture_as_data(css, work) for css in styles)
    except ScanTooBig:
        raise PublishError("The brand's tokens.css, or the page, is too long or too tangled to check for addresses outside the "
                           "file: shorten it.")
    for found in finds:
        if IMPORT_FOUND in found:
            raise PublishError("The brand's tokens.css uses @import, which would reach outside the file: embed the font in "
                               "tokens.css instead.")
        if ADDRESS_FOUND in found:
            raise PublishError("The brand's tokens.css names a font or image by address, which would reach outside the "
                               "file: embed the font in tokens.css instead.")
    if pictures:
        raise PublishError("The brand's tokens.css, or the page, embeds a picture in its style, which the page's cards do not "
                           "use: embed only the font in tokens.css.")


# The block data_block() writes, and only where render() puts it: straight before the last </body>, on a line of its own. Its
# text has no `<` (data_block writes every one as \u003c), so the match cannot start at an imitation earlier in the file and
# run on past the first </script>. An opener anywhere else is page markup and is scanned like the rest (#106).
DATA_BLOCK = re.compile(r'<script type="application/json" id="clark-data">[^<]*</script>\n\Z')


def without_data_block(text):
    """`text` with the one clark-data block the builder inserted cut out: the one that ends exactly where the last </body> begins.
    Nothing else is cut, whatever it looks like."""
    end = text.rfind("</body>")
    m = DATA_BLOCK.search(text, 0, end) if end >= 0 else None
    return text if m is None else text[:m.start()] + text[m.end():]


LINK_START = re.compile(r"<link\b", re.I | re.A)         # ASCII letters only: U+212A is not a k in a tag (as for STYLE_START)
ICON_PAYLOAD = re.compile(r"base64,([A-Za-z0-9+/=]+)")


LINK_MAX = 16384          # the longest icon link is about 7.4 KB (the 180 px picture as base64); a <link whose > is farther is not one


def icon_link(text, start):
    """The SHA-256 of the picture if the <link at text[start] is clark's own icon link (#73), else None. It is if its whole text,
    up to the first >, equals page.icon_link() of the picture its payload decodes to, character for character: the one spelling
    the build writes (rel, type, href in that order, double quotes, one space between, no other attribute), so nothing can ride
    in the spacing, an attribute or a different spelling. The picture must be one of page.ICON_LINKS' (by SHA-256 of its bytes).
    The > is looked for within LINK_MAX characters only: a <link with none there is not an icon link (a search to the end of the
    text for every <link is quadratic)."""
    close = text.find(">", start, start + LINK_MAX)
    if close < 0:
        return None
    tag = text[start:close + 1]
    m = ICON_PAYLOAD.search(tag)
    if not m:
        return None
    try:
        picture = base64.b64decode(m.group(1), validate=True)
    except ValueError:
        return None
    digest = hashlib.sha256(picture).hexdigest()
    if digest not in page.ICON_LINKS:
        return None
    rel, mime = page.ICON_LINKS[digest]
    return digest if tag == page.icon_link(rel, mime, base64.b64encode(picture).decode("ascii")) else None


def has_other_links(text, work=None):
    """True if the text has a <link that is not exactly one of clark's three icon links, or the same one twice. Wherever it
    stands (a comment, a script, a template), every <link in the text is checked and only the exact spelling passes. It stops
    at the first that isn't, so at most three genuine links are ever worked through."""
    work = work or Work()
    seen = set()
    for m in LINK_START.finditer(text):
        work.spend()
        digest = icon_link(text, m.start())
        if digest is None or digest in seen:
            return True
        seen.add(digest)
    return False


# ===== A second look at the tags, as a browser reads them (#112) =====
# The patterns in outside_addresses read the bytes as typed. A browser reads an attribute's value after decoding its character
# references (&#47; is /), ignoring tabs and new lines in an address, and treating \ as /. The tag reader below finds every tag and
# attribute in one forward pass (no pattern that can start again from every `<`), and the checks run on each value as typed
# and as decoded once, twice and to the end, so a doubly encoded address is seen too. This only adds findings: every older pattern
# still runs on the bytes as typed.
_ENTITY = re.compile(r"&(?:#[0-9]+|#[xX][0-9A-Fa-f]+|[A-Za-z][A-Za-z0-9]*);?")
_TAG_NAME = re.compile(r"[A-Za-z][^\s/>\x00]*")
_ATTR = re.compile(r"""[\s/\x00]*(?:(>)|([^\s/>\x00][^\s/>=\x00]*)(?:[\s\x00]*=[\t\n\f\r ]*(?:"([^"]*)"|'([^']*)'|([^\t\n\f\r >]*)))?)""")
_ADDRESS_JUNK = re.compile(r"[\t\n\r\x00]")
LIST_ATTRS = ("srcset", "imagesrcset", "ping")          # several addresses, parted by white space or commas
URL_ATTRS = ("src", "href", "action", "poster", "data", "formaction", "background", "xlink:href", "manifest", "codebase",
             "longdesc", "cite", "lowsrc", "dynsrc")
FRAME_TAGS = ("iframe", "frame", "frameset", "object", "embed", "applet", "portal")   # a page or program inside the page
_SCHEME = re.compile(r"[a-z][a-z0-9+.\-]*:")


def _unescape_once(value):
    def one(m):
        out = htmllib.unescape(m.group(0))
        return m.group(0) if out in ("<", ">") else out            # &lt; and &gt; stay as written
    return _ENTITY.sub(one, value)


def spellings(value):
    """`value` as typed, then decoded once, twice and so on until it stops changing (at most five times), without repeats."""
    seen = [value]
    for _ in range(5):
        nxt = _unescape_once(seen[-1])
        if nxt == seen[-1]:
            break
        seen.append(nxt)
    return seen


_LETTERS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
NAME_MAX = 32          # no tag name the checks look for is longer than this; longer names are cut to it


def tags(text, work=None):
    """Every start tag in `text` as (lower-case name, [(lower-case attribute name, value as typed)]), in a forward pass. A quote
    that never closes runs to the end of the text, as it does in a browser. Text inside a comment, a script, a textarea or a
    title is read as markup too: the scan wants more, not fewer, findings. A quoted value that holds a `<` may be only what the
    page reads as text (a quote opened inside a comment, a textarea or a title swallows the real tags after it), so every `<`
    inside a quoted value is also read as the start of a tag, once (#112 H4). That stays linear: each start is read once, and a
    read ends where an earlier one already stood at the same place between attributes in the same kind of tag (script, meta or
    other: the only kinds whose attributes mean something different), because everything after it was already yielded. As the
    HTML rules say, an attribute name may start with `=`."""
    work = work or Work()
    pos = 0
    started, queued, later = set(), set(), []             # starts read; starts waiting in `later` (a heap); the heap
    seen = set()                                           # place * 3 + kind of tag, between attributes, already read from
    rs = re_ = 0                                           # the last run of name characters read: [rs, re_)
    nxt = -2                                               # the next < at or after pos; looked for again only once pos has passed it
    while True:
        work.spend()
        if nxt != -1 and nxt < pos:                        # (-1: none left, and none can appear) a search per pop is quadratic on a long run of <
            nxt = text.find("<", pos)
        while later and later[0] in started:
            heapq.heappop(later)
        sequential = not later or (0 <= nxt < later[0])
        if sequential:
            if nxt < 0:
                return
            i = nxt
        else:
            i = heapq.heappop(later)
        if sequential:
            pos = i + 1
        if i in started:
            continue
        started.add(i)
        p = i + 1
        if rs <= p < re_:                                 # inside a run of name characters already read: it ends where that one did
            if text[p] not in _LETTERS:
                continue
            end = re_
        else:
            name = _TAG_NAME.match(text, p)
            if name is None:
                continue
            rs, re_ = p, name.end()
            end = re_
        word = text[p:min(end, p + NAME_MAX)].lower()               # no tag name that means anything is longer: a longer one is cut
        kind = {"script": 1, "meta": 2}.get(word, 0) if end - p <= 6 else 0
        attrs, j = [], end
        while True:
            work.spend()
            place = j * 3 + kind
            if place in seen:
                break
            seen.add(place)
            m = _ATTR.match(text, j)
            if m is None:
                break
            j = m.end()
            closer, attr, dq, sq, bare = m.group(1, 2, 3, 4, 5)
            if closer:
                break
            if dq is not None or sq is not None:
                attrs.append((attr.lower(), dq if dq is not None else sq))
                g = 3 if dq is not None else 4
                k = text.find("<", m.start(g), j)
                while k >= 0:
                    work.spend()
                    if k not in started and k not in queued:
                        queued.add(k)
                        heapq.heappush(later, k)
                    k = text.find("<", k + 1, j)
            else:
                attrs.append((attr.lower(), bare or ""))
        yield word, attrs
        if sequential:
            pos = max(pos, j)


def bad_address(value):
    """True if an attribute value, once decoded the way a browser does, names somewhere outside the file or runs something:
    a protocol-relative `//` (or its backslash spellings), or any scheme but mailto:, tel: and a data:image/ picture (http:,
    https:, file:, javascript:, data:text/html and the rest), however it is spaced, cased or encoded. A link within the page
    (#top) and a plain relative name are not addresses outside the file."""
    for form in spellings(value):
        v = _ADDRESS_JUNK.sub("", form).lstrip("".join(map(chr, range(33)))).lower()
        if v[:2] in ("//", "\\\\", "/\\", "\\/"):
            return True
        if _SCHEME.match(v) and not v.startswith(("mailto:", "tel:", "data:image/")):
            return True
    return False


_MAY_BE_ADDRESS = re.compile(r"[:/\\&]")          # a word without any of these is no scheme, no // and no character reference


def bad_candidate(value):
    """True if any candidate of a srcset (or any address in a list that white space or commas separate) is outside the file.
    Every word that starts after a space or a comma is read as the start of an address, so the candidate after a data: one is
    checked like the first (a data: address holds a comma of its own, so the list is cut by pieces, not by the comma alone)."""
    return any(bad_address(piece) for form in spellings(value) if _MAY_BE_ADDRESS.search(form)
               for piece in re.split(r"[\s,]+", form) if piece and _MAY_BE_ADDRESS.search(piece))


IMPORT_FOUND = "a stylesheet that imports another"
ADDRESS_FOUND = "a stylesheet address that isn't embedded data"


_CSS_ESCAPE = re.compile(r"\\(?:([0-9A-Fa-f]{1,6})(?:\r\n|[ \t\n\r\f])?|(\r\n|[\n\r\f])|(.))", re.S)
_CSS_PIECE = re.compile(r"""(?s:\"[^"\\\n\r\f]*(?:\\.[^"\\\n\r\f]*)*"?|'[^'\\\n\r\f]*(?:\\.[^'\\\n\r\f]*)*'?)|(-?[A-Za-z_][\w-]*)\s*\(|\(|\)|[\w-]+|(?:(?s:\\.|\\)|[^"'()\w\\-])+""")
_IMAGE_FUNCTION = re.compile(r"(?:-[a-z]+-)?(?:image-set|src|image|cross-fade)$", re.I)
_URL_OPEN = re.compile(r"url\(", re.I)


_NOT_DECODED = frozenset("\"'\\\n\r\f")      # an escape for one of these stays as typed: it is a character of a name or a string, never a quote, a backslash or a line end


def _css_escape(m):
    if m.group(1):
        n = int(m.group(1), 16)
        c = chr(n) if 0 < n <= 0x10FFFF and not 0xD800 <= n <= 0xDFFF else "\ufffd"
        return m.group(0) if c in _NOT_DECODED else c
    if m.group(2):
        return "\\\n"                 # a backslash and a line end stays one (as LF): in a string it joins the lines, outside one it is a break between tokens
    return m.group(0) if m.group(3) in _NOT_DECODED else m.group(3)


_COMMENT_STOP = re.compile(r"/\*|[\"'\\(]")
_DQ_STRING = re.compile(r'"(?:[^"\\\n\r\f]|\\\r\n|\\.)*"?', re.S)
_SQ_STRING = re.compile(r"'(?:[^'\\\n\r\f]|\\\r\n|\\.)*'?", re.S)
_UNQUOTED_URL = re.compile(r"[\t\n\f\r ]*(?![\"'\t\n\f\r ])(?:[^)\\]|\\.)*\)?", re.S)
_QUOTE_NEXT = re.compile(r"[\t\n\f\r ]*[\"']")
_URL_NAME_ENDS = frozenset("lLcC \t\n\r\f")      # the last character of url( as written plainly (l) or as an escape (\6c, \6C, with or without a space)
_IDENT_AT_END = re.compile(r"(?:[\w-]|[^\x00-\x7f]|\\(?:[0-9A-Fa-f]{1,6}[ \t\n\r\f]?|.))+\Z", re.S)


def _without_comments(css, gap=" "):
    """`css` with each /* ... */ cut out, as a browser's reader finds comments: not inside a string (a "/*" in a string is no
    comment, so it cannot swallow a real address up to a later */), not after a backslash (\\/* is no comment), and not inside an
    unquoted url( (url(a/*) is a whole address, so a real address after it is still read). A comment with no end is cut at its
    start only: what follows is still read (stricter than a browser, which hides it). Nothing real is ever hidden by a comment."""
    pos, out, tail = 0, [], ""
    while True:
        m = _COMMENT_STOP.search(css, pos)
        if m is None:
            out.append(css[pos:])
            return "".join(out)
        out.append(css[pos:m.start()])
        tail = (tail + css[pos:m.start()])[-64:]
        c = m.group(0)
        if c == "/*":
            out.append(gap)                 # gap " ": a comment ends the token before it (red/**/image-set( is red, then image-set( ), as in a browser
            tail = (tail + gap)[-64:]         # gap "": the comment is cut out and the two sides join (the stricter old reading, u/**/rl( is url( ); both are scanned
            j = css.find("*/", m.end())
            pos = m.end() if j < 0 else j + 2
            continue
        if c in "\"'":
            piece = (_DQ_STRING if c == '"' else _SQ_STRING).match(css, m.start()).group(0)
        elif c == "\\":
            piece = css[m.start():m.start() + 2]
        else:
            piece = "("
            ident = _IDENT_AT_END.search(tail[-24:]) if tail[-1:] in _URL_NAME_ENDS else None      # "url" is at most 24 characters even spelled with escapes; most names end otherwise
            name = _CSS_ESCAPE.sub(_css_escape, ident.group(0)).lower() if ident else ""
            if name == "url" and not _QUOTE_NEXT.match(css, m.end()):
                piece = "(" + _UNQUOTED_URL.match(css, m.end()).group(0)
        out.append(piece)
        tail = (tail + piece)[-64:]
        pos = m.start() + len(piece)


def css_plain(css, gap=" "):
    """Style text as a browser's reader sees it: each null byte read as U+FFFD (not dropped), no comments, each \\75 or \\u escape
    turned into the character it stands for (so \\75rl( and u/**/rl( are url( and \\69mport is import). One forward pass at each step.
    Comments are cut before the escapes are turned into characters, never after: an escape cannot make a comment (\\2f* is no
    comment), so it cannot hide what follows it either."""
    return _CSS_ESCAPE.sub(_css_escape, _without_comments(css.replace("\x00", "\ufffd"), gap))


_DATA_START = re.compile(r"[\"' ]*data:", re.I)


def _not_data(value):
    return not value.strip("\"' ").lower().startswith("data:")


def _url_outside(text, work=None):
    """True if `text` has a url( whose address isn't data: (an unclosed url( runs to the end). One forward pass: the end of the
    address is searched for once for all the url( before it."""
    work = work or Work()
    close = -1
    for m in _URL_OPEN.finditer(text):
        work.spend()
        if close < m.end():
            close = text.find(")", m.end())
            close = len(text) if close < 0 else close
        m2 = _DATA_START.match(text, m.end())          # matched in place: a slice per url( is quadratic
        if not (m2 and m2.end() <= close):
            return True
    return False


def css_findings(css, work=None):
    """What style text reaches for, as the plain-words problems outside_addresses reports (a set). The text as typed is read
    first, then css_plain() of it: an @import, any url() whose address isn't data: (an unclosed url( runs to the end), and a
    string that opens an argument of image-set(), src(), image() or cross-fade() (with a vendor prefix) unless it is data:."""
    work = work or Work()
    found = set()
    if "(" not in css and "@" not in css and "\\" not in css:
        return found             # no bracket, @ or escape: no url(, no @import (u/**/rl( keeps its bracket, \40 import its backslash)
    # a browser reads a null byte as U+FFFD; the guard also reads the text with it dropped (the stricter reading kept from before)
    gaps = (" ", "") if "/*" in css else (" ",)
    plains = [css_plain(css, g) for g in gaps] + ([css_plain(css.replace("\x00", ""), g) for g in gaps] if "\x00" in css else [])
    for text in [_without_comments(css, g) for g in gaps] + plains:      # the text as typed, less its comments: a url( in a comment reaches nothing
        if re.search(r"@\s*import", text, re.I):
            found.add(IMPORT_FOUND)
        if _url_outside(text, work):
            found.add(ADDRESS_FOUND)
    for plain in plains:
        images, argument_start = 0, False
        stack = []
        for m in _CSS_PIECE.finditer(plain):
            work.spend()
            piece = m.group(0)
            if m.group(1) is not None:
                stack.append(bool(_IMAGE_FUNCTION.match(m.group(1))))
                images += stack[-1]
                argument_start = True
            elif piece == "(":
                stack.append(False)
                argument_start = True
            elif piece == ")":
                images -= stack.pop() if stack else 0
                argument_start = False
            elif piece[0] in "\"'":
                if images and argument_start and _not_data(piece):
                    found.add(ADDRESS_FOUND)
                argument_start = False
            else:
                argument_start = piece.rstrip().endswith(",") or (argument_start and not piece.strip())
    return found


def tag_findings(text, work=None):
    """What the tags of `text` reach for, as the plain-words problems outside_addresses reports (a set)."""
    work = work or Work()
    found = set()
    for name, attrs in tags(text, work):
        work.spend()
        if name in FRAME_TAGS:
            found.add("a page or program inside the page")
        if name == "base":
            found.add("a base address")
        for attr, value in attrs:
            work.spend()
            if (attr in URL_ATTRS and bad_address(value)) or (attr in LIST_ATTRS and bad_candidate(value)):
                found.add("an attribute that names an outside address")
            if attr == "src" and name == "script":
                found.add("a script loaded by address")
            if attr == "style":
                for form in spellings(value):
                    found |= css_findings(form, work)
            if attr == "http-equiv" and name == "meta" and any(f.strip().lower().startswith("refresh") for f in spellings(value)):
                found.add("a page refresh")
    return found


def outside_addresses(text):
    """What in a finished file reaches outside it, as a list of plain-words problems (empty when it is clean). The rules of
    #39's test of the finished bytes, in one place so #43 runs the same ones on the copy in the client folder: no <link> (but
    clark's own three icon links, each the pinned picture itself as data:, #73), no script src, no src/href/action/... that is an address, no meta refresh, no @import (an @font-face is fine: the font is data:), no url() that isn't
    data:, and no Google Fonts. The clark-data block the builder inserted (without_data_block: by its place before the last
    </body>, not by what it looks like) is left out: it is data, not markup. Style text is read in any letter case."""
    text = without_data_block(text)
    work = Work(size=len(text))
    try:
        return _outside_addresses(text, work)
    except ScanTooBig:
        return [TOO_BIG_FOUND]


def _outside_addresses(text, work):
    found = []
    if FOREIGN.search(text):
        found.append(FOREIGN_FOUND)
    if has_other_links(text, work):
        found.append("a <link> tag")
    # (a script's src and a meta refresh are found by tag_findings below, in one pass; patterns that start again at every <script
    # or <meta and run to the next > are quadratic on a file of open tags, #112 H2)
    for pattern, what in ((r"""(?i)\b(src|srcset|href|action|poster|data|formaction|background|ping)\s*=\s*["']?(https?:)?//""",
                           "an attribute that names an outside address"),):
        if re.search(pattern, text):
            found.append(what)
    # each style on its own, as a browser reads it: a stray quote in one must not swallow the next one's address
    css_found = set()
    for css in style_texts(text, work):
        css_found.update(css_findings(css, work))
    found.extend(sorted(css_found))
    if "fonts.googleapis" in text:
        found.append("a Google Fonts address")
    if [a for a in re.findall(r"""(?i)\b(?:src|href)\s*=\s*["']([^"']+)""", text) if a.startswith(("http:", "https:", "//"))]:
        found.append("a link or source that is an outside address")
    found.extend(f for f in sorted(tag_findings(text, work)) if f not in found)
    return found


def csp_meta(html):
    """The <meta> policy for the file as it will be sent, with the hash of its script and of each inline style (taken from
    these exact bytes, so call it last and insert it first in <head>). No 'self': a file:// page has an opaque origin."""
    h = csp_hashes(html)
    scripts, styles = " ".join(h["script"]) or "'none'", " ".join(h["style"]) or "'none'"
    policy = "; ".join(["default-src 'none'", f"script-src {scripts}", f"style-src-elem {styles}", "img-src data:",
                        "font-src data:", "connect-src 'none'", "object-src 'none'", "base-uri 'none'", "form-action 'none'"])
    return f'<meta http-equiv="Content-Security-Policy" content="{policy}">'


def add_glance(published, inputs):
    """#45: put the At a glance figures and the use case strip in `published["data"]["glance"]`, worked out here, at publish time,
    as at the publish date (a static file must not move with the day it is opened). They are counted from `select`'s own
    output, the rows it already kept, so a figure cannot include a row select dropped; select itself is not changed.
    Counts and fixed labels only, never a stored text: {"tiles": [{tile, label, value, detail, colour, outline}], "strip":
    {total, words: {status: n}, rows: [{id, open, overdue}]}}. colour and outline are one of G A R N, or '' (automatic outline).
    A hidden tile is absent, so is one whose section is hidden. Project health is carried even when its tile is hidden (it is the
    project's health, which the file carries anyway), but when the At a glance section is hidden the section is not in the file at
    all: Health goes with it (Head's ruling, #89 review). The strip is absent when the
    Use cases section is hidden or no use case is kept. Returns `published`."""
    from clark import glance                  # glance imports this module, so it is imported here, not at the top
    as_at = inputs["as_at"]
    kept = glance.kept_from(published, inputs.get("sections"), bool(inputs.get("sections_deleted")))
    settings = glance.tile_settings(inputs.get("glance_tiles"))
    project = published["data"]["project"]
    shown = glance.tiles({"project": project}, as_at, tile_order=settings["order"], hidden=settings["hidden"] - {"health"},
                         outlines=settings["outlines"], for_client=True, kept=kept)
    if "glance" in kept["hidden_types"]:      # the At a glance section is left off the page: its figures are not carried either
        shown = []
    tiles = [{"tile": t["tile"], "label": t["title"], "value": t["value"], "detail": t["detail"],
              "colour": t["class"].upper(), "outline": settings["outlines"].get(t["tile"]) or ""} for t in shown]
    out = {"tiles": tiles}
    if kept["use_cases"] and "usecases" not in kept["hidden_types"]:
        strip = glance.use_case_strip(None, None, as_at, for_client=True, kept=kept)
        out["strip"] = {"total": strip["total"], "words": {c["status"]: c["count"] for c in strip["counts"]},
                        "rows": [{"id": r["id"], "open": r["open"], "overdue": r["overdue"]} for r in strip["rows"]]}
    published["data"]["glance"] = out
    published["style"] = section_style(inputs)
    return published


STYLES = ("slim", "roomy", "grey", "card")       # how the sections sit on the page (#45); the page's stores/style.js holds the same four
DEFAULT_STYLE = "slim"


def section_style(inputs):
    """The project's section style for the file: one of STYLES, else DEFAULT_STYLE. It is read from the project's own setting
    (`inputs["section_style"]`, which the store supplies once the project keeps one); anything else, a missing value included,
    is replaced by slim, so the file never carries a word the page doesn't know."""
    got = inputs.get("section_style")
    return got if isinstance(got, str) and got in STYLES else DEFAULT_STYLE


def data_block(published, as_at, number=None):
    """The <script type="application/json" id="clark-data"> block. < > & are \\u escapes, so the text can neither close the
    block nor be read as markup, and ensure_ascii makes U+2028 and U+2029 escapes too."""
    style = published.get("style")
    block = {"v": VERSION, "as_at": as_at, "style": style if style in STYLES else DEFAULT_STYLE,
             "data": published["data"], "sections": published["sections"], "tabs": published["tabs"]}
    if number:                         # #120: which publication this file is; the page's footer reads it. A preview has none
        block["publication"] = {"n": number}
    body = json.dumps(block, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    for ch in "<>&":
        body = body.replace(ch, "\\u%04x" % ord(ch))
    return f'<script type="application/json" id="clark-data">{body}</script>'


def render(published, page_text, as_at, title, number=None):
    """The whole file as text: `page_text` (clark.page.page_html()) with the title, view mode, the data block and, last, the
    policy that covers the finished bytes. Raises PublishError if the page has a token block or the brand reaches outside."""
    if 'id="clark-boot"' in page_text:
        raise PublishError("The page has a server token in it. A published file never has one.")
    check_brand(page_text)
    h = _once(page_text, '<html lang="en-GB">', '<html lang="en-GB" data-mode="view">')
    h = re.sub(r"<title>.*?</title>", lambda m: f"<title>{htmllib.escape(title or 'clark', quote=True)}</title>", h, count=1,
               flags=re.S)
    i = h.rfind("</body>")
    if i < 0:
        raise PublishError("The page clark builds has no end of body, so no report could be made from it.")
    h = h[:i] + data_block(published, as_at, number) + "\n" + h[i:]
    charset = '<meta charset="utf-8">'
    return _once(h, charset, charset + csp_meta(h))


def file_name(code, week_ending, as_at, folder=None):
    """{CODE}-report-{week_ending or as_at}.html, made safe for Windows, OneDrive and SharePoint (platform.safe_name)."""
    return platform.safe_name(f"{code}-report-{week_ending or as_at}.html", folder)


# ===== Reading (Store.publish_inputs: one read-only connection, one read transaction) =====
def read_inputs(store, code, as_at=None):
    """Everything select() needs, read from the store in ONE read-only transaction (so a write can't come between two reads).
    Only the columns in PUBLISH_FIELDS (and GATES, to decide) are asked for: internal_note, movement and source never leave the
    database. The SQL itself lives in store.py, the only module that touches the database."""
    if not CODE.fullmatch(code or ""):
        raise PublishError("Give the project's code (3 to 7 capital letters or digits).")
    fields = {t: tuple(dict.fromkeys(PUBLISH_FIELDS.get(t, ()) + GATES.get(t, ()) + (("project",) if t in KINDS + ("workstreams",) else ())))
              for t in ("projects",) + KINDS + ("workstreams", "gantt_lines")}
    fields["projects"] += tuple(c for c in ("archived",) if c not in fields["projects"])      # #126: publish() refuses an archived project
    try:
        got = store.publish_inputs(code, fields)
    except Exception as e:             # a database that can't be read: said in words, whatever sqlite called it
        raise PublishError(f"The database could not be read ({e}).") from e
    if got is None:
        raise PublishError(f"There is no project with the code {code}.")
    got["as_at"] = as_at or milestones.today()
    return got


# ===== Making the file =====
def build(store, code, now=None, branding=None, section_style=None, number=None, workbook=False, past_reports=None):
    """Make the report once, in memory, and write nothing: {"body", "sha256", "project", "as_at", "published"}. `body` is the
    finished file's UTF-8 bytes, `published` is what select() kept (the same object render() was given). `now` is the publish
    date (YYYY-MM-DD); due dates and Overdue read as at that date. publish() and the To client route (#43) both start here, so
    the file written to Local and the file copied to the client are the same bytes, made once. `section_style` is the style the
    person chose on the page (section_style() keeps it only if it is one of STYLES); the file carries it in its own data block.
    #120: the file carries its publication number (its footer reads "Publication N"): `number` is the one the caller made the file
    with (the rebuild keeps it), else Store.next_publication gives it; 0 means no number (a preview, which is not published).
    The number is returned too, for Store.log_publication, which refuses if another publication took it meanwhile.
    Item 713: `workbook` (off by default, so the bytes are as they were) makes the client workbook from `published` and puts it in
    the data block's data (excel_client.embed: `client_workbook` {name, base64}, or `client_workbook_too_large` True); a workbook that
    cannot be made never stops the publish (it is logged by class name only). `past_reports` ([{week_ending, file}], from
    past_files.listing) goes in the data as `past_reports` when it has rows; the caller reads the folder, so this module stays pure."""
    as_at = str(now or milestones.today())
    try:
        if not re.fullmatch(r"\d{4}-\d\d-\d\d", as_at):          # Python 3.11 and later also read 20261028
            raise ValueError
        date.fromisoformat(as_at)
    except ValueError:
        raise PublishError(f"{as_at!r} is not a date. Give the publish date as YYYY-MM-DD.") from None
    inputs = read_inputs(store, code, as_at)
    if section_style is not None:
        inputs["section_style"] = section_style
    if inputs["data"]["project"].get("archived"):           # #126: checked here, not in select (glance.kept_rows calls select and must still work)
        raise PublishError("An archived project can't be published. Restore it first.")
    published = select(inputs)
    dropped = published.pop("needs_dropped", 0)         # row 811b: only a publish or preview build says so, as a count and nothing else
    if dropped:
        LOG.warning("The Needs from you list is full: %d flagged item(s) are left out of the published file.", dropped)
    published = add_glance(published, inputs)
    if workbook:
        from clark import excel_client           # not at the top: openpyxl is loaded only when a workbook is made
        try:
            embedded = excel_client.embed(published)
        except Exception as e:                     # the report is the thing: no spreadsheet is better than no report
            logging.getLogger("clark.publish").warning("The client workbook could not be made (%s).", type(e).__name__)   # the class only: never a message or a row
        else:
            published["data"].update(embedded)
    project = published["data"]["project"]
    here = file_name(code, project["week_ending"], as_at)          # the file being made is never one of its own earlier reports
    past = [{"week_ending": r["week_ending"], "file": r["file"]} for r in past_reports or () if r["file"] != here]
    if past:
        published["data"]["past_reports"] = past
    n = store.next_publication(code) if number is None else number
    text = render(published, page.page_html(branding, view=True), as_at, project["name"], n)      # #65: the view-only page
    body = text.encode("utf-8")
    if len(body) > MAX_BYTES:
        raise PublishError(f"The report is {len(body) / 1048576:.1f} MB, which is over the {MAX_BYTES // 1048576} MB limit. "
                           "Remove or shrink the largest image or attachment, then publish again.")
    return {"body": body, "sha256": hashlib.sha256(body).hexdigest(), "project": project, "as_at": as_at, "published": published, "number": n, "past_reports": past}


EARLIER_TOO_BIG = ("The file already there is too big to keep a copy of, so it was not replaced. "
                   "Move or remove it first, then publish again.")


def read_plain(path, limit=None):
    """The bytes of an ordinary file (at most `limit` of them), or OSError for a link, a pipe, a folder or anything else."""
    if not stat.S_ISREG(os.lstat(path).st_mode):
        raise OSError("not an ordinary file")
    with open(path, "rb") as f:
        return f.read() if limit is None else f.read(limit)


EARLIER_MAX = 64 * 1048576      # #326: the most of a replaced file that is kept to put back; a larger one is not replaced


def read_earlier(path):
    """The bytes of the ordinary file at `path` (kept to put back if a publish is refused), or OSError for anything else.
    A file over EARLIER_MAX is refused with PublishError rather than kept cut short: it would be put back truncated."""
    data = read_plain(path, EARLIER_MAX + 1)
    if len(data) > EARLIER_MAX:
        raise PublishError(EARLIER_TOO_BIG)
    return data


def still_ours(path, digest):
    """Whether the file at `path` still holds exactly the bytes whose SHA-256 is `digest`."""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest
    except OSError:
        return False


def _link_no_follow(src, dest):
    """A second name for `src` itself: a link moved aside is put back as that link, never as the file it points at (#604)."""
    try:
        os.link(src, dest, follow_symlinks=False)
    except NotImplementedError:
        os.link(src, dest)


def _put_back(aside, dest):
    """Move `aside` back to `dest`, never over a name taken meanwhile. True when placed; False when the name was taken
    (`aside` is left as it is); None when it could not be moved (`aside` is left as it is, bytes intact)."""
    try:
        return platform.move_unless_exists(aside, dest, link=_link_no_follow)
    except (OSError, platform.PlatformError):
        return None


def take_back(path, digest):
    """Remove a file this call wrote and nothing else: only when it still holds exactly the bytes written. True when it is gone.
    #604: there is no gap between the check and the removal. Whatever is at `path` is first moved aside in one step and
    checked there; only our own bytes are removed, and anything else is put straight back, never replaced."""
    path = Path(path)
    aside = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(4)}.aside")
    try:
        os.rename(path, aside)
    except FileNotFoundError:
        return True
    except OSError:
        return False
    if still_ours(aside, digest):
        try:
            os.unlink(aside)
            return True
        except OSError:
            pass                                        # ours, but it would not go: put back below, not left hidden
    _put_back(aside, path)
    return False


def put_link_back(dest, target, digest):
    """Put the link `dest` -> `target` back in place of the file this call wrote (#388, #604), without a check-then-act gap:
    whatever is at `dest` is first moved aside in one step, and only a file that holds exactly the bytes whose SHA-256 is
    `digest` is replaced; anything else is put straight back (never replaced) and the link is not made. The link itself
    is made with os.symlink, which never replaces a name that has appeared meanwhile. If the link cannot be made, our
    file is put back, so `dest` is never left empty. Returns "linked", "kept" (our file is still at `dest`; the link was
    not put back: also when it could not even be moved aside), "other" (something that is not ours is at `dest`, or it
    is gone; it was left alone, no link made) or "aside" (a file could not be put back to `dest`, ours when the link
    could not be made, or someone else's that was moved aside: it is under its hidden aside name, not at `dest`)."""
    dest = Path(dest)
    aside = dest.with_name(f".{dest.name}.{os.getpid()}.{secrets.token_hex(4)}.aside")

    def back():                                         # aside -> dest, never over a name taken meanwhile; True when placed
        try:
            return platform.move_unless_exists(aside, dest, link=_link_no_follow)    # a swapped-in link goes back as that link
        except (OSError, platform.PlatformError):       # replace_file raises PlatformError: the caller still ends in PublishError
            return None                                 # left under its aside name, which keeps the bytes

    def drop_aside():                                   # a failing unlink is raised as PublishError, never a bare OSError, never swallowed
        try:
            os.unlink(aside)
        except OSError as e:                            # the os error stays on __cause__ only; the user sees the owner's sentence
            raise PublishError("The old copy could not be cleared.") from e

    try:
        os.rename(dest, aside)
    except OSError:                                     # nothing was moved: if our file is still at dest, say so (#605)
        return "kept" if still_ours(dest, digest) else "other"
    if not still_ours(aside, digest):
        if back() is None:                              # their file could not be put back: it is under its aside name, dest is empty
            return "aside"                              # the caller says so
        return "other"                                  # put back, or the name was taken meanwhile (theirs is left, never deleted)
    try:
        os.symlink(target, dest)
    except OSError:
        placed = back()
        if placed:
            return "kept"
        if placed is False:                             # the name was taken meanwhile: ours is the extra copy
            drop_aside()
            return "other"
        return "aside"                                  # None: the report is under its aside name
    drop_aside()
    return "linked"


def publish(store, code, folder, *, by_user, overwrite=False, now=None, branding=None):
    """Write {folder}/{CODE}-report-{date}.html and return {"path", "sha256", "bytes", "seq"}. The file is encoded once,
    hashed once, written with platform.write_file (a temporary file, then replaced: never half a file), read back and
    compared; only then is it recorded with Store.log_publication (once). An existing file of that name is refused unless
    overwrite=True, and the name is reserved with an exclusive create first, so two publishes at once can't both take it.
    `now` is the publish date (YYYY-MM-DD); due dates and Overdue read as at that date."""
    folder = Path(folder)
    if not folder.is_dir():
        raise PublishError(f"{platform.folder_phrase(folder, True)} isn't there. Choose a folder that exists.")
    built = build(store, code, now, branding)
    project, as_at, body = built["project"], built["as_at"], built["body"]
    dest = folder / file_name(code, project["week_ending"], as_at, folder)
    reserved = False
    if not overwrite:
        try:
            os.close(os.open(dest, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))      # exclusive: the name is ours or refused
            reserved = True
        except FileExistsError:
            raise PublishError(f"{dest.name} is already in that folder. Choose another name, or replace it.") from None
        except OSError as e:
            raise PublishError(f"{dest.name} could not be saved ({e.strerror or e}). Nothing was written.") from e
    digest = built["sha256"]
    earlier = None                         # #120: a file overwrite=True replaces is put back if the publish fails or loses the race
    earlier_link = None                    # #388: so is a link it replaces (the link itself, not the file it points at)
    if overwrite:
        try:
            earlier = read_earlier(dest)
        except OSError:
            earlier = None
            try:
                earlier_link = os.readlink(dest)
            except OSError:
                earlier_link = None
    try:
        try:
            platform.write_file(dest, body)
        except OSError as e:
            raise PublishError(f"{dest.name} could not be saved ({e.strerror or e}). Nothing was written.") from e
        if hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
            raise PublishError(f"{dest.name} was not saved as it was made (the folder may be syncing). Try again.")
    except BaseException:
        if reserved:                       # take the empty name back if nothing real was put there
            try:
                if dest.stat().st_size == 0:
                    dest.unlink()
            except OSError:
                pass
        raise
    try:
        seq = store.log_publication(code, dest, project["week_ending"], digest, by_user, number=built["number"])
    except NumberTaken as e:           # another publication took the number: this file says a number it does not have, so it is taken back
        if not overwrite:
            take_back(dest, digest)
        elif earlier is not None:
            if still_ours(dest, digest):
                try:
                    platform.write_file(dest, earlier)
                except (OSError, platform.PlatformError):
                    pass
        elif earlier_link is not None:
            placed = put_link_back(dest, earlier_link, digest)
            if placed == "kept":                                         # #605: said plainly, not swallowed
                raise PublishError(f"{e} The link that was at {dest.name} could not be put back, so this report is still there "
                                   "under that name.") from e
            if placed == "aside":                                        # said the same way as "kept"
                raise PublishError(f"{e} The report could not be put back in the folder under its name. It is still in the folder under a hidden name.") from e
        else:
            take_back(dest, digest)
        raise PublishError(str(e)) from e
    except Exception as e:             # the file is good; only the record failed: say so, so nobody publishes it twice
        raise PublishError(f"{dest.name} was saved in {platform.folder_phrase(folder)}, but clark could not record it. The file is fine. "
                           "Publish again to record it, or ask for help if it happens again.") from e
    return {"path": str(dest), "sha256": digest, "bytes": len(body), "seq": seq, "number": built["number"]}


def main(argv):
    """python3 -m clark.publish CODE FOLDER [--db clark.db] [--overwrite]: one report, for manual runs and CI."""
    ap = argparse.ArgumentParser(prog="python3 -m clark.publish", description=main.__doc__.split(": ", 1)[1])
    ap.add_argument("code")
    ap.add_argument("folder")
    ap.add_argument("--db", help="the database (default: clark.db in clark's data folder)")
    ap.add_argument("--by", dest="by_user", default=getpass.getuser(), help="who is publishing (default: this login)")
    ap.add_argument("--overwrite", action="store_true", help="replace a file of the same name")
    args = ap.parse_args(argv)
    try:
        store = open_store(args.db or platform.data_dir() / "clark.db")
        try:
            done = publish(store, args.code, args.folder, by_user=args.by_user, overwrite=args.overwrite)
        finally:
            store.close()
    except (PublishError, platform.PlatformError, StoreInvalid) as e:
        print(e)
        return 1
    print(f"wrote {done['path']} ({done['bytes']:,} bytes, sha256 {done['sha256']})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
