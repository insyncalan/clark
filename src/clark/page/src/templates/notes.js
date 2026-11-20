// The typed notes (#96 G5: Callout, Quote, Contacts, Table): what a section carries, read the same way in the served View and in
// the published file (FR-11). A published file's section carries `content` (section_kinds/<type>.py published); the page clark
// serves carries the stored `body` (JSON text, the same fields). Both are read here, defensively: anything that is not the
// expected kind of value is left out, so a view only ever draws text. Pure: no DOM, no Preact.
import { safeHref } from "./safe.js";
import { richOf } from "./files.js";

export const TONES = ["info", "decision", "warning"];
export const TONE_WORDS = { info: "Information", decision: "Decision needed", warning: "Warning" };
// item 1272: the colour and icon names (the words the store keeps, section_kinds/callout.py COLOURS and ICONS) and what an older callout's tone drew.
export const COLOURS = { plain: "Plain", violet: "Violet", amber: "Amber", red: "Red", green: "Green", grey: "Grey" };
export const ICONS = { none: "No icon", info: "Information", question: "Question", warning: "Warning triangle", alert: "Alert", check: "Tick", clock: "Clock",
  cal: "Calendar", flag: "Flag", lock: "Lock", key: "Key", bulb: "Light bulb", star: "Star", bell: "Bell", megaphone: "Megaphone", doc: "Document",
  link: "Link", people: "People", money: "Money", chart: "Chart", shield: "Shield",
  flash: "Lightning", eye: "Eye", table: "Table", gear: "Gear", sparkle: "Sparkle", fork: "Two ways" };
export const TONE_LOOK = { info: ["violet", "info"], decision: ["amber", "question"], warning: ["red", "warning"] };
export const LIMITS = { category: 30, title: 120, para: 600, paras: 6, quote: 600, name: 120, people: 8, cols: 8, rows: 30, cell: 200, caption: 200 };

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

// A field the callout does not store stays undefined (so a save does not rewrite an older callout); calloutLook gives what the reader draws.
// Row 1272: the callout's own look (no tile, no heading) for any section; null for other types, so Section.jsx needs no branch on the type.
export function calloutShape(section) {
  return section && section.type === "callout" ? tidyCallout(source(section)) : null;
}

export function tidyCallout(v, clean) {
  const o = v || {};
  const tone = TONES.includes(o.tone) ? o.tone : "info";
  const out = { tone, title: text(o.title), paras: list(o.paras).map(text).filter(Boolean).slice(0, LIMITS.paras), html: richOf(o.html, clean) };
  if (typeof o.category === "string") out.category = text(o.category).slice(0, LIMITS.category);
  if (Object.hasOwn(COLOURS, o.colour)) out.colour = o.colour;
  if (Object.hasOwn(ICONS, o.icon)) out.icon = o.icon;
  if (typeof o.tile === "boolean") out.tile = o.tile;
  if (typeof o.heading === "boolean") out.heading = o.heading;
  return out;
}
// What is drawn: the word, the colour, the icon, and whether the tile and the heading show. An older callout (no category, colour or icon stored) draws its
// tone's word, colour and icon. A colour with no word and no icon draws its own shape (`shape`), so a colour is never alone.
export function calloutLook(c) {
  const older = c.category === undefined && c.colour === undefined && c.icon === undefined;
  const [colour, icon] = TONE_LOOK[c.tone];
  const k = { word: older ? TONE_WORDS[c.tone] : c.category || "", colour: c.colour || colour, icon: c.icon || icon, tile: c.tile !== false, heading: c.heading !== false };
  k.shape = k.colour !== "plain" && !k.word && k.icon === "none" ? "sh" + k.colour[0].toUpperCase() + k.colour.slice(1) : "";
  return k;
}
export const calloutEmpty = (c) => !c.title && c.paras.length === 0 && !c.html;

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
export const mailHref = (email) => (email && !/[\s<>"?%]/.test(email) ? safeHref(`mailto:${email}`) : "");

export function tidyTable(v) {
  const o = v || {};
  const cols = list(o.cols).slice(0, LIMITS.cols).map(text);
  const rows = list(o.rows).slice(0, LIMITS.rows).filter(Array.isArray).map((r) => cols.map((_, i) => text(r[i])));
  return { cols, rows: rows.filter((r) => r.some(Boolean)), caption: text(o.caption) };
}
export const tableEmpty = (t) => !t.cols.some(Boolean) && t.rows.length === 0;

// item 1251 hook (the prompt words are written under item 1251): the grey placeholders a just-added Callout shows. Placeholders only: nothing here is ever stored, so none of it can
// reach the published page. item 1251 changes these two strings and nothing else.
export const PROMPTS = { title: "Add a title: what the reader must see", words: "Click to write." };

// item 1272 decision 4, the shared part: whether a section shows its tile and its heading, for every type. A callout keeps the two switches in its own content (slice 2);
// any other type reads the same two flags from the section itself (`tile`, `heading`: false turns it off) once the store carries them. Nothing else in the page
// asks the section type, so the store step only has to fill these two fields.
// item 1272: the tag Edit puts beside a section whose tile or heading View does not draw, as the ticket's mock-up words it. The one place these words live.
export const NOT_SHOWN = { tile: "Tile not shown in View", heading: "Heading not shown in View", both: "Heading and tile not shown in View" };
export function notShownTag(shows) {
  return shows.tile && shows.heading ? "" : !shows.tile && !shows.heading ? NOT_SHOWN.both : shows.tile ? NOT_SHOWN.heading : NOT_SHOWN.tile;
}

export function sectionShows(section) {
  const c = section.type === "callout" ? tidyCallout(source(section)) : section;
  return { tile: c.tile !== false, heading: c.heading !== false };
}
