// The typed notes (#96 G5: Callout, Quote, Contacts, Table): what a section carries, read the same way in the served View and in
// the published file (FR-11). A published file's section carries `content` (section_kinds/<type>.py published); the page clark
// serves carries the stored `body` (JSON text, the same fields). Both are read here, defensively: anything that is not the
// expected kind of value is left out, so a view only ever draws text. Pure: no DOM, no Preact.
import { safeHref } from "./safe.js";

export const TONES = ["info", "decision", "warning"];
export const TONE_WORDS = { info: "Information", decision: "Decision needed", warning: "Warning" };
export const LIMITS = { title: 120, para: 600, paras: 6, quote: 600, name: 120, people: 8, cols: 8, rows: 30, cell: 200, caption: 200 };

const text = (v) => (typeof v === "string" ? v.trim() : "");
const list = (v) => (Array.isArray(v) ? v : []);

// The section's content as an object ({} when there is none or it can't be read).
export function source(section) {
  if (section && section.content && typeof section.content === "object" && !Array.isArray(section.content)) return section.content;
  if (section && typeof section.body === "string" && section.body) {
    try { const v = JSON.parse(section.body); if (v && typeof v === "object" && !Array.isArray(v)) return v; } catch (e) { /* not content */ }
  }
  return {};
}

export function tidyCallout(v) {
  const o = v || {};
  return { tone: TONES.includes(o.tone) ? o.tone : "info", title: text(o.title), paras: list(o.paras).map(text).filter(Boolean).slice(0, LIMITS.paras) };
}
export const calloutEmpty = (c) => !c.title && c.paras.length === 0;

export function tidyQuote(v) {
  const o = v || {};
  return { quote: text(o.quote), by: text(o.by), role: text(o.role) };
}
export const quoteEmpty = (q) => !q.quote;

export const PERSON_FIELDS = ["name", "role", "email", "phone"];
export function tidyContacts(v) {
  const people = list((v || {}).people).filter((p) => p && typeof p === "object").map((p) => Object.fromEntries(PERSON_FIELDS.map((f) => [f, text(p[f])])));
  return { people: people.filter((p) => p.name).slice(0, LIMITS.people) };
}
export const contactsEmpty = (c) => c.people.length === 0;
// A person's email as a link the file may carry (mailto: only, through the shared check), or "".
export const mailHref = (email) => (email && !/[\s<>"]/.test(email) ? safeHref(`mailto:${email}`) : "");

export function tidyTable(v) {
  const o = v || {};
  const cols = list(o.cols).slice(0, LIMITS.cols).map(text);
  const rows = list(o.rows).slice(0, LIMITS.rows).filter(Array.isArray).map((r) => cols.map((_, i) => text(r[i])));
  return { cols, rows: rows.filter((r) => r.some(Boolean)), caption: text(o.caption) };
}
export const tableEmpty = (t) => !t.cols.some(Boolean) && t.rows.length === 0;
