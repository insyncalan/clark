// Image with caption (#96), store type "imagecap": its view part. One picture with its caption under it. Its Edit part is
// edit/templates/ImageCap.jsx; its rules and what it publishes are src/clark/section_kinds/imagecap.py. View: text nodes only, never
// dangerouslySetInnerHTML; the picture through safe.js. isEmpty(section, data): true (no picture) leaves the section out of the served
// View and the published file.
import { contentOf, Figure, lineOf, picturesOf } from "./pictures.jsx";
import { safeImage } from "./safe.js";

export const READY = true;

// The mirror of imagecap.py published(): the picture with its caption and description, or null while there is no picture.
export function shown(v) {
  const image = lineOf(picturesOf(v).image);
  return image ? { image, caption: lineOf(v.caption), alt: lineOf(v.alt) } : null;
}

export function isEmpty(section) {
  const c = contentOf(section, shown);
  return !c || !safeImage(c.image);
}

export function View({ section }) {
  const c = contentOf(section, shown);
  return c ? <div class="tpl-cap"><Figure src={c.image} alt={c.alt} caption={c.caption} /></div> : null;
}
