// The project-record picker's logic ("Add from your project record", FR-16; the planning repo #67). Plain functions, no DOM and no
// Preact, so a test can run them alone. A row is "hidden from the report" when its id is in report_hidden, or (a Work item
// only) client_visible is 0; those are the only rows the picker offers. Nothing here saves: the caller gets the chosen ids
// and #65's change path does the adding.
import { dayNumber, showDate } from "../workItems.js";

// The kinds in the order the picker lists them. `key` is the array in the project's data (Store.data_for), `noun` a word for
// the plain-words label, `text` the field a person reads and searches.
export const KINDS = [
  { kind: "actions", key: "actions", label: "Actions", noun: "Action", text: (r) => r.description, work: true },
  { kind: "raid", key: "raid", label: "Risks and issues", noun: "Risk or issue", text: (r) => r.description, work: true },
  { kind: "decisions", key: "decisions", label: "Decisions", noun: "Decision", text: (r) => r.decision, work: true },
  { kind: "milestones", key: "milestones", label: "Milestones", noun: "Milestone", text: (r) => r.name, work: true },
  { kind: "usecases", key: "use_cases", label: "Use cases", noun: "Use case", text: (r) => String(r.title || "").split("\n")[0], work: false },
  { kind: "documents", key: "documents", label: "Documents", noun: "Document", text: (r) => r.title, work: false },
];

// A date as a person reads it everywhere in clark, DD-MM-YYYY (showDate, the Work items list's own). A stored text that is not a
// real day (2026-02-31, "soon") is shown as it was stored, never made into a day; nothing stored shows nothing (never throws).
export function plainDate(s) {
  const text = s == null ? "" : String(s);
  return dayNumber(text) === null ? text : showDate(text);
}

function idSet(ids) {
  return new Set(ids == null ? [] : Array.from(ids));
}

// The group a row belongs to: its `group` when pickable() has set it, else worked out from the id's shape
// (ABC-A-001 action, ABC-D-001 decision, ABC-M-001 milestone, ABC-U-001 use case, ABC-001 risk or issue).
export function groupOf(row) {
  if (row.group) return row.group;
  const m = /^[A-Z0-9]+-([A-Z])-\d+$/.exec(String(row.id));
  if (m) return { A: "actions", D: "decisions", M: "milestones", U: "usecases" }[m[1]] || "documents";
  return /^[A-Z0-9]+-\d+$/.test(String(row.id)) ? "raid" : "documents";
}
function kindOf(row) {
  const g = groupOf(row);
  return KINDS.find((k) => k.kind === g);
}

// A row's own words, as a plain string (the one text a person searches and reads).
export function textOf(row) {
  const k = kindOf(row);
  return String((k ? k.text(row) : row.text) || "").trim();
}

// The one-line label for a row, in plain words, per kind: "Action ABC-A-001: Agree the plan (owner Sam, due 03-11-2026)".
// Always text, never markup; a long line is cut at 140 characters.
export function describe(row) {
  const k = kindOf(row);
  const g = groupOf(row), bits = [];
  if (g === "actions") {
    bits.push(row.owner && row.owner !== "TBC" ? `owner ${row.owner}` : "no owner", row.due_date ? `due ${plainDate(row.due_date)}` : "no due date");
  } else if (g === "raid") {
    bits.push(String(row.type || "Risk").toLowerCase(), row.owner && row.owner !== "TBC" ? `owner ${row.owner}` : "no owner");
  } else if (g === "decisions") {
    bits.push(String(row.status || "Made").toLowerCase(), row.made_by ? `by ${row.made_by}` : "");
  } else if (g === "milestones") {
    bits.push(String(row.state || row.status || "Planned").toLowerCase(), row.baseline_date ? `agreed ${plainDate(row.baseline_date)}` : "no agreed date");
  } else if (g === "usecases") {
    bits.push(String(row.status || "").toLowerCase());
  } else if (g === "documents") {
    bits.push(row.kind || "", row.date ? plainDate(row.date) : "");
  }
  const text = textOf(row) || "No text";
  const ref = g === "usecases" && row.ref ? ` ${row.ref}` : "";
  const line = `${k ? k.noun : "Item"}${ref} ${row.id}: ${text}${bits.filter(Boolean).length ? ` (${bits.filter(Boolean).join(", ")})` : ""}`;
  // cut by code points, so an emoji is never split in two
  const chars = Array.from(line);
  return chars.length > 140 ? `${chars.slice(0, 139).join("").trimEnd()}…` : line;
}

// Is this row left out of the report? Its id is in report_hidden, or (every kind that has the column, so not a document) its
// client_visible is 0.
function hiddenFrom(row, k, hidden) {
  return hidden.has(row.id) || (k.kind !== "documents" && Number(row.client_visible) === 0);
}

// The rows the picker may offer: hidden from the report, matching the search, grouped by kind in KINDS order (rows keep
// the data's own order inside a group; empty groups are left out). `onPage` is an optional list of ids already put back on
// the page this session: they are never offered, even while still in hiddenIds. Archived rows are never offered.
// Returns [{ kind, label, rows: [{ ...row, group, text, summary }] }]; `group` is the kind the row was listed under
// (a document has its own `kind` field, so the row's group is never called kind).
export function pickable(data, hiddenIds, query, onPage) {
  const hidden = idSet(hiddenIds), already = idSet(onPage);
  const terms = String(query == null ? "" : query).toLowerCase().split(/\s+/).filter(Boolean);
  const seen = new Set();
  const groups = [];
  for (const k of KINDS) {
    const rows = [];
    for (const raw of (data && data[k.key]) || []) {
      if (!raw || raw.id == null || seen.has(raw.id) || already.has(raw.id) || Number(raw.archived) === 1) continue;
      if (!hiddenFrom(raw, k, hidden)) continue;
      const row = { ...raw, group: k.kind };
      const hay = `${row.id} ${textOf(row)}`.toLowerCase();
      if (!terms.every((t) => hay.includes(t))) continue;
      seen.add(row.id);
      rows.push({ ...row, text: textOf(row), summary: describe(row) });
    }
    if (rows.length) groups.push({ kind: k.kind, label: k.label, rows });
  }
  return groups;
}

// Every id in a result of pickable(), in listed order.
export function idsOf(groups) {
  return groups.flatMap((g) => g.rows.map((r) => r.id));
}

// Taking several at once. A selection is a plain array of ids in the order they were chosen; each function gives a new one.
export function toggle(selection, id) {
  const have = selection || [];
  return have.includes(id) ? have.filter((x) => x !== id) : [...have, id];
}
export function selectAll(selection, groups) {
  const have = selection || [];
  return [...have, ...idsOf(groups).filter((id) => !have.includes(id))];
}
export function clear() {
  return [];
}

// What "Add selected" hands on: the selected ids that are still on offer (a row that left the list is not added), in the
// order they were chosen.
export function chosen(selection, data, hiddenIds, onPage) {
  const offered = new Set(idsOf(pickable(data, hiddenIds, "", onPage)));
  return (selection || []).filter((id) => offered.has(id));
}

// The words under the search box and on the button.
export function countWords(n) {
  return n ? `${n} selected` : "None selected";
}
export function addWords(n) {
  return n ? `Add ${n}` : "Add selected";
}
// The empty-state sentence: nothing hidden at all, or nothing matching the search.
export const ALL_ON_PAGE = "Everything is already on the page.";
export function emptyWords(data, hiddenIds, query, onPage) {
  if (!idsOf(pickable(data, hiddenIds, "", onPage)).length) return ALL_ON_PAGE;
  return idsOf(pickable(data, hiddenIds, query, onPage)).length ? "" : "Nothing matches your search. Clear it to see what can be added.";
}
