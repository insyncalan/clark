// Rich text, read-only (#192): the page's cleaner (cleanHtml) run over a stored body, then drawn. Never the stored text itself, so a
// row written past the store can't reach the page as markup. No editor, no click: the Client Requested Report View uses it for the
// dashboard's text sections. It lives in edit/ because cleanHtml is not in a published file (the file's text was cleaned at publish).
import { cleanHtml } from "../logic/cleanHtml.js";

export function RichRead({ html, empty = "Nothing written yet." }) {
  let clean = "";
  try { clean = cleanHtml(typeof html === "string" ? html : ""); } catch (e) { clean = ""; }
  return clean ? <div class="sec-body prose" data-rich-read dangerouslySetInnerHTML={{ __html: clean }} /> : empty ? <p class="quiet">{empty}</p> : null;
}
