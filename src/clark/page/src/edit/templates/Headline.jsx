// Headline band (#96), store type "headline": its Edit part, filled in place. The message, the button's words and its link, and an
// optional picture with its description; each saved on its own (one change, one step, one Undo, place "report"); the picture through
// POST /api/section-image (pictureEdit.jsx). A link is https:, mailto: or a place on the page (#): anything else is said before it
// is sent. Given { section, tools }. Limits are headline.py's.
import { LineField, PictureSlot, PicturesTotal } from "./pictureEdit.jsx";
import { picturesOf, stored } from "../../templates/pictures.jsx";
import { safeHref } from "../../templates/safe.js";

const WORDS = { added: "Picture added.", removed: "Picture taken out." };
export const BAD_LINK = "A button's link must start with https:// or mailto:, or go to a place on the page (#). Check the link and try again.";

export function Edit({ section }) {
  const v = stored(section) || {};
  const image = picturesOf(v).image || "";
  const empty = !image && !v.words && !(v.label && v.href);
  return (
    <div class="tpl-edit tpl-band-edit">
      {empty ? <p class="quiet tpl-hint">Write the message the report opens with. Until then this section stays out of the published page.</p> : null}
      <LineField section={section} field="words" label="Message" value={v.words} max={400} words="Message saved." />
      <div class="tpl-band-btnrow">
        <LineField section={section} field="label" label="Button words (optional)" value={v.label} max={40} words="Button saved." />
        <LineField section={section} field="href" label="Button link" value={v.href} max={2000} hint="https://" words="Link saved."
          check={(t) => (t && !safeHref(t) ? BAD_LINK : "")} />
      </div>
      {v.label && !v.href ? <p class="quiet">The button shows once it has a link.</p> : null}
      <PictureSlot section={section} slot="image" image={image} label="Picture (optional)" words={WORDS} />
      {image ? <LineField section={section} field="alt" label="Describe the picture for someone who can't see it" value={v.alt} max={300} words="Description saved." /> : null}
      <PicturesTotal />
    </div>
  );
}
