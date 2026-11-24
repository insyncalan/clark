// Text and image (#96), store type "textimage": its view part. Words beside one picture, with its caption; the picture on the right
// unless the section says left. Its Edit part is edit/templates/TextImage.jsx; its rules and what it publishes are
// src/clark/section_kinds/textimage.py. View: the old lines as text nodes, the rich words as cleaned html only (never the stored string); the picture through safe.js.
// isEmpty(section, data): true (no words and no picture) leaves the section out of the served View and the published file.
import { contentOf, Figure, lineOf, captionOf, linesOf, picturesOf } from "./pictures.jsx";
import { safeImage } from "./safe.js";
import { CleanProse } from "../components/CleanProse.jsx";

//
// Row 1232: a body of version 2 is Text and Image Side by Side, and this is its ONE View part too. One image as framed, the words
// beside it (a full width section: `side` says left or right, `share` how much of the width the image takes) or above and below it (a
// half width section: `hpos`, "top" or "bottom"); each width keeps its own choice. `shape` is how the image fills its place: "fill"
// (default: as tall as the words beside it, or 16:9 at half width), "4:3", "square" or "whole"; `fx`, `fy` (0 to 1000) are the focus the
// image keeps in view when it fills. At 900 px wide a full width section stacks (left puts the image above, right below). No tool, no
// dot, no description box: a screen reader reads the description (the img's alt), then the caption. The file holds only the framed
// copy. Same keys as the content textimage.py published() will carry (the server piece).
export const READY = true;
export const SHARES = ["half", "third", "two"];
export const SHAPES = ["fill", "4:3", "square", "whole"];
const inThousand = (n) => (typeof n === "number" && Number.isInteger(n) && n >= 0 && n <= 1000 ? n : 500);

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
  if (image) Object.assign(c, { image, caption: captionOf(v.caption), alt: lineOf(v.alt) });
  if (v.v === 2) {
    c.sbs = 1;
    if (v.hpos === "bottom") c.hpos = "bottom";
    if (image) {
      if (v.share === "third" || v.share === "two") c.share = v.share;
      if (SHAPES.includes(v.shape) && v.shape !== "fill") c.shape = v.shape;
      if (inThousand(v.fx) !== 500) c.fx = v.fx;
      if (inThousand(v.fy) !== 500) c.fy = v.fy;
    }
  }
  return c;
}

const hasWords = (h) => typeof h === "string" && h.replace(/<[^>]*>|&nbsp;|\s/g, "") !== "";

// isEmpty has no cleaner (it only asks whether there is anything to draw), so a stored html counts as words when it holds a visible
// character; an empty paragraph does not.
export function isEmpty(section) {
  const c = contentOf(section, (v) => shown(v, (h) => h));
  return !c || !(linesOf(c.words).length || hasWords(c.html) || safeImage(c.image));
}

function Side({ c, words, pic, html }) {
  const shape = SHAPES.includes(c.shape) ? c.shape : "fill";
  const cls = ["tpl-sbs", `share-${SHARES.includes(c.share) ? c.share : "half"}`, c.side === "left" ? "pos-left" : "pos-right", `hpos-${c.hpos === "bottom" ? "bottom" : "top"}`,
    `shape-${shape === "4:3" ? "43" : shape}`, pic ? "" : "no-pic", html || words.length ? "" : "no-words"].filter(Boolean).join(" ");
  const at = pic ? { objectPosition: `${inThousand(c.fx) / 10}% ${inThousand(c.fy) / 10}%` } : null;
  const caption = lineOf(c.caption);
  if (!pic && !html && !words.length) return null;
  return (
    <div class={cls}>
      {pic ? (
        <figure class="tpl-sbs-fig">
          <div class="tpl-sbs-frame"><img src={pic} alt={lineOf(c.alt)} style={at} loading="lazy" decoding="async" /></div>
          {caption ? <figcaption>{caption}</figcaption> : null}
        </figure>
      ) : null}
      {html ? <CleanProse html={html} cls="tpl-words prose tpl-sbs-words" />
        : words.length ? <div class="tpl-words tpl-sbs-words">{words.map((p, i) => <p key={i}>{p}</p>)}</div> : null}
    </div>
  );
}

export function View({ section, clean }) {
  const c = contentOf(section, (v) => shown(v, clean));
  if (!c) return null;
  const words = linesOf(c.words), pic = safeImage(c.image), html = hasWords(c.html) ? c.html : "";
  if (c.sbs) return <Side c={c} words={words} pic={pic} html={html} />;
  return (
    <div class={`tpl-ti${pic ? "" : " no-pic"}${c.side === "left" ? " pic-left" : ""}`}>
      {html ? <CleanProse html={html} cls="tpl-words prose" />
        : words.length ? <div class="tpl-words">{words.map((p, i) => <p key={i}>{p}</p>)}</div> : null}
      {pic ? <Figure src={pic} alt={c.alt} caption={c.caption} /> : null}
    </div>
  );
}
