// The section templates and the Add a section box's logic (#96): pure functions and one list. No DOM, no signals, nothing sent.
// docs/handoff/design-96-templates.md has the rules. A template is data; the box (edit/AddDialog.jsx) draws it and edit/actions.js
// sends the requests that `plan` gives back.
//
// A template is placeable only when its entry says `ready: true` AND the store takes its type (ACCEPTS). The store takes every
// template type from #96's registry change (R0); each template's `ready` is switched on by the lead once that template is built
// (its section_kinds module and its page part say READY; tests/test_section_registry.py refuses `ready` on a stub). Until then
// it is listed but says "Coming with a later release." LATER holds the second slice's entries: in the catalogue, not yet in the
// box; the lead moves each one into TEMPLATES with its Help row.
import { rows } from "./placement.js";
import { TEMPLATE_TYPES } from "../templates/types.js";

// What the store takes in a new section (changes.py NEW_SECTION_TYPES: text, and every type in the template registry).
export const ACCEPTS = { types: ["text", ...TEMPLATE_TYPES] };

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

// Words and parts are the prototype's (system/prototype/views.js, the same list Help's table draws from). `fit` puts the better width first.
export const TEMPLATES = [
  { id: "text", name: "Text", kind: "text", fit: ["full", "half"], type: "text", title: "New section", body: "", ready: true,
    description: "Words under a heading, written in clark’s one editor.", holds: ["Heading", "Text"] },
  { id: "text-image", name: "Text and image", kind: "text", fit: ["full", "half"], type: "textimage", title: "Text and image", body: "", ready: true,
    description: "A story with a picture: a site visit, a design, a screenshot of the new system.", holds: ["Heading", "Text", "Image", "Caption"] },
  { id: "figures-4", name: "Key figures, four", kind: "figures", fit: ["full", "half"], type: "figures4", title: "Key figures", body: "", ready: true,
    description: "Three or four numbers with labels and a change since last week.", holds: ["Heading", "Figure · live", "Figure · live", "Figure · typed", "Figure · typed", "Caption"] },
  { id: "figures-3", name: "Key figures, three", kind: "figures", fit: ["full", "half"], type: "figures3", title: "Key figures", body: "", ready: true,
    description: "Three numbers with labels, in wider cards, so a short note fits under the change.", holds: ["Heading", "Figure · live", "Figure · live", "Figure · typed"] },
  { id: "raid-3", name: "RAID cards, three", kind: "work", fit: ["full"], type: "raid3", title: "Risks and issues", body: "", ready: true,
    description: "The risks, actions, issues or decisions you want the reader to see, as cards.", holds: ["Heading", "RAID card ×3", "Text source", "Text"] },
  { id: "raid-4", name: "RAID cards, four", kind: "work", fit: ["full"], type: "raid4", title: "Risks and issues", body: "", ready: true,
    description: "Four shorter cards: good for “this week’s actions” or “decisions needed”.", holds: ["Heading", "RAID card ×4"] },
  { id: "work-items", name: "Work items list", kind: "work", fit: ["full", "half"], type: "workitems", title: "Work items", body: "", ready: true,
    description: "Live rows from Work items, chosen by a filter: open actions due soon, red risks, decisions needed.", holds: ["Heading", "Filter (set in Edit)", "Work item list · live", "Caption (optional)"] },
  { id: "docs-links", name: "Documents and links", kind: "files", fit: ["full", "half"], type: "doclinks", title: "Documents and links", body: "", ready: true,
    description: "The papers that go with this week’s report.", holds: ["Heading", "File (one or more)", "Link list"] },
  { id: "callout", name: "Callout", kind: "notes", fit: ["half", "full"], type: "callout", title: "Callout", body: "", ready: true,
    description: "One thing the reader must see.", holds: ["Heading", "Callout · decision"] },
  { id: "key-dates", name: "Key dates", kind: "dates", fit: ["half", "full"], type: "keydates", title: "Key dates", body: "", ready: true,
    description: "What’s coming, from the milestones.", holds: ["Heading", "Date (from milestones)"] },
  { id: "link-preview", name: "Link preview", kind: "files", fit: ["full"], type: "linkcard", title: "Link preview", body: "", ready: true,
    description: "A web page shown as a card you write: a dashboard, a news item, a recording.", holds: ["Heading", "Link", "Card text"] },
  { id: "one-doc", name: "One document", kind: "files", fit: ["half", "full"], type: "onedoc", title: "Document", body: "", ready: true,
    description: "A single file to read.", holds: ["Heading", "File", "Text"] },
];

// The second slice (#96): every other template type, built (its section_kinds module and page part say READY) but not in the
// box yet (find, list and plan read TEMPLATES only). No words here: their names, descriptions and parts wait for their words and
// Help rows, and a template the box does not offer is not named on the page. The lead moves an entry into TEMPLATES, with its
// words and its Help row.
export const LATER = [
  { id: "headline", type: "headline", ready: true },
  { id: "gallery", type: "gallery", ready: true },
  { id: "table", type: "table", ready: true },
  { id: "image-caption", type: "imagecap", ready: true },
  { id: "quote", type: "quote", ready: true },
  { id: "contacts", type: "contacts", ready: true },
  { id: "checklist", type: "checklist", ready: true },
];

// Every template entry, in the box or not: one per template type, and Text.
export const CATALOGUE = [...TEMPLATES, ...LATER];

export const MESSAGES = {
  gone: "That section isn't in the report any more. Reload the page.",
  noneYet: "There is no section yet to sit beside.",
  hasPartner: "That section already shares its row. Place it on its own row.",
  needsFull: "This template needs the full width. Place it on its own row.",
  later: "Coming with a later release.",
  unknown: "That template isn't in the list.",
  notAlone: "The section was added, but it could not be put on its own row. Undo removes it.",
};

const FIT_WORDS = { full: "Full width", half: "Half width" };
export const fitWords = (t) => t.fit.map((f) => FIT_WORDS[f]).join(" or ");

export const find = (id) => TEMPLATES.find((t) => t.id === id) || null;
export const available = (t) => !!t && t.ready === true && ACCEPTS.types.includes(t.type);
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

// What to say when nothing is shown, by cause: the search alone, the search inside a chosen kind, or a kind with nothing in it.
export function noMatch({ query = "", kind = "" } = {}) {
  const chosen = kind && kind !== "all";
  const name = kind === RECENT ? "Recently used" : kindName(kind);
  if (String(query).trim()) return chosen ? `Nothing in ${name} matches that search. Try another word, or choose All templates.` : "No template matches that search. Try another word.";
  return chosen ? `There is nothing in ${name} yet. Choose All templates.` : "There are no templates to show.";
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

// Whether a template can sit beside the section above, section `after`, which it then shares a row with as the second half:
// { ok: true, with: that section's title } or { ok: false, message }. Only a section on a row of its own can have a partner, and the
// last section can.
export function besideState(sections, after, template) {
  if (!template) return { ok: false, message: MESSAGES.unknown };
  if (!template.fit.includes("half")) return { ok: false, message: MESSAGES.needsFull };
  if (after === null || after === undefined) return { ok: false, message: MESSAGES.noneYet };
  const row = rows(sections).find((r) => r.some((x) => x.id === after));
  if (!row) return { ok: false, message: MESSAGES.gone };
  if (row.length !== 1) return { ok: false, message: MESSAGES.hasPartner };
  return { ok: true, with: row[0].title };
}

// The requests to make to add template `id` below section `after` (null: at the end), alone or beside that section as its second
// half. { ok: true, requests, words, partial } or { ok: false, message }. Beside is one request (`new` takes `beside`, and clark sets the pairing in the same step). A section added alone below a
// last section that carries a stale pairing flag needs a second request to clear it, because `new` does not clear it; `partial` is
// what the toast says if that second request fails. A template that is not available (not ready yet) is refused here, in words,
// before anything is sent.
export function plan(sections, id, after, beside = false) {
  const t = find(id);
  if (!t) return { ok: false, message: MESSAGES.unknown };
  if (!available(t)) return { ok: false, message: MESSAGES.later };
  const a = anchor(sections, after);
  if (!a.ok) return a;
  if (beside) {
    const b = besideState(sections, after, t);
    if (!b.ok) return b;
    return { ok: true, requests: [{ op: "new", values: { type: t.type, title: t.title }, after: a.id, beside: 1, place: "report" }],
             words: `${t.name} added, beside the section above.`, template: t };
  }
  const requests = [{ op: "new", values: { type: t.type, title: t.title }, after: a.id, place: "report" }];
  const all = rows(sections), tail = all.length ? all[all.length - 1] : null;
  const last = a.id === null ? (tail && tail[tail.length - 1]) : sections.find((s) => s.id === a.id);      // null is "at the end": below the final section
  const lone = last && all.some((r) => r.length === 1 && r[0].id === last.id);
  if (lone && last.beside) requests.push({ op: "update", id: last.id, changes: { beside: 0 }, place: "report" });   // a flag on the last section is ignored by the page; the new section after it would pair with it
  return { ok: true, requests, words: `${t.name} added.`, partial: MESSAGES.notAlone, template: t };
}
