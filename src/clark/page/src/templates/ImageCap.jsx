// Image with caption (#96), store type "imagecap": its view part. One picture with its caption under it. Its Edit part is
// edit/templates/ImageCap.jsx; its rules and what it publishes are src/clark/section_kinds/imagecap.py. View: text nodes only, never
// dangerouslySetInnerHTML; the picture through safe.js. isEmpty(section, data): true (no picture) leaves the section out of the served
// View and the published file.
//
// Row 1223: a body of version 2 is the Full width image, and this is its ONE View part. One image as framed across the whole width of the
// section, its caption under it in small grey type when there is one. No tool, no focus dot, no handle: a screen reader reads the
// description (the img's alt), then the caption. The file holds only the framed copy (pictures.image), so this draws it whole; the
// original lives in the editor's data and is never in a view. A small image sits centred at its own size with a fill each side
// (content.fill: "blur" the image's own blurred copy, "brand" the brand colour, "plain" none), or across the width when content.fit is
// "stretch". Same words and keys as section_kinds/imagecap.py published().
import { contentOf, Figure, lineOf, captionOf, picturesOf } from "./pictures.jsx";
import { safeImage } from "./safe.js";
import { FITS, FILLS } from "../logic/fullImageWords.js";

export const READY = true;

// The mirror of imagecap.py published(): the picture with its caption and description, or null while there is no picture. A body of
// version 2 also says `full` and, when they are not the defaults, how a small image sits (`fit`, `fill`).
export function shown(v) {
  const image = lineOf(picturesOf(v).image);
  if (!image) return null;
  const out = { image, caption: captionOf(v.caption), alt: lineOf(v.alt) };
  if (v.v === 2) {
    out.full = 1;
    if (v.fit === "stretch") out.fit = "stretch";
    if (v.fill === "brand" || v.fill === "plain") out.fill = v.fill;
  }
  return out;
}

export function isEmpty(section) {
  const c = contentOf(section, shown);
  return !c || !safeImage(c.image);
}

function Full({ c }) {
  const src = safeImage(c.image);
  if (!src) return null;
  const centred = c.fit !== "stretch";
  const fill = centred ? (FILLS.includes(c.fill) ? c.fill : FILLS[0]) : "";
  const caption = lineOf(c.caption);
  return (
    <figure class={`tpl-fullimg${centred ? ` fill-${fill}` : " stretch"}`} data-fit={centred ? FITS[0] : "stretch"}>
      <div class="tpl-fullimg-frame">
        {fill === "blur" ? <img class="tpl-fullimg-blur" src={src} alt="" aria-hidden="true" loading="lazy" decoding="async" /> : null}
        <img class="tpl-fullimg-img" src={src} alt={lineOf(c.alt)} loading="lazy" decoding="async" />
      </div>
      {caption ? <figcaption>{caption}</figcaption> : null}
    </figure>
  );
}

export function View({ section }) {
  const c = contentOf(section, shown);
  if (!c) return null;
  if (c.full) return <Full c={c} />;
  return <div class="tpl-cap"><Figure src={c.image} alt={c.alt} caption={c.caption} /></div>;
}
