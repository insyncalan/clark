// Row 1543 AP8 to AP12: the search of a published report. A pure index over what the file holds and nothing else: the file already
// leaves out everything for the team only (publish.py), and this reads only `data` and its report sections, so a word that is not in the
// file cannot be found. Work items by ID, title, owner and client message; milestones; use cases; and the text of every section.
import { richWords } from "./richWords.js";

const SKIP = new Set(["id", "type", "beside", "sort_order", "style", "layout", "colour", "color", "url", "href", "src", "image", "icon"]);      // structure and addresses, never words a reader sees
const MAX_RESULTS = 50;

const plain = (v) => richWords(v).replace(/\s+/g, " ").trim();
const join = (...parts) => parts.map(plain).filter(Boolean).join(" ");

/** Every word a section holds: its title and each text in its fields, however deep (a table's cells, a list's lines), never a key, an id or a data: address. */
export function sectionText(section) {
  const out = [];
  const walk = (v, key) => {
    if (typeof v === "string") { if (!SKIP.has(key) && !/^data:/i.test(v)) out.push(plain(v)); }
    else if (Array.isArray(v)) v.forEach((x) => walk(x, key));
    else if (v && typeof v === "object") for (const k of Object.keys(v)) walk(v[k], k);
  };
  walk(section, "");
  return out.filter(Boolean).join(" ");
}

/** The entries of a report's data: {id, kind, view, title, text}. `kind` is the name of the page it is on. */
export function buildIndex(data) {
  const d = data || {}, out = [];
  const add = (id, kind, view, title, text) => { const t = plain(title); if (id) out.push({ id: String(id), kind, view, title: t || String(id), text: join(id, t, text).toLowerCase() }); };
  for (const r of d.actions || []) add(r.id, "Work items", "work", r.description, join(r.owner, r.client_message));
  for (const r of d.raid || []) add(r.id, "Work items", "work", r.description, join(r.owner, r.client_message));
  for (const r of d.decisions || []) add(r.id, "Work items", "work", r.decision, join(r.made_by, r.client_message));
  for (const m of d.milestones || []) add(m.id, "Milestones", "milestones", m.name, join(m.description, m.owner, m.client_message));
  for (const u of d.use_cases || []) add(u.id, "Use cases", "usecases", join(u.ref, u.title), join(u.headline, u.standing, u.owner));
  for (const s of d.report_sections || []) add(s.id, "Dashboard", "dashboard", s.title, sectionText(s));
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
