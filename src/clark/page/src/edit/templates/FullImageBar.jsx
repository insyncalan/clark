// Full width image (row 1223), Edit only: the ONE icon toolbar docked under the image (role=toolbar, not separate buttons). Groups with
// dividers: Shape (Whole, 16:9, Strip 3:1, Free); Crop... and Reset; for a small image only Centre or Stretch, then Fill; Replace and
// Remove at the right. Every icon has an accessible name and a tooltip on hover and focus; the arrow keys move along the bar (one tab stop).
import { useEffect, useRef } from "preact/hooks";
import { WORDS as W, SHAPES, FILLS } from "../../logic/fullImageWords.js";

const P = {
  whole: <rect x="3" y="5" width="14" height="10" rx="1.5" />,
  "16:9": <rect x="2" y="6" width="16" height="9" rx="1.5" />,
  banner: <rect x="2" y="8" width="16" height="4" rx="1" />,
  free: <><rect x="4" y="3" width="12" height="14" rx="1.5" /><path d="M10 6v8M8 8l2-2 2 2M8 12l2 2 2-2" /></>,
  crop: <path d="M6 2v12h12M2 6h12v12" />,
  reset: <path d="M4 10a6 6 0 1 0 2-4.5M4 3v4h4" />,
  centre: <><rect x="6" y="5" width="8" height="10" rx="1" /><path d="M2 5v10M18 5v10" /></>,
  stretch: <><rect x="2" y="5" width="16" height="10" rx="1" /><path d="M5 10h10M7 8l-2 2 2 2M13 8l2 2-2 2" /></>,
  blur: <><rect x="6" y="5" width="8" height="10" rx="1" /><path d="M2 7v6M4 6v8M16 6v8M18 7v6" /></>,
  brand: <><rect x="6" y="5" width="8" height="10" rx="1" /><rect x="2" y="5" width="3" height="10" fill="currentColor" /><rect x="15" y="5" width="3" height="10" fill="currentColor" /></>,
  plain: <><rect x="6" y="5" width="8" height="10" rx="1" /><rect x="2" y="5" width="3" height="10" /><rect x="15" y="5" width="3" height="10" /></>,
  replace: <path d="M3 8h11l-3-3M17 12H6l3 3" />,
  remove: <path d="M4 6h12M8 6V4h4v2M6 6l1 10h6l1-10" />,
};
const Icon = ({ name }) => <svg viewBox="0 0 20 20" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">{P[name]}</svg>;
const Sep = () => <span class="fi-sep" role="separator" aria-orientation="vertical" />;

function Btn({ icon, name, tip, on, onClick, disabled, act }) {
  return (
    <button type="button" class={`fi-btn${on ? " on" : ""}`} aria-label={name} data-tip={tip || name} data-act={act || icon}
      aria-pressed={on === undefined ? undefined : on ? "true" : "false"} disabled={disabled} tabIndex={-1} onClick={onClick}>
      <Icon name={icon} />
    </button>
  );
}

// The arrow keys move along a bar (one tab stop), and a focused button is the tab stop; the Image gallery's bar uses the same two.
export function along(e, bar) {
  const keys = { ArrowRight: 1, ArrowLeft: -1, Home: "first", End: "last" };
  if (!(e.key in keys)) return;
  const all = [...bar.querySelectorAll("button:not([disabled])")], at = all.indexOf(document.activeElement);
  if (!all.length) return;
  e.preventDefault();
  const k = keys[e.key];
  const to = k === "first" ? 0 : k === "last" ? all.length - 1 : (at + k + all.length) % all.length;
  all.forEach((b, i) => { b.tabIndex = i === to ? 0 : -1; });
  all[to].focus();
}
export function focusAt(e, bar) { if (e.target.tagName === "BUTTON") [...bar.querySelectorAll("button:not([disabled])")].forEach((b) => { b.tabIndex = b === e.target ? 0 : -1; }); }

// `a`: { shape, fit, fill, small, canReset, busy, onShape, onCrop, onReset, onFit, onFill, onReplace, onRemove }
export function Bar({ a }) {
  const bar = useRef(null);
  const onKeyDown = (e) => along(e, bar.current);
  const onFocusIn = (e) => focusAt(e, bar.current);
  const d = a.busy;
  useEffect(() => restTab(bar.current));      // one tab stop: kept after every draw
  return (
    <div class="fi-bar" role="toolbar" aria-label={W.toolbar} aria-orientation="horizontal" data-busy={a.busy ? "1" : undefined} ref={bar} onKeyDown={onKeyDown} onFocusIn={onFocusIn}>
      {SHAPES.map((s) => <Btn key={s} icon={s} name={W.shape[s]} tip={W.shapeTip[s]} act={`shape-${s}`} on={a.shape === s} disabled={d} onClick={() => a.onShape(s)} />)}
      <Sep />
      <Btn icon="crop" name={W.crop} tip={W.cropTip} disabled={d} onClick={a.onCrop} />
      <Btn icon="reset" name={W.reset} tip={W.resetTip} disabled={d || !a.canReset} onClick={a.onReset} />
      {a.small ? <>
        <Sep />
        <Btn icon="centre" name={W.centre} act="fit-centre" on={a.fit !== "stretch"} disabled={d} onClick={() => a.onFit("centre")} />
        <Btn icon="stretch" name={W.stretch} act="fit-stretch" on={a.fit === "stretch"} disabled={d} onClick={() => a.onFit("stretch")} />
        {a.fit !== "stretch" ? <>
          <Sep />
          {FILLS.map((f) => <Btn key={f} icon={f} name={W.fill[f]} act={`fill-${f}`} on={a.fill === f} disabled={d} onClick={() => a.onFill(f)} />)}
        </> : null}
      </> : null}
      <span class="fi-grow" />
      <Sep />
      <Btn icon="replace" name={W.replace} disabled={d} onClick={a.onReplace} />
      <Btn icon="remove" name={W.remove} disabled={d} onClick={a.onRemove} />
    </div>
  );
}

// The tab stop: the first enabled button of the bar, until focus has been along it (called by the Edit part after each draw).
export function restTab(bar) {
  if (!bar) return;
  const all = [...bar.querySelectorAll("button")];
  if (all.some((b) => b.tabIndex === 0 && !b.disabled)) return;
  const f = all.find((b) => !b.disabled);
  all.forEach((b) => { b.tabIndex = b === f ? 0 : -1; });
}
