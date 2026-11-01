// Text and image (#96), store type "textimage": its view part. Words beside one picture, with its caption; the picture on the right
// unless the section says left. Its Edit part is edit/templates/TextImage.jsx; its rules and what it publishes are
// src/clark/section_kinds/textimage.py. View: text nodes only, never dangerouslySetInnerHTML; the picture through safe.js.
// isEmpty(section, data): true (no words and no picture) leaves the section out of the served View and the published file.
import { contentOf, Figure, lineOf, linesOf, picturesOf } from "./pictures.jsx";
import { safeImage } from "./safe.js";

export const READY = true;

// The mirror of textimage.py published(): the words and the picture (its caption and description only with it), or null.
export function shown(v) {
  const image = lineOf(picturesOf(v).image), words = linesOf(v.words);
  if (!image && !words.length) return null;
  const c = { words, side: v.side === "left" ? "left" : "right" };
  if (image) Object.assign(c, { image, caption: lineOf(v.caption), alt: lineOf(v.alt) });
  return c;
}

export function isEmpty(section) {
  const c = contentOf(section, shown);
  return !c || !(linesOf(c.words).length || safeImage(c.image));
}

export function View({ section }) {
  const c = contentOf(section, shown);
  if (!c) return null;
  const words = linesOf(c.words), pic = safeImage(c.image);
  return (
    <div class={`tpl-ti${pic ? "" : " no-pic"}${c.side === "left" ? " pic-left" : ""}`}>
      {words.length ? <div class="tpl-words">{words.map((p, i) => <p key={i}>{p}</p>)}</div> : null}
      {pic ? <Figure src={pic} alt={c.alt} caption={c.caption} /> : null}
    </div>
  );
}
