// Text and image (#96), store type "textimage": its Edit part, filled in place. The words, the picture, its caption and its
// description, and which side the picture sits on; each saved on its own (one change, one step, one Undo, place "report"); the
// picture through POST /api/section-image (pictureEdit.jsx). Given { section, tools }. Limits are textimage.py's.
import { LineField, WordsField, PictureSlot, PicturesTotal, saveWords, wordsOf } from "./pictureEdit.jsx";
import { picturesOf, stored } from "../../templates/pictures.jsx";

const WORDS = { added: "Picture added.", removed: "Picture taken out." };

export function Edit({ section }) {
  const v = stored(section) || {};
  const image = picturesOf(v).image || "";
  const left = v.side === "left";
  const empty = !image && !(Array.isArray(v.words) && v.words.length);
  return (
    <div class={`tpl-edit tpl-ti-edit${left ? " pic-left" : ""}`}>
      {empty ? <p class="quiet tpl-hint">Add some words, a picture or both. Until then this section stays out of the published page.</p> : null}
      <div class="tpl-ti-grid">
        <WordsField section={section} field="words" label="Text (each line is a paragraph)" value={v.words} max={20 * 2001} words="Text saved." />
        <div class="tpl-ti-pic">
          <PictureSlot section={section} slot="image" image={image} label="Picture" words={WORDS} />
          <LineField section={section} field="caption" label="Caption" value={v.caption} max={300} words="Caption saved." />
          <LineField section={section} field="alt" label="Describe the picture for someone who can't see it" value={v.alt} max={300} words="Description saved." />
          <fieldset class="tpl-side">
            <legend>Picture on the</legend>
            {[["right", "Right"], ["left", "Left"]].map(([k, w]) => (
              <label key={k}><input type="radio" name={`side-${section.id}`} value={k} checked={(left ? "left" : "right") === k}
                onChange={() => { if ((wordsOf(section).side || "right") !== k) saveWords(section, { side: k === "left" ? "left" : "" }, "Picture moved."); }} /> {w}</label>
            ))}
          </fieldset>
        </div>
      </div>
      <PicturesTotal />
    </div>
  );
}
