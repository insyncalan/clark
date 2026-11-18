"""ask: the open project's own data as passages (#47d, commit 8 of the design note). Read only.

ONE FILTER, NOT TWO (owner decision: "report only"; a reviewer's MEDIUM 4 on the design note). The passages are built from
`publish.select(publish.read_inputs(store, code))`: exactly what the published file would carry, and nothing else. So a row hidden
from the report, a row that isn't client-visible, an archived row, a row labelled Sensitive (or with any label that is left out of
the report), a hidden section, and every column the published file never carries (internal notes, Movement, sources, reasoning,
options, response actions) can never become a passage, because select() never hands them over. This module adds no second rule
of its own about what may be seen; it only turns the selected rows into text, cuts the text into passages and picks the ones that
fit the budget.

The store is read through read_inputs' one read-only transaction (store.publish_inputs); nothing here opens the database, a file
or a process, and nothing is written.
"""
import html
import re
from dataclasses import dataclass

from clark import publish, sanitise
from clark import ask
from clark import timefmt
from clark.ask import BUDGET, MAX_PASSAGE, Passage

PASSAGE_SIZE = 1200          # characters a passage is cut to, about (one or a few rows)
KIND_WORDS = {"milestones": "milestones", "actions": "actions", "raid": "risks and issues", "decisions": "decisions",
              "use_cases": "use cases"}
LABELS = {"project": "report: the project", "milestones": "report: milestones", "actions": "report: actions",
          "raid": "report: risks and issues", "decisions": "report: decisions", "use_cases": "report: use cases", "left_out": "report: left out"}
KIND_ORDER = ("milestones", "actions", "raid", "decisions", "use_cases")
TITLE = {"milestones": "name", "actions": "description", "raid": "description", "decisions": "decision", "use_cases": "title"}
OWNER = {"milestones": "owner", "actions": "owner", "raid": "owner", "decisions": "made_by"}
DATES = ("baseline_date", "forecast_date", "actual_date", "due_date", "raised", "closed", "date", "needed_by", "revisit",
         "week_ending")
SHOWN = {
    "milestones": ("status", "owner", "baseline_date", "forecast_date", "actual_date", "percent_complete", "state_word",
                   "state_reason", "description", "client_message", "workstream"),
    "actions": ("status", "owner", "priority", "due_date", "raised", "closed", "latest_update", "client_message", "workstream",
                "milestone", "use_case"),
    "raid": ("type", "status", "owner", "priority", "impact", "likelihood", "due_date", "raised", "closed", "client_message",
             "workstream", "milestone", "use_case"),
    "decisions": ("status", "made_by", "date", "needed_by", "revisit", "replaces", "client_message", "use_case"),
    "use_cases": ("ref", "status", "commitment", "headline", "standing"),
}
WORDS = re.compile(r"[^\W_]{3,}", re.UNICODE)
ID_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]{2,6}-[A-Z]?-?\d{1,4}\b")
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
    kinds_left_out: tuple = ()          # row 1213: the kinds whose whole section is left out of the report (named in a passage and a note)


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


def _score(words, ids, passage):
    text = passage.text.casefold()
    return sum(5 for i in ids if i.casefold() in text) + sum(1 for w in words if w in text)


def choose(passages, question, budget=BUDGET):
    """The passages that fit `budget` characters, best first by plain keyword overlap with the question (an item ID it names
    counts most), kept in their original order. Returns (chosen, left_out_count). The first passage (the project) always goes
    first when it fits."""
    words = {w.casefold() for w in WORDS.findall(question or "")}
    ids = set(ID_PATTERN.findall(question or ""))
    ranked = sorted(range(len(passages)), key=lambda i: (i != 0, -_score(words, ids, passages[i]), i))
    keep, used = set(), 0
    for i in ranked:
        size = len(passages[i].text)
        if used + size <= budget:
            keep.add(i)
            used += size
    return tuple(passages[i] for i in sorted(keep)), len(passages) - len(keep)


def facts_of(selected):
    """{id: {"title", "owner"}} for every published row, so the claims check can compare a reply's title or owner."""
    out = {}
    for kind in KIND_ORDER:
        for row in selected.get(kind) or ():
            if row.get("id"):
                out[row["id"]] = {"title": plain(row.get(TITLE[kind]) or ""), "owner": plain(row.get(OWNER.get(kind, "")) or "")}
    return out


def kinds_left_out(inputs):
    """Row 1213: the kinds whose whole section is left out of the report (names only, never a row or a count)."""
    hidden = publish.hidden_types(inputs.get("sections"), bool(inputs.get("sections_deleted")))
    return tuple(k for k in KIND_ORDER if publish.SECTION_OF_KIND[k] in hidden)


def left_out_line(kinds):
    """The plain words that say which kinds the report leaves out, so the answer never says none exist."""
    names = ", ".join(KIND_WORDS[k] for k in kinds)
    return (f"Left out of the report this answer reads: {names}. They may exist in the project, but they are not given here. "
            "Do not say there are none; say they were not part of what you were given.")


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


def project_data(store, code, question="", budget=BUDGET, as_at=None):
    """The open project's data for one question, from what the published file would carry (publish.select). Raises
    publish.PublishError (plain words) for a code that isn't a project."""
    inputs = publish.read_inputs(store, code, as_at)
    selected = publish.select(inputs)["data"]
    passages, secret = _cut_screened(LABELS["project"], project_lines(selected.get("project") or {}))
    left_kinds = kinds_left_out(inputs)
    if left_kinds:
        passages += _cut(LABELS["left_out"], [left_out_line(left_kinds)])
    totals = {}
    for kind in KIND_ORDER:
        rows = [row_line(kind, r) for r in selected.get(kind) or ()]
        more, n = _cut_screened(LABELS[kind], rows)
        passages += more
        secret += n
        totals[kind] = len(rows)
    chosen, left = choose(passages, question, budget)
    counts = tuple((k, sum(p.text.count("\n") + 1 for p in chosen if p.label == LABELS[k]), t) for k, t in totals.items() if t)
    return ProjectData(chosen, facts_of(selected), left, secret, timefmt.day_text(inputs.get("as_at")) if _is_day(inputs.get("as_at")) else "", counts, left_kinds)
