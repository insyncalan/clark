// Image gallery (#96), store type "gallery": its view part. Up to six pictures in a grid, each with its caption, in their slot order.
// Its Edit part is edit/templates/Gallery.jsx; its rules and what it publishes are src/clark/section_kinds/gallery.py. View: text
// nodes only, never dangerouslySetInnerHTML; every picture through safe.js. isEmpty(section, data): true (no picture) leaves the
// section out of the served View and the published file.
import { contentOf, Figure, lineOf, picturesOf } from "./pictures.jsx";
import { safeImage } from "./safe.js";

export const READY = true;
export const SLOTS = ["1", "2", "3", "4", "5", "6"];

// The mirror of gallery.py published(): the pictures in slot order, each with its caption and description, or null.
export function shown(v) {
  const pics = picturesOf(v), items = v.items && typeof v.items === "object" && !Array.isArray(v.items) ? v.items : {};
  const list = SLOTS.filter((s) => lineOf(pics[s])).map((s) => {
    const it = items[s] && typeof items[s] === "object" ? items[s] : {};
    return { image: pics[s], caption: lineOf(it.caption), alt: lineOf(it.alt) };
  });
  return list.length ? { pictures: list } : null;
}

const listOf = (c) => (c && Array.isArray(c.pictures) ? c.pictures.filter((p) => p && safeImage(p.image)) : []);

export function isEmpty(section) {
  return !listOf(contentOf(section, shown)).length;
}

export function View({ section }) {
  const list = listOf(contentOf(section, shown));
  if (!list.length) return null;
  return (
    <div class={`tpl-gal n-${Math.min(list.length, 3)}`}>
      {list.map((p, i) => <Figure key={i} src={p.image} alt={p.alt} caption={p.caption} />)}
    </div>
  );
}
