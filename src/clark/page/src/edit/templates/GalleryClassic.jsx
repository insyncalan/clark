// Image gallery (row 1233, gal 2), the Classic Edit part for a gallery that holds at least one image (edit/templates/Gallery.jsx hands over to it; an
// empty gallery and the Cards look keep the Edit part they had). Up to six images in a grid: a tile each (click or focus selects it; a frame round the
// selected one), the dashed add tile after the last, the one icon toolbar under the grid (Replace the selected image, and the plus), files dropped on the
// section (up to six), the description and caption of the SELECTED image under the toolbar, and the count note. An image goes on its own to POST
// /api/section-image (slot "1" to "6": clark frames it, gallery.py), after the words make the gallery a version 2 one. Not built here: Remove (bin, Delete),
// drag by the dots, the focus dot, Crop, Reset, the red mark, the columns and shape controls. Given { section }. Words and numbers: logic/galleryEditWords.js.
import { useEffect, useRef, useState } from "preact/hooks";
import { change, say } from "../../stores/changes.js";
import { sendPicture, wordsOf, PicturesTotal } from "./pictureEdit.jsx";
import { shrink, TYPES, NOT_A_PICTURE } from "./shrink.js";
import { picturesOf, stored } from "../../templates/pictures.jsx";
import { safeImage } from "../../templates/safe.js";
import { SLOTS } from "../../templates/Gallery.jsx";
import { ItemField, itemsOf } from "./Gallery.jsx";
import { along, focusAt, restTab } from "./FullImageBar.jsx";
import { WORDS as W, FILE_MB, PRINT_WIDE, MOST_BYTES, SHAPES, COLUMNS } from "../../logic/galleryEditWords.js";

const P = {
  replace: <path d="M3 8h11l-3-3M17 12H6l3 3" />,
  add: <path d="M10 4v12M4 10h12" />,
};
const Icon = ({ name }) => <svg viewBox="0 0 20 20" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">{P[name]}</svg>;
const Btn = ({ icon, name, act, disabled, onClick }) => (
  <button type="button" class="fi-btn" aria-label={name} data-tip={name} data-act={act} disabled={disabled} tabIndex={-1} onClick={onClick}><Icon name={icon} /></button>
);

export function Edit({ section }) {
  const v = stored(section) || {};
  const pics = picturesOf(v), items = itemsOf(v);
  const filled = SLOTS.filter((s) => typeof pics[s] === "string" && pics[s]);
  const free = SLOTS.filter((s) => !filled.includes(s));
  const [pick, setPick] = useState("");
  const sel = filled.includes(pick) ? pick : filled[0] || "";
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const input = useRef(null), bar = useRef(null), replacing = useRef("");
  useEffect(() => restTab(bar.current));      // one tab stop on the toolbar, kept after every draw

  // A gallery of the old kind becomes the new one by its words alone (its images stay): one quiet step, before the first image is sent.
  async function newKind() {
    if (v.v === 2) return true;
    const next = { ...wordsOf(section), v: 2 };
    return !!(await change({ op: "update", id: section.id, changes: { body: JSON.stringify(next) }, place: "report" }, "", { silent: true }));
  }
  async function take(file, slot, said) {
    if (!TYPES.includes(file.type)) { say("problem", NOT_A_PICTURE); return false; }
    if (file.size > FILE_MB * 1024 * 1024) { say("problem", W.tooBig); return false; }
    const made = await shrink(file, { longest: 8000, widest: PRINT_WIDE, most: MOST_BYTES });
    if (!made.ok) { say("problem", made.message); return false; }
    return !!(await sendPicture(section, slot, made.data, said));
  }
  async function addMany(list) {
    const files = [...list].filter(Boolean);
    if (!files.length || busy) return;
    if (!free.length) { say("problem", W.seventh); return; }
    setBusy(true);
    try {
      if (!(await newKind())) return;
      const taken = files.slice(0, free.length);
      let at = 0, last = "";
      for (const f of taken) { if (await take(f, free[at], W.added)) { last = free[at]; at++; } else break; }
      if (last) setPick(last);
      if (files.length > taken.length && at === taken.length) say("problem", W.some(taken.length, files.length));
    } finally { setBusy(false); }
  }
  async function replace(file) {
    const slot = replacing.current;
    replacing.current = "";
    if (!file || !slot || busy) return;
    setBusy(true);
    try { if (await newKind()) await take(file, slot, W.replaced); } finally { setBusy(false); }
  }
  const choose = (slot = "") => { replacing.current = slot; if (input.current) { input.current.multiple = !slot; input.current.click(); } };
  const onDrop = (e) => {
    e.preventDefault(); setOver(false);
    const fs = e.dataTransfer && e.dataTransfer.files;
    if (fs && fs.length) addMany(fs);
  };
  const n = filled.indexOf(sel) + 1, it = items[sel] || {};
  const columns = COLUMNS.includes(v.columns) ? v.columns : 3, shape = SHAPES.includes(v.shape) ? v.shape : "4:3";
  return (
    <div class={`tpl-edit tpl-gal-edit gal-classic${over ? " over" : ""}`} data-columns={columns} data-shape={shape}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={onDrop}>
      <div class="gal-grid" data-gal-grid>
        {filled.map((s, i) => (
          <div class={`gal-tile${s === sel ? " sel" : ""}`} key={s} data-slot={s} tabIndex={0} role="group" aria-label={W.select(i + 1)} onClick={() => setPick(s)} onFocus={() => setPick(s)}>
            <div class="gal-frame"><img src={safeImage(pics[s])} alt="" draggable={false} /></div>
          </div>
        ))}
        {free.length ? (
          <button type="button" class="gal-addtile" data-act="add-tile" aria-label={W.tile} disabled={busy} onClick={() => choose()}>
            <span class="gal-plus" aria-hidden="true">+</span><span>{busy ? W.making : W.tile}</span>
          </button>
        ) : null}
      </div>
      <div class="fi-bar" role="toolbar" aria-label={W.toolbar} aria-orientation="horizontal" ref={bar} onKeyDown={(e) => along(e, bar.current)} onFocusIn={(e) => focusAt(e, bar.current)}>
        <div class="gal-group" role="group" aria-label={W.selected}>
          <Btn icon="replace" name={W.replace} act="replace" disabled={busy} onClick={() => choose(sel)} />
        </div>
        <span class="fi-grow" />
        <Btn icon="add" name={free.length ? W.add : W.full} act="add" disabled={busy || !free.length} onClick={() => choose()} />
      </div>
      <div key={sel}>
        <ItemField section={section} slot={sel} field="alt" label={<>{W.describe(n)} <span class="quiet">{W.describeHint}</span></>} value={it.alt} words="Description saved." />
        {it.alt ? null : <p class="fi-red" data-alt-note>{W.noDescription}</p>}
        <ItemField section={section} slot={sel} field="caption" label={<>{W.caption} <span class="quiet">{W.optional}</span></>} value={it.caption} words="Caption saved." />
      </div>
      <p class="quiet gal-note" role="status" data-gal-note>{W.note(filled.length)}</p>
      <PicturesTotal />
      <input ref={input} type="file" accept={TYPES.join(",")} class="tpl-file" tabIndex={-1} aria-hidden="true" multiple
        onChange={(e) => { const fs = [...(e.target.files || [])]; e.target.value = ""; if (replacing.current) replace(fs[0]); else addMany(fs); }} />
    </div>
  );
}
