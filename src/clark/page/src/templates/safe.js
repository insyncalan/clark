// The one place a section template checks a link, a picture or a file before it draws it, and words a date (#96). Every template
// uses these; no template writes its own. Pure: no DOM, no Preact. Each answers "" for anything it does not allow, so a template
// draws nothing rather than something unsafe.
import { dayNumber, showDate } from "../workItems.js";

const SPACES = /[\x00-\x20]+/g;
const CONTROLS = /[\x00-\x1f\x7f]+/g;

// A link a reader may follow: https:, mailto: or a link within the page, as publish.safe_href allows (javascript:, data:, http:, a
// relative or protocol-relative address are not). The link without control characters, trimmed, or "".
export function safeHref(value) {
  if (typeof value !== "string") return "";
  const v = value.replace(SPACES, "").toLowerCase();
  return v.startsWith("https://") || v.startsWith("mailto:") || v.startsWith("#") ? value.replace(CONTROLS, "").trim() : "";
}

// A picture the file can carry: a data: address of a PNG, JPEG or WebP, base64 only (never SVG or GIF, never an outside address).
const IMAGE = /^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/]+={0,2}$/;
export function safeImage(value) {
  return typeof value === "string" && IMAGE.test(value) ? value : "";
}

// A file copied beside the report, in its "Report files" folder (#96, files are links to the shared folder): a relative address
// "Report files/<name>", one name, no folder above, no scheme. The address made safe to use as a link, or "".
export const FILES_FOLDER = "Report files";
export function fileHref(rel) {
  if (typeof rel !== "string" || !rel.startsWith(`${FILES_FOLDER}/`)) return "";
  const name = rel.slice(FILES_FOLDER.length + 1);
  if (!name || name === "." || name === ".." || /[\/\\:\u0000-\u001f]/.test(name)) return "";
  return `${encodeURIComponent(FILES_FOLDER)}/${encodeURIComponent(name)}`;
}

// A stored day (YYYY-MM-DD) as a person reads it everywhere in clark: DD-MM-YYYY. Anything that is not a real day is "".
export function dateWords(iso) {
  return dayNumber(iso) === null ? "" : showDate(iso);
}
