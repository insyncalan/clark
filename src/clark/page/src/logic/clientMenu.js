// The published file's menu (issue 713), as plain functions with no document, so a test can run them alone: what the data block
// may hold for it, read defensively. The page never trusts the shape of the block.
//
// The shapes the publish side writes into the data block (all optional; absent means the part is not drawn):
//   client_workbook:           { name: "file-name.xlsx", base64: "..." }   the client-visible workbook, made at publish time
//   client_workbook_too_large: true                                         when the workbook was left out for size
//   past_reports:              [ { week_ending: "YYYY-MM-DD", file: "name.html" } ]   earlier editions in the same folder
import { showDate } from "../workItems.js";

const isObj = (x) => !!x && typeof x === "object" && !Array.isArray(x);
const ISO = /^\d{4}-\d\d-\d\d$/;

/** The workbook to offer: {name, base64}, or null when there is none (or it is not a plain name and base64 text). */
export function workbookOf(d) {
  const w = d && d.client_workbook;
  if (!isObj(w) || typeof w.base64 !== "string" || !w.base64 || !/^[A-Za-z0-9+/=\s]+$/.test(w.base64)) return null;
  const name = typeof w.name === "string" && /^[^\\/:*?"<>|\x00-\x1f]{1,120}$/.test(w.name) ? w.name : "report.xlsx";
  return { name: /\.xlsx$/i.test(name) ? name : name + ".xlsx", base64: w.base64.replace(/\s+/g, "") };
}

export const tooLarge = (d) => !!d && d.client_workbook_too_large === true;

/** A file name that is only a name in this file's folder (no folder, no address, no query), or "". */
export const plainFile = (f) => (typeof f === "string" && /^[^\\/:?#\x00-\x1f]+$/.test(f) && !f.startsWith(".") && f.length <= 200 ? f : "");

/** The earlier reports, newest first: [{date: "DD-MM-YYYY", iso, href}]. A row without a real date or a plain file name is left out. */
export function pastReportsOf(d) {
  const list = d && Array.isArray(d.past_reports) ? d.past_reports : [];
  const out = [];
  for (const r of list) {
    if (!isObj(r) || typeof r.week_ending !== "string" || !ISO.test(r.week_ending) || !plainFile(r.file)) continue;
    out.push({ iso: r.week_ending, date: showDate(r.week_ending), href: encodeURIComponent(r.file) });
  }
  return out.sort((a, b) => (a.iso < b.iso ? 1 : a.iso > b.iso ? -1 : 0));
}

/** The bytes of a base64 text, or null when it is not valid. */
export function bytesOf(base64) {
  try {
    const bin = atob(base64);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  } catch (e) { return null; }
}
