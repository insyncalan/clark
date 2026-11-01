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

from clark import publish
from clark import ask
from clark.ask import BUDGET, MAX_PASSAGE, Passage

PASSAGE_SIZE = 1200          # characters a passage is cut to, about (one or a few rows)
LABELS = {"project": "report: the project", "milestones": "report: milestones", "actions": "report: actions",
          "raid": "report: risks and issues", "decisions": "report: decisions", "use_cases": "report: use cases"}
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
    "use_cases": ("ref", "status", "headline", "standing"),
}
WORDS = re.compile(r"[^\W_]{3,}", re.UNICODE)
_TAG = re.compile(r"<[^>]*>")


@dataclass(frozen=True)
class ProjectData:
    """What the open project's data gives a question: the chosen `passages`, the `facts` the claims check compares against
    ({id: {"title", "owner"}}, published rows only), and `left_out`, how many passages did not fit the budget."""
    passages: tuple
    facts: dict
    left_out: int


def plain(value):
    """A value as one line of plain text: HTML the editor wrote is reduced to its words, dates shown DD-MM-YYYY."""
    text = html.unescape(_TAG.sub(" ", str(value)))
    return " ".join(text.split())


def _shown_date(value):
    s = str(value or "")
    return f"{s[8:10]}-{s[5:7]}-{s[0:4]}" if re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", s) else s


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
        p = _field(f, project.get(f))
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
    ids = set(re.findall(r"\b[A-Z][A-Z0-9]{2,6}-[A-Z]?-?\d{1,4}\b", question or ""))
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


def project_data(store, code, question="", budget=BUDGET):
    """The open project's data for one question, from what the published file would carry (publish.select). Raises
    publish.PublishError (plain words) for a code that isn't a project."""
    selected = publish.select(publish.read_inputs(store, code))["data"]
    passages, secret = _cut_screened(LABELS["project"], project_lines(selected.get("project") or {}))
    for kind in KIND_ORDER:
        more, n = _cut_screened(LABELS[kind], [row_line(kind, r) for r in selected.get(kind) or ()])
        passages += more
        secret += n
    chosen, left = choose(passages, question, budget)
    return ProjectData(chosen, facts_of(selected), left + secret)
