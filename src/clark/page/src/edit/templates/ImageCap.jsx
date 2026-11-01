// Image with caption (#96), store type "imagecap": its Edit part, filled in place. The picture, its caption and its description,
// each saved on its own (one change, one step, one Undo, place "report"); the picture through POST /api/section-image
// (pictureEdit.jsx). Given { section, tools }. Limits are imagecap.py's.
import { LineField, PictureSlot, PicturesTotal } from "./pictureEdit.jsx";
import { picturesOf, stored } from "../../templates/pictures.jsx";

const WORDS = { added: "Picture added.", removed: "Picture taken out." };

export function Edit({ section }) {
  const v = stored(section) || {};
  const image = picturesOf(v).image || "";
  return (
    <div class="tpl-edit tpl-cap-edit">
      {!image ? <p class="quiet tpl-hint">Add a picture. Until then this section stays out of the published page.</p> : null}
      <PictureSlot section={section} slot="image" image={image} label="Picture" words={WORDS} />
      <LineField section={section} field="caption" label="Caption" value={v.caption} max={300} words="Caption saved." />
      <LineField section={section} field="alt" label="Describe the picture for someone who can't see it" value={v.alt} max={300} words="Description saved." />
      <PicturesTotal />
    </div>
  );
}
