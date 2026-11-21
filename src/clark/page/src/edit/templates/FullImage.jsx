// Full width image (row 1223), an imagecap section with a body of version 2: its Edit part (edit/templates/ImageCap.jsx hands over to it).
// No image: one drop area. With an image: it fills the content width (rounded corners) with ONE icon toolbar under it (FullImageBar.jsx),
// a focus dot, a height handle, Crop (FullImageCrop.jsx), the file note, "+ Add a caption" / "Remove caption", and "Describe the image".
// The page sends clark the ORIGINAL (POST /api/section-image, slot "original") and the framing as whole numbers with the words
// (logic/fullImageFrame.js bodyFields); clark makes the framed copy from them, so the page never sends one. The stage draws the original
// through the frame. A JPEG or WebP original is made a PNG (fullFrame.js) before a shape or crop, which clark can cut. Given { section }.
// Words and limits: logic/fullImageWords.js (unruled).
import { useEffect, useLayoutEffect, useRef, useState } from "preact/hooks";
import { LineField, CaptionField, saveWords, sendPicture, picturesTotal, NEAR } from "./pictureEdit.jsx";
import { classicLook } from "../startingText.js";
import { samplePicture } from "../samplePicture.js";
import { Bar } from "./FullImageBar.jsx";
import { Crop } from "./FullImageCrop.jsx";
import { shrink, TYPES } from "./shrink.js";
import { pngOf } from "./fullFrame.js";
import { say } from "../../stores/changes.js";
import { data } from "../../stores/report.js";
import { picturesOf, stored } from "../../templates/pictures.jsx";
import { safeImage } from "../../templates/safe.js";
import { cleanFrame, frameOfBody, bodyFields, regionOf, aspectOf, cuts, ratioFor, ratioLimits, drawnWide, outSize, baseOf, applyCrop, useWholeImage, nudgeFocus } from "../../logic/fullImageFrame.js";
import { WORDS as W, fileNote, PRINT_WIDE, SMALL_WIDE, MOST_BYTES, SLOT_ORIGINAL as ORIGINAL } from "../../logic/fullImageWords.js";

const pct = (n) => `${(n * 100).toFixed(3)}%`;

// The size of the stored original, once it has loaded.
function useNatural(url) {
  const [nat, setNat] = useState(null);
  useEffect(() => {
    if (!url) { setNat(null); return undefined; }
    const img = new Image();
    let live = true;
    img.onload = () => { if (live && img.naturalWidth) setNat({ w: img.naturalWidth, h: img.naturalHeight }); };
    img.src = url;
    return () => { live = false; };
  }, [url]);
  return nat;
}

function useWide(ref) {
  const [w, setW] = useState(1000);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const read = () => { const n = Math.round(el.getBoundingClientRect().width); if (n > 0) setW(n); };
    read();
    if (typeof ResizeObserver === "undefined") return undefined;
    const ro = new ResizeObserver(read);
    ro.observe(el);
    return () => ro.disconnect();
  });
  return w;
}

export function Edit({ section }) {
  const v = stored(section) || {};
  const pics = picturesOf(v);
  const originalUrl = typeof pics[ORIGINAL] === "string" ? pics[ORIGINAL] : "";
  const shownUrl = safeImage(originalUrl);
  const info = useNatural(shownUrl);
  const frame = frameOfBody(v);
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const [cropping, setCropping] = useState(false);
  const [live, setLive] = useState(null);
  const [capOpen, setCapOpen] = useState(!!v.caption);
  const wrap = useRef(null), stage = useRef(null), input = useRef(null), liveRef = useRef(null), timer = useRef(0);
  const wide = useWide(wrap);
  useEffect(() => { if (v.caption) setCapOpen(true); }, [v.caption]);
  useEffect(() => () => clearTimeout(timer.current), []);

  const eff = live || frame;
  const region = info ? regionOf(info, eff) : null;
  const ar = info ? aspectOf(info, eff) : 1;
  const out = info ? outSize(info, eff) : { w: wide, h: wide };
  const dw = region ? drawnWide(eff, out.w, wide) : wide;
  const high = dw / ar;
  const small = !!info && baseOf(info, eff).w < SMALL_WIDE;

  // ---- saving (a change is the framing as whole numbers, with the words; a shape or crop of a JPEG or WebP first sends it as a PNG) ----
  async function commit(next, said = W.framed) {
    if (busy || !info) return false;
    next = cleanFrame(next);
    setBusy(true);
    try {
      if ((next.shape || next.crop) && !originalUrl.startsWith("data:image/png")) {
        const made = await pngOf(originalUrl);
        if (!made.ok) { say("problem", made.message || W.notFramed); return false; }
        if (!(await sendPicture(section, ORIGINAL, made.data, said))) return false;       // a new original starts from no framing: the whole is saved next
      }
      return !!(await saveWords(section, { ...bodyFields(next), from_w: v.from_w }, said));
    } finally { setBusy(false); setLive(null); liveRef.current = null; }
  }
  const later = (next) => {                  // a key press: draw now, save when the keys stop
    liveRef.current = next; setLive(next);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => { const n = liveRef.current; if (n) commit(n); }, 600);
  };

  async function take(file) {
    if (!file || busy) return;
    if (!TYPES.includes(file.type)) { say("problem", W.notAnImage); return; }
    setBusy(true);
    try {
      const made = await shrink(file, { longest: 8000, widest: PRINT_WIDE, most: MOST_BYTES });
      if (!made.ok) { say("problem", made.message); return; }
      const said = originalUrl ? W.replaced : W.added;
      if (!(await sendPicture(section, ORIGINAL, made.data, said))) return;             // clark makes the framed copy; a new image starts from no framing
      if (made.from && made.from > made.width) await saveWords(section, { from_w: made.from }, said);
    } finally { setBusy(false); setLive(null); }
  }
  async function remove() {
    if (busy) return;
    setBusy(true);
    try { await sendPicture(section, ORIGINAL, null, W.removed); } finally { setBusy(false); setLive(null); }
  }
  const pick = () => input.current && input.current.click();
  const file = (
    <input ref={input} type="file" accept={TYPES.join(",")} class="tpl-file" tabIndex={-1} aria-hidden="true"
      onChange={(e) => { const f = e.target.files && e.target.files[0]; e.target.value = ""; take(f); }} />
  );
  const onDrop = (e) => {
    e.preventDefault(); setOver(false);
    const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) take(f);
  };

  // ---- the height handle and the focus dot ----
  const grab = useRef(null);
  const heightDown = (e) => {
    e.preventDefault();
    e.currentTarget.setPointerCapture(e.pointerId);
    grab.current = { y: e.clientY, h: high, moved: false };
  };
  const heightMove = (e) => {
    const g = grab.current;
    if (!g || e.clientY === g.y) return;
    g.moved = true;
    const next = cleanFrame({ ...frame, shape: "free", ratio: ratioFor(dw, g.h + (e.clientY - g.y), window.innerHeight, g.h) });
    liveRef.current = next; setLive(next);
  };
  const heightUp = () => {
    const g = grab.current;
    grab.current = null;
    if (g && g.moved && liveRef.current) commit(liveRef.current); else { setLive(null); liveRef.current = null; }
  };
  const heightKey = (e) => {
    const step = { ArrowUp: -1, ArrowDown: 1 }[e.key];
    if (!step || busy) return;
    e.preventDefault();
    const now = liveRef.current ? aspectOf(info, liveRef.current) : ar;
    const h = dw / now + step * (e.shiftKey ? 40 : 10);
    later(cleanFrame({ ...frame, shape: "free", ratio: ratioFor(dw, h, window.innerHeight, high) }));
  };
  const lim = ratioLimits(dw, window.innerHeight);
  const vertical = !!region && !!info && ar > (info ? regionBaseAspect(info, eff) : 1);
  const dotShown = !!info && cuts(info, eff);
  const dotRef = useRef(null), dotGrab = useRef(false);
  const dotAt = (e) => {
    const r = stage.current.querySelector(".fi-box").getBoundingClientRect();
    const fx = (e.clientX - r.left) / r.width, fy = (e.clientY - r.top) / r.height;
    const next = cleanFrame({ ...frame, ...(vertical ? { fy } : { fx }) });
    liveRef.current = next; setLive(next);
  };
  const dotKey = (e) => {
    const d = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[e.key];
    if (!d || busy) return;
    e.preventDefault();
    const now = liveRef.current || frame;
    const key = vertical ? "fy" : "fx", sign = vertical ? d[1] : d[0];
    if (!sign) return;
    later(nudgeFocus(now, key, sign));
  };

  // ---- the toolbar ----
  const shapeNow = eff.shape || "whole";
  const bar = {
    shape: shapeNow, fit: eff.fit, fill: eff.fill || "blur", small, busy,
    canReset: !!(frame.shape || frame.crop || frame.fx !== undefined || frame.fy !== undefined || frame.fit || frame.fill),
    onShape: (s) => commit(s === "free" ? { ...frame, shape: "free", ratio: ratioFor(dw, high, window.innerHeight, high) } : { ...frame, shape: s === "whole" ? undefined : s, ratio: undefined }),
    onCrop: () => setCropping(true),
    onReset: () => commit({}, W.resetDone),
    onFit: (f) => commit({ ...frame, fit: f }),
    onFill: (f) => commit({ ...frame, fill: f }),
    onReplace: pick, onRemove: remove,
  };

  if (!shownUrl) {
    return (
      <div class="tpl-edit tpl-full-edit">
        {classicLook() ? <img src={samplePicture(0)} alt="" class="tpl-pic-sample" data-sample aria-hidden="true" /> : null}
        <div class={`fi-drop${over ? " over" : ""}`} data-slot="image" onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={onDrop}>
          <button type="button" class="btn sm" data-act="pick" disabled={busy} onClick={pick}>{W.choose}</button>
          <span class="quiet">{busy ? W.making : W.drop}</span>
        </div>
        <p class="quiet tpl-hint">{W.hint}</p>
        {file}
      </div>
    );
  }

  if (!info) return <div class="tpl-edit tpl-full-edit" aria-busy="true"><p class="quiet" role="status">{W.making}</p></div>;
  const fillBlur = dw < wide && (eff.fill || "blur") === "blur";
  const pic = {
    width: pct(info.w / region.w), left: pct(-region.x / region.w), top: pct(-region.y / region.h),
  };
  const dotFx = eff.fx === undefined ? 0.5 : eff.fx, dotFy = eff.fy === undefined ? 0.5 : eff.fy;
  const note = fileNote({ w: info.w, from: v.from_w }, out.w);
  return (
    <div class="tpl-edit tpl-full-edit">
      <div class="fi-wrap" ref={wrap}>
        {cropping ? (
          <Crop src={shownUrl} info={info} start={frame.crop}
            onApply={(b) => { setCropping(false); commit(applyCrop(frame, b), W.cropped); }}
            onCancel={() => setCropping(false)} onWhole={() => { setCropping(false); commit(useWholeImage(frame), W.cropped); }} />
        ) : (
          <div class={`fi-stage fi-fill-${eff.fill || "blur"}${over ? " over" : ""}`} ref={stage} style={{ height: `${high}px` }} data-shape={shapeNow}
            onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={onDrop}>
            {fillBlur ? <img class="fi-bg" src={shownUrl} alt="" aria-hidden="true" /> : null}
            <div class="fi-box" style={{ width: `${dw}px`, height: `${high}px` }}>
              <img class="fi-pic" src={shownUrl} alt={v.alt || ""} style={pic} draggable={false} />
              {dotShown ? (
                <div class="fi-dot" ref={dotRef} role="slider" tabIndex={0} aria-label={W.focus} aria-description={W.focusHelp} data-focus-dot
                  aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.round((vertical ? dotFy : dotFx) * 100)}
                  aria-valuetext={(vertical ? W.down : W.across)(Math.round((vertical ? dotFy : dotFx) * 100))}
                  style={{ left: pct(dotFx), top: pct(dotFy) }}
                  onPointerDown={(e) => { e.preventDefault(); e.currentTarget.setPointerCapture(e.pointerId); dotGrab.current = true; }}
                  onPointerMove={(e) => { if (dotGrab.current) dotAt(e); }}
                  onPointerUp={() => { dotGrab.current = false; if (liveRef.current) commit(liveRef.current); }}
                  onKeyDown={dotKey} />
              ) : null}
            </div>
            <div class="fi-handle" role="slider" tabIndex={0} aria-label={W.height} aria-orientation="vertical" data-height-handle
              aria-valuemin={Math.round(dw / lim.hi)} aria-valuemax={Math.round(dw / lim.lo)} aria-valuenow={Math.round(high)} aria-valuetext={W.pixels(Math.round(high))}
              onPointerDown={heightDown} onPointerMove={heightMove} onPointerUp={heightUp} onPointerCancel={heightUp} onKeyDown={heightKey} />
          </div>
        )}
      </div>
      {cropping ? null : <Bar a={bar} />}
      {cropping ? null : <p class="quiet fi-file" role="status" data-file-note>{note}</p>}
      {capOpen ? (
        <>
          <CaptionField section={section} field="caption" label={W.caption} value={v.caption} max={300} words={W.captionSaved} />
          <div><button type="button" class="btn sm quiet" data-act="caption-out" onClick={async () => { await saveWords(section, { caption: "" }, W.captionSaved); setCapOpen(false); }}>{W.removeCaption}</button></div>
        </>
      ) : <div><button type="button" class="btn sm quiet" data-act="caption-add" onClick={() => setCapOpen(true)}>{W.addCaption}</button></div>}
      <LineField section={section} field="alt" label={W.describe} value={v.alt} max={300} words={W.altSaved} />
      {!v.alt ? <p class="fi-red" data-alt-note>{W.describeNote}</p> : null}
      <Total />
      {file}
    </div>
  );
}

// The aspect of the frame's base (the crop or the whole), for which side the shape cuts.
function regionBaseAspect(info, frame) {
  const c = frame && frame.crop;
  return c ? (c.w * info.w) / (c.h * info.h) : info.w / info.h;
}

// The running total of the images in the report against the 5 MB a published page can hold (the framed copies only: the original is not in the page).
function Total() {
  const n = picturesTotal(data.value && data.value.report_sections);
  if (!n) return null;
  const mb = (n / (1024 * 1024)).toFixed(1);
  return (
    <p class={`quiet tpl-total${n >= NEAR ? " near" : ""}`} role="status">
      {W.total(mb)}
      {n >= NEAR ? W.totalNear : ""}
    </p>
  );
}
