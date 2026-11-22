// Row 1292 (S12): a Draft from ask clark, put into a report section. The Draft opens beside the panel, is edited freely, and nothing is in the
// report until "Add to the report" is pressed. Here: what the answer's draft is read as, what the menu offers, and the one change each choice makes.
// A Text section only (type "text"); a replace is one update of its body and an add is one new section with its body, so each is one step with one Undo.
import { cleanHtml, plainText } from "../logic/cleanHtml.js";

export const TITLE_MAX = 120;

const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const cut = (s) => (typeof s === "string" ? Array.from(s.trim()).slice(0, TITLE_MAX).join("") : "");

/** What a turn's `draft` field is read as: {html, title, sec} with the html cleaned as a section body is, or null when there is nothing to open.
 * Model text is never trusted: it goes through cleanHtml; if that refuses it, the words are kept as plain paragraphs. */
export function readDraft(d) {
  if (!d || typeof d !== "object" || typeof d.html !== "string" || !d.html.trim()) return null;
  let html;
  try { html = cleanHtml(d.html); } catch (e) { html = d.html.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean).map((p) => "<p>" + esc(p).replace(/\n/g, "<br>") + "</p>").join(""); }
  try { if (!plainText(html).trim()) return null; } catch (e) { return null; }      // too long for a field even as plain paragraphs: no draft, the answer is still shown
  const via = Array.isArray(d.via) ? d.via.filter((v) => typeof v === "string" && v).slice(0, 8) : [];
  return { html, title: cut(d.title), sec: typeof d.sec === "string" ? d.sec : "", ...(via.length ? { via } : {}) };
}

/** The words in a body, for "(38 words now)". */
export function wordsIn(html) {
  const t = plainText(typeof html === "string" ? html : "").trim();
  return t ? t.split(/\s+/).length : 0;
}

const textSections = (sections) => (Array.isArray(sections) ? sections : []).filter((s) => s && s.type === "text");

/** The menu: one "Replace" for each Text section (the one the draft is for first), then "Add as a new Text section" after that section (when the
 * draft is for one) and at the end. [{kind: "replace" | "add", id, after, label}]. */
export function choices(sections, pref, classic = false) {
  const text = textSections(sections);
  const out = [...text.filter((s) => s.id === pref), ...text.filter((s) => s.id !== pref)].map((s) => {
    const n = wordsIn(s.body);
    const title = s.title || "this section", tail = n || !classic ? `(${n} ${n === 1 ? "word" : "words"} now)` : "(empty)";      // row 1347: Classic says (empty) for a section with no text; Cards keeps (0 words now)
    return { kind: "replace", id: s.id, after: null, title, tail, label: `Replace the text of ${title} ${tail}` };
  });
  const at = text.find((s) => s.id === pref);
  if (at) out.push({ kind: "add", id: "", after: at.id, label: `Add as a new Text section after ${at.title || "this section"}` });
  out.push({ kind: "add", id: "", after: null, label: "Add as a new Text section at the end" });
  return out;
}

/** The one request, and what the toast says, for a choice and the draft as edited. null when the edited text is empty or the place is gone. */
export function request(choice, html, title, sections) {
  const body = cleanHtml(typeof html === "string" ? html : "");
  if (!choice || !plainText(body).trim()) return null;
  if (choice.kind === "replace") {
    const s = textSections(sections).find((x) => x.id === choice.id);
    if (!s) return null;
    return { req: { op: "update", id: s.id, changes: { body }, place: "report" }, done: `Draft put in ${s.title || "the section"}.` };
  }
  const values = { type: "text", body };
  const t = cut(title);
  if (t) values.title = t;
  return { req: { op: "new", values, after: choice.after || null, place: "report" }, done: "Draft added as a new section." };
}
