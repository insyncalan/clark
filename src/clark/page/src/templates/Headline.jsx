// Headline band (#96), store type "headline": its view part. A band that opens the report with a message, an optional button that
// links on and an optional picture beside the words (never behind them, so the words keep their contrast). Its Edit part is
// edit/templates/Headline.jsx; its rules and what it publishes are src/clark/section_kinds/headline.py. View: text nodes only, never
// dangerouslySetInnerHTML; the picture and the link through safe.js. isEmpty(section, data): true (no message, no button and no
// picture) leaves the section out of the served View and the published file.
import { contentOf, Figure, lineOf, picturesOf } from "./pictures.jsx";
import { safeHref, safeImage } from "./safe.js";

export const READY = true;

// The mirror of headline.py published(): the message, the button (only with both its words and its link) and the picture.
export function shown(v) {
  const c = {};
  if (lineOf(v.words)) c.words = v.words;
  if (lineOf(v.label) && lineOf(v.href)) Object.assign(c, { label: v.label, href: v.href });
  const image = lineOf(picturesOf(v).image);
  if (image) Object.assign(c, { image, alt: lineOf(v.alt) });
  return Object.keys(c).length ? c : null;
}

const parts = (c) => ({
  words: c ? lineOf(c.words) : "", pic: c ? safeImage(c.image) : "",
  label: c ? lineOf(c.label) : "", href: c ? safeHref(c.href) : "",
});

export function isEmpty(section) {
  const p = parts(contentOf(section, shown));
  return !(p.words || p.pic || (p.label && p.href));
}

export function View({ section }) {
  const c = contentOf(section, shown);
  const p = parts(c);
  if (!(p.words || p.pic || (p.label && p.href))) return null;
  const outside = /^(https:|mailto:)/i.test(p.href.trim());
  return (
    <div class={`tpl-band${p.pic ? " has-pic" : ""}`}>
      <div class="tpl-band-text">
        {p.words ? <p class="tpl-band-words">{p.words}</p> : null}
        {p.label && p.href ? <a class="tpl-band-btn" href={p.href} {...(outside ? { target: "_blank", rel: "noopener noreferrer" } : {})}>{p.label}</a> : null}
      </div>
      {p.pic ? <Figure src={p.pic} alt={c.alt} cls="tpl-band-pic" /> : null}
    </div>
  );
}
