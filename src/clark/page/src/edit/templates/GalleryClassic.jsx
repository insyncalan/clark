// Image gallery (row 1233, gal 2), the Classic Edit part for a gallery that holds at least one image (edit/templates/Gallery.jsx hands over to it; an
// empty gallery and the Cards look keep the Edit part they had). Up to six images in a grid: a tile each (click or focus selects it; a frame round the
// selected one), the dashed add tile after the last, the one icon toolbar under the grid (Replace the selected image, and the plus), files dropped on the
// section (up to six), the description and caption of the SELECTED image under the toolbar, and the count note. An image goes on its own to POST
// /api/section-image (slot "1" to "6": clark frames it, gallery.py), after the words make the gallery a version 2 one. Remove (gal 3: the bin on a tile, the toolbar bin, the Delete key when no box is being typed in; one step, one Undo) is here. Drag (gal 4, AP7): the dots on a tile (24 px, top left, hover or selected) move it; the grid reorders live while the pointer moves (the dragged tile
// at opacity .3, nothing else redrawn), and the drop saves the new `order` once: one change, one Undo step, the words (kept by slot) moving with the image;
// Escape puts it back. Row 1233 AP9: the red mark on a tile with no description (Edit only). Not built here: the focus dot, Crop, Reset, the columns and shape controls. Given { section }. Words and numbers: logic/galleryEditWords.js.
import { useEffect, useRef, useState } from "preact/hooks";
import { change, say } from "../../stores/changes.js";
import { sendPicture, wordsOf, saveWords, PicturesTotal } from "./pictureEdit.jsx";
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
  remove: <path d="M4 6h12M8 6V4h4v2M6 6l1 10h6l1-10" />,
  move: <path d="M7 5h.01M13 5h.01M7 10h.01M13 10h.01M7 15h.01M13 15h.01" stroke-width="2.4" />,
};
const Icon = ({ name }) => <svg viewBox="0 0 20 20" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">{P[name]}</svg>;
const Btn = ({ icon, name, act, disabled, onClick }) => (
  <button type="button" class="fi-btn" aria-label={name} data-tip={name} data-act={act} disabled={disabled} tabIndex={-1} onClick={onClick}><Icon name={icon} /></button>
);

export function Edit({ section }) {
  const v = stored(section) || {};
  const pics = picturesOf(v), items = itemsOf(v);
  const shown = (Array.isArray(v.order) ? v.order.filter((s) => SLOTS.includes(s)) : []).concat(SLOTS).filter((s, i, a) => a.indexOf(s) === i);
  const saved = shown.filter((s) => typeof pics[s] === "string" && pics[s]);
  const [live, setLive] = useState(null);                    // the order while a drag is going on: the filled slots, or null
  const filled = live && live.length === saved.length ? live : saved;
  const free = SLOTS.filter((s) => !filled.includes(s));
  const [pick, setPick] = useState("");
  const sel = filled.includes(pick) ? pick : filled[0] || "";
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const grid = useRef(null), drag = useRef(null);
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
  // Remove one image (its words go with it on the server; the toast carries Undo). The next tile, else the one before, is selected.
  async function remove(slot) {
    if (!slot || busy) return;
    const at = filled.indexOf(slot), next = filled[at + 1] || filled[at - 1] || "";
    setBusy(true);
    try { if (await sendPicture(section, slot, null, W.removed)) setPick(next); } finally { setBusy(false); }
  }
  // Reorder: `now` is the filled slots in their new order; the order saved is all six (the empty ones after, as gallery.py reads it). One change.
  async function reorder(now) {
    if (now.join() === saved.join()) return;
    const all = now.concat(SLOTS.filter((s) => !now.includes(s)));
    await saveWords(section, { order: all.join() === SLOTS.join() ? [] : all }, "");
  }
  const target = (x, y) => {
    const tiles = [...grid.current.querySelectorAll(".gal-tile")];
    let best = "", gap = Infinity;
    for (const t of tiles) {
      const r = t.getBoundingClientRect();
      const d = Math.hypot(Math.max(r.left - x, 0, x - r.right), Math.max(r.top - y, 0, y - r.bottom)) * 1e4 + Math.hypot(x - (r.left + r.right) / 2, y - (r.top + r.bottom) / 2);
      if (d < gap) { gap = d; best = t.dataset.slot; }
    }
    return best;
  };
  const down = (e, s) => {
    if (busy || e.button > 0 || saved.length < 2) return;
    e.preventDefault(); e.stopPropagation();
    setPick(s);
    try { e.currentTarget.setPointerCapture(e.pointerId); } catch (_) { /* no live pointer (a script): the move events still arrive */ }
    drag.current = { slot: s, order: saved.slice(), moved: false };
    setLive(saved.slice());
  };
  const move = (e) => {
    const d = drag.current;
    if (!d) return;
    const over = target(e.clientX, e.clientY);
    if (!over || over === d.slot) return;
    const from = d.order.indexOf(d.slot), to = d.order.indexOf(over);
    const next = d.order.slice(); next.splice(from, 1); next.splice(to, 0, d.slot);
    d.order = next; d.moved = true;
    setLive(next);
  };
  const up = (e, cancel) => {
    const d = drag.current;
    if (!d) return;
    drag.current = null;
    const now = d.order;
    if (cancel || !d.moved) { setLive(null); return; }
    setLive(now.slice());                                      // keep the new order drawn until the save is back: no flicker
    reorder(now).finally(() => setLive(null));
  };
  const handleKey = (e) => {
    if (e.key === "Escape" && drag.current) { e.stopPropagation(); up(e, true); }
  };
  const typing = (t) => !!t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || !!(t.closest && t.closest("[role=textbox]")));
  const onKey = (e) => { if (e.key === "Delete" && !e.defaultPrevented && !typing(e.target)) { e.preventDefault(); remove(sel); } };
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
      onKeyDown={onKey} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={onDrop}>
      <div class="gal-grid" data-gal-grid ref={grid}>
        {filled.map((s, i) => (
          <div class={`gal-tile${s === sel ? " sel" : ""}${drag.current && drag.current.slot === s ? " dragging" : ""}`} key={s} data-slot={s} tabIndex={0} role="group" aria-label={W.select(i + 1)} onClick={() => setPick(s)} onFocus={() => setPick(s)}>
            <div class="gal-frame"><img src={safeImage(pics[s])} alt="" draggable={false} /></div>
            {(items[s] || {}).alt ? null : <span class="gal-red" role="img" aria-label={W.redTitle} title={W.redTitle}>!</span>}
            {filled.length > 1 ? (
              <button type="button" class="gal-move" data-act="move" aria-label={W.moveName(i + 1)} title={W.moveTitle} disabled={busy}
                onPointerDown={(e) => down(e, s)} onPointerMove={move} onPointerUp={(e) => up(e, false)} onPointerCancel={(e) => up(e, true)} onKeyDown={handleKey} onClick={(e) => e.stopPropagation()}><Icon name="move" /></button>
            ) : null}
            <button type="button" class="gal-bin" data-act="bin" aria-label={W.binName(i + 1)} title={W.binTitle} disabled={busy} onClick={(e) => { e.stopPropagation(); remove(s); }}><Icon name="remove" /></button>
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
          <Btn icon="remove" name={W.remove} act="remove" disabled={busy} onClick={() => remove(sel)} />
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
