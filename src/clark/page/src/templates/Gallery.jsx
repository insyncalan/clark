// Image gallery (#96), store type "gallery": its view part. Up to six images in a grid, each with its caption, in their slot order.
// Its Edit part is edit/templates/Gallery.jsx; its rules and what it publishes are src/clark/section_kinds/gallery.py. View: text
// nodes only, never dangerouslySetInnerHTML; every image through safe.js. isEmpty(section, data): true (no image) leaves the
// section out of the served View and the published file.
//
// Row 1233: the published view. The grid draws each image as framed (the file holds only the framed copy), in the one shape chosen for
// all (4:3 when none is said, as before), two or three across (two across at half width and at 900 px), its caption under it when it has
// one. No tool, dot, bin or red mark. Click an image (or Enter on it) to see it larger with its caption; Esc, a click outside it, or the
// close button closes it. Same words and keys as section_kinds/gallery.py published().
import { useEffect, useRef, useState } from "preact/hooks";
import { contentOf, lineOf, captionOf, picturesOf } from "./pictures.jsx";
import { safeImage } from "./safe.js";

export const READY = true;
export const SLOTS = ["1", "2", "3", "4", "5", "6"];
export const SHAPES = ["4:3", "square", "16:9", "whole"];
export const COLUMNS = [2, 3];

// The mirror of gallery.py published(): the images in slot order, each with its caption and description, or null. A body that says
// how many across (`columns`, 2 or 3) and the one shape for all (`shape`) passes them on; anything else is left out.
export function shown(v) {
  const pics = picturesOf(v), items = v.items && typeof v.items === "object" && !Array.isArray(v.items) ? v.items : {};
  const list = SLOTS.filter((s) => lineOf(pics[s])).map((s) => {
    const it = items[s] && typeof items[s] === "object" ? items[s] : {};
    return { image: pics[s], caption: captionOf(it.caption), alt: lineOf(it.alt) };
  });
  if (!list.length) return null;
  const out = { pictures: list };
  if (COLUMNS.includes(v.columns)) out.columns = v.columns;
  if (SHAPES.includes(v.shape)) out.shape = v.shape;
  return out;
}

const listOf = (c) => (c && Array.isArray(c.pictures) ? c.pictures.filter((p) => p && safeImage(p.image)) : []);

export function isEmpty(section) {
  return !listOf(contentOf(section, shown)).length;
}

const SHAPE_CLASS = { "4:3": "s43", square: "s11", "16:9": "s169", whole: "swhole" };

// The large view: a modal dialog, so Esc closes it, focus stays inside it and goes first to the close button.
function Large({ p, onClose, opener }) {
  const ref = useRef(null), live = useRef(true);
  useEffect(() => {
    const d = ref.current;
    live.current = true;
    if (d && !d.open && typeof d.showModal === "function") d.showModal();
    // The close event of a dialog taken away arrives late; it must not close the next one that has been opened since.
    return () => { live.current = false; if (d && d.open) d.close(); if (opener && opener.isConnected) opener.focus(); };
  }, []);
  const src = safeImage(p.image), caption = lineOf(p.caption);
  return (
    <dialog class="tpl-gal-large" ref={ref} aria-label={caption || lineOf(p.alt) || undefined} onClose={() => { if (live.current) onClose(); }}
      onClick={(e) => { if (e.target === ref.current) onClose(); }}>
      <div class="tpl-gal-large-in">
        <button type="button" class="tpl-gal-x" aria-label="Close" title="Close" onClick={onClose}>
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" /></svg>
        </button>
        <img src={src} alt={lineOf(p.alt)} />
        {caption ? <p>{caption}</p> : null}
      </div>
    </dialog>
  );
}

export function View({ section }) {
  const c = contentOf(section, shown);
  const list = listOf(c);
  const [open, setOpen] = useState(-1);
  const opener = useRef(null);
  if (!list.length) return null;
  const said = c && COLUMNS.includes(c.columns);
  const grid = said ? `c-${Math.min(list.length, c.columns)}` : `n-${Math.min(list.length, 3)}`;
  const shape = SHAPE_CLASS[c && c.shape] || SHAPE_CLASS["4:3"];
  return (
    <div class={`tpl-gal ${grid} ${shape}`}>
      {list.map((p, i) => {
        const caption = lineOf(p.caption);
        return (
          <figure class="tpl-fig tpl-gal-fig" key={i}>
            <button type="button" class="tpl-gal-open" aria-haspopup="dialog" onClick={(e) => { opener.current = e.currentTarget; setOpen(i); }}>
              <img src={safeImage(p.image)} alt={lineOf(p.alt)} loading="lazy" decoding="async" />
            </button>
            {caption ? <figcaption>{caption}</figcaption> : null}
          </figure>
        );
      })}
      {open >= 0 && list[open] ? <Large p={list[open]} opener={opener.current} onClose={() => setOpen(-1)} /> : null}
    </div>
  );
}
