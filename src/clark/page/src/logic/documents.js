// Supporting documents (#74): what the page shows of a document link, in Edit, in View and in a published file. Pure: no DOM, no
// Preact, so a test can run it alone. clark's link rule (clark/doclinks.py) decides what is saved, and the publish build checks every
// link again; this file only refuses to draw an address that is not http, https or mailto with nothing hidden in it, so a row
// written around clark is never drawn as a link.
import { dateWords } from "../templates/safe.js";

// The kinds a document may be: the same list, in the same order, as clark/doclinks.py KINDS (a test reads both).
export const KINDS = ["Minutes", "Actions list", "Report", "Slides", "Plan", "Other"];

const LINK = /^(?:https?:\/\/|mailto:)[^\u0000- \u007f-\u009f"<>\\]+$/i;

// The address to put in a link, or "" for one the page will not draw.
export function docHref(url) {
  return typeof url === "string" && url.length <= 2000 && LINK.test(url) ? url : "";
}

// Whether a link is an email address (it opens the mail program, not a new tab).
export const isMail = (url) => /^mailto:/i.test(String(url || ""));

// The site name a link goes to, as the person reads it beside the title: example.com, or the part after the @ of an email link.
export function siteOf(url) {
  const href = docHref(url);
  if (!href) return "";
  if (isMail(href)) {
    const at = href.lastIndexOf("@");
    return at >= 0 ? href.slice(at + 1).toLowerCase() : "";
  }
  const rest = href.replace(/^https?:\/\//i, "");
  return rest.split(/[/?#]/)[0].split(":")[0].toLowerCase().replace(/\.$/, "");
}

// What is said under a document's title: its date (DD-MM-YYYY) and the site name, each only when there is one.
export function factsOf(doc) {
  return [dateWords(doc && doc.date), siteOf(doc && doc.url)].filter(Boolean).join(" · ");
}

function hiddenSet(d) {
  return new Set(((d && d.report_hidden) || []).map((h) => (h && h.item_id) || h));
}

// The documents a reader sees, in order. A published file carries only those already (the publish build chose them); the page
// clark serves leaves out an archived one, one hidden with the eye, and one whose link it will not draw.
export function visibleDocs(d, file = false) {
  const list = Array.isArray(d && d.documents) ? d.documents : [];
  if (file) return list.filter((doc) => doc && docHref(doc.url));
  const hidden = hiddenSet(d);
  return list.filter((doc) => doc && !doc.archived && !hidden.has(doc.id) && docHref(doc.url));
}

// The documents left out with the eye (not archived), for "Add back a document".
export function hiddenDocs(d) {
  const list = Array.isArray(d && d.documents) ? d.documents : [];
  const hidden = hiddenSet(d);
  return list.filter((doc) => doc && !doc.archived && hidden.has(doc.id));
}

// The fields of a form that differ from the saved document: what an edit sends ({} when nothing changed). A date is "" or YYYY-MM-DD.
export function changedFields(doc, form) {
  const out = {};
  for (const k of ["title", "kind", "url", "date"]) {
    const was = (doc && doc[k]) || "", now = (form[k] || "").trim();
    if (now !== was) out[k] = now;
  }
  return out;
}
