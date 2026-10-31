// The milestone timeline (#44a; FR-51): scrolls sideways inside its box, a today line and a Today button, a solid mark on each
// agreed date, a ghost on the expected date of a slipped one with a dashed line back and "N days later". Dragging the bottom
// edge zooms (70% to 300%), remembered for each place, with Reset. View and Edit draw the same markup; the click opens the peek
// (#42) in the editor and does nothing in a published file.
import { Fragment } from "preact";
import { useRef, useEffect, useLayoutEffect, useState } from "preact/hooks";
import { MsMark } from "./MsMark.jsx";
import { Icon } from "./Icon.jsx";
import { showDate, timelineSpan, monthStarts, clampZoom, labelLines, addDays, farRows, FAR_NOTE, MONTHS } from "../logic/milestones.js";
import { dayNumber } from "../workItems.js";
import { recall, remember } from "../logic/remember.js";

const PXD0 = 5, BASE = 76, LINE = 34;       // pixels a day at 100%, the strip's own height and each label line's (zoom scale)
const MARGIN = 2;                               // spare pixels added to every measured label width (sub-pixel differences between fonts and systems)
const LY0 = 50, T00 = 66, LANE = 40, GAP = 8;   // the line, the first label lane and each lane's height never shrink: a label is always readable

export function MsTimeline({ rows: all, today, place, open }) {
  const far = farRows(all), rows = all.filter((r) => !far.includes(r));   // a date far outside 2000 to 2100 is named below the line, not drawn
  const wrap = useRef(null), centre = useRef(null);
  const [zoom, setZoom] = useState(() => clampZoom(recall(`tlZoom.${place}`, 1)));
  const z = zoom;
  const { start, end } = timelineSpan(rows, today);
  const x = (iso) => Math.round((dayNumber(iso) - dayNumber(start)) * PXD0 * z);
  const W = x(end), RH = LANE, T0 = T00, LY = LY0;
  const labs = [];
  for (const r of rows) {
    const s = r.marks.solid;
    if (s) labs.push({ r, kind: "main", at: s.date, x: x(s.date) });
    if (r.marks.ghost) labs.push({ r, kind: "exp", at: r.marks.ghost.date, x: x(r.marks.ghost.date) });
  }
  labs.sort((a, b) => a.x - b.x);
  const strip = useRef(null);
  const [widths, setWidths] = useState({});           // each label's real width, measured after it draws
  const [sb, setSb] = useState(0);                      // the height of the sideways scrollbar when the system draws one inside the box (Linux, Windows)
  const [, setTick] = useState(0);                  // bumped when fonts finish loading or the window changes size: measure again
  const Tag = open ? "button" : "span";            // in a published file a mark or label is plain text, not a button
  const btn = (id) => (open ? { type: "button", tabindex: "-1", onClick: () => open(id) } : {});
  const wOf = (l) => (widths[`${l.r.id}:${l.kind}`] || 136) + MARGIN;
  labs.forEach((l) => { const w = wOf(l); l.cx = Math.max(w / 2, Math.min(l.x, W - w / 2)); });   // a label never hangs off either end
  labs.sort((a, b) => a.cx - b.cx);
  const lines = labelLines(labs.map((l) => l.cx), labs.map(wOf), GAP);
  labs.forEach((l, i) => { l.line = lines[i]; });
  const nLines = Math.max(1, ...labs.map((l) => l.line + 1));
  const need = T00 + nLines * LANE + 8;
  const height = Math.max(need, Math.round((BASE + nLines * LINE) * z)) + sb;   // the lanes and the box come from the same measured widths
  const months = monthStarts(start, end);
  useLayoutEffect(() => {                              // measure the labels; if any width changed, lay them out again
    if (!strip.current) return;
    const next = {};
    strip.current.querySelectorAll(".mv-lab").forEach((el) => { next[el.dataset.lab] = Math.ceil(el.getBoundingClientRect().width); });
    const same = Object.keys(next).length === Object.keys(widths).length && Object.keys(next).every((k) => next[k] === widths[k]);
    if (!same) setWidths(next);
    const w = wrap.current;
    if (w) {
      const cs = getComputedStyle(w);
      const bars = Math.max(0, Math.round(w.offsetHeight - w.clientHeight - parseFloat(cs.borderTopWidth || 0) - parseFloat(cs.borderBottomWidth || 0)));
      if (bars !== sb) setSb(bars);
    }
  });
  useEffect(() => {                                   // measure again once the fonts are in and when the window changes size
    let gone = false;
    const again = () => { if (!gone) setTick((t) => t + 1); };
    if (typeof document !== "undefined" && document.fonts && document.fonts.ready) document.fonts.ready.then(again);
    window.addEventListener("resize", again);
    return () => { gone = true; window.removeEventListener("resize", again); };
  }, []);

  const toToday = (smooth) => { const w = wrap.current; if (w) w.scrollTo({ left: Math.max(0, x(today) - w.clientWidth * 0.35), behavior: smooth ? "smooth" : "auto" }); };
  useEffect(() => { toToday(false); }, [place]);     // opens on today
  useEffect(() => {                                   // keeps the middle of what is shown when the zoom changes
    const w = wrap.current;
    if (w && centre.current !== null) { w.scrollLeft = centre.current * W - w.clientWidth / 2; centre.current = null; }
  }, [zoom]);
  // The user drags the bottom edge (CSS resize): the line zooms to the new height, as creaite's milestone line does.
  useEffect(() => {
    const w = wrap.current;
    if (!w || typeof ResizeObserver === "undefined") return undefined;
    let timer = 0;
    const ro = new ResizeObserver(() => {
      const h = w.offsetHeight;
      if (!h || Math.abs(h - height) < 4) return;
      clearTimeout(timer);
      timer = setTimeout(() => {
        centre.current = (w.scrollLeft + w.clientWidth / 2) / (w.scrollWidth || 1);
        const next = clampZoom(Math.round((h - sb) / (BASE + nLines * LINE) * 100) / 100);
        remember(`tlZoom.${place}`, next);
        setZoom(next);
      }, 120);
    });
    ro.observe(w);
    return () => { clearTimeout(timer); ro.disconnect(); };
  }, [height, nLines, place, sb]);

  const reset = () => { centre.current = (wrap.current.scrollLeft + wrap.current.clientWidth / 2) / (wrap.current.scrollWidth || 1); remember(`tlZoom.${place}`, 1); setZoom(1); };
  const step = (k) => { const w = wrap.current; if (w) w.scrollBy({ left: k * 30 * PXD0 * z, behavior: "smooth" }); };
  const range = (iso) => `${MONTHS[+iso.slice(5, 7) - 1].slice(0, 3)} ${iso.slice(0, 4)}`;

  return (
    <div class="mv" data-place={place}>
      <div class="mv-bar">
        <button type="button" class="ib" data-mv="-1" aria-label="Earlier" onClick={() => step(-1)}><Icon name="left" /></button>
        <button type="button" class="ib" data-mv="1" aria-label="Later" onClick={() => step(1)}><Icon name="right" /></button>
        <button type="button" class="btn" data-mv="0" onClick={() => toToday(true)}>Today</button>
        <span class="num">{range(start)} to {range(addDays(end, -1))}</span>
        <span class="grow" />
        <span class="mv-zoom">Drag the bottom edge to zoom{z !== 1 ? <> {" · "}<span class="num" data-zoom={Math.round(z * 100)}>{Math.round(z * 100)}%</span> <button type="button" class="link" data-zreset onClick={reset}>Reset</button></> : null}</span>
      </div>
      {far.length ? <p class="muted mv-far" data-far>{FAR_NOTE}: {far.map((r) => r.name).join(", ")}.</p> : null}
      <div class="mv-wrap" ref={wrap} tabindex="0" data-zoom-pct={Math.round(z * 100)} style={{ height: `${height}px`, maxHeight: `${Math.max(900, height)}px` }}
        aria-label="Milestone timeline; scroll sideways to see all of it; drag the bottom edge to zoom">
        <div class="mv-strip" ref={strip} style={{ width: `${W}px` }}>
          {months.map((m) => <div class="mv-month" key={m} style={{ left: `${x(m)}px` }}>{MONTHS[+m.slice(5, 7) - 1].slice(0, 3)}{m.slice(5, 7) === "01" ? ` ${m.slice(0, 4)}` : ""}</div>)}
          <div class="mv-line" style={{ top: `${LY}px` }} />
          <div class="mv-today" data-today style={{ left: `${x(today)}px` }}><b>Today</b></div>
          {rows.map((r) => {
            const s = r.marks.solid;
            if (!s) return null;
            const px = x(s.date), say = `${r.name}, ${showDate(s.date)}, ${r.word}`;
            return (
              <Fragment key={r.id}>
                {r.marks.line ? <div class="mv-conn" key={`c${r.id}`} data-conn={r.id} style={{ left: `${px}px`, top: `${LY}px`, width: `${x(r.marks.line.to) - px}px` }} /> : null}
                {r.marks.ghost ? <div class="mv-ghost" key={`g${r.id}`} data-ghost={r.id} title={r.marks.ghost.label} style={{ left: `${x(r.marks.ghost.date)}px`, top: `${LY + 1}px` }} /> : null}
                <Tag {...(open ? { type: "button", onClick: () => open(r.id) } : { role: "img" })} class={`mv-mk c-${r.colour}${open ? "" : " plain"}`} key={`m${r.id}`} data-ms={r.id} data-mark-at={s.date} aria-label={say} title={say}
                  style={{ left: `${px}px`, top: `${LY + 1}px` }}><MsMark name={r.mark} /></Tag>
              </Fragment>
            );
          })}
          {labs.map((l) => l.kind === "exp"
            ? <Tag {...btn(l.r.id)} class={`mv-lab gl${open ? "" : " plain"}`} key={`e${l.r.id}`} data-lab={`${l.r.id}:exp`} style={{ left: `${l.cx}px`, top: `${T0 + l.line * RH}px` }}>
                <span data-slip={l.r.id}>{l.r.slipText}</span>{" · "}Expected {showDate(l.at)}<br />{l.r.name}</Tag>
            : <Tag {...btn(l.r.id)} class={`mv-lab${l.r.state === "Achieved" ? " ok" : ""}${open ? "" : " plain"}`} key={`n${l.r.id}`} data-lab={`${l.r.id}:main`} style={{ left: `${l.cx}px`, top: `${T0 + l.line * RH}px` }}>
                <b>{l.r.name}</b>{showDate(l.at)}</Tag>)}
        </div>
      </div>
    </div>
  );
}
