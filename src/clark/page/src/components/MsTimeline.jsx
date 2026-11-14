// The milestone timeline (#44a; FR-51): scrolls sideways inside its box, a today line and a Today button, a solid mark on each
// agreed date, a ghost on the expected date of a slipped one with a dashed line back and "+N days" (one label line a milestone, 'name date +N days'; the Expected date is in the list). Dragging the bottom
// edge zooms (70% to 300%), remembered for each place, with Reset. Week, Month and Quarter (row 1159) set the pixels a day, as the Calendar's
// do its scale. Labels sit in one lane: a name with no room beside it is hidden (its mark keeps the name in its title and shows it on hover and focus). View and Edit draw the same markup; the click opens the peek
// (#42) in the editor and does nothing in a published file.
import { Fragment } from "preact";
import { useRef, useEffect, useLayoutEffect, useState } from "preact/hooks";
import { MsMark } from "./MsMark.jsx";
import { Icon } from "./Icon.jsx";
import { showDate, timelineSpan, monthStarts, clampZoom, labelLines, addDays, farRows, FAR_NOTE, MONTHS } from "../logic/milestones.js";
import { dayNumber } from "../workItems.js";
import { recall, remember } from "../logic/remember.js";
import { printing } from "../stores/print.js";
import { reduced } from "../stores/motion.js";

const SCALES = [["week", "Week"], ["month", "Month"], ["quarter", "Quarter"]];
const PXD = { week: 20, month: 5, quarter: 1.6 };   // pixels a day at 100% for each scale; Month is the opening scale and the former single scale
const SCALE_KEYS = SCALES.map(([v]) => v);
const BASE = 68, LINE = 24;       // the strip's own height and each label line's (zoom scale)
const SBROOM = 16;                              // an overlay scrollbar's height, kept free under the last lane
const MARGIN = 2;                               // spare pixels added to every measured label width (sub-pixel differences between fonts and systems)
const PRINT_W = 680;                            // the printed line is this wide (an A4 page less its margins): the whole span fits, nothing scrolls (row 767)
const PRINT_TAIL = 60;                          // on paper a month name that would start within this many pixels of the line's end is left off: the frame clips it
const LY0 = 50, T00 = 64, LANE = 24, GAP = 8;   // the line, the first label lane and each lane's height never shrink: a label is always readable

const MONTH_ROOM = 70;      // px a month name needs to the right of its line (the longest, "Sep 2029", is about 62)

export function MsTimeline({ rows: all, today, place, open, client }) {
  const far = farRows(all), rows = all.filter((r) => !far.includes(r));   // a date far outside 2000 to 2100 is named below the line, not drawn
  const wrap = useRef(null), centre = useRef(null);
  const [scale, setScale] = useState(() => { const s = client || !place ? null : recall(`tlScale.${place}`, null); return SCALE_KEYS.includes(s) ? s : "month"; });   // remembered per place; a published file remembers nothing
  const [zoom, setZoom] = useState(() => clampZoom(recall(`tlZoom.${place}`, 1)));
  const fit = printing.value;                     // while the browser prints, the line is drawn to fit the page, at the zoom of 100%
  const z = fit ? 1 : zoom;
  const { start, end } = timelineSpan(rows, today);
  const pxd = fit ? PRINT_W / Math.max(1, dayNumber(end) - dayNumber(start)) : PXD[scale];
  const x = (iso) => Math.round((dayNumber(iso) - dayNumber(start)) * pxd * z);
  const W = x(end), RH = LANE, T0 = T00, LY = LY0;
  const labs = [];
  for (const r of rows) {
    const s = r.marks.solid;
    if (s) labs.push({ r, kind: "main", at: s.date, x: x(s.date) });
  }
  labs.sort((a, b) => a.x - b.x);
  const strip = useRef(null);
  const [widths, setWidths] = useState({});           // each label's real width, measured after it draws
  const [room, setRoom] = useState(0);              // overlay scrollbars (macOS) take no room but are drawn over the bottom of the box while it scrolls sideways: the last lane keeps clear of them
  const [sb, setSb] = useState(0);                      // the height of the sideways scrollbar when the system draws one inside the box (Linux, Windows)
  const [, setTick] = useState(0);                  // bumped when fonts finish loading or the window changes size: measure again
  const Tag = open ? "button" : "span";            // in a published file a mark or label is plain text, not a button
  const btn = (id) => (open ? { type: "button", tabindex: "-1", onClick: () => open(id) } : {});
  const wOf = (l) => (widths[`${l.r.id}:${l.kind}`] || 136) + MARGIN;
  labs.forEach((l) => { const w = wOf(l); l.cx = Math.max(w / 2, Math.min(l.x, W - w / 2)); });   // a label never hangs off either end
  labs.sort((a, b) => a.cx - b.cx);
  const lines = labelLines(labs.map((l) => l.cx), labs.map(wOf), GAP);
  labs.forEach((l, i) => { l.line = 0; l.hid = lines[i] > 0; });   // no room beside it: the name is left to its mark
  const nLines = 1;
  const need = T00 + nLines * LANE + 6;
  const height = Math.max(need, Math.round((BASE + nLines * LINE) * z)) + sb + room;   // the lanes and the box come from the same measured widths
  const hidden = new Set(labs.filter((l) => l.hid).map((l) => l.r.id));
  const allMonths = monthStarts(start, end).filter((m) => scale !== "quarter" || (+m.slice(5, 7) - 1) % 3 === 0);   // a quarter's scale names its first months only
  const months = fit ? allMonths.filter((m, i) => i % Math.ceil(allMonths.length / 10) === 0 && x(m) <= W - PRINT_TAIL) : allMonths;   // on the page about ten names fit
  useLayoutEffect(() => {                              // measure the labels; if any width changed, lay them out again
    if (!strip.current) return;
    const next = {};
    strip.current.querySelectorAll(".mv-lab").forEach((el) => { next[el.dataset.lab] = Math.ceil(el.getBoundingClientRect().width); });
    strip.current.querySelectorAll(".mv-meas").forEach((el) => { next[el.dataset.lab] = widths[el.dataset.lab] || Math.ceil(el.getBoundingClientRect().width); });   // a hidden name keeps the width it had; measured once, it cannot flip between shown and hidden
    const same = Object.keys(next).length === Object.keys(widths).length && Object.keys(next).every((k) => next[k] === widths[k]);
    if (!same) setWidths(next);
    const w = wrap.current;
    if (w) {
      const cs = getComputedStyle(w);
      const bars = Math.max(0, Math.round(w.offsetHeight - w.clientHeight - parseFloat(cs.borderTopWidth || 0) - parseFloat(cs.borderBottomWidth || 0)));
      if (bars !== sb) setSb(bars);
      const over = bars === 0 && w.scrollWidth > w.clientWidth + 1 ? SBROOM : 0;      // no scrollbar room of its own, yet it scrolls sideways: an overlay one
      if (over !== room) setRoom(over);
    }
  });
  useEffect(() => {                                   // measure again once the fonts are in and when the window changes size
    let gone = false;
    const again = () => { if (!gone) setTick((t) => t + 1); };
    if (typeof document !== "undefined" && document.fonts && document.fonts.ready) document.fonts.ready.then(again);
    window.addEventListener("resize", again);
    return () => { gone = true; window.removeEventListener("resize", again); };
  }, []);

  const toToday = (smooth) => { const w = wrap.current; if (w) w.scrollTo({ left: Math.max(0, x(today) - w.clientWidth * 0.35), behavior: reduced() ? "auto" : (smooth ? "smooth" : "auto") }); };
  useEffect(() => { toToday(false); }, [place]);     // opens on today
  useEffect(() => {                                   // keeps the middle of what is shown when the zoom changes
    const w = wrap.current;
    if (w && centre.current !== null) { w.scrollLeft = centre.current * W - w.clientWidth / 2; centre.current = null; }
  }, [zoom, scale]);
  // The user drags the bottom edge (CSS resize): the line zooms to the new height, as creaite's milestone line does.
  useEffect(() => {
    const w = wrap.current;
    if (!w || typeof ResizeObserver === "undefined") return undefined;
    let timer = 0;
    const ro = new ResizeObserver(() => {
      const h = w.offsetHeight;
      if (!h || Math.abs(h - height) < 4) return;
      if (height < h && h <= (parseFloat(getComputedStyle(w).minHeight) || 0) + 1) return;   // the box is held up by its CSS minimum (taller than the lanes need): not a drag
      clearTimeout(timer);
      timer = setTimeout(() => {
        const next = clampZoom(Math.round((h - sb - room) / (BASE + nLines * LINE) * 100) / 100);
        if (Math.abs(next - z) < 0.02) return;           // the box only changed by the room kept under an overlay scrollbar: not a drag
        centre.current = (w.scrollLeft + w.clientWidth / 2) / (w.scrollWidth || 1);
        remember(`tlZoom.${place}`, next);
        setZoom(next);
      }, 120);
    });
    ro.observe(w);
    return () => { clearTimeout(timer); ro.disconnect(); };
  }, [height, nLines, place, sb, room]);

  const reset = () => { centre.current = (wrap.current.scrollLeft + wrap.current.clientWidth / 2) / (wrap.current.scrollWidth || 1); remember(`tlZoom.${place}`, 1); setZoom(1); wrap.current.focus({ preventScroll: true }); };   // the Reset button goes with the zoom: focus stays on the line, not the page
  const step = (k) => { const w = wrap.current; if (w) w.scrollBy({ left: k * 30 * PXD[scale] * z, behavior: reduced() ? "auto" : "smooth" }); };
  const pick = (v) => {
    const w = wrap.current;
    if (w) centre.current = (w.scrollLeft + w.clientWidth / 2) / (w.scrollWidth || 1);
    if (!client && place) remember(`tlScale.${place}`, v);
    setScale(v);
  };
  const range = (iso) => `${MONTHS[+iso.slice(5, 7) - 1].slice(0, 3)} ${iso.slice(0, 4)}`;

  return (
    <div class="mv" data-place={place}>
      <div class="mv-bar">
        <button type="button" class="ib" data-mv="-1" aria-label="Earlier" onClick={() => step(-1)}><Icon name="left" /></button>
        <button type="button" class="ib" data-mv="1" aria-label="Later" onClick={() => step(1)}><Icon name="right" /></button>
        <button type="button" class="btn" data-mv="0" onClick={() => toToday(true)}>Today</button>
        <span class="num">{range(start)} to {range(addDays(end, -1))}</span>
        <span class="grow" />
        <span class="seg cal-sc" role="group" aria-label="Timeline scale">{SCALES.map(([v, t]) => <button type="button" key={v} data-scale-b={v} aria-current={String(scale === v)} onClick={() => pick(v)}>{t}</button>)}</span>
        <span class="mv-zoom">Drag the bottom edge to zoom{z !== 1 ? <> {" · "}<span class="num" data-zoom={Math.round(z * 100)}>{Math.round(z * 100)}%</span> <button type="button" class="link" data-zreset onClick={reset}>Reset</button></> : null}</span>
      </div>
      {far.length ? <p class="muted mv-far" data-far>{FAR_NOTE}: {far.map((r) => r.name).join(", ")}.</p> : null}
      <div class="mv-wrap" ref={wrap} tabindex="0" role="region" data-zoom-pct={Math.round(z * 100)} style={{ height: `${height}px`, maxHeight: `${Math.max(900, height)}px` }}
        aria-label="Milestone timeline; scroll sideways to see all of it; drag the bottom edge to zoom">
        <div class="mv-strip" ref={strip} style={{ width: `${W}px` }}>
          {months.map((m) => {
            const say = `${MONTHS[+m.slice(5, 7) - 1].slice(0, 3)}${m.slice(5, 7) === "01" || months.length < allMonths.length ? ` ${m.slice(0, 4)}` : ""}`;
            return fit && W - x(m) < MONTH_ROOM         // on paper the last names would run past the box (cut off): they sit just left of their line
              ? <div class="mv-month mv-month-end" key={m} style={{ left: `${x(m)}px` }}><span>{say}</span></div>
              : <div class="mv-month" key={m} style={{ left: `${x(m)}px` }}>{say}</div>;
          })}
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
                <Tag {...(open ? { type: "button", onClick: () => open(r.id) } : { role: "img" })} class={`mv-mk c-${r.colour}${open ? "" : " plain"}`} key={`m${r.id}`} data-ms={r.id} data-mark-at={s.date}{...(hidden.has(r.id) ? { "data-hid": say } : {})} aria-label={say} title={say}
                  style={{ left: `${px}px`, top: `${LY + 1}px`, "--at": `${px}px` }}><MsMark name={r.mark} /></Tag>
              </Fragment>
            );
          })}
          {labs.map((l) => (l.hid
            ? <span class="mv-meas" key={`n${l.r.id}`} aria-hidden="true" data-lab={`${l.r.id}:main`}><b>{l.r.name}</b>{" "}{showDate(l.at)}{l.r.marks.ghost ? <>{" "}<span class="slip" data-slip={l.r.id}>+{l.r.slipText.replace(" later", "")}</span></> : null}</span>
            : <Tag {...btn(l.r.id)} class={`mv-lab${l.r.state === "Achieved" ? " ok" : ""}${open ? "" : " plain"}`} key={`n${l.r.id}`} data-lab={`${l.r.id}:main`} style={{ left: `${l.cx}px`, top: `${T0 + l.line * RH}px` }}>
              <b>{l.r.name}</b>{" "}{showDate(l.at)}
              {l.r.marks.ghost ? <>{" "}<span class="sr">expected {showDate(l.r.marks.ghost.date)}, </span><span class="slip" data-slip={l.r.id}>+{l.r.slipText.replace(" later", "")}</span></> : null}
            </Tag>))}
        </div>
      </div>
    </div>
  );
}
