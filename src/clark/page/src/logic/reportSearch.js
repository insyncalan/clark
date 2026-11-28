// Row 1543 AP8 to AP12: the search of a published report. A pure index over what the file holds and nothing else: the file already
// leaves out everything for the team only (publish.py), and this reads only `data` and its report sections, so a word that is not in the
// file cannot be found. Work items by ID, title, owner and client message; milestones; use cases; and the text each section's view draws (the whitelist DRAWN below).
import { richWords } from "./richWords.js";
import { docItems, oneDoc, linkCard, typeWords } from "../templates/files.js";
import { linesOf as keyDateLines } from "../templates/keydates.js";

const MAX_RESULTS = 50;

const plain = (v) => richWords(v).replace(/\s+/g, " ").trim();
const join = (...parts) => parts.map(plain).filter(Boolean).join(" ");

// Row 1543, the whitelist: for each section type, the fields of the published section that its view DRAWS as text (src/clark/page/src/templates/*,
// components/Tracker.jsx). Only these are indexed, so a field the view does not draw as text (an image's alt, a file's folder path, a tone or colour name,
// an alignment, an order, a column id, a date in ISO form) can never be found. A path is dotted, read from the published section; a list on the way is read
// item by item. The keys are exact (no case folding, no trimming). A type that is not here indexes its title only (fail closed), and so do the types
// whose words are the report's own rows (glance, use cases, milestones, documents, the Gantt sections, the work item lists' rows).
export const DRAWN = Object.freeze({
  text: ["body"],
  textimage: ["content.words", "content.html", "content.caption", "content.heading"],       // the picture's `alt` is the img's alt, not drawn text
  imagecap: ["content.caption"],
  gallery: ["content.pictures.caption"],
  headline: ["content.words", "content.label"],
  figures4: ["figures.label", "figures.value", "figures.detail"],
  figures3: ["figures.label", "figures.value", "figures.detail"],
  table: ["content.caption", "content.cols", "content.rows"],
  doclinks: [],                                                                              // read as the view reads it (docItems), see EXTRA
  linkcard: [],
  onedoc: [],
  raid3: ["cards.text"],
  raid4: ["cards.text"],
  workitems: ["caption"],
  callout: ["content.title", "content.paras", "content.html"],                               // and the category word, see EXTRA
  quote: ["content.quotes.quote", "content.quotes.by", "content.quotes.role"],              // `heading` is a switch, not words
  contacts: ["content.people.name", "content.people.role", "content.people.email", "content.people.phone"],
  checklist: ["items.text"],                                                                 // a linked line is drawn from its work item, which is indexed as itself
  keydates: [],                                                                              // read as the view reads it (keydates.js linesOf): the label and the state word; the ISO day stays out, see EXTRA
  reportheadline: ["content.headline", "content.sentence"],                                  // and the health word while the pill shows, see EXTRA
  glancetemplate: ["content.bespoke.label", "content.bespoke.figure", "content.bespoke.tag", "content.bespoke.note"],
  tracker: ["groups.name", "groups.lines.no", "groups.lines.text", "overall.note"],
});

const TONE_WORDS = { info: "Information", decision: "Decision needed", warning: "Warning" };       // templates/notes.js: an older callout's word
const HEALTH_WORDS = { on_track: "On track", at_risk: "At risk", off_track: "Off track" };            // templates/ReportHeadline.jsx HEALTHS
const own = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
const body = (s) => (s && s.content && typeof s.content === "object" && !Array.isArray(s.content) ? s.content : {});

// The words the view draws that are not one plain field. Each is the view's own reading (templates/files.js, notes.js, ReportHeadline.jsx).
const EXTRA = Object.freeze({
  callout: (s) => { const c = body(s), older = c.category === undefined && c.colour === undefined && c.icon === undefined; return [older ? TONE_WORDS[c.tone] || TONE_WORDS.info : c.category]; },
  reportheadline: (s) => { const c = body(s); return c.pill === false ? [] : [own(HEALTH_WORDS, c.health) ? HEALTH_WORDS[c.health] : "Not set"]; },        // the pill is the eye: off draws no health word
  doclinks: (s) => docItems(s).flatMap((i) => [i.label, i.kind === "file" ? i.name : i.shown, typeWords(i)]),      // DocLinks.jsx: the name, then "<Type> · <size or site>"; the path and the raw kind are never drawn
  keydates: (s, d, today) => keyDateLines(s, d, { fromFile: true, today }).flatMap((l) => [l.label, l.words]),           // keydates.js: the label and, for a milestone, its state word ('' for a typed day); never the day itself
  onedoc: (s) => { const d = oneDoc(s); return d ? [d.label, d.file.name, ...d.text, d.html] : []; },
  linkcard: (s) => { const c = linkCard(s); return c ? [c.site || c.link.shown, c.title || c.link.shown, ...c.text, c.html] : []; },
});

/** Every text at `path` in `v`: a list on the way is read item by item, the end may be one text or a list of texts (a table's rows are lists of lists). */
function textsAt(v, path, i = 0, out = []) {
  if (Array.isArray(v)) { v.forEach((x) => textsAt(x, path, i, out)); return out; }
  if (i === path.length) { if (typeof v === "string") out.push(v); return out; }
  if (v && typeof v === "object" && own(v, path[i])) textsAt(v[path[i]], path, i + 1, out);
  return out;
}

// A callout or a quote can draw without its heading (the switch, `content.heading`: notes.js sectionShows); then its title is not drawn and is not searched.
const headingShown = (s) => !((s.type === "callout" || s.type === "quote") && body(s).heading === false);

/** Every word a section's view draws as text: its title (while its heading shows) and the whitelisted fields of its type (DRAWN), nothing else. `data` and `today` are what a keydates line reads. */
export function sectionText(section, data, today) {
  const s = section || {};
  const known = typeof s.type === "string" && own(DRAWN, s.type);
  const out = [headingShown(s) ? plain(s.title) : ""];
  if (known) {
    for (const p of DRAWN[s.type]) for (const t of textsAt(s, p.split("."))) out.push(plain(t));
    if (own(EXTRA, s.type)) for (const t of EXTRA[s.type](s, data, today)) if (typeof t === "string") out.push(plain(t));
  }
  return out.filter(Boolean).join(" ");
}

/** The sections of an added page: `sections` is a list, or the JSON text of one (a published file's page, stores/report.js filePages). Anything else, or text that does not parse to a list, has none; a list's entries that are not objects are skipped. */
function pageSections(page) {
  let list = page && page.sections;
  if (typeof list === "string") { try { list = JSON.parse(list); } catch { return []; } }
  return Array.isArray(list) ? list.filter((s) => s && typeof s === "object") : [];
}

/** The entries of a report's data: {id, kind, view, title, text}. `kind` is the name of the page it is on. */
export function buildIndex(data, today) {
  const d = data || {}, out = [];
  const add = (id, kind, view, title, text, titleDrawn = true) => { const t = plain(title); if (id) out.push({ id: String(id), kind, view, title: t || String(id), text: join(id, titleDrawn ? t : "", text).toLowerCase() }); };      // a section's title is part of its sectionText (only while its heading shows), so a section passes titleDrawn false
  for (const r of d.actions || []) add(r.id, "Work items", "work", r.description, join(r.owner, r.client_message));
  for (const r of d.raid || []) add(r.id, "Work items", "work", r.description, join(r.owner, r.client_message));
  for (const r of d.decisions || []) add(r.id, "Work items", "work", r.decision, join(r.made_by, r.client_message));
  for (const m of d.milestones || []) add(m.id, "Milestones", "milestones", m.name, join(m.description, m.owner, m.client_message));
  for (const u of d.use_cases || []) add(u.id, "Use cases", "usecases", join(u.ref, u.title), join(u.headline, u.standing, u.owner));
  for (const s of d.report_sections || []) add(s.id, "Dashboard", "dashboard", s.title, sectionText(s, d, today), false);
  for (const p of d.added_pages || []) for (const s of pageSections(p)) add(s.id, plain(p.name) || "Page", "page:" + p.id, s.title, sectionText(s, d, today), false);      // an added page, where the page draws it (`added_pages`, stores/report.js:19,20,94). A published file's page reaches it with `sections` as JSON text (filePages, stores/report.js), the editor's as a list: both are read
  return out;
}

/** The entries whose text holds every word typed (case does not matter); title matches first, then the order of the report. No words, no results. */
export function searchReport(index, q) {
  const words = String(q == null ? "" : q).toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const hits = (index || []).filter((e) => words.every((w) => e.text.includes(w)));
  const inTitle = (e) => words.every((w) => e.title.toLowerCase().includes(w));
  return [...hits.filter(inTitle), ...hits.filter((e) => !inTitle(e))].slice(0, MAX_RESULTS);
}

// Row 1543 AP11 (part 2): the keys of the search, as pure rules over a key event's fields so the box and the tests share them.

/** The result Up (dir -1) or Down (dir 1) reaches from `at` (-1: none chosen) among `n` results; the ends wrap (as the editor's palette); -1 when there are none. */
export function stepAt(n, at, dir) {
  if (!n) return -1;
  if (at < 0) return dir > 0 ? 0 : n - 1;
  return (at + dir + n) % n;
}

/** The chosen result among `n` for the words `q`: the first when there is one, the pick's own only while the words are the ones it was made for; -1 when there are none. */
export const chosenAt = (pick, q, n) => (n ? (pick.q === q ? Math.min(pick.at, n - 1) : 0) : -1);

/** The pick after the words change: none (the words go back to an earlier value and the old pick must not come back with them). */
export const pickOnType = (pick) => ({ q: "", at: 0 });

/** Ctrl or Cmd + K, nothing else held, and not while an input method is composing (as edit/Palette.jsx). A plain k, typed anywhere, is not it. */
export const isShortcut = (e) => String(e.key || "").toLowerCase() === "k" && !!(e.metaKey || e.ctrlKey) && !e.altKey && !e.shiftKey && !e.isComposing;

/** What a key does in the open box: {do: "move", at} | {do: "choose", at} | null (not ours). `at` is the chosen result (-1 none); Esc is the dialog's own cancel. */
export function boxKey(e, n, at) {
  if (e.isComposing) return null;
  if (e.key === "ArrowDown" || e.key === "ArrowUp") return e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || !n ? null : { do: "move", at: stepAt(n, at, e.key === "ArrowDown" ? 1 : -1) };
  if (e.key === "Enter") return at >= 0 && at < n ? { do: "choose", at } : null;
  return null;
}
