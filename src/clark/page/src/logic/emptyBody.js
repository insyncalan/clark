// A rich text body with nothing to read (#74): no letters once tags and spaces are gone (a non-breaking space is a space) and no
// picture. `<p></p>`, `<br>`, `&nbsp;` or spaces alone are empty. The body is HTML already cleaned (publish.clean_html in a file,
// cleanHtml in the page clark serves); it is parsed as an inert document (nothing in it runs or loads) only to read its text.
// One more case counts as empty (row 1251): the Plan summary template's stored body, exactly as the template stores it (its two
// headings with an empty paragraph and bullet), unedited. It is read from planSummaryBody.js (the template uses it too), compared as markup with the
// whitespace between tags dropped. Any typed word, in a heading or below, or a plain Text section with only a heading, is not it.
import { PLAN_SUMMARY_BODY } from "./planSummaryBody.js";

const markup = (html) => new DOMParser().parseFromString(html, "text/html").body.innerHTML.replace(/>\s+</g, "><").trim();

export function emptyBody(html) {
  if (typeof html !== "string" || !html.trim()) return true;
  const doc = new DOMParser().parseFromString(html, "text/html");
  if (!doc.body.textContent.trim() && !doc.body.querySelector("img")) return true;
  return markup(html) === markup(PLAN_SUMMARY_BODY);
}
