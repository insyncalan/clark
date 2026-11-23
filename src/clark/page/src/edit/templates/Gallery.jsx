// Image gallery (#96), store type "gallery": its Edit part, filled in place. Up to six pictures, each with a caption and a
// description; each saved on its own (one change, one step, one Undo, place "report"); a picture through POST /api/section-image
// (pictureEdit.jsx), made smaller than in the one-picture templates so six fit one section. Taking a picture out takes its caption
// with it. Given { section, tools }. Limits are gallery.py's.
//
// Row 1233 (Classic only; Cards keeps the slot list, Slots below): the tiles. Up to six images in a grid (three across, two at half
// width and at 900 px; one shape for all), each a tile with a frame round the selected one; the dashed "Add an image" tile at the end;
// no image yet: one large dashed area. Add by the file window or by dropping files (up to six at once); a seventh is refused in words.
// The selected image's description and caption sit under the grid, then the count line. A body stays version 1 until an edit needs a
// version 2 field: opening, adding to a version 1 body and publishing never rewrite it. Words and numbers: logic/galleryWords.js.
import { useRef, useState } from "preact/hooks";
import { LineField, CaptionField, PictureSlot, PicturesTotal, saveWords, wordsOf, sendPicture } from "./pictureEdit.jsx";
import { shrink, TYPES } from "./shrink.js";
import { say } from "../../stores/changes.js";
import { safeImage } from "../../templates/safe.js";
import { SLOTS as ALL, WORDS as W, SHAPES, PICTURE_MAX, ORIGINAL_MAX, WIDTH_MAX, V1_LONGEST, V1_MOST, shownSlots, freeSlots } from "../../logic/galleryWords.js";
import { samplePicture } from "../samplePicture.js";
import { startOr, classicLook } from "../startingText.js";
import { picturesOf, stored } from "../../templates/pictures.jsx";
import { SLOTS } from "../../templates/Gallery.jsx";

const WORDS = { added: "Picture added.", removed: "Picture taken out." };
export const LONGEST = 1200;
export const MOST = 400 * 1024;              // gallery.py V1_PICTURE_MAX: this page still sends version 1 bodies (test_gallery_v2_survivors keeps them equal)

function itemsOf(v) {
  return v && v.items && typeof v.items === "object" && !Array.isArray(v.items) ? v.items : {};
}

// A caption or description of one picture: the items object saved whole, with that one field changed.
function ItemField({ section, slot, field, label, value, words, empty }) {
  const Box = field === "caption" ? CaptionField : LineField;          // item 1005: a caption is on the one editor, a description stays one line
  return (
    <Box section={section} field={`${field}-${slot}`} label={label} value={value} max={300} words={words} empty={empty}
      save={(v) => {
        const items = { ...itemsOf(wordsOf(section)) };
        const one = { ...(items[slot] || {}) };
        if (v) one[field] = v; else delete one[field];
        if (Object.keys(one).length) items[slot] = one; else delete items[slot];
        return saveWords(section, { items }, words);
      }} />
  );
}

export function Edit({ section }) {
  return classicLook() ? <Tiles section={section} /> : <Slots section={section} />;
}

// One image's description and caption (the selected tile's), under the grid.
function Fields({ section, slot, n, items }) {
  const it = items[slot] || {};
  return (
    <div class="tpl-gal-fields">
      <ItemField section={section} slot={slot} field="alt" label={<>{W.describe(n)} <span class="quiet">{W.describeHint}</span></>} value={it.alt} words={W.altSaved} />
      {!it.alt ? <p class="tpl-gal-warn" data-alt-note>{W.noDescription}</p> : null}
      <ItemField section={section} slot={slot} field="caption" label={<>{W.caption} <span class="quiet">{W.optional}</span></>} value={it.caption} words={W.captionSaved} />
    </div>
  );
}

function Tiles({ section }) {
  const v = stored(section) || {};
  const pics = picturesOf(v), items = itemsOf(v);
  const shown = shownSlots(v, pics);
  const [pick, setPick] = useState("");
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const input = useRef(null);
  const now = shown.includes(pick) ? pick : shown[0];
  const two = v.v === 2;

  async function take(list) {
    const files = Array.from(list || []);
    if (!files.length || busy) return;
    const free = freeSlots(pics);
    if (!free.length) { say("problem", W.full); return; }
    setBusy(true);
    let added = 0, last = null;
    try {
      for (const f of files) {
        if (added >= free.length) break;
        if (f.size > PICTURE_MAX) { say("problem", W.tooBig()); continue; }
        const made = await (two ? shrink(f, { longest: 8000, widest: WIDTH_MAX, most: ORIGINAL_MAX }) : shrink(f, { longest: V1_LONGEST, most: V1_MOST }));
        if (!made.ok) { say("problem", made.message); continue; }
        const r = await sendPicture(section, free[added], made.data, W.added);
        if (!r) break;
        last = r; added++;
        if (added === 1 && !shown.length) setPick(free[0]);
      }
      if (added && files.length > added) say("done", W.partial(added, files.length), last && last.apply_id);
    } finally { setBusy(false); }
  }
  const choose = () => input.current && input.current.click();
  const file = (
    <input ref={input} type="file" multiple accept={TYPES.join(",")} class="tpl-file" tabIndex={-1} aria-hidden="true"
      onChange={(e) => { const f = e.target.files; const got = Array.from(f || []); e.target.value = ""; take(got); }} />
  );
  const drop = {
    onDragOver: (e) => { e.preventDefault(); setOver(true); }, onDragLeave: () => setOver(false),
    onDrop: (e) => { e.preventDefault(); setOver(false); take(e.dataTransfer && e.dataTransfer.files); },
  };
  const grid = `tpl-gal-tiles c${v.v === 2 && v.columns === 2 ? 2 : 3} ${SHAPES[v.v === 2 && SHAPES[v.shape] ? v.shape : "4:3"]}`;
  if (!shown.length) {
    return (
      <div class="tpl-edit tpl-gal-edit">
        <button type="button" class={`tpl-gal-empty${over ? " over" : ""}`} data-act="pick" disabled={busy} onClick={choose} {...drop}>
          <b aria-hidden="true">+</b><span>{busy ? W.making : W.empty}</span>
        </button>
        {file}
      </div>
    );
  }
  return (
    <div class="tpl-edit tpl-gal-edit">
      <div class={`${grid}${over ? " over" : ""}`} {...drop}>
        {shown.map((s, i) => {
          const on = s === now, cap = (items[s] || {}).caption;
          return (
            <div class={`tpl-gal-tile${on ? " sel" : ""}`} key={s} data-slot={s} role="button" tabIndex={0} aria-pressed={on} aria-label={W.tile(i + 1)}
              onClick={() => setPick(s)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setPick(s); } }}>
              <div class="tpl-gal-frame"><img src={safeImage(pics[s])} alt="" draggable={false} /></div>
              {cap ? <div class="tpl-gal-tcap">{cap}</div> : null}
            </div>
          );
        })}
        {shown.length < ALL.length ? (
          <button type="button" class="tpl-gal-add" data-act="add" aria-label={W.addTile} disabled={busy} onClick={choose}><div><b aria-hidden="true">+</b><span>{W.addTile}</span></div></button>
        ) : null}
      </div>
      <Fields section={section} slot={now} n={shown.indexOf(now) + 1} items={items} />
      <p class="quiet tpl-gal-count" role="status" data-count>{W.count(shown.length)}</p>
      <PicturesTotal />
      {file}
    </div>
  );
}

// The 1.0.7 slot list, kept for Cards (frozen).
function Slots({ section }) {
  const v = stored(section) || {};
  const pics = picturesOf(v), items = itemsOf(v);
  const filled = SLOTS.filter((s) => pics[s]);
  const free = SLOTS.find((s) => !pics[s]);
  const shownSlots = free ? [...filled, free] : filled;
  return (
    <div class="tpl-edit tpl-gal-edit">
      {!filled.length ? <p class="quiet tpl-hint">Add two to six pictures. Until there is one, this section stays out of the published page.</p> : null}
      <div class="tpl-gal-grid">
        {shownSlots.map((s, i) => (
          <div class="tpl-gal-one" key={s}>
            <PictureSlot section={section} slot={s} image={pics[s] || ""} label={`Picture ${i + 1}`} longest={LONGEST} most={MOST} words={WORDS} emptyWords={startOr("", "gallery", "empty")} sample={classicLook() && !filled.length} sampleNo={i} />
            {pics[s] ? <ItemField section={section} slot={s} field="caption" label={`Caption ${i + 1}`} value={(items[s] || {}).caption} words="Caption saved." empty={startOr(undefined, "gallery", "caption")} /> : null}
            {pics[s] ? <ItemField section={section} slot={s} field="alt" label={`Describe picture ${i + 1}`} value={(items[s] || {}).alt} words="Description saved." /> : null}
          </div>
        ))}
        {classicLook() && !filled.length ? [1, 2, 3, 4, 5].map((n) => (
          <div class="tpl-gal-one" key={`sample-${n}`}><img src={samplePicture(n)} alt="" class="tpl-pic-sample" data-sample aria-hidden="true" /></div>
        )) : null}
      </div>
      {!free ? <p class="quiet">A gallery holds six pictures. Take one out to add another.</p> : null}
      <PicturesTotal />
    </div>
  );
}
