// Row 1232: Text and Image Side by Side (store type "textimage", a body of version 2): its Edit part (TextImage.jsx hands over to it).
// A heading box, the words in the one rich editor, and the image with ONE icon toolbar docked under it: Shape, where the image sits (this
// width's two places, then Swap), the image width (full width only), Crop… and Reset framing, Replace and Remove. A focus dot and the Crop
// box are the Full width image's (FullImageCrop.jsx, logic/fullImageFrame.js); the page sends clark the ORIGINAL (slot "original") and the
// framing as whole numbers with the words, and clark makes the framed copy, so the page never sends one. A JPEG or WebP original is made a
// PNG before a shape or crop (fullFrame.js). Each change is one saveWords or one picture send: one step, one Undo.
// logic/textImageSideWords.js. Given { section }.
import { useLayoutEffect, useRef, useState, useEffect } from "preact/hooks";
import { LineField, CaptionField, saveWords, sendPicture, wordsOf, PicturesTotal } from "./pictureEdit.jsx";
import { RichField } from "../RichField.jsx";
import { Crop } from "./FullImageCrop.jsx";
import { useNatural } from "./FullImage.jsx";
import { shrink, TYPES } from "./shrink.js";
import { pngOf } from "./fullFrame.js";
import { say } from "../../stores/changes.js";
import { picturesOf, stored } from "../../templates/pictures.jsx";
import { safeImage } from "../../templates/safe.js";
import { frameOfBody, bodyFields, applyCrop, useWholeImage } from "../../logic/fullImageFrame.js";
import { MOST_BYTES } from "../../logic/fullImageWords.js";
import { WORDS as W, PRINT_WIDE, SLOT_ORIGINAL as ORIGINAL, SHARES, SHAPES, placesFor, placeField, placeOf, swapped, cuts, fileNote } from "../../logic/textImageSideWords.js";

const esc = (t) => String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const richValue = (v) => (typeof v.html === "string" && v.html ? v.html : (Array.isArray(v.words) ? v.words : []).filter((p) => typeof p === "string" && p).map((p) => `<p>${esc(p)}</p>`).join(""));
const noBreaks = (html) => html.replace(/[\r\n]+/g, " ");
const thousand = (n) => Math.max(0, Math.min(1000, Math.round(n)));

const P = {
  fill: <><rect x="3" y="3" width="14" height="14" rx="1.5" /><path d="M10 6v8M8 8l2-2 2 2M8 12l2 2 2-2" /></>,
  wide: <rect x="2" y="6" width="16" height="9" rx="1.5" />,
  "4:3": <rect x="3" y="5" width="14" height="10.5" rx="1.5" />,
  square: <rect x="4" y="4" width="12" height="12" rx="1.5" />,
  whole: <rect x="3" y="5" width="14" height="10" rx="1.5" strokeDasharray="2 2" />,
  left: <><rect x="2" y="4" width="7" height="12" rx="1" /><path d="M12 7h6M12 10h6M12 13h6" /></>,
  right: <><rect x="11" y="4" width="7" height="12" rx="1" /><path d="M2 7h6M2 10h6M2 13h6" /></>,
  top: <><rect x="3" y="2" width="14" height="7" rx="1" /><path d="M3 12h14M3 15h14" /></>,
  bottom: <><rect x="3" y="11" width="14" height="7" rx="1" /><path d="M3 5h14M3 8h14" /></>,
  swap: <path d="M3 7h12l-3-3M17 13H5l3 3" />,
  third: <><rect x="2" y="4" width="16" height="12" rx="1" /><path d="M7.3 4v12" /></>,
  half: <><rect x="2" y="4" width="16" height="12" rx="1" /><path d="M10 4v12" /></>,
  two: <><rect x="2" y="4" width="16" height="12" rx="1" /><path d="M12.7 4v12" /></>,
  crop: <path d="M6 2v12h12M2 6h12v12" />,
  reset: <path d="M4 10a6 6 0 1 0 2-4.5M4 3v4h4" />,
  replace: <path d="M3 8h11l-3-3M17 12H6l3 3" />,
  remove: <path d="M4 6h12M8 6V4h4v2M6 6l1 10h6l1-10" />,
};
const Icon = ({ name }) => <svg viewBox="0 0 20 20" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">{P[name]}</svg>;
const Sep = () => <span class="fi-sep" role="separator" aria-orientation="vertical" />;
function Btn({ icon, name, on, onClick, disabled, act, danger }) {
  return (
    <button type="button" class={`fi-btn${on ? " on" : ""}${danger ? " danger" : ""}`} aria-label={name} data-tip={name} data-act={act || icon}
      aria-pressed={on === undefined ? undefined : on ? "true" : "false"} disabled={disabled} tabIndex={-1} onClick={onClick}>
      <Icon name={icon} />
    </button>
  );
}

// `a`: { half, shape, place, share, canReset, busy, ...handlers }. One tab stop; the arrow keys move along the bar.
function Bar({ a }) {
  const bar = useRef(null);
  const live = () => [...bar.current.querySelectorAll("button:not([disabled])")];
  const onKeyDown = (e) => {
    const keys = { ArrowRight: 1, ArrowLeft: -1, Home: "first", End: "last" };
    if (!(e.key in keys)) return;
    const all = live(), at = all.indexOf(document.activeElement);
    if (!all.length) return;
    e.preventDefault();
    const k = keys[e.key];
    const to = k === "first" ? 0 : k === "last" ? all.length - 1 : (at + k + all.length) % all.length;
    all.forEach((b, i) => { b.tabIndex = i === to ? 0 : -1; });
    all[to].focus();
  };
  const onFocusIn = (e) => { if (e.target.tagName === "BUTTON") live().forEach((b) => { b.tabIndex = b === e.target ? 0 : -1; }); };
  useEffect(() => {
    const all = [...bar.current.querySelectorAll("button")];
    if (all.some((b) => b.tabIndex === 0 && !b.disabled)) return;
    const f = all.find((b) => !b.disabled);
    all.forEach((b) => { b.tabIndex = b === f ? 0 : -1; });
  });
  const d = a.busy;
  return (
    <div class="fi-bar tpl-sbs-bar" role="toolbar" aria-label={W.toolbar} aria-orientation="horizontal" ref={bar} onKeyDown={onKeyDown} onFocusIn={onFocusIn}>
      <span class="tpl-sbs-grp" role="group" aria-label={W.groups.shape}>
        {SHAPES.map((s) => <Btn key={s} icon={s === "fill" && a.half ? "wide" : s} act={`shape-${s}`} name={s === "fill" ? (a.half ? W.wide : W.fill) : W.shape[s]} on={a.shape === s} disabled={d} onClick={() => a.onShape(s)} />)}
      </span>
      <Sep />
      <span class="tpl-sbs-grp" role="group" aria-label={W.groups.where}>
        {placesFor(a.half).map((p) => <Btn key={p} icon={p} act={`place-${p}`} name={W.place[p]} on={a.place === p} disabled={d} onClick={() => a.onPlace(p)} />)}
        <Btn icon="swap" name={W.swap} disabled={d} onClick={a.onSwap} />
      </span>
      {a.half ? null : <>
        <Sep />
        <span class="tpl-sbs-grp" role="group" aria-label={W.groups.width}>
          {SHARES.map((s) => <Btn key={s} icon={s} act={`share-${s}`} name={W.share[s]} on={a.share === s} disabled={d} onClick={() => a.onShare(s)} />)}
        </span>
      </>}
      <Sep />
      <span class="tpl-sbs-grp" role="group" aria-label={W.groups.crop}>
        <Btn icon="crop" name={W.crop} disabled={d} onClick={a.onCrop} />
        <Btn icon="reset" name={W.reset} disabled={d || !a.canReset} onClick={a.onReset} />
      </span>
      <span class="fi-grow" />
      <Btn icon="replace" name={W.replace} disabled={d} onClick={a.onReplace} />
      <Btn icon="remove" name={W.remove} danger disabled={d} onClick={a.onRemove} />
    </div>
  );
}

export function Edit({ section }) {
  const v = stored(section) || {};
  const pics = picturesOf(v);
  const originalUrl = typeof pics[ORIGINAL] === "string" ? pics[ORIGINAL] : "";
  const framedUrl = safeImage(typeof pics.image === "string" ? pics.image : "") || safeImage(originalUrl);
  const info = useNatural(safeImage(originalUrl));
  const root = useRef(null), stage = useRef(null), input = useRef(null), liveRef = useRef(null), timer = useRef(0), dotGrab = useRef(false);
  const [half, setHalf] = useState(false);
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const [cropping, setCropping] = useState(false);
  const [live, setLive] = useState(null);
  useLayoutEffect(() => { if (root.current) setHalf(!!root.current.closest(".slot-left, .slot-right")); });
  useEffect(() => () => clearTimeout(timer.current), []);

  const shape = SHAPES.includes(v.shape) ? v.shape : "fill";
  const place = placeOf(v, half);
  const share = v.share === "third" || v.share === "two" ? v.share : "half";
  const at = live || { fx: Number.isInteger(v.fx) ? v.fx : 500, fy: Number.isInteger(v.fy) ? v.fy : 500 };
  const cropNow = frameOfBody(v).crop;
  const canReset = !!(v.shape || v.crop || v.fx !== undefined || v.fy !== undefined);

  // ---- saving: the framing is always sent whole (a key given as "" is taken out); a shape or crop of a JPEG or WebP first sends a PNG ----
  async function put(frame, said) {
    if (busy || !originalUrl) return false;
    setBusy(true);
    try {
      const f = { shape: frame.shape === "fill" ? "" : frame.shape || "", fx: frame.fx === 500 ? "" : frame.fx, fy: frame.fy === 500 ? "" : frame.fy, crop: frame.crop || "" };
      if (cuts(f.shape, f.crop) && !originalUrl.startsWith("data:image/png")) {
        const made = await pngOf(originalUrl);
        if (!made.ok) { say("problem", made.message || W.notFramed); return false; }
        if (!(await sendPicture(section, ORIGINAL, made.data, said))) return false;      // a new original starts from no framing: the whole is saved next
      }
      return !!(await saveWords(section, f, said));
    } finally { setBusy(false); setLive(null); liveRef.current = null; }
  }
  const now = () => ({ shape, fx: at.fx, fy: at.fy, crop: Array.isArray(v.crop) ? v.crop : "" });
  const later = (next) => {                  // a key press: draw now, save when the keys stop
    liveRef.current = next; setLive({ fx: next.fx, fy: next.fy });
    clearTimeout(timer.current);
    timer.current = setTimeout(() => { const n = liveRef.current; if (n) put(n, W.framed); }, 600);
  };
  async function take(file) {
    if (!file || busy) return;
    if (!TYPES.includes(file.type)) { say("problem", W.notFramed); return; }
    setBusy(true);
    try {
      const made = await shrink(file, { longest: 8000, widest: PRINT_WIDE, most: MOST_BYTES });
      if (!made.ok) { say("problem", made.message); return; }
      const said = originalUrl ? W.replaced : W.added;
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
  const dotAt = (e) => {
    const r = stage.current.getBoundingClientRect();
    const next = { ...now(), fx: thousand(((e.clientX - r.left) / r.width) * 1000), fy: thousand(((e.clientY - r.top) / r.height) * 1000) };
    liveRef.current = next; setLive({ fx: next.fx, fy: next.fy });
  };
  const dotKey = (e) => {
    const d = { ArrowLeft: [-50, 0], ArrowRight: [50, 0], ArrowUp: [0, -50], ArrowDown: [0, 50] }[e.key];
    if (!d || busy) return;
    e.preventDefault();
    const n = liveRef.current || now();
    later({ ...n, fx: thousand(n.fx + d[0]), fy: thousand(n.fy + d[1]) });
  };

  const bar = {
    half, shape, place, share, canReset, busy,
    onShape: (s) => put({ ...now(), shape: s }, W.framed),
    onPlace: (p) => { if (p !== place) saveWords(section, placeField(p), W.moved); },
    onSwap: () => saveWords(section, placeField(swapped(place)), W.swapped),
    onShare: (s) => saveWords(section, { share: s === "half" ? "" : s }, W.moved),
    onCrop: () => setCropping(true),
    onReset: () => put({ shape: "fill", fx: 500, fy: 500, crop: "" }, W.resetDone),
    onReplace: pick, onRemove: remove,
  };
  const empty = !originalUrl && !v.html && !(Array.isArray(v.words) && v.words.length);
  const file = (
    <input ref={input} type="file" accept={TYPES.join(",")} class="tpl-file" tabIndex={-1} aria-hidden="true"
      onChange={(e) => { const f = e.target.files && e.target.files[0]; e.target.value = ""; take(f); }} />
  );
  return (
    <div class={`tpl-edit tpl-sbs-edit share-${share} pos-${place}${half ? " is-half" : ""} shape-${shape === "4:3" ? "43" : shape}`} ref={root}>
      {empty ? <p class="quiet tpl-hint">{W.empty}</p> : null}
      <LineField section={section} field="heading" label={W.heading} hint={W.optional} value={v.heading} max={120} words={W.headingSaved} />
      <div class="tpl-sbs-edit-grid">
        <div class="tpl-pic-field tpl-sbs-edit-words">
          <label>{W.text}</label>
          <RichField field="textimage" id={section.id} value={richValue(v)} label={`${section.title} text`} empty="Click to write."
            save={(html) => saveWords(section, { html: noBreaks(html), words: [] }, "Text saved.")} />
        </div>
        <div class="tpl-sbs-edit-pic">
          {cropping && info ? (
            <Crop src={safeImage(originalUrl)} info={info} start={cropNow}
              onApply={(b) => { setCropping(false); put({ ...now(), crop: bodyFields(applyCrop({}, b)).crop }, W.cropped); }}
              onCancel={() => setCropping(false)} onWhole={() => { setCropping(false); put({ ...now(), crop: "" }, W.cropped); }} />
          ) : originalUrl ? (
            <div class={`tpl-sbs-edit-frame${over ? " over" : ""}`} ref={stage} style={{ position: "relative" }} data-slot="image"
              onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={onDrop}>
              <img src={framedUrl} alt={v.alt || ""} draggable={false} style={{ maxWidth: "100%", objectPosition: `${at.fx / 10}% ${at.fy / 10}%` }} />
              {shape !== "whole" ? (
                <div class="fi-dot" role="slider" tabIndex={0} aria-label={W.focus} data-focus-dot aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.round(at.fx / 10)}
                  style={{ left: `${at.fx / 10}%`, top: `${at.fy / 10}%` }}
                  onPointerDown={(e) => { e.preventDefault(); e.currentTarget.setPointerCapture(e.pointerId); dotGrab.current = true; }}
                  onPointerMove={(e) => { if (dotGrab.current) dotAt(e); }}
                  onPointerUp={() => { dotGrab.current = false; if (liveRef.current) put(liveRef.current, W.framed); }}
                  onKeyDown={dotKey} />
              ) : null}
            </div>
          ) : (
            <div class={`fi-drop${over ? " over" : ""}`} data-slot="image" onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={onDrop}>
              <button type="button" class="btn sm" data-act="pick" disabled={busy} onClick={pick}>{W.choose}</button>
              <span class="quiet">{busy ? W.making : W.drop}</span>
            </div>
          )}
          {originalUrl && !cropping ? <Bar a={bar} /> : null}
          {originalUrl && !cropping && info ? <p class="quiet fi-file tpl-sbs-note" role="status" data-file-note>{fileNote(info.w, info.h)}</p> : null}
        </div>
      </div>
      <LineField section={section} field="alt" label={W.describe} hint={W.describeHint} value={v.alt} max={300} words={W.altSaved} />
      {originalUrl && !v.alt ? <p class="fi-red tpl-sbs-red" data-alt-note>{W.noDescription}</p> : null}
      <CaptionField section={section} field="caption" label={W.caption} hint={W.optional} empty={W.optional} value={v.caption} max={300} words={W.captionSaved} />
      <PicturesTotal />
      {file}
    </div>
  );
}
