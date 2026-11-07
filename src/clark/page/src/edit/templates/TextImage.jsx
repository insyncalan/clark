// Text and image (#96), store type "textimage": its Edit part, filled in place. The words, the picture, its caption and its
// description, and which side the picture sits on; each saved on its own (one change, one step, one Undo, place "report"); the
// picture through POST /api/section-image (pictureEdit.jsx). Given { section, tools }. Limits are textimage.py's.
import { LineField, PictureSlot, PicturesTotal, saveWords, wordsOf } from "./pictureEdit.jsx";
import { RichField } from "../RichField.jsx";
import { picturesOf, stored } from "../../templates/pictures.jsx";

// The words as the rich editor is given them (row 1005): the stored `html`, or the old lines (plain text, escaped, one paragraph each).
// Never the raw stored text: RichField draws cleanHtml of this.
const esc = (t) => String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
export const richValue = (v) => (typeof v.html === "string" && v.html ? v.html : (Array.isArray(v.words) ? v.words : []).filter((p) => typeof p === "string" && p).map((p) => `<p>${esc(p)}</p>`).join(""));
const noBreaks = (html) => html.replace(/[\r\n]+/g, " ");

const WORDS = { added: "Picture added.", removed: "Picture taken out." };

export function Edit({ section }) {
  const v = stored(section) || {};
  const image = picturesOf(v).image || "";
  const left = v.side === "left";
  const empty = !image && !(Array.isArray(v.words) && v.words.length) && !v.html;
  return (
    <div class={`tpl-edit tpl-ti-edit${left ? " pic-left" : ""}`}>
      {empty ? <p class="quiet tpl-hint">Add some words, a picture or both. Until then this section stays out of the published page.</p> : null}
      <div class="tpl-ti-grid">
        <div class="tpl-pic-field">
          <label>Text</label>
          <RichField field={`textimage-${section.id}`} id={section.id} value={richValue(v)} label={`${section.title} text`} empty="Click to write."
            save={(html) => saveWords(section, { html: noBreaks(html), words: [] }, "Text saved.")} />
        </div>
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
