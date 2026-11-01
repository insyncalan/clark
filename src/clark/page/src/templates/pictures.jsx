// The Pictures group's shared view parts (#96: Text and image, Image with caption, Image gallery, Headline band). Pure helpers and one
// figure; no Edit part, nothing sent. A template's content is read in one of two ways, so the served View and the published file draw
// the same thing (FR-11): in a published file the section carries `content`, what section_kinds/<type>.py published() chose; in the
// page clark serves the section carries its stored `body`, and the template's own `shown` (the mirror of published(), pinned by
// tests/test_tpl_*.py) picks the same fields from it. Every picture goes through safeImage and every link through safeHref at draw time.
import { safeImage } from "./safe.js";

export const PICTURE_TYPES = ["textimage", "imagecap", "gallery", "headline"];

// The stored body of a section as an object, or null (none, or not readable).
export function stored(section) {
  const b = section && section.body;
  if (typeof b !== "string" || !b) return null;
  try {
    const v = JSON.parse(b);
    return v && typeof v === "object" && !Array.isArray(v) ? v : null;
  } catch (e) { return null; }
}

// What the section shows: the file's `content`, or `shown(stored body)` in the page clark serves; null when there is nothing to show.
export function contentOf(section, shown) {
  if (!section) return null;
  if (section.content && typeof section.content === "object" && !Array.isArray(section.content)) return section.content;
  const v = stored(section);
  return v ? shown(v) : null;
}

const text = (v) => (typeof v === "string" ? v : "");
export const lineOf = text;
export const linesOf = (v) => (Array.isArray(v) ? v.filter((p) => typeof p === "string" && p) : []);
export const picturesOf = (v) => (v && v.pictures && typeof v.pictures === "object" && !Array.isArray(v.pictures) ? v.pictures : {});

// One picture with its caption under it. `alt` describes it for someone who can't see it; with none it is read as decoration.
export function Figure({ src, alt, caption, cls }) {
  const img = safeImage(src);
  if (!img) return null;
  return (
    <figure class={`tpl-fig${cls ? ` ${cls}` : ""}`}>
      <img src={img} alt={text(alt)} loading="lazy" decoding="async" />
      {text(caption) ? <figcaption>{text(caption)}</figcaption> : null}
    </figure>
  );
}
