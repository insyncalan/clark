// The section templates and the Add a section box's logic (#96): pure functions and one list. No DOM, no signals, nothing sent.
// docs/handoff/design-96-templates.md has the rules. A template is data; the box (edit/AddDialog.jsx) draws it and edit/actions.js
// sends the requests that `plan` gives back. The second slice adds entries to TEMPLATES and nothing else.
import { rows } from "./placement.js";

// What the store takes in a new section today (changes.py: type "text" only). A template whose type is not here is listed but
// not offered. Widen this only with the guarded change in the design note, section 6.
export const ACCEPTS = { types: ["text"] };

export const KINDS = [
  { id: "text", name: "Text and pictures" },
  { id: "figures", name: "Figures" },
  { id: "work", name: "Work items" },
  { id: "files", name: "Files and links" },
  { id: "dates", name: "People and dates" },
  { id: "notes", name: "Notes" },
];
export const RECENT = "recent";
export const RECENT_MAX = 3;

export const TEMPLATES = [
  { id: "text", name: "Text", kind: "text", fit: ["full", "half"], type: "text", title: "New section", body: "",
    description: "A heading and a block of your own words.", holds: ["A heading", "Text you write"] },
  { id: "text-image", name: "Text and image", kind: "text", fit: ["full", "half"], type: "textimage", title: "Text and image", body: "",
    description: "Words on one side and a picture on the other.", holds: ["A heading", "Text you write", "One image"] },
  { id: "figures-3", name: "Key figures, three", kind: "figures", fit: ["full", "half"], type: "figures", title: "Key figures", body: "",
    description: "Three big numbers side by side, each with a label. Each can follow the project or be typed in.", holds: ["Three figures, each with a label"] },
  { id: "figures-4", name: "Key figures, four", kind: "figures", fit: ["full", "half"], type: "figures", title: "Key figures", body: "",
    description: "Four big numbers side by side, each with a label. Each can follow the project or be typed in.", holds: ["Four figures, each with a label"] },
  { id: "raid-3", name: "RAID cards, three", kind: "work", fit: ["full"], type: "raidcards", title: "Risks and issues", body: "",
    description: "Three cards, each showing one work item from your project with its owner, date and status. The text under a card is the latest update, the client wording or your own words.",
    holds: ["Three work items from your project", "A line of text under each"] },
  { id: "raid-4", name: "RAID cards, four", kind: "work", fit: ["full"], type: "raidcards", title: "Risks and issues", body: "",
    description: "Four cards, each showing one work item from your project with its owner, date and status. The text under a card is the latest update, the client wording or your own words.",
    holds: ["Four work items from your project", "A line of text under each"] },
  { id: "work-items", name: "Work items list", kind: "work", fit: ["full", "half"], type: "workitems", title: "Work items", body: "",
    description: "A live list of work items chosen by a filter you set: type, status, due date, owner and more. Hidden and client-hidden items are never published.",
    holds: ["A filter", "Live rows from Work items"] },
  { id: "docs-links", name: "Documents and links", kind: "files", fit: ["full", "half"], type: "doclinks", title: "Documents and links", body: "",
    description: "A tidy list of files and links. A file is a link to the project's shared SharePoint folder.", holds: ["Files", "Links"] },
  { id: "callout", name: "Callout", kind: "notes", fit: ["half", "full"], type: "callout", title: "Callout", body: "",
    description: "A highlighted box for information, a decision needed or a warning.", holds: ["A short message", "Information, decision needed or warning"] },
  { id: "key-dates", name: "Key dates", kind: "dates", fit: ["half"], type: "keydates", title: "Key dates", body: "",
    description: "A short list of the dates that matter, typed in or taken from your milestones.", holds: ["Dates with a label each"] },
];

export const MESSAGES = {
  gone: "That section isn't in the report any more. Reload the page.",
  noNext: "This is the last section, so there is nothing to sit beside.",
  noneYet: "There is no section yet to sit beside.",
  nextFull: "The next row already has two sections. Place it on its own row.",
  needsFull: "This template needs the full width. Place it on its own row.",
  later: "Coming with a later release.",
  unknown: "That template isn't in the list.",
};

const FIT_WORDS = { full: "Full width", half: "Half width" };
export const fitWords = (t) => t.fit.map((f) => FIT_WORDS[f]).join(" or ");

export const find = (id) => TEMPLATES.find((t) => t.id === id) || null;
export const available = (t) => !!t && ACCEPTS.types.includes(t.type);
export const kindName = (id) => (KINDS.find((k) => k.id === id) || { name: "" }).name;

const words = (s) => String(s || "").toLowerCase().split(/\s+/).filter(Boolean);
const matches = (t, q) => {
  const hay = `${t.name} ${t.description} ${kindName(t.kind)} ${t.holds.join(" ")}`.toLowerCase();
  return words(q).every((w) => hay.includes(w));
};

// The templates for a search and a choice of kind ("" or "all": every kind; RECENT: the recently used ones, newest first).
export function list({ query = "", kind = "", recent = [] } = {}) {
  const found = TEMPLATES.filter((t) => matches(t, query));
  if (kind === RECENT) return recent.map((id) => found.find((t) => t.id === id)).filter(Boolean);
  return kind && kind !== "all" ? found.filter((t) => t.kind === kind) : found;
}

// How many each choice would show for the search: { all, recent, <kind id>: n ... }.
export function counts({ query = "", recent = [] } = {}) {
  const out = { all: list({ query }).length, [RECENT]: list({ query, kind: RECENT, recent }).length };
  for (const k of KINDS) out[k.id] = list({ query, kind: k.id }).length;
  return out;
}

// The last templates used, newest first, each once, at most RECENT_MAX. Unknown ids are dropped.
export function remember(recent, id) {
  if (!find(id)) return (recent || []).filter(find).slice(0, RECENT_MAX);
  return [id, ...(recent || []).filter((r) => r !== id && find(r))].slice(0, RECENT_MAX);
}

// The section the new one is made after: the last of the row that holds `after`, so a pair is never split. null: the end.
export function anchor(sections, after) {
  if (after === null || after === undefined) return { ok: true, id: null };
  const row = rows(sections).find((r) => r.some((s) => s.id === after));
  return row ? { ok: true, id: row[row.length - 1].id } : { ok: false, message: MESSAGES.gone };
}

// Whether a template can sit beside the next section after `after`: { ok: true } or { ok: false, message }.
export function besideState(sections, after, template) {
  if (!template) return { ok: false, message: MESSAGES.unknown };
  if (!template.fit.includes("half")) return { ok: false, message: MESSAGES.needsFull };
  if (after === null || after === undefined) return { ok: false, message: MESSAGES.noneYet };
  const a = anchor(sections, after);
  if (!a.ok) return a;
  const all = rows(sections);
  const i = all.findIndex((r) => r.some((s) => s.id === a.id));
  if (i + 1 >= all.length) return { ok: false, message: MESSAGES.noNext };
  if (all[i + 1].length !== 1) return { ok: false, message: MESSAGES.nextFull };
  return { ok: true };
}

// The requests to make to add template `id` below section `after` (null: at the end), alone or beside the next section.
// { ok: true, requests, words } or { ok: false, message }. A request's `id: "$new"` means the section the first one made.
// Today a template other than the available ones is refused here, in words, before anything is sent.
export function plan(sections, id, after, beside = false) {
  const t = find(id);
  if (!t) return { ok: false, message: MESSAGES.unknown };
  if (!available(t)) return { ok: false, message: MESSAGES.later };
  const a = anchor(sections, after);
  if (!a.ok) return a;
  if (beside) {
    const b = besideState(sections, after, t);
    if (!b.ok) return b;
  }
  const requests = [{ op: "new", values: { type: t.type, title: t.title }, after: a.id, place: "report" }];
  const last = a.id === null ? null : sections.find((s) => s.id === a.id);
  const lone = last && rows(sections).some((r) => r.length === 1 && r[0].id === last.id);
  if (!beside && lone && last.beside) requests.push({ op: "update", id: last.id, changes: { beside: 0 }, place: "report" });   // a flag on the last section is ignored by the page; the new section after it would pair with it
  if (beside) requests.push({ op: "update", id: "$new", changes: { beside: 1 }, place: "report" });
  return { ok: true, requests, words: `${t.name} added${beside ? ", beside the next section" : ""}.`, template: t };
}
