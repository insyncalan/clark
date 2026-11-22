// Image gallery (#96), store type "gallery": its Edit part, filled in place. Up to six pictures, each with a caption and a
// description; each saved on its own (one change, one step, one Undo, place "report"); a picture through POST /api/section-image
// (pictureEdit.jsx), made smaller than in the one-picture templates so six fit one section. Taking a picture out takes its caption
// with it. Given { section, tools }. Limits are gallery.py's.
import { LineField, CaptionField, PictureSlot, PicturesTotal, saveWords, wordsOf } from "./pictureEdit.jsx";
import { samplePicture } from "../samplePicture.js";
import { startOr, classicLook } from "../startingText.js";
import { picturesOf, stored } from "../../templates/pictures.jsx";
import { SLOTS } from "../../templates/Gallery.jsx";
import { Edit as ClassicEdit } from "./GalleryClassic.jsx";

const WORDS = { added: "Picture added.", removed: "Picture taken out." };
export const LONGEST = 1200;
export const MOST = 400 * 1024;              // gallery.py V1_PICTURE_MAX: this page still sends version 1 bodies (test_gallery_v2_survivors keeps them equal)

export function itemsOf(v) {
  return v && v.items && typeof v.items === "object" && !Array.isArray(v.items) ? v.items : {};
}

// A caption or description of one picture: the items object saved whole, with that one field changed.
export function ItemField({ section, slot, field, label, value, words, empty }) {
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

// Row 1233 (gal 2): in the Classic look a gallery has the redesigned Edit part (GalleryClassic.jsx, with the large empty area when it holds no image); the Cards look keeps this one.
export function Edit({ section }) {
  return classicLook() ? <ClassicEdit section={section} /> : <OldEdit section={section} />;
}

function OldEdit({ section }) {
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
