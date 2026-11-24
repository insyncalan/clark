"""ask: the open project's own data as passages (#47d, commit 8 of the design note). Read only.

ROW 1367 (ruling 19-11, reverses the earlier "report only" rule): the passages are built from the project's OWN rows as
`publish.read_inputs` hands them over, not from `publish.select`. A row hidden from the report (eye off, not client visible,
in a hidden section) IS read, for the owner. Still left out: an archived row (unless a later change reads them), a row with a label
the report leaves out (Sensitive), every column read_inputs does not ask for (team-only fields wait for an answer, row 1367 Q4), and
any line that looks like a password or a key (ask._secret, via _cut_screened). Nothing the client gets changes: publish.select is
untouched. This module adds the cut to the budget only; the note says what was cut, with counts.

The store is read through read_inputs' one read-only transaction (store.publish_inputs); nothing here opens the database, a file
or a process, and nothing is written.
"""
import html
import re
from dataclasses import dataclass

from clark import glance, publish, sanitise
from clark import ask
from clark import milestones, timefmt
from clark.ask import BUDGET, ID_PATTERN, MAX_PASSAGE, Passage

PASSAGE_SIZE = 1200          # characters a passage is cut to, about (one or a few rows)
KIND_WORDS = {"milestones": "milestones", "actions": "actions", "raid": "risks and issues", "decisions": "decisions",
              "use_cases": "use cases", "workstreams": "workstreams"}
LABELS = {"project": "report: the project", "milestones": "report: milestones", "actions": "report: actions",
          "raid": "report: risks and issues", "decisions": "report: decisions", "use_cases": "report: use cases",
          "workstreams": "report: workstreams"}
KIND_ORDER = ("milestones", "actions", "raid", "decisions", "use_cases", "workstreams")
TITLE = {"milestones": "name", "actions": "description", "raid": "description", "decisions": "decision", "use_cases": "title",
         "workstreams": "name"}
OWNER = {"milestones": "owner", "actions": "owner", "raid": "owner", "decisions": "made_by"}
DATES = ("baseline_date", "forecast_date", "actual_date", "due_date", "raised", "closed", "date", "needed_by", "revisit",
         "week_ending", "created")
SHOWN = {
    "milestones": ("status", "owner", "baseline_date", "forecast_date", "actual_date", "percent_complete", "state_word",
                   "state_reason", "description", "client_message", "workstream"),
    "actions": ("status", "owner", "priority", "due_date", "raised", "closed", "latest_update", "client_message", "workstream",
                "milestone", "use_case"),
    "raid": ("type", "status", "owner", "priority", "impact", "likelihood", "due_date", "raised", "closed", "client_message",
             "workstream", "milestone", "use_case"),
    "decisions": ("status", "made_by", "date", "needed_by", "revisit", "replaces", "client_message", "use_case"),
    "use_cases": ("ref", "status", "commitment", "headline", "standing"),
    "workstreams": ("status", "created"),          # the lead, keywords and aliases are never read for a report (store.NEVER_PUBLISH)
}
_TAG = re.compile(r"<[^>]*>")


@dataclass(frozen=True)
class ProjectData:
    """What the open project's data gives a question: the chosen `passages`, the `facts` the claims check compares against
    ({id: {"title", "owner"}}, published rows only), `left_out`, how many passages did not fit the budget, and `secret`, how many
    lines were left out because they looked like a password or a key (shown by the same note as a passage left out for that)."""
    passages: tuple
    facts: dict
    left_out: int
    secret: int = 0
    today: str = ""                     # #1293 B: the report's as-at day as DD-MM-YYYY ("" when it is not a day)
    counts: tuple = ()                  # #1293 B: (kind, rows sent, rows in all) for each kind that has rows
    cut: int = 0                        # Row 1293: how many row lines were longer than MAX_PASSAGE and were cut (the Used line says so)


def _is_day(value):
    return isinstance(value, str) and timefmt.day_text(value) != value


def plain(value):
    """A value as one line of plain text: HTML the editor wrote is reduced to its words, dates shown DD-MM-YYYY."""
    text = html.unescape(_TAG.sub(" ", str(value)))
    return " ".join(text.split())


def _shown_date(value):
    return timefmt.day_text(value, prefix=True)


def _field(name, value):
    if value is None or value == "":
        return None
    value = _shown_date(value) if name in DATES else plain(value)
    return f"{name.replace('_', ' ')}: {value}" if value else None


def row_line(kind, row):
    """One row as one line: its ID, its title, then the fields the report shows that have a value."""
    head = " ".join(x for x in (str(row.get("id") or ""), plain(row.get(TITLE[kind]) or "")) if x)
    parts = [head] + [p for p in (_field(f, row.get(f)) for f in SHOWN[kind]) if p]
    return " | ".join(parts)


def project_lines(project):
    lines = []
    for f in ("name", "code", "sponsor", "phase", "health", "health_reason", "client_name", "week_ending"):
        p = _field(f, sanitise.rich_plain_text(project.get(f)) if f == "health_reason" else project.get(f))      # row 1005: the reason's words, not its markup
        if p:
            lines.append(p)
    current = plain(project.get("current_state") or "")
    if current:
        lines.append(f"current state: {current}")
    return lines


def _cut(label, lines):
    """Lines joined into passages of about PASSAGE_SIZE characters; a line longer than a passage is cut at MAX_PASSAGE."""
    out, run = [], []
    for line in lines:
        line = line[:MAX_PASSAGE]
        if run and sum(len(x) + 1 for x in run) + len(line) > PASSAGE_SIZE:
            out.append(Passage(label, "\n".join(run)))
            run = []
        run.append(line)
    if run:
        out.append(Passage(label, "\n".join(run)))
    return out


def _cut_screened(label, lines):
    """`_cut`, but a line too long for one passage is screened whole first: a password across the cut would be too short to match
    in either half. A line that looks like a secret is left out. Returns (passages, left_out_count)."""
    keep = [x for x in lines if len(x) <= MAX_PASSAGE or not ask._secret(x)]
    return _cut(label, keep), len(lines) - len(keep)


def long_rows(lines):
    """Row 1293: how many of `lines` are cut by _cut (longer than MAX_PASSAGE) and still sent (a secret-looking one is left out whole)."""
    return sum(1 for x in lines if len(x) > MAX_PASSAGE and not ask._secret(x))


def choose(passages, question, budget=BUDGET, limit=None):
    """The passages that fit `budget` characters, best first by plain keyword overlap with the question (an item ID it names
    counts most), kept in their original order. Returns (chosen, left_out_count). The first passage (the project) always goes
    first when it fits. `limit` is the most passages kept (none: no limit); the rest count as left out like any that did not fit."""
    keep, left = ask.choose([(p.label, p.text) for p in passages], question, budget, len(passages) if limit is None else limit)
    return tuple(passages[i] for i in keep), left


def state_of(kind, row, today):
    """DRAFT contract (row 1332): the words of ask.ITEM_STATES that apply to a published row. overdue: open and due before `today`
    (a milestone: its own state is Overdue); red: an open risk, issue, assumption or dependency rated Urgent or High, the same rows the
    page's High risks and issues tile counts (an action, a decision or a milestone is never red); no_owner: open and the owner field is blank
    or TBC, as the page reads an owner (a kind without an owner field has none to miss)."""
    if kind == "milestones":
        state = row.get("state")
        live = state != "Achieved"
        late, red = state == "Overdue", False
    else:
        full = {**row, "kind": "decision"} if kind == "decisions" else row
        live = glance.is_open(full)
        late = glance.is_overdue(full, today)
        red = live and kind == "raid" and glance.colour_of_priority(row.get("priority")) == "red"
    owner = plain(row.get(OWNER.get(kind, "")) or "").strip()
    blank = live and kind in OWNER and (not owner or owner.upper() == "TBC")
    return [w for w, on in (("overdue", late), ("red", red), ("no_owner", blank)) if on]


def facts_of(selected, today=None):
    """{id: {"title", "owner", "state"}} for every published row, so the claims check can compare a reply's title or owner, and the
    reply's items can say which rows are overdue, red or without an owner. `today` is the report's as-at day (ISO), None for none."""
    out = {}
    for kind in KIND_ORDER:
        for row in selected.get(kind) or ():
            if row.get("id"):
                out[row["id"]] = {"title": plain(row.get(TITLE[kind]) or ""), "owner": plain(row.get(OWNER.get(kind, "")) or ""),
                                  "state": state_of(kind, row, today)}
    return out


def ids_in_turns(turns, last=4):
    """The item IDs named in the last few turns of a chat, in order, so a follow-up ("and when is it due?") ranks the same items."""
    found = []
    for _role, text in list(turns or ())[-last:]:
        for i in ID_PATTERN.findall(text):
            if i not in found:
                found.append(i)
    return found


def partial_lines(counts):
    """One line per kind that was sent in part: "actions: 7 of 12 rows sent". Nothing for a kind sent whole."""
    return [f"{KIND_WORDS[k]}: {sent} of {total} rows sent" for k, sent, total in counts if sent < total]


def read_counts(data):
    """Row 1292: what a question read, for the line under its answer: the rows sent of each kind (work items are actions, risks and
    issues, and decisions) and the report's as-at day as DD-MM-YYYY ("" when it was not a day). Row 1294: `items` is every row sent and
    `left_out` every row of the project that was cut (0 when nothing was), for the line "N items read, M left out". Counts only; no row, title or text."""
    sent = {k: n for k, n, _total in data.counts}
    return {"work_items": sum(sent.get(k, 0) for k in ("actions", "raid", "decisions")), "milestones": sent.get("milestones", 0),
            "use_cases": sent.get("use_cases", 0), "as_at": data.today,
            "items": sum(n for _k, n, _total in data.counts), "left_out": sum(max(0, total - n) for _k, n, total in data.counts)}


# Row 1294 (rule 4): a question that asks for a count, a total or an overview. Said in plain words, whatever the case; a question that
# only names one item is not one of these.
_WHOLE = re.compile(r"\b(?:how\s+many|how\s+much|how\s+often|counts?|totals?|number\s+of|overviews?|summary|summaries|summari[sz]e|averages?|percents?|percentages?|per\s+cent|altogether|in\s+all|all\s+of\s+the|breakdowns?|list\s+all|list\s+every|tall(?:y|ies)|sums?|how\s+large|figures?|stat(?:istic)?s|all\s+(?:the\s+|of\s+the\s+|open\s+|closed\s+|late\s+)?(?:risks?|issues?|actions?|decisions?|items?|milestones?|use\s+cases?))\b", re.I)


def partial_answer(question, counts):
    """The ruled sentence for an answer that covers only part of the project: "" unless something was cut (some kind sent in part) and the
    question asks for a count, a total or an overview. The numbers are the rows read and the rows left out, as read_counts gives them."""
    got = read_counts(ProjectData((), {}, 0, 0, "", tuple(counts or ())))
    if got["left_out"] < 1 or not isinstance(question, str) or not _WHOLE.search(question):
        return ""
    n = got["items"]
    return f"This answer is partial: it covers only the {n} {'item that was' if n == 1 else 'items that were'} read, not the {got['left_out']} that {'was' if got['left_out'] == 1 else 'were'} left out."


def left_out_lines(counts):
    """Row 1367 R3: one plain line per kind that was cut, with counts, for the person. Nothing for a kind sent whole, so a project
    where nothing was cut gives no line at all."""
    return [f"Sent {sent} of {total} {KIND_WORDS[k]} (the closest to your question); {total - sent} {'was' if total - sent == 1 else 'were'} left out."
            for k, sent, total in counts if sent < total]


def own_rows(inputs):
    """Row 1367: the project's own rows by kind as read from the store, hidden ones included. Left out: an archived row, a row of
    another project, a row with a label the report excludes. A milestone carries its state words as the report would give them."""
    data, as_at = inputs["data"], inputs["as_at"]
    code = (data.get("project") or {}).get("code")
    blocked = publish._excluded_labels(inputs.get("label_rules"))
    labels = data.get("labels") or {}
    out = {}
    for kind in KIND_ORDER:
        rows = []
        for r in data.get(kind) or ():
            if r.get("archived") or (code and r.get("project", code) != code):
                continue
            if any(str(x).casefold() in blocked for x in labels.get(r.get("id"), ())):
                continue
            c = dict(r)
            for f in publish.RICH.get(kind, ()):          # the same clean-up the report gives its rich text (script and style bodies dropped)
                c[f] = publish.clean_html(sanitise.legacy_to_html(c[f]) if (kind, f) in publish.LEGACY_RICH and c.get(f) and not sanitise.HTML_START.match(c[f]) else c.get(f))
            if kind == "milestones":
                state = milestones.milestone_state(r, as_at)
                c.update(state=state, state_word=milestones.client_word(state))
            rows.append(c)
        out[kind] = rows
    return out


def project_data(store, code, question="", budget=BUDGET, as_at=None, limit=None):
    """The open project's own data for one question (row 1367), hidden rows included, archived left out, secret lines screened.
    Raises publish.PublishError (plain words) for a code that isn't a project. `limit` is the most passages kept (none: ask.MAX_PASSAGES; the
    service passes what a file added to the question leaves)."""
    inputs = publish.read_inputs(store, code, as_at)
    selected = own_rows(inputs)
    project = dict(publish.select(inputs)["data"].get("project") or {})
    project["current_state"] = publish.clean_html((inputs["data"].get("project") or {}).get("current_state") or "") or project.get("current_state")    # a hidden Current state section does not change what is read
    own = project_lines(project)
    passages, secret = _cut_screened(LABELS["project"], own)
    cut = long_rows(own)
    totals = {}
    for kind in KIND_ORDER:
        rows = [row_line(kind, r) for r in selected[kind]]
        more, n = _cut_screened(LABELS[kind], rows)
        cut += long_rows(rows)
        passages += more
        secret += n
        totals[kind] = len(rows) - n          # a line screened out as a secret has its own note, so it is not counted a second time
    chosen, left = choose(passages, question, budget, ask.MAX_PASSAGES if limit is None else limit)     # the request takes at most MAX_PASSAGES: more is refused
    counts = tuple((k, sum(p.text.count("\n") + 1 for p in chosen if p.label == LABELS[k]), t) for k, t in totals.items() if t)
    return ProjectData(chosen, facts_of(selected, inputs.get("as_at") if _is_day(inputs.get("as_at")) else None), left, secret, timefmt.day_text(inputs.get("as_at")) if _is_day(inputs.get("as_at")) else "", counts, cut)
