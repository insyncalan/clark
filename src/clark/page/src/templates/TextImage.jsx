// Text and image (#96), store type "textimage": its view part. Words beside one picture, with its caption; the picture on the right
// unless the section says left. Its Edit part is edit/templates/TextImage.jsx; its rules and what it publishes are
// src/clark/section_kinds/textimage.py. View: the old lines as text nodes, the rich words as cleaned html only (never the stored string); the picture through safe.js.
// isEmpty(section, data): true (no words and no picture) leaves the section out of the served View and the published file.
import { contentOf, Figure, lineOf, linesOf, picturesOf } from "./pictures.jsx";
import { safeImage } from "./safe.js";
import { CleanProse } from "../components/CleanProse.jsx";

export const READY = true;

// The mirror of textimage.py published(): the words and the picture (its caption and description only with it), or null.
// `html` (row 1005) is the rich words: in a published file the server already cleaned it, so it is drawn as it is; in the page clark
// serves it is the stored text, so `clean` (the page's cleanHtml, given by Section.jsx; the published page has none) cleans it first,
// and with no cleaner it is not drawn at all. The old `words` lines stay text nodes.
export function shown(v, clean) {
  const image = lineOf(picturesOf(v).image);
  let html = typeof v.html === "string" ? v.html : "";
  html = html && clean ? clean(html) : "";
  const words = html ? [] : linesOf(v.words);
  if (!image && !words.length && !html) return null;
  const c = { words, side: v.side === "left" ? "left" : "right" };
  if (html) c.html = html;
  if (image) Object.assign(c, { image, caption: lineOf(v.caption), alt: lineOf(v.alt) });
  return c;
}

const hasWords = (h) => typeof h === "string" && h.replace(/<[^>]*>|&nbsp;|\s/g, "") !== "";

// isEmpty has no cleaner (it only asks whether there is anything to draw), so a stored html counts as words when it holds a visible
// character; an empty paragraph does not.
export function isEmpty(section) {
  const c = contentOf(section, (v) => shown(v, (h) => h));
  return !c || !(linesOf(c.words).length || hasWords(c.html) || safeImage(c.image));
}

export function View({ section, clean }) {
  const c = contentOf(section, (v) => shown(v, clean));
  if (!c) return null;
  const words = linesOf(c.words), pic = safeImage(c.image), html = hasWords(c.html) ? c.html : "";
  return (
    <div class={`tpl-ti${pic ? "" : " no-pic"}${c.side === "left" ? " pic-left" : ""}`}>
      {html ? <CleanProse html={html} cls="tpl-words prose" />
        : words.length ? <div class="tpl-words">{words.map((p, i) => <p key={i}>{p}</p>)}</div> : null}
      {pic ? <Figure src={pic} alt={c.alt} caption={c.caption} /> : null}
    </div>
  );
}
