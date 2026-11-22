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
import { TEMPLATE_TYPES, PENDING_TYPES } from "../templates/types.js";
import { WORDS } from "./fullImageWords.js";
import { defaults, bodyOf } from "../templates/workItemsList.js";
import { glanceShowsHealth } from "../templates/glanceBody.js";
import { PLAN_SUMMARY_BODY } from "./planSummaryBody.js";

// What the store takes in a new section (changes.py NEW_SECTION_TYPES: text
// and every type in the template registry (#96)). A template whose type is not here is listed but not offered.
export const ACCEPTS = { types: ["text", ...TEMPLATE_TYPES, "current", "glance", "usecases", "milestones", "raid", "actions", "decisions", "docs", ...PENDING_TYPES] };      // row 926: the Gantt section (no body, no registry module) is taken by the store at layout 19; row 1068: the Gantt table section at layout 21

export const KINDS = [
  { id: "info", name: "Project information" },      // item 1272 (owner 16-11): the group the Callout moves to; the headline and glance cards follow with their rows
  { id: "text", name: "Text and pictures" },
  { id: "figures", name: "Figures" },
  { id: "work", name: "Work items" },
  { id: "files", name: "Files and links" },
  { id: "dates", name: "People and dates" },
  { id: "notes", name: "Notes" },
];
export const RECENT = "recent";
export const RECENT_MAX = 3;

// Row 1068: the card name and the starting title of the Gantt table template (type gantttable), the owner's word. The Notes grid
// template (type table) is also called Table; the ONE place to change this one's word (Help's row carries the same word).
export const GANTT_TABLE_NAME = "Table";

// Words and parts are the prototype's (system/prototype/views.js, the same list Help's table draws from). `fit` puts the better width first.
export const TEMPLATES = [
  { id: "text", name: "Text", kind: "text", fit: ["full", "half"], type: "text", title: "New section", body: "", ready: true,
    description: "Words under a heading, written in clark’s one editor.", holds: ["Heading", "Text"] },
  { id: "text-image", name: "Text and Image Side by Side", kind: "text", fit: ["full", "half"], type: "textimage", title: "Text and Image Side by Side", body: "", start: '{"v":2}', ready: true,
    description: "A story with a picture: a site visit, a design, a screenshot of the new system.", holds: ["Heading", "Text", "Image", "Caption"] },
  { id: "figures-4", name: "Key figures, four", kind: "figures", fit: ["full", "half"], type: "figures4", title: "Key figures", body: "", ready: true,
    description: "Three or four numbers with labels and a change since last week.", holds: ["Heading", "Figure · live", "Figure · live", "Figure · typed", "Figure · typed", "Caption"] },
  { id: "figures-3", name: "Key figures, three", kind: "figures", fit: ["full", "half"], type: "figures3", title: "Key figures", body: "", ready: true,
    description: "Three numbers with labels, in wider cards, so a short note fits under the change.", holds: ["Heading", "Figure · live", "Figure · live", "Figure · typed"] },
  // Row 1264 slice 9: the glance template (type glancetemplate), its own card (the built-in At a glance card is gone, row 1411). The words are
  // the ruled ones (words file group 1): the name, the description and the holds list, quoted. The new section starts with the card's name as its title.
  { id: "glance-template", name: "Project at a glance", kind: "figures", fit: ["full", "half"], type: "glancetemplate", title: "Project at a glance", body: "", ready: true,
    description: "Three counts, an optional project health and tiles of your own.",
    holds: ["Decisions needed", "High risks and issues", "Overdue actions", "optional Project health", "your own tiles"] },
  { id: "gallery", name: "Image gallery", kind: "text", fit: ["full"], type: "gallery", title: "Image gallery", body: "", ready: true,
    description: "Pictures in a grid, each with a caption.", holds: ["Heading", "Image", "Caption", "Image", "Caption", "Image"] },
  { id: "table", name: "Table", kind: "notes", fit: ["full"], type: "table", title: "Table", body: "", ready: true,
    description: "Anything with rows: a budget line, a cut-over plan, a training schedule.", holds: ["Heading", "Table"] },
  { id: "raid-3", name: "RAID cards, three", kind: "work", fit: ["full"], type: "raid3", title: "Risks and issues", body: "", ready: true,
    description: "The risks, actions, issues or decisions you want the reader to see, as cards.", holds: ["Heading", "RAID card ×3", "Text source", "Text"] },
  { id: "raid-4", name: "RAID cards, four", kind: "work", fit: ["full"], type: "raid4", title: "Risks and issues", body: "", ready: true,
    description: "Four shorter cards: good for “this week’s actions” or “decisions needed”.", holds: ["Heading", "RAID card ×4"] },
  { id: "work-items", name: "Work items list", kind: "work", fit: ["full", "half"], type: "workitems", title: "Work items", body: "", start: bodyOf(defaults()), ready: true,
    description: "Live rows from Work items, chosen by a filter: open actions due soon, red risks, decisions needed.", holds: ["Heading", "Filter (set in Edit)", "Work item list · live", "Caption (optional)"] },
  { id: "docs-links", name: "Documents and links", kind: "files", fit: ["full", "half"], type: "doclinks", title: "Documents and links", body: "", ready: true,
    description: "The papers that go with this week’s report.", holds: ["Heading", "File (one or more)", "Link list"] },
  // Row 1261: the Report headline card (type reportheadline). Name: "Report headline" (the owner's rename 16-11, the ticket title; ruling 20-11). Description:
  // the ticket's own title words (Row 1261: "health pill, headline and supporting sentence at the top of the report"); `holds` are the Edit part's fields.
  { id: "report-headline", name: "Report headline", kind: "info", fit: ["full", "half"], type: "reportheadline", title: "Headline", body: "", ready: true,
    description: "A health pill, a headline and a supporting sentence at the top of the report.", holds: ["Health pill · optional", "Headline", "Supporting sentence"] },
  { id: "callout", name: "Callout", kind: "info", fit: ["half", "full"], type: "callout", title: "Callout", body: "", ready: true,
    description: "One thing the reader must see.", more: "Type a category of your own or pick one, then a colour and an icon. Or leave them out.",
    holds: ["Heading", "Callout · decision", "Callout · category, colour, icon", "Callout · tile and heading on or off"] },      // item 1272 G: `more` is the extra line under the description
  { id: "image-caption", name: "Image with caption", kind: "text", fit: ["half", "full"], type: "imagecap", title: "Image with caption", body: "", ready: true,
    description: "One picture with its caption.", holds: ["Heading", "Image", "Caption"] },
  // Row 1223: the same store type as Image with caption (imagecap), started with a body of version 2 (`start`: changes.py takes exactly this body for a new
  // imagecap section; section_kinds/imagecap.py START). Full width only. Its name is unruled (logic/fullImageWords.js).
  { id: "full-image", name: WORDS.name, kind: "text", fit: ["full"], type: "imagecap", title: WORDS.name, body: "", start: '{"v":2}', ready: true,
    description: WORDS.description, holds: WORDS.holds },
  { id: "quote", name: "Quote", kind: "text", fit: ["half", "full"], type: "quote", title: "Quote", body: "", ready: true,
    description: "A voice from the business.", holds: ["Heading", "Quote", "Said by", "Role"] },
  { id: "contacts", name: "Contacts", kind: "dates", fit: ["half", "full"], type: "contacts", title: "Contacts", body: "", ready: true,
    description: "Who to ask.", holds: ["Heading", "Person", "Person", "Person"] },
  { id: "checklist", name: "Checklist", kind: "dates", fit: ["half", "full"], type: "checklist", title: "Checklist", body: "", ready: true,
    description: "Next steps or readiness, ticked off.", holds: ["Heading", "Checklist · linked to work items"] },
  { id: "key-dates", name: "Key dates", kind: "dates", fit: ["half", "full"], type: "keydates", title: "Key dates", body: "", ready: true,
    description: "What’s coming, from the milestones.", holds: ["Heading", "Date (from milestones)"] },
  { id: "link-preview", name: "Link preview", kind: "files", fit: ["full"], type: "linkcard", title: "Link preview", body: "", ready: true,
    description: "A web page shown as a card you write: a dashboard, a news item, a recording.", holds: ["Heading", "Link", "Card text"] },
  { id: "current-state", name: "Header and Text", kind: "text", fit: ["full", "half"], type: "text", title: "Current state", body: "", ready: true,
    description: "The state of the project in a few lines, to sit beside another section.", holds: ["Heading", "Text"] },
  { id: "plan-summary", name: "Plan summary", kind: "text", fit: ["full", "half"], type: "text", title: "Plan summary", ready: true,
    body: PLAN_SUMMARY_BODY,
    description: "Where the plan stands, in clark’s one editor: headings, lists and links. Starts with two headings to fill in.",
    holds: ["Heading", "Rich text: headings, lists, quote, links"] },
  { id: "gantt", name: "Gantt", kind: "dates", fit: ["full"], type: "gantt", title: "Gantt", body: "", ready: true,
    description: "The plan as bars on a timeline, from your Gantt lines. Only lines put in the client view show.", holds: ["Heading", "The Gantt chart"] },
  { id: "gantt-table", name: GANTT_TABLE_NAME, kind: "dates", fit: ["full", "half"], type: "gantttable", title: GANTT_TABLE_NAME, body: "", ready: true,
    description: "The plan as a table, from your Gantt lines. Only lines put in the client view show.", holds: ["Heading", "The plan table"] },
  { id: "one-doc", name: "One document", kind: "files", fit: ["half", "full"], type: "onedoc", title: "Document", body: "", ready: true,
    description: "A single file to read.", holds: ["Heading", "File", "Text"] },
];

// The second slice (#96): every other template type, built (its section_kinds module and page part say READY) but not in the
// box yet (find, list and plan read TEMPLATES only). No words here: their names, descriptions and parts wait for their words and
// Help rows, and a template the box does not offer is not named on the page. The lead moves an entry into TEMPLATES, with its
// words and its Help row.
export const LATER = [
  { id: "headline", type: "headline", ready: true },
];

// The built-in sections (row 906): a deleted one is added again from the box, one of each, with the title and settings it starts
// with (changes.py BUILT_IN_TYPES). Listed only while the report has no section of that type (`list` and `counts` take `sections`).
// Row 1407: Risks and issues, Open actions and Decisions are not in this list; the Work items list (its views in filterLine.js) covers them.
// Row 1411: the built-in At a glance card is gone too (the glance template is its own card).
// Item 1191: Use case summary has its words, parts and width like any template; the section it makes is the built-in's own (type usecases),
// so the strip, the rows, the edit in place, View, Word, Excel and the published file are the built-in's. Full width only: a row is a grid of fixed columns.
const USECASES_CARD = { fit: ["full"], description: "The use cases, with a count for each status and one row for each: its headline, where it stands and the open next steps.",
                        holds: ["Heading", "Count for each status", "A row for each use case", "Where it stands", "Next steps"] };
// Item 1192: the Milestones card is a library card like the others; the section it makes is the built-in's own (type milestones, MsBlock),
// so the timeline or calendar, the list, the edit in place, View, Word, Excel and the published file are the built-in's. Full width only.
export const MILESTONES_CARD = { fit: ["full"], description: "The milestones on a timeline or a calendar, with the list beneath.",
                                 holds: ["Heading", "Timeline or Calendar · live", "Milestone list · live"] };
const builtIn = (type, title, kind, more = {}) => ({ id: `built-in-${type}`, name: title, kind, fit: ["full"], type, title, body: "", ready: true, description: "", holds: [], builtIn: true, ...more });
export const BUILT_INS = [
  builtIn("current", "Current state", "text"), builtIn("usecases", "Use case summary", "work", USECASES_CARD),
  builtIn("milestones", "Milestones", "dates", MILESTONES_CARD), builtIn("docs", "Supporting documents", "files"),      // row 1407: no Risks and issues, Open actions or Decisions card: the Work items list covers them
];
// Item 1188: the first default section is now the text section "Current state", which "Header and Text" also adds, so the older
// "current" built-in is not offered (a second card that makes the same heading); a report that has one keeps it.
const missing = (sections) => (sections ? BUILT_INS.filter((b) => b.type !== "current" && !sections.some((s) => s.type === b.type)) : []);

// Every template entry, in the box or not: one per template type, and Text.
export const CATALOGUE = [...TEMPLATES, ...LATER];

export const MESSAGES = {
  gone: "That section isn't in the report any more. Reload the page.",
  noneYet: "There is no section yet to sit beside.",
  hasPartner: "That section already shares its row. Place it on its own row.",
  needsFull: "This template needs the full width. Place it on its own row.",
  later: "Coming with a later release.",
  unknown: "That template isn't in the list.",
};

const FIT_WORDS = { full: "Full width", half: "Half width" };
export const fitList = (t) => t.fit.map((f) => FIT_WORDS[f]);     // one chip each on the box's cards (#783)
export const fitWords = (t) => fitList(t).join(" or ");

// The small sketch on each card of the Add a section box and the larger one in its preview (#783): the prototype's (views.js `sk`),
// [the grid's style, one style per part]. Shapes only, no words; tokens only, so dark mode follows.
const IMG = "background:color-mix(in srgb, var(--brand-blue) 30%, var(--surface))";
export const SKETCHES = {
  "text": ["grid-template-rows:repeat(3,1fr)", ["", "width:80%", "width:60%"]],
  "text-image": ["grid-template-columns:1.4fr 1fr", ["", IMG]],
  "figures-4": ["grid-template-columns:repeat(4,1fr)", ["", "", "", ""]],
  "figures-3": ["grid-template-columns:repeat(3,1fr)", ["", "", ""]],
  "gallery": ["grid-template-columns:repeat(3,1fr)", [IMG, IMG, IMG]],
  "table": ["grid-template-rows:repeat(4,1fr)", ["", "", "", ""]],
  "raid-3": ["grid-template-columns:repeat(3,1fr)", ["border-top:3px solid var(--status-red)", "border-top:3px solid var(--status-amber)", "border-top:3px solid var(--brand-blue)"]],
  "raid-4": ["grid-template-columns:repeat(4,1fr)", ["border-top:3px solid var(--status-red)", "border-top:3px solid var(--status-amber)", "border-top:3px solid var(--status-amber)", ""]],
  "work-items": ["grid-template-rows:repeat(4,1fr)", ["width:90%", "width:75%", "width:85%", "width:70%"]],
  "docs-links": ["grid-template-rows:repeat(3,1fr)", ["", "", ""]],
  "report-headline": ["grid-template-columns:1fr 3fr", ["border-radius:999px;background:var(--status-amber-tint)", ""]],
  "callout": ["", ["background:var(--status-amber-tint);border-left:3px solid var(--status-amber)"]],
  "image-caption": ["grid-template-rows:2fr 1fr", [IMG, "width:50%"]],
  "full-image": ["grid-template-rows:3fr 1fr", [IMG, "width:40%"]],
  "quote": ["grid-template-rows:2fr 1fr", ["background:var(--grey-100);border-radius:var(--radius)", "width:40%"]],      // item 1271: no cyan stripe; the quote on a soft panel, the person under it
  "contacts": ["grid-template-rows:repeat(3,1fr)", ["width:70%", "width:70%", "width:70%"]],
  "checklist": ["grid-template-rows:repeat(3,1fr)", ["width:80%", "width:60%", "width:70%"]],
  "key-dates": ["grid-template-rows:repeat(3,1fr)", ["width:90%", "width:90%", "width:90%"]],
  "link-preview": ["grid-template-columns:1fr 2fr", [IMG, ""]],
  "built-in-milestones": ["grid-template-rows:repeat(3,1fr)", ["width:60%", "width:50%;margin-left:25%", "width:40%;margin-left:55%"]],      // item 1192: bars on a timeline, as the Gantt card's
  "gantt": ["grid-template-rows:repeat(3,1fr)", ["width:60%", "width:50%;margin-left:25%", "width:40%;margin-left:55%"]],
  "gantt-table": ["grid-template-rows:repeat(4,1fr)", ["", "", "", ""]],
  "one-doc": ["grid-template-rows:1fr 1fr", ["", "width:70%"]],
  "current-state": ["grid-template-rows:repeat(3,1fr)", ["width:85%", "width:70%", "width:50%"]],
  "built-in-usecases": ["grid-template-rows:repeat(4,1fr)", ["width:35%", "width:90%", "width:75%", "width:85%"]],
  "plan-summary": ["grid-template-rows:repeat(4,1fr)", ["width:40%", "width:80%", "width:40%", "width:70%"]],
  "glance-template": ["grid-template-columns:repeat(3,1fr)", ["border-top:3px solid var(--status-red)", "border-top:3px solid var(--status-amber)", "border-top:3px solid var(--status-green)"]],      // row 1264: low tiles, a tone edge on each
  "built-in-glance": ["grid-template-columns:repeat(4,1fr)", ["", "border-top:3px solid var(--status-red)", "border-top:3px solid var(--status-amber)", ""]],      // kept: the Cards look is frozen (row 1411 removes only the card)
};

// Row 1272: the Classic Theme's own sketch for a template (look B for the Callout); Cards keeps SKETCHES. The shapes are drawn by themes/prototype-2.0/rules.css (.sk-callout-b).
export const CLASSIC_SKETCHES = { "callout": ["", ["grid-row:1 / 3;width:var(--space-4);height:var(--space-4);border-radius:50%", "width:40%", "width:80%"]] };

export const find = (id) => TEMPLATES.find((t) => t.id === id) || BUILT_INS.find((t) => t.id === id) || null;
export const available = (t) => !!t && t.ready === true && ACCEPTS.types.includes(t.type);
export const kindName = (id) => (KINDS.find((k) => k.id === id) || { name: "" }).name;

const words = (s) => String(s || "").toLowerCase().split(/\s+/).filter(Boolean);
const matches = (t, q) => {
  const hay = `${t.name} ${t.description} ${kindName(t.kind)} ${t.holds.join(" ")}`.toLowerCase();
  return words(q).every((w) => hay.includes(w));
};

// The templates for a search and a choice of kind ("" or "all": every kind; RECENT: the recently used ones, newest first).
export function list({ query = "", kind = "", recent = [], sections = null } = {}) {
  const found = [...TEMPLATES, ...missing(sections)].filter((t) => matches(t, query));
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
export function counts({ query = "", recent = [], sections = null } = {}) {
  const out = { all: list({ query, sections }).length, [RECENT]: list({ query, kind: RECENT, recent, sections }).length };
  for (const k of KINDS) out[k.id] = list({ query, kind: k.id, sections }).length;
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
// half. { ok: true, requests, words } or { ok: false, message }. Always one request: `new` takes `beside`, and clark sets the pairing
// (or clears a stale one on the last section) in the same step. Today a template other than the available ones is refused here, in words,
// before anything is sent.
// Row 1261: health shows once. A new Report headline starts with its pill off when At a glance already shows the health (a new project starts with the built-in one), on otherwise.
export const REPORT_HEADLINE_NO_PILL = '{"pill":false,"v":1}';      // section_kinds/reportheadline.py START
// Row 1251: Header and Text starts with the title Header in Classic (the page has <style id="theme">); Cards keeps Current state (its look is frozen).
const startTitle = (t) => (t.id === "current-state" && typeof document !== "undefined" && document.getElementById("theme") ? "Header" : t.title);
export function plan(sections, id, after, beside = false) {
  const t0 = find(id);
  const t = t0 && t0.type === "reportheadline" && glanceShowsHealth(sections) ? { ...t0, start: REPORT_HEADLINE_NO_PILL } : t0;
  if (!t) return { ok: false, message: MESSAGES.unknown };
  if (t.builtIn && !missing(sections).includes(t)) return { ok: false, message: MESSAGES.unknown };      // already in the report: not offered twice
  if (!available(t)) return { ok: false, message: MESSAGES.later };
  const a = anchor(sections, after);
  if (!a.ok) return a;
  if (beside) {
    const b = besideState(sections, after, t);
    if (!b.ok) return b;
    return { ok: true, requests: [{ op: "new", values: { type: t.type, title: startTitle(t), ...(t.start ? { body: t.start } : {}) }, after: a.id, beside: 1, place: "report" }],
             words: `${t.name} added, beside the section above.`, template: t };
  }
  // clark clears a stale pairing flag on the last section in the same step (#244), so this is one request and one Undo.
  return { ok: true, requests: [{ op: "new", values: { type: t.type, title: startTitle(t), ...(t.start ? { body: t.start } : {}) }, after: a.id, place: "report" }], words: `${t.name} added.`, template: t };
}
