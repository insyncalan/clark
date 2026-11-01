// The Files and links templates' content, as their view parts draw it (#96: Documents and links, One document, Link preview). Pure:
// no DOM, no Preact. The same shape whether it comes from a published file (the fields publish picked, `section.content`) or from the
// page clark serves (the stored `body`), so the served View and the file decide alike what is empty (FR-11). Every link goes through
// safe.js (safeHref for a link, fileHref for a file: a relative "Report files/..." address is allowed only for a file entry).
// src/clark/section_kinds/doclinks.py, onedoc.py and linkcard.py are the rules a save meets; this only reads.
import { safeHref, fileHref, FILES_FOLDER } from "./safe.js";

// The section's content as an object, or null.
export function contentOf(section) {
  if (!section) return null;
  if (section.content && typeof section.content === "object" && !Array.isArray(section.content)) return section.content;
  if (typeof section.body !== "string" || !section.body) return null;
  try {
    const v = JSON.parse(section.body);
    return v && typeof v === "object" && !Array.isArray(v) ? v : null;
  } catch (e) { return null; }
}

const words = (v) => (typeof v === "string" ? v.trim() : "");
const lines = (v) => (Array.isArray(v) ? v.map(words).filter(Boolean) : []);

// A file entry as it is drawn: { name, href, bytes } (bytes null when unknown), or null when it is not one the folder can hold.
export function fileOf(f) {
  if (!f || typeof f !== "object" || typeof f.name !== "string" || f.rel !== `${FILES_FOLDER}/${f.name}`) return null;
  const href = fileHref(f.rel);
  if (!href) return null;
  return { name: f.name, href, bytes: Number.isSafeInteger(f.bytes) && f.bytes >= 0 ? f.bytes : null };
}

// A link as it is drawn: { href, shown } (shown: the site's name for https, the address for mailto), or null.
export function linkOf(href) {
  const safe = safeHref(href);
  if (!safe || safe.startsWith("#")) return null;
  return { href: safe, shown: siteOf(safe) };
}

// The site part of an https link (no "www."), or the address of a mailto link.
export function siteOf(href) {
  const v = String(href || "");
  if (/^mailto:/i.test(v)) return v.slice(7).split("?")[0];
  const host = v.replace(/^https:\/\//i, "").split(/[/?#]/)[0].replace(/:\d+$/, "");
  return host.replace(/^www\./i, "");
}

// Documents and links: the entries that can be drawn, in their order: { kind: "file", name, href, bytes, label } or
// { kind: "link", href, shown, label }.
export function docItems(section) {
  const c = contentOf(section);
  const out = [];
  for (const i of (c && Array.isArray(c.items) ? c.items : [])) {
    if (!i || typeof i !== "object") continue;
    if (i.kind === "file") {
      const f = fileOf(i);
      if (f) out.push({ kind: "file", ...f, label: words(i.label) });
    } else if (i.kind === "link") {
      const l = linkOf(i.href);
      if (l) out.push({ kind: "link", ...l, label: words(i.label) });
    }
  }
  return out;
}

// One document: { file, label, text } when there is a file to draw, else null (words alone stay out, as in the file).
export function oneDoc(section) {
  const c = contentOf(section);
  const file = c ? fileOf(c.file) : null;
  return file ? { file, label: words(c.label), text: lines(c.text) } : null;
}

// Link preview: { link, title, site, text } when there is a link to draw, else null.
export function linkCard(section) {
  const c = contentOf(section);
  const link = c ? linkOf(c.href) : null;
  return link ? { link, title: words(c.title), site: words(c.site), text: lines(c.text) } : null;
}

// A file's size as a person reads it: "12 KB", "3.4 MB". "" when unknown.
export function sizeWords(bytes) {
  if (!Number.isSafeInteger(bytes) || bytes < 0) return "";
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.ceil(bytes / 1024))} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1).replace(/\.0$/, "")} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1).replace(/\.0$/, "")} GB`;
}

// What kind of file it is, by its ending: PDF, Word, Excel, PowerPoint, or the ending in capitals ("File" without one).
const KINDS = { pdf: "PDF", doc: "Word", docx: "Word", xls: "Excel", xlsx: "Excel", csv: "Excel", ppt: "PowerPoint", pptx: "PowerPoint" };
export function kindWords(name) {
  const m = /\.([A-Za-z0-9]{1,8})$/.exec(String(name || ""));
  if (!m) return "File";
  const ext = m[1].toLowerCase();
  return KINDS[ext] || ext.toUpperCase();
}


// Edit's check of a typed link before it is sent, in the same words as the store's (section_kinds/doclinks.py BAD_LINK): "" when
// it can be saved.
export const BAD_LINK = "That link can't be used. It must start with https:// or mailto: and have no spaces. Paste the whole address and try again.";
export function linkProblem(text) {
  const v = String(text || "");
  if (!v || v.length > 2000 || /[\u0000- \u007f\\]/.test(v)) return BAD_LINK;
  if (/^https:\/\//i.test(v)) {
    const host = v.slice(8).split(/[/?#]/)[0];
    return !host || host.includes("@") || /^[.:]/.test(host) ? BAD_LINK : "";
  }
  return /^mailto:./i.test(v) ? "" : BAD_LINK;
}
