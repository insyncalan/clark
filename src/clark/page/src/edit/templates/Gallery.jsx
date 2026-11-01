// Image gallery (#96), store type "gallery": its Edit part, filled in place. Up to six pictures, each with a caption and a
// description; each saved on its own (one change, one step, one Undo, place "report"); a picture through POST /api/section-image
// (pictureEdit.jsx), made smaller than in the one-picture templates so six fit one section. Taking a picture out takes its caption
// with it. Given { section, tools }. Limits are gallery.py's.
import { LineField, PictureSlot, PicturesTotal, saveWords, wordsOf } from "./pictureEdit.jsx";
import { picturesOf, stored } from "../../templates/pictures.jsx";
import { SLOTS } from "../../templates/Gallery.jsx";

const WORDS = { added: "Picture added.", removed: "Picture taken out." };
export const LONGEST = 1200;
export const MOST = 400 * 1024;              // gallery.py PICTURE_MAX

function itemsOf(v) {
  return v && v.items && typeof v.items === "object" && !Array.isArray(v.items) ? v.items : {};
}

// A caption or description of one picture: the items object saved whole, with that one field changed.
function ItemField({ section, slot, field, label, value, words }) {
  return (
    <LineField section={section} field={`${field}-${slot}`} label={label} value={value} max={300} words={words}
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
            <PictureSlot section={section} slot={s} image={pics[s] || ""} label={`Picture ${i + 1}`} longest={LONGEST} most={MOST} words={WORDS} />
            {pics[s] ? <ItemField section={section} slot={s} field="caption" label={`Caption ${i + 1}`} value={(items[s] || {}).caption} words="Caption saved." /> : null}
            {pics[s] ? <ItemField section={section} slot={s} field="alt" label={`Describe picture ${i + 1}`} value={(items[s] || {}).alt} words="Description saved." /> : null}
          </div>
        ))}
      </div>
      {!free ? <p class="quiet">A gallery holds six pictures. Take one out to add another.</p> : null}
      <PicturesTotal />
    </div>
  );
}
