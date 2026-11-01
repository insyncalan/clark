// A rich text body with nothing to read (#74): no letters once tags and spaces are gone (a non-breaking space is a space) and no
// picture. `<p></p>`, `<br>`, `&nbsp;` or spaces alone are empty. The body is HTML already cleaned (publish.clean_html in a file,
// cleanHtml in the page clark serves); it is parsed as an inert document (nothing in it runs or loads) only to read its text.
export function emptyBody(html) {
  if (typeof html !== "string" || !html.trim()) return true;
  const doc = new DOMParser().parseFromString(html, "text/html");
  return !doc.body.textContent.trim() && !doc.body.querySelector("img");
}
