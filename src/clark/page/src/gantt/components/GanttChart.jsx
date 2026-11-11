// The project Gantt chart (row 926), the chart half only: props in, callbacks out. It fetches nothing and saves nothing; the page that holds it
// owns the lines and answers each callback (and shows the Undo that goes with a change). The rules are in ../logic/gantt.js.
//
//   lines          the plan, as logic/gantt.js describes a line (id, name, type, parent, start, end, pct, depends, show)
//   edit           false = View (what the client sees: eye-on lines only, read only), true = Edit (every line, and the interactions below)
//   today          today as YYYY-MM-DD (the page's own clock; the default is the computer's)
//   filter         "all" | "phases" | "milestones" | "ticked" (Edit only); with onFilter(f) the page owns it, without, the chart does
//   hiddenCols     "start" | "end" | "pct" left out of the View (an older file; the page passes none). There is no eye on them: the data layer never hides them
//   defaultRows    the saved plan height in rows (null = every row). In Edit the grip changes it and calls onDefaultRows(n or null);
//                  a viewer's own height is the chart's and is never sent anywhere
//   onChange(id, field, value)   field "name" | "pct" (a number) | "dates" ({ start, end }: the cells, the edit box, a bar moved or stretched)
//   onToggleEye(id)              the line's eye: put it on, or take it off, the client view
//   onAdd(afterId, type)         "Add a task / phase / milestone below"
//   onDelete(id)                 "Delete this line" in the edit box
// Every colour is a token. Bars carry their name as text (beside the bar when the bar is too short), so nothing depends on hover.
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "preact/hooks";
import { Fade } from "../../components/Menu.jsx";
import { Icon } from "../../components/Icon.jsx";
import { todayIso } from "../../workItems.js";
import { reduced } from "../../stores/motion.js";
import {
  WORDS, SCALES, tidyAll, leftOut, visibleRows, filtersFor, filterWord, outline, clashes, statusOf, statusWord, typeWord, rowsShown, rowsFromDrag,
  chartRange, fitPpd, ppdFor, zoomIn, zoomOut, xOf, headerCells, arrowPath, moved, resized, checkEdit, checkBox, detailOf,
  formatDate, endOf, linesShown,
} from "../logic/gantt.js";

export const RH = 32;          // a row
export const HH = 68;          // the header: Today flag, upper band, lower band
const BAR = 20;
const PAD = 6;
const MINW = { name: 110, start: 84, end: 84, pct: 44 };
const MAXW = { name: 420, start: 200, end: 200, pct: 120 };

const G = {
  zout: '<circle cx="11" cy="11" r="7"/><path d="M21 21l-5-5M8 11h6"/>',
  zin: '<circle cx="11" cy="11" r="7"/><path d="M21 21l-5-5M11 8v6M8 11h6"/>',
  week: '<rect x="3" y="4.5" width="18" height="16.5" rx="2.2"/><path d="M8 2.5v3.5M16 2.5v3.5M3 9.5h18"/><rect x="5.5" y="12" width="13" height="3.6" rx="1" fill="currentColor" stroke="none"/>',
  month: '<rect x="3" y="4.5" width="18" height="16.5" rx="2.2"/><path d="M8 2.5v3.5M16 2.5v3.5M3 9.5h18M8 13.5h.01M12 13.5h.01M16 13.5h.01M8 17h.01M12 17h.01M16 17h.01"/>',
  quarter: '<rect x="3" y="4.5" width="18" height="16" rx="2.2"/><path d="M9 4.5v16M15 4.5v16"/><rect x="9.8" y="5.3" width="4.4" height="14.4" fill="currentColor" stroke="none" opacity=".9"/>',
  filter: '<path d="M3 5h18l-7 8v6l-4-2v-4z"/>',
};
const Glyph = ({ name }) => (
  <svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"
    dangerouslySetInnerHTML={{ __html: G[name] }} />
);

// row 971: the lines whose bar has grown in once, kept across mounts (a tab return draws nothing again) per project; a different project key clears it.
const grown = new Map();
let grownKey = null;
function grownFor(key) {
  const k = key || grownKey || "";      // a chart with no key (none given) is not a project change: it keeps what the open project has grown
  if (grownKey !== k) { grown.clear(); grownKey = k; }
  if (!grown.has(k)) grown.set(k, new Set());
  return grown.get(k);
}

const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n));

export function GanttChart({
  lines, edit = false, today, filter: filterProp, onFilter, defaultRows = null, onDefaultRows, hiddenCols = [], projectKey = "",
  onChange, onToggleEye, onAdd, onDelete, addBelowWord = "", eyeWords = {},      // addBelowWord: the Edit-only add button's words (edit/ganttWords.js), given by the page
}) {
  const now = today || todayIso();
  const all = useMemo(() => tidyAll(lines), [lines]);
  const out = useMemo(() => leftOut(lines, { edit }).length, [lines, edit]);      // lines with no usable start date: not drawn, and said so
  const [scale, setScale] = useState("month");
  const [zoom, setZoom] = useState(1);
  const [ownFilter, setOwnFilter] = useState("all");
  const [own, setOwn] = useState(null);                 // a viewer's own plan height, in rows (never saved)
  const [grip, setGrip] = useState(null);               // the rows while the grip is being dragged
  const [full, setFull] = useState(false);
  const [sel, setSel] = useState(null);
  const [drag, setDrag] = useState(null);               // { id, start, end } while a bar is being moved or stretched
  const [box, setBox] = useState(null);                 // the edit box: { id, left, top }
  const [menu, setMenu] = useState(null);               // the add menu: { id, left, top }
  const [showOpen, setShowOpen] = useState(false);
  const [msg, setMsg] = useState("");
  const [width, setWidth] = useState(900);
  const [cw0, setCw] = useState({ name: 150, start: 92, end: 92, pct: 52 });
  const gx = useRef(null);
  const dragged = useRef(false);
  const dragNow = useRef(null);
  const seen = grownFor(projectKey);                   // row 971: lines whose bar has been drawn once since the page opened or the project changed (not per mount)
  const born = useRef(new Map());                      // line id to true while its first-draw grow may still run

  // On a narrow page the left columns give up some width so the chart keeps room for its month labels (a person's own widths still win when smaller).
  const narrow = width < 1000;
  const cwN = narrow ? { name: Math.min(cw0.name, 120), start: Math.min(cw0.start, 94), end: Math.min(cw0.end, 94), pct: Math.min(cw0.pct, 44) } : cw0;
  const cw = cwN;
  const filter = onFilter ? filterProp : ownFilter;
  const setFilter = (f) => { setShowOpen(false); if (onFilter) onFilter(f); else setOwnFilter(f); };
  const cols = ["start", "end", "pct"].filter((k) => edit || !hiddenCols.includes(k));      // no eye on these in Edit (the data layer refuses them as hidden); an older file may still leave one out

  // The lines with a bar being dragged drawn where it is now, so the clash marks and the arrows follow the pointer.
  const live = useMemo(() => (drag ? all.map((l) => (l.id === drag.id ? { ...l, start: drag.start, end: drag.end } : l)) : all), [all, drag]);
  const nos = useMemo(() => outline(live), [live]);
  const bad = useMemo(() => clashes(live), [live]);
  const rows = useMemo(() => visibleRows(live, { edit, filter }), [live, edit, filter]);
  const range = useMemo(() => chartRange(all, now), [all, now]);

  const drawn = !!range && rows.length > 0;      // a plan that starts empty has no chart element yet: it is measured when the first line makes one
  useLayoutEffect(() => {
    const el = gx.current;
    if (!el) return undefined;
    const read = () => setWidth(el.clientWidth);
    read();
    if (typeof ResizeObserver !== "function") return undefined;
    const ro = new ResizeObserver(read);
    ro.observe(el);
    return () => ro.disconnect();
  }, [drawn]);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== "Escape") return;
      if (box) setBox(null); else if (menu) setMenu(null); else if (showOpen) setShowOpen(false); else if (full) setFull(false);
    };
    const onDown = (e) => {
      if (showOpen && !e.target.closest("[data-g-showwrap]")) setShowOpen(false);
      if (menu && !e.target.closest("[data-g-addmenu], [data-g-add]")) setMenu(null);
      if (box && !e.target.closest("[data-g-box]")) setBox(null);
      if (sel && !e.target.closest("[data-g-bar], [data-g-detail], [data-g-box], [data-g-addmenu], [data-g-add]")) setSel(null);      // a click anywhere else lets go of the selected line
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onDown, true);
    return () => { document.removeEventListener("keydown", onKey); document.removeEventListener("pointerdown", onDown, true); };
  }, [box, menu, showOpen, full, sel]);

  const leftW = PAD + (edit ? 28 : 0) + 40 + cw.name + cols.reduce((n, k) => n + 4 + cw[k], 0) + PAD;
  const fit = fitPpd(Math.max(200, width - leftW), range);
  const ppd = ppdFor(scale, fit, zoom);
  const W = range ? Math.ceil(xOf(range.end, range, ppd) + ppd + 40) : 0;
  const total = rows.length;
  const nShown = full ? total : (grip !== null ? grip : rowsShown(total, defaultRows, own, edit));
  const cut = !full && nShown < total;
  const canvasH = total * RH;
  const X = (iso) => xOf(iso, range, ppd);

  if (!range || !total) {
    return (
      <section class="gt" data-gantt data-mode={edit ? "edit" : "view"}>
        <p class="gt-none" data-g-none>{WORDS.noLines}</p>
        {out ? <p data-g-count>{linesShown(0, out)}</p> : null}
      </section>
    );
  }

  const pos = {};
  rows.forEach((l, i) => {
    const x1 = X(l.start), x2 = l.type === "milestone" ? x1 : X(l.end) + ppd;
    pos[l.id] = l.type === "milestone" ? { i, x1: x1 - 8, x2: x1 + 8, l } : { i, x1, x2: Math.max(x2, x1 + 14), l };
  });

  const goToday = () => {
    const el = gx.current;
    if (el) el.scrollTo({ left: Math.max(0, X(now) - (el.clientWidth - leftW) / 2), behavior: "smooth" });
  };
  const rowsAt = (n) => {
    if (full) return;
    if (edit) { if (onDefaultRows) onDefaultRows(n >= total ? null : n); } else setOwn(n);
  };
  const startResize = (key) => (e) => {
    e.preventDefault(); e.stopPropagation();
    const el = e.currentTarget, x0 = e.clientX, w0 = cw[key];
    el.setPointerCapture(e.pointerId);
    el.onpointermove = (m) => setCw((c) => ({ ...c, [key]: clamp(w0 + m.clientX - x0, MINW[key], MAXW[key]) }));
    el.onpointerup = () => { el.onpointermove = null; el.onpointerup = null; };
  };
  const gripDown = (e) => {
    e.preventDefault();
    const el = e.currentTarget, y0 = e.clientY, r0 = nShown;
    el.setPointerCapture(e.pointerId);
    let last = r0;
    el.onpointermove = (m) => { last = rowsFromDrag(r0, m.clientY - y0, RH, total); setGrip(last); };
    el.onpointerup = () => { el.onpointermove = null; el.onpointerup = null; setGrip(null); if (last !== r0) rowsAt(last); };
  };
  const gripKey = (e) => {
    const step = e.key === "ArrowUp" ? -1 : e.key === "ArrowDown" ? 1 : e.key === "Home" ? -total : e.key === "End" ? total : 0;
    if (!step) return;
    e.preventDefault();
    rowsAt(clamp(nShown + step, 1, total));
  };

  const barDown = (l) => (e) => {
    if (!edit || e.button) return;
    const rz = !!e.target.closest("[data-rz]") && l.type !== "milestone";
    const el = e.currentTarget, x0 = e.clientX, s0 = l.start, e0 = l.end;
    el.setPointerCapture(e.pointerId);
    dragged.current = false;
    el.onpointermove = (m) => {
      const dx = m.clientX - x0;
      if (Math.abs(dx) > 3) dragged.current = true;
      if (!dragged.current) return;
      const days = Math.round(dx / ppd);
      const next = rz ? resized({ ...l, start: s0, end: e0 }, days) : moved({ ...l, start: s0, end: e0 }, days);
      dragNow.current = { id: l.id, ...next };
      setDrag(dragNow.current);
    };
    el.onpointerup = () => {
      el.onpointermove = null; el.onpointerup = null;
      const d = dragNow.current;
      dragNow.current = null;
      setDrag(null);
      if (d && dragged.current && (d.start !== s0 || d.end !== e0) && onChange) onChange(l.id, "dates", { start: d.start, end: d.end });
      setSel(l.id);
      setTimeout(() => { dragged.current = false; }, 50);
    };
  };

  const openBox = (id, el) => {
    const r = el.getBoundingClientRect();
    setMenu(null);
    setBox({ id, left: clamp(r.left, 8, window.innerWidth - 330), top: clamp(r.bottom + 6, 8, window.innerHeight - 340) });
  };
  const openAdd = (id, el) => {
    const r = el.getBoundingClientRect();
    setBox(null);
    setMenu({ id, left: clamp(r.left, 8, window.innerWidth - 220), top: clamp(r.bottom + 4, 8, window.innerHeight - 150) });
  };

  const cell = (l, field) => {
    const ms = l.type === "milestone";
    if (field === "end" && ms) return null;
    const text = field === "pct" ? String(l.pct) : formatDate(field === "start" ? l.start : l.end);
    if (!edit) return <span class={`gt-c gt-c-${field}`} style={{ width: `${cw[field]}px` }} data-g-cell={field}>{field === "pct" ? `${l.pct}%` : text}</span>;
    const commit = (e) => {
      const res = checkEdit(l, field, e.currentTarget.value);
      if (!res.ok) { setMsg(res.message); e.currentTarget.value = text; return; }
      setMsg("");
      const same = res.field === "dates" ? res.value.start === l.start && res.value.end === l.end : res.value === l.pct;
      if (!same && onChange) onChange(l.id, res.field, res.value);
    };
    return (
      <input class={`gt-li gt-c gt-c-${field}`} style={{ width: `${cw[field]}px` }} key={`${l.id}-${field}-${text}`} defaultValue={text}
        aria-label={`${WORDS[field]} of ${nos[l.id]} ${l.name}`} data-g-cell={field} data-g-edit={`${l.id}:${field}`} inputMode={field === "pct" ? "numeric" : undefined}
        onChange={commit} onKeyDown={(e) => cellKey(e, field, text)} />
    );
  };
  const cellKey = (e, field, text) => {
    if (e.key === "Escape") { e.stopPropagation(); e.currentTarget.value = text; e.currentTarget.blur(); }
    else if (e.key === "Enter") {
      e.preventDefault();
      const list = [...gx.current.querySelectorAll(`input[data-g-cell="${field}"]:not([disabled])`)];
      const next = list[list.indexOf(e.currentTarget) + 1];
      if (next) next.focus(); else e.currentTarget.blur();
    }
  };

  const eyeBtn = (on, label, click, extra) => (
    <button type="button" class={`gt-eye${on ? " on" : ""}`} aria-pressed={on} aria-label={label} title={label} onClick={click} {...extra}>
      <Icon name={on ? "eye" : "eyeoff"} />
    </button>
  );

  // ── the header ──
  const head = headerCells(scale, range, ppd);
  // A label is shown only where it fits: one that would run into the next is left out, so no month is ever clipped.
  const thin = (cells, wide) => {
    let edge = -1;
    return cells.map((c) => {
      const x = X(c.iso), show = x >= edge;
      if (show) edge = x + c.label.length * 7 + 16;
      return { c, show, wide };
    });
  };
  const upperShown = thin(head.upper, true);
  const lowerShown = thin(head.lower, false);

  const picked = sel && rows.some((l) => l.id === sel) ? live.find((l) => l.id === sel) : null;
  const detail = picked ? detailOf(picked, live, now) : null;

  const labelOut = (l, w) => l.type === "phase" || (l.name.length * 7.6 + 18 > w);
  // A name beside a bar or a milestone goes on the right; where it would run off the right edge of the chart it goes on the left instead.
  const textW = (t) => Math.ceil(t.length * 8 + 6);
  const beside = (x1, x2, text, top, cls, gap) => (x2 + 6 + textW(text) > W
    ? <span class={`${cls} gt-flip`} style={{ right: `${W - x1 + gap}px`, top: `${top}px`, textAlign: "right", "--gt-room": `${Math.max(40, x1 - gap - 4)}px` }}>{text}</span>
    : <span class={cls} style={{ left: `${x2 + 6}px`, top: `${top}px` }}>{text}</span>);
  const ms2 = (x1, text, top) => (x1 + 22 + textW(text) > W
    ? <span class="gt-mslab gt-flip" style={{ right: `${W - x1 + 6}px`, top: `${top}px`, textAlign: "right", "--gt-room": `${Math.max(40, x1 - 10)}px` }}>{text}</span>
    : <span class="gt-mslab" style={{ left: `${x1 + 22}px`, top: `${top}px` }}>{text}</span>);
  const filters = filtersFor(edit);
  const height = cut ? HH + nShown * RH + 2 : undefined;

  return (
    <section class={`gt${full ? " gt-full" : ""}`} data-gantt data-mode={edit ? "edit" : "view"} data-full={full ? "1" : "0"}>
      <div class="gt-bar" role="toolbar" aria-label="Chart">
        <button type="button" class="gt-ib" onClick={() => setZoom(zoomOut(zoom))} disabled={zoom <= 1} aria-label={WORDS.zoomOut} title={WORDS.zoomOut} data-g-zout><Glyph name="zout" /></button>
        <button type="button" class="gt-zf" onClick={() => setZoom(1)} aria-label={WORDS.fit} title={WORDS.fit} data-g-fit>{Math.round(zoom * 100)}%</button>
        <button type="button" class="gt-ib" onClick={() => setZoom(zoomIn(zoom))} aria-label={WORDS.zoomIn} title={WORDS.zoomIn} data-g-zin><Glyph name="zin" /></button>
        <span class="gt-sep" aria-hidden="true" />
        <span class="gt-grp" role="group" aria-label="Scale">
          {SCALES.map((s) => (
            <button type="button" key={s} class="gt-ib" aria-pressed={scale === s} aria-label={WORDS[s]} title={WORDS[s]} data-g-scale={s} onClick={() => setScale(s)}><Glyph name={s} /></button>
          ))}
        </span>
        <span class="gt-sp" />
        <span class="gt-showwrap" data-g-showwrap>
          <button type="button" class="gt-ib" aria-haspopup="menu" aria-expanded={showOpen} aria-label={`${WORDS.show}: ${filterWord(filter)}`} title={`${WORDS.show}: ${filterWord(filter)}`}
            data-g-show onClick={() => setShowOpen(!showOpen)}><Glyph name="filter" /></button>
          {showOpen ? (
            <div class="gt-pop" role="menu" aria-label={WORDS.show} data-g-showmenu>
              {filters.map((f) => (
                <button type="button" key={f} role="menuitemradio" aria-checked={filter === f || (f === "all" && !filters.includes(filter))} data-g-filter={f} onClick={() => setFilter(f)}>
                  <span class="gt-ck" aria-hidden="true">{filter === f || (f === "all" && !filters.includes(filter)) ? "✓" : ""}</span>{filterWord(f)}
                </button>
              ))}
            </div>
          ) : null}
        </span>
        <button type="button" class="gt-wd" onClick={goToday} title={WORDS.scrollToday} aria-label={WORDS.scrollToday} data-g-today-btn><Icon name="clock" /> {WORDS.today}</button>
        <button type="button" class="gt-ib" onClick={() => setFull(!full)} aria-pressed={full} aria-label={full ? WORDS.unexpand : WORDS.expand} title={full ? WORDS.unexpand : WORDS.expand} data-g-expand>
          <Icon name={full ? "shrink" : "expand"} />
        </button>
      </div>

      <div class="gt-gx" ref={gx} style={height ? { height: `${height}px` } : undefined} data-g-gx>
        <div class="gt-in" style={{ gridTemplateColumns: `${leftW}px 1fr`, "--gt-rh": `${RH}px`, "--gt-hh": `${HH}px` }}>
          <div class="gt-lhead" data-g-lhead>
            {edit ? <span class="gt-eyeh" title={eyeWords.head} aria-label={eyeWords.head}><Icon name="eye" /></span> : null}
            <span class="gt-h gt-h-name" style={{ width: `${40 + cw.name}px` }}>{WORDS.name}<i class="gt-rz" data-g-rz="name" onPointerDown={startResize("name")} /></span>
            {cols.map((k) => (
              <span class={`gt-h gt-h-${k}`} style={{ width: `${cw[k]}px` }} key={k}>
                {WORDS[k]}
                <i class="gt-rz" data-g-rz={k} onPointerDown={startResize(k)} />
              </span>
            ))}
          </div>

          <div class="gt-rhead" style={{ width: `${W}px` }} data-g-rhead>
            {upperShown.map(({ c, show }, i) => {
              let j = i + 1;
              while (j < upperShown.length && !upperShown[j].show) j += 1;
              const to = j < upperShown.length ? X(upperShown[j].c.iso) : X(c.to);
              const room = j < upperShown.length ? to - X(c.iso) : Math.max(to - X(c.iso), c.label.length * 7 + 16);   // the last label may run on past the end of the plan
              return <div class="gt-hc gt-u" key={`u${c.iso}`} style={{ left: `${X(c.iso)}px`, width: `${room}px` }}>{show ? c.label : ""}</div>;
            })}
            {lowerShown.map(({ c, show }) => <div class={`gt-hc gt-l${c.edge ? " gt-edge" : ""}`} key={`l${c.iso}`} style={{ left: `${X(c.iso)}px` }}>{show ? c.label : ""}</div>)}
            <button type="button" class="gt-tflag" style={{ left: `${X(now)}px`, "--tx": `${X(now)}px` }} onClick={goToday} title={WORDS.scrollToday} data-g-today>{WORDS.today}</button>
            <div class="gt-tstem gt-tstem-h" style={{ left: `${X(now)}px` }} />
          </div>

          <div class="gt-left" data-g-left>
            {rows.map((l) => (
              <div class={`gt-ln gt-${l.type}`} key={l.id} data-g-row={l.id} data-g-no={nos[l.id]}>
                {edit ? eyeBtn(l.show, `${l.show ? eyeWords.on : eyeWords.off}: ${l.name}`, () => onToggleEye && onToggleEye(l.id), { "data-g-eye": l.id }) : null}
                <span class="gt-id" aria-label={`Number ${nos[l.id]}`}>{nos[l.id]}</span>
                {edit ? (
                  <input class="gt-li gt-nm" style={{ width: `${cw.name}px` }} key={`${l.id}-n-${l.name}`} defaultValue={l.name} aria-label={`Name of ${nos[l.id]}`} data-g-cell="name" data-g-edit={`${l.id}:name`}
                    onChange={(e) => {
                      const res = checkEdit(l, "name", e.currentTarget.value);
                      if (!res.ok) { setMsg(res.message); e.currentTarget.value = l.name; return; }
                      setMsg("");
                      if (res.value !== l.name && onChange) onChange(l.id, "name", res.value);
                    }}
                    onKeyDown={(e) => cellKey(e, "name", l.name)} />
                ) : <span class="gt-nm" style={{ width: `${cw.name}px` }} title={l.name} data-g-cell="name">{l.name}</span>}
                {cols.map((k) => (cell(l, k) || <span class={`gt-c gt-c-${k}`} style={{ width: `${cw[k]}px` }} key={k} />))}
                {edit ? <button type="button" class="gt-addb" data-g-add={l.id} aria-label={`${addBelowWord} ${nos[l.id]}`} title={addBelowWord} onClick={(e) => openAdd(l.id, e.currentTarget)}><Icon name="plus" /></button> : null}
              </div>
            ))}
          </div>

          <div class="gt-canvas" style={{ width: `${W}px`, height: `${canvasH}px` }} data-g-canvas>
            {rows.map((l, i) => <div class={`gt-rw gt-${l.type}`} key={l.id} style={{ top: `${i * RH}px`, height: `${RH}px` }} />)}
            {head.upper.map((c) => <div class="gt-gl" key={c.iso} style={{ left: `${X(c.iso)}px` }} />)}
            <svg class="gt-dep" width={W} height={canvasH} aria-hidden="true" data-g-arrows>
              {rows.flatMap((l) => l.depends.map((d) => {
                const a = pos[d], b = pos[l.id];
                if (!a || !b) return null;
                const isBad = !!(bad[l.id] && bad[l.id].includes(d));
                const p = arrowPath(a.x2, a.i * RH + RH / 2, b.x1, b.i * RH + RH / 2, RH);
                return (
                  <g key={`${d}>${l.id}`} class={isBad ? "gt-bad" : ""} data-g-arrow={`${d}>${l.id}`} data-g-clash-arrow={isBad ? "1" : undefined}>
                    <path d={p.d} /><polygon points={p.head} />
                  </g>
                );
              }))}
            </svg>
            <div class="gt-tstem" style={{ left: `${X(now)}px` }} />
            {rows.map((l, i) => {
              const q = pos[l.id], top = i * RH;
              const st = statusOf(l, now);
              const flag = bad[l.id] ? <span class="gt-clash" style={{ left: `${q.x1 - 18}px`, top: `${top + 6}px` }} title={`${WORDS.startsBefore} ${bad[l.id].map((d) => nos[d] || d).join(", ")} ends`} data-g-clash={l.id}>⚠</span> : null;
              if (l.type === "milestone") {
                const label = `${l.name}, ${formatDate(l.start)}, ${statusWord(st)}`;
                return (
                  <div key={l.id}>
                    <button type="button" class={`gt-ms${l.pct >= 100 ? " done" : ""}${sel === l.id ? " sel" : ""}${edit ? " edit" : ""}`} style={{ left: `${q.x1 + 8}px`, top: `${top + 9}px` }}
                      aria-label={label} data-g-bar={l.id} data-g-type="milestone" onPointerDown={barDown(l)} onClick={() => { if (!dragged.current) setSel(l.id); }}
                      onDblClick={(e) => { if (edit) openBox(l.id, e.currentTarget); }} />
                    {ms2(q.x1, `${l.name} · ${formatDate(l.start)}`, top + 6)}
                    {flag}
                  </div>
                );
              }
              const w = q.x2 - q.x1, out = labelOut(l, w);
              if (!seen.has(l.id)) { seen.add(l.id); born.current.set(l.id, !reduced()); }       // row 1000: drawn while reduced = drawn once, never marked (no animationend would take the mark off, and switching reduced motion off would then grow every bar)
              if (drag && drag.id === l.id) born.current.set(l.id, false);       // a grabbed bar never grows, nor does it start when let go
              const label = `${l.name}, ${formatDate(l.start)} to ${formatDate(l.end)}, ${l.pct} percent, ${statusWord(st)}`;
              return (
                <div key={l.id}>
                  <div role="button" tabindex="0" class={`gt-b gt-b-${l.type}${edit ? " edit" : ""}${sel === l.id ? " sel" : ""}${drag && drag.id === l.id ? " drag" : ""}${born.current.get(l.id) ? " gt-grow" : ""}`}
                    onAnimationEnd={(e) => { if (e.target === e.currentTarget) born.current.set(l.id, false); }}
                    style={{ left: `${q.x1}px`, width: `${w}px`, top: `${l.type === "phase" ? top + 10 : top + 6}px` }} aria-label={label} data-g-bar={l.id} data-g-type={l.type}
                    onPointerDown={barDown(l)} onClick={() => { if (!dragged.current) setSel(l.id); }}
                    onDblClick={(e) => { if (edit) openBox(l.id, e.currentTarget); }}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); if (edit && sel === l.id) openBox(l.id, e.currentTarget); else setSel(l.id); } }}>
                    {l.type === "task" ? <i style={{ width: `${l.pct}%` }} /> : null}
                    {out ? null : <span class="gt-bt">{l.name}</span>}
                    {edit && l.type === "task" ? <b class="gt-rzb" data-rz="1" /> : null}
                  </div>
                  {out ? beside(q.x1, q.x2, l.name, top + 6, l.type === "phase" ? "gt-mslab gt-phlab" : "gt-mslab", bad[l.id] ? 24 : 6) : null}
                  {flag}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div class="gt-grip" role="separator" aria-orientation="horizontal" aria-label={WORDS.gripLabel} aria-valuemin={1} aria-valuemax={total} aria-valuenow={cut ? nShown : total}
        tabindex="0" title={WORDS.grip} data-g-grip onPointerDown={gripDown} onKeyDown={gripKey}>
        <i />{grip !== null ? <span class="gt-gl2">{grip} of {total}</span> : null}
      </div>

      <div class="gt-legend">
        <span><b class="gt-sw gt-sw-p" />{WORDS.legendPhase}</span>
        <span><b class="gt-sw gt-sw-t" />{WORDS.legendTask}</span>
        <span><b class="gt-sw gt-sw-m" />{WORDS.legendMilestone}</span>
        <span><b class="gt-sw gt-sw-d" />{WORDS.legendAchieved}</span>
        <span><b class="gt-sw gt-sw-n" />{WORDS.legendToday}</span>
        <span><b class="gt-sw gt-sw-a" />{WORDS.legendDepends}</span>
        <span class="gt-pill"><b class="gt-sw gt-sw-c" />{WORDS.legendClash}</span>
        {edit || out ? <span data-g-count>{linesShown(rows.length, all.length + out)}</span> : null}
        {msg ? <span class="gt-msg" role="alert" data-g-msg>{msg}</span> : null}
      </div>

      <div class="gt-detail" data-g-detail aria-live="polite">
        {detail ? (
          <>
            <b>{detail.title}</b> · {detail.kind} · {detail.when} · {detail.pct}% done · {detail.status}
            <br />Depends on: {detail.depends.length ? detail.depends.join(", ") : "nothing"}
            {detail.clash ? <> <span class="gt-pill" data-g-detail-clash>{detail.clash}</span></> : null}{eyeWords.detail ? <> · {eyeWords.detail}: <b>{detail.shown ? "Yes" : "No"}</b></> : null}
          </>
        ) : WORDS.detailEmpty}
      </div>

      {menu ? (
        <Fade class="gt-menu" role="menu" style={{ left: `${menu.left}px`, top: `${menu.top}px` }} data-g-addmenu>
          {[["task", WORDS.addTask], ["phase", WORDS.addPhase], ["milestone", WORDS.addMilestone]].map(([t, w], i) => (
            <button type="button" role="menuitem" key={t} data-g-addtype={t} ref={(el) => { if (el && i === 0) el.focus(); }}
              onClick={() => { const id = menu.id; setMenu(null); if (onAdd) onAdd(id, t); }}>{w}</button>
          ))}
        </Fade>
      ) : null}

      {box && live.find((x) => x.id === box.id) ? <EditBox key={box.id} line={live.find((x) => x.id === box.id)} no={nos[box.id]} at={box} onClose={() => setBox(null)}
        onSave={(changes) => { if (onChange) for (const c of changes) onChange(box.id, c.field, c.value); setBox(null); setSel(box.id); }}
        onDelete={onDelete ? () => { const id = box.id; setBox(null); setSel(null); onDelete(id); } : null} /> : null}
    </section>
  );
}

// The edit box (double-click a bar): name, dates, done. A refusal is said in words and the box stays open.
function EditBox({ line, no, at, onClose, onSave, onDelete }) {
  const ms = line.type === "milestone";
  const [f, setF] = useState({ name: line.name, start: formatDate(line.start), end: formatDate(endOf(line)), pct: String(line.pct) });
  const [err, setErr] = useState(null);
  const first = useRef(null);
  const boxEl = useRef(null);
  const [place, setPlace] = useState({ left: at.left, top: at.top });
  // The box's real size and place are only known once it is drawn: keep all of it inside the window.
  useLayoutEffect(() => {
    const el = boxEl.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const vw = document.documentElement.clientWidth || window.innerWidth;
    const vh = document.documentElement.clientHeight || window.innerHeight;
    // A fixed box inside a moved or transformed ancestor sits off from where it was asked to be: that shift is measured and taken out.
    const dx = r.left - at.left, dy = r.top - at.top;
    setPlace({ left: clamp(at.left, 8, Math.max(8, vw - r.width - 8)) - dx, top: clamp(at.top, 8, Math.max(8, vh - r.height - 8)) - dy });
  }, [at.left, at.top]);
  useEffect(() => { if (first.current) { first.current.focus(); first.current.select(); } }, []);
  const set = (k) => (e) => { const v = e.currentTarget.value; setF((old) => ({ ...old, [k]: v })); };   // from the latest values, so two edits before a redraw both stay
  const save = () => {
    const res = checkBox(line, f);
    if (!res.ok) { setErr(res); return; }
    onSave(res.changes);
  };
  const bad = (k) => (err && err.field === k ? " bad" : "");
  return (
    <div class="gt-box" role="dialog" aria-label={`Edit ${no} ${line.name}`} ref={boxEl} style={{ left: `${place.left}px`, top: `${place.top}px` }} data-g-box
      onKeyDown={(e) => { if (e.key === "Enter" && e.target.tagName === "INPUT") { e.preventDefault(); save(); } else if (e.key === "Escape") { e.stopPropagation(); onClose(); } }}>
      <b>{no}</b> {typeWord(line.type)}
      <label for="gt-bn">{WORDS.boxName}</label>
      <input id="gt-bn" ref={first} class={bad("name").trim()} value={f.name} onInput={set("name")} data-g-bn />
      <div class="gt-r">
        <div><label for="gt-bs">{ms ? WORDS.boxDate : WORDS.boxStart}</label><input id="gt-bs" class={bad("start").trim()} value={f.start} onInput={set("start")} data-g-bs /></div>
        {ms ? null : <div><label for="gt-be">{WORDS.boxEnd}</label><input id="gt-be" class={bad("end").trim()} value={f.end} onInput={set("end")} data-g-be /></div>}
      </div>
      {ms ? null : <><label for="gt-bp">{WORDS.boxPct}</label><input id="gt-bp" type="number" min="0" max="100" class={bad("pct").trim()} value={f.pct} onInput={set("pct")} data-g-bp /></>}
      <div class="gt-emsg" role="alert" data-g-bmsg>{err ? err.message : ""}</div>
      <div class="gt-bt2">
        {onDelete ? <button type="button" class="gt-btn gt-danger" onClick={onDelete} data-g-bdel>{WORDS.deleteLine}</button> : null}
        <span class="gt-sp" />
        <button type="button" class="gt-btn" onClick={onClose} data-g-bcancel>{WORDS.cancel}</button>
        <button type="button" class="gt-btn gt-primary" onClick={save} data-g-bsave>{WORDS.save}</button>
      </div>
    </div>
  );
}
