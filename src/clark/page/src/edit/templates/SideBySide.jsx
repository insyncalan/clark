// Row 1232, Text and Image Side by Side (a textimage section with a body of version 2): its Edit part (edit/templates/TextImage.jsx hands over
// to it). The heading box, the words in the one rich editor, and the image as clark frames it (the stored framed copy: what the report shows)
// with the ONE icon toolbar docked under it (role=toolbar; the same bar parts as the Full width image, FullImageBar.jsx): Shape, Position
// (this width's two choices, then Swap), Image width (full width only), and Replace and Remove at the right; the file note; the description
// and the caption. Position follows the section width: a section that shares its row is half width (top or underneath), any other is full
// width (left or right, a third, a half or two thirds). Each choice is its own saved change (one step, one Undo). The image goes to clark
// as the ORIGINAL (POST /api/section-image, slot "original"); clark makes the framed copy. Not here yet: Crop and Reset, the focus dot, the
// 3,000 px upload note in its changing form, the arrow keys on the dot. Words: logic/textImageEdit.js. Given { section }.
import { useEffect, useRef, useState } from "preact/hooks";
import { LineField, CaptionField, saveWords, sendPicture, picturesTotal, NEAR } from "./pictureEdit.jsx";
import { RichField } from "../RichField.jsx";
import { Btn, Sep, barKeys, restTab } from "./FullImageBar.jsx";
import { useNatural } from "./FullImage.jsx";
import { shrink, TYPES } from "./shrink.js";
import { pngOf } from "./fullFrame.js";
import { startOr } from "../startingText.js";
import { say } from "../../stores/changes.js";
import { data } from "../../stores/report.js";
import { picturesOf, stored } from "../../templates/pictures.jsx";
import { safeImage } from "../../templates/safe.js";
import { slots } from "../../logic/placement.js";
import { WORDS as W, MOST_BYTES, SLOT_ORIGINAL as ORIGINAL } from "../../logic/fullImageWords.js";
import { TOOLBAR, GROUP, NAMES, FIELDS, SHARES, isHalf, positions, chosen, setting, swapped, shapes, fileNote, PRINT_WIDE } from "../../logic/textImageEdit.js";

const noBreaks = (html) => html.replace(/[\r\n]+/g, " ");
const richOf = (v) => (typeof v.html === "string" && v.html ? v.html : "");
const withHint = (label, hint) => <>{label}<span class="ti-opt">{hint}</span></>;
const CUTS = ["4:3", "square"];            // the shapes clark cuts: only from a PNG original

export function SideBySide({ section }) {
  const v = stored(section) || {};
  const original = typeof picturesOf(v)[ORIGINAL] === "string" ? picturesOf(v)[ORIGINAL] : "";
  const framed = safeImage(picturesOf(v).image || "");
  const info = useNatural(safeImage(original));
  const half = isHalf((slots((data.value && data.value.report_sections) || [])[section.id]) || "full");
  const c = chosen(v);
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const input = useRef(null), bar = useRef(null);
  const { onKeyDown, onFocusIn } = barKeys(bar);
  useEffect(() => restTab(bar.current));

  async function put(fields, said) {
    if (busy) return;
    setBusy(true);
    try {
      if (CUTS.includes(fields.shape) && original && !original.startsWith("data:image/png")) {
        const made = await pngOf(original);
        if (!made.ok) { say("problem", made.message || W.notFramed); return; }
        if (!(await sendPicture(section, ORIGINAL, made.data, said))) return;      // a new original starts from no framing: the choice is saved next
      }
      await saveWords(section, fields, said);
    } finally { setBusy(false); }
  }
  async function take(file) {
    if (!file || busy) return;
    if (!TYPES.includes(file.type)) { say("problem", W.notAnImage); return; }
    setBusy(true);
    try {
      const made = await shrink(file, { longest: 8000, widest: PRINT_WIDE, most: MOST_BYTES });
      if (!made.ok) { say("problem", made.message); return; }
      const said = original ? W.replaced : W.added;
      if (!(await sendPicture(section, ORIGINAL, made.data, said))) return;
      if (made.from && made.from > made.width) await saveWords(section, { from_w: made.from }, said);
    } finally { setBusy(false); }
  }
  async function remove() {
    if (busy) return;
    setBusy(true);
    try { await sendPicture(section, ORIGINAL, null, W.removed); } finally { setBusy(false); }
  }
  const pick = () => input.current && input.current.click();
  const onDrop = (e) => {
    e.preventDefault(); setOver(false);
    const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) take(f);
  };
  const file = (
    <input ref={input} type="file" accept={TYPES.join(",")} class="tpl-file" tabIndex={-1} aria-hidden="true"
      onChange={(e) => { const f = e.target.files && e.target.files[0]; e.target.value = ""; take(f); }} />
  );

  const empty = !framed && !richOf(v) && !(Array.isArray(v.words) && v.words.length);
  const cls = ["tpl-sbs", `share-${c.share}`, c.side === "left" ? "pos-left" : "pos-right", `hpos-${c.half}`,
    `shape-${c.shape === "4:3" ? "43" : c.shape}`, framed ? "" : "no-pic"].filter(Boolean).join(" ");
  const at = { objectPosition: `${(Number.isInteger(v.fx) ? v.fx : 500) / 10}% ${(Number.isInteger(v.fy) ? v.fy : 500) / 10}%` };
  const note = info ? fileNote(info.w, info.h) : "";
  return (
    <div class="tpl-edit tpl-ti-edit tpl-sbs-edit" data-half={half ? "1" : undefined}>
      {empty ? <p class="quiet tpl-hint">Add some words, an image or both. Until then this section stays out of the published page.</p> : null}
      <LineField section={section} field="heading" label={withHint(FIELDS.heading, FIELDS.optional)} value={v.heading} max={300} words={"Text saved."} />
      <div class={cls}>
        {framed ? (
          <figure class="tpl-sbs-fig">
            <div class="tpl-sbs-frame"><img src={framed} alt={v.alt || ""} style={at} draggable={false} /></div>
            <div class="fi-bar ti-bar" role="toolbar" aria-label={TOOLBAR} aria-orientation="horizontal" data-busy={busy ? "1" : undefined} ref={bar} onKeyDown={onKeyDown} onFocusIn={onFocusIn}>
              <div class="ti-grp" role="group" aria-label={GROUP.shape}>
                {shapes(half).map((s) => <Btn key={s.key} icon={s.icon} name={s.name} act={`shape-${s.key}`} on={c.shape === s.key} disabled={busy} onClick={() => put(setting("shape", s.key), W.framed)} />)}
              </div>
              <Sep />
              <div class="ti-grp" role="group" aria-label={GROUP.position}>
                {positions(half).map((p) => <Btn key={p.key} icon={p.key === "bottom" ? "under" : p.key} name={NAMES[p.key]} act={`pos-${p.key}`} on={c[p.field] === p.value} disabled={busy} onClick={() => put(setting(p.field, p.value), W.framed)} />)}
                <Btn icon="swap" name={NAMES.swap} act="swap" disabled={busy} onClick={() => put(swapped(v, half), W.framed)} />
              </div>
              {half ? null : (
                <>
                  <Sep />
                  <div class="ti-grp" role="group" aria-label={GROUP.share}>
                    {SHARES.map((k) => <Btn key={k} icon={k} name={NAMES[k]} act={`share-${k}`} on={c.share === k} disabled={busy} onClick={() => put(setting("share", k), W.framed)} />)}
                  </div>
                </>
              )}
              <span class="fi-grow" />
              <Btn icon="replace" name={NAMES.replace} act="replace" disabled={busy} onClick={pick} />
              <Btn icon="remove" name={NAMES.remove} act="remove" disabled={busy} onClick={remove} />
            </div>
            {note ? <p class="quiet fi-file ti-note" role="status" data-file-note>{note}</p> : null}
          </figure>
        ) : null}
        <div class="tpl-pic-field tpl-sbs-words">
          <label>{FIELDS.text}</label>
          <RichField field="textimage" id={section.id} value={richOf(v) || (Array.isArray(v.words) ? v.words.filter((p) => typeof p === "string" && p).map((p) => `<p>${p.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")}</p>`).join("") : "")}
            label={`${section.title} text`} empty={startOr("Click to write.", "text-image", "empty", 0)}
            save={(html) => saveWords(section, { html: noBreaks(html), words: [] }, "Text saved.")} />
        </div>
      </div>
      {framed ? null : (
        <div class={`fi-drop${over ? " over" : ""}`} data-slot="image" onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={onDrop}>
          <button type="button" class="btn sm" data-act="pick" disabled={busy} onClick={pick}>{W.choose}</button>
          <span class="quiet">{busy ? W.making : W.drop}</span>
        </div>
      )}
      {framed ? (
        <>
          <LineField section={section} field="alt" label={withHint(FIELDS.describe, FIELDS.describeHint)} value={v.alt} max={300} words={W.altSaved} />
          {!v.alt ? <p class="fi-red" data-alt-note>{FIELDS.noDescription}</p> : null}
          <CaptionField section={section} field="caption" label={FIELDS.caption} hint={FIELDS.optional} value={v.caption} max={300} words={W.captionSaved} />
        </>
      ) : null}
      <Total />
      {file}
    </div>
  );
}

function Total() {
  const n = picturesTotal(data.value && data.value.report_sections);
  if (!n) return null;
  return (
    <p class={`quiet tpl-total${n >= NEAR ? " near" : ""}`} role="status">
      {W.total((n / (1024 * 1024)).toFixed(1))}
      {n >= NEAR ? W.totalNear : ""}
    </p>
  );
}
