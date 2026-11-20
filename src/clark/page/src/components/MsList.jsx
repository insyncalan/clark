// The bar above the rows holds 'Hide milestone details' (left) and the Legend (right, passed in as `legend`) on one row (row 1020).
// The milestone list in the design system's rail form (#44a; FR-52): 5 rows, then "Show all N milestones" / "Show the first 5",
// remembered for each place, under a "Hide milestone details" / "Show milestone details" toggle (also remembered for each place;
// not in a published file, which shows the list as it is). Each row: a point on the rail, the date and how it compares, the name, the state and progress.
// In Edit each row also has the eye (`Eye`, edit/MsEye.jsx), a button beside the row that leaves it out of the published page; a row
// that is left out says so in words (`left`: the set of ids). View and a published file pass neither.
import { useState, useLayoutEffect, useRef } from "preact/hooks";
import { Icon } from "./Icon.jsx";
import { classicTheme } from "./Contents.jsx";
import { MsMark } from "./MsMark.jsx";
import { isChanged, WORD } from "../stores/changed.js";
import { fromFile } from "../stores/report.js";
import { showDate, subLine, agreedText, expectedCell, railRows, railWord, RAIL } from "../logic/milestones.js";
import { recall, remember } from "../logic/remember.js";
import { MS_VIEW_ON, MS_VIEW_OFF, MS_REGION } from "./msViewWords.js";
import { defsOf, standardIds } from "../logic/tableColumns.js";
import { visibleItems, scrollRows } from "../logic/useCaseView.js";

// The Milestones page's list (place "page"; the row 1230 ruling: the Dashboard section only changes): the date is the first line of the row; its second line
// (Agreed, or Expected date and days later in red) is `Sub`, a small line under the date and the name (row 1020).
function When({ r }) {
  if (r.state === "Achieved" && r.achieved) return <b class="num">{showDate(r.achieved)}</b>;
  if (r.state === "Achieved") return <b class="num">&mdash;</b>;
  return <b class="num">{showDate(r.baseline || r.forecast)}</b>;
}

function Sub({ r }) {
  const { text, late } = subLine(r);
  return <small class={`msl-sub${late ? " late" : ""}`}>{text}</small>;
}

// Row 1230: "Expected or achieved" is the date (bold) with a small line under it (Cell, from logic/milestones.js expectedCell); "Agreed" is its own column.
function Expected({ r }) {
  const { date, text, late } = expectedCell(r);
  return <><b class="num">{date}</b>{text ? <small class={`msl-sub${late ? " late" : ""}`}>{text}</small> : null}</>;
}

// Progress: a bar (its length is the share done) and the number as text, so it is never colour alone. The bar is a picture only; the
// text carries the name for a screen reader. Anything that is not a number from 0 to 100 reads as not set and draws no bar.
// The milestone peek's header line draws the same (Peek.jsx, row 1078).
// `dash` (row 1230, the Dashboard's detail table): none draws a muted dash that a screen reader names "Progress not set".
export function MsProgress({ value, dash = false }) {
  const n = value === null || value === undefined || value === "" ? NaN : Number(value);
  if (!Number.isFinite(n)) return dash ? <span class="muted" role="img" aria-label="Progress not set">&mdash;</span> : <span class="muted">Progress not set</span>;
  const pct = Math.max(0, Math.min(100, Math.round(n)));
  return <><span class="pbar" aria-hidden="true"><i style={{ width: `${pct}%` }} /></span><span class="num"><span class="sr">Progress </span>{pct}%</span></>;
}

// Edit only (row 1104): a heading row over the columns, each with a drag handle (edit/colWidths.jsx), and `--msl-cols` set to the chosen widths.
// `CW` is that hook; with none (a published file, View) the list is drawn as it was, with no heading row.
// Row 1222: `CM` (edit/ColumnsMenu.jsx) chooses which columns: the heading row's Columns button (outside the hidden heading row, so a keyboard reaches it) opens the menu.
// A column that is off keeps its cell in the row, marked `cols-off`, so the narrow stacked layout (no columns, no heading row) still shows the standard four.
const TRACK_PAGE = { date: "minmax(150px, 190px)", name: "minmax(160px, 1fr)", state: "150px", prog: "130px", id: "70px", description: "minmax(140px, 1fr)", workstream: "110px", owner: "110px", agreed: "100px", forecast: "100px", order: "64px", reason: "minmax(120px, 1fr)" };
const WIDER_PAGE = { ...TRACK_PAGE, date: "minmax(240px, 17rem)" };
const TRACK = { name: "minmax(140px, 1fr)", state: "130px", agreed: "100px", date: "minmax(150px, 190px)", prog: "120px", id: "70px", description: "minmax(140px, 1fr)", workstream: "110px", owner: "110px", forecast: "100px", order: "64px", reason: "minmax(120px, 1fr)" };
const WIDER = { ...TRACK, name: "minmax(180px, 1fr)", state: "150px", agreed: "110px", date: "minmax(170px, 14rem)", prog: "130px" };
// The table's name: "milestones" for the Milestones page, "msDash" for the Dashboard section (tableColumns.js).
const tableOf = (place) => (place === "page" ? "milestones" : "msDash");
const STD_OF = (place) => standardIds(tableOf(place));
const labelOf = (id, place) => (defsOf(tableOf(place)).find((c) => c.id === id) || {}).label || id;
const track = (map, id, cw) => (cw.px(id) !== null ? `${cw.px(id)}px` : map[id]);
function Sized({ CW, CM, place, children }) {
  const table = tableOf(place), STD = STD_OF(place), maps = place === "page" ? [TRACK_PAGE, WIDER_PAGE] : [TRACK, WIDER];
  const cw = CW(table), cm = CM ? CM(table) : null, shown = cm ? cm.shown : STD;
  const set = shown.some((id) => cw.px(id) !== null), custom = shown.length !== STD.length || shown.some((id, i) => id !== STD[i]);
  const vars = set || custom ? { "--msl-cols": shown.map((id) => track(maps[0], id, cw)).join(" "), "--msl-cols-w": shown.map((id) => track(maps[1], id, cw)).join(" ") } : undefined;
  const hd = (
    <div class="msl-hdw" {...(cm ? cm.rowProps : {})}>
      <div class={`msl-hd${set || custom ? " set" : ""}`} aria-hidden="true" data-msl-hd={place}><div class="msl-hc">{shown.map((id) => <span key={id} data-col={id} {...cw.head(id, labelOf(id, place), true)}>{labelOf(id, place)}{cw.grip(id, labelOf(id, place))}</span>)}</div></div>
      {cm ? cm.button("ms") : null}
    </div>
  );
  return children(vars, hd, shown, cm ? cm.menu : null);
}

export function MsList({ CW, CM, ...rest }) { return CW ? <Sized CW={CW} CM={CM} place={rest.place}>{(vars, hd, shown, menu) => <MsRows {...rest} vars={vars} hd={hd} cols={shown} menu={menu} />}</Sized> : <MsRows {...rest} />; }

const XCELL = { id: (r) => r.id, description: (r) => r.description, workstream: (r) => r.workstream, owner: (r) => r.owner, agreed: (r) => (r.baseline ? showDate(r.baseline) : ""),
  forecast: (r) => (r.forecast ? showDate(r.forecast) : ""), order: (r) => String(r.sort_order), reason: (r) => r.reason };
const xText = (id, r) => { const t = String((XCELL[id] || (() => ""))(r) || "").trim(); return t || "—"; };

// The Dashboard section in View and in a published file: the same heading row, with no grips and no Columns button (Edit's `Sized` draws its own, row 1104).
// The Milestones page has none here: its heading row is Edit's alone.
function Heads({ place }) {
  return <div class={`msl-hdw${classicTheme() ? " plain" : ""}`}><div class="msl-hd" aria-hidden="true" data-msl-hd={place}><div class="msl-hc">{STD_OF(place).map((id) => <span key={id} data-col={id}>{labelOf(id, place)}</span>)}</div></div></div>;
}

function MsRows({ view, rows, place, open, internalTag, Eye, Note, More, left, legend, canFold = true, vars, hd, cols, menu }) {
  const STD = STD_OF(place), page = place === "page";
  cols = cols || STD;
  const on = (id) => cols.includes(id), off = (id) => (on(id) ? "" : " cols-off");
  const [all, setAll] = useState(() => !fromFile.value && !!recall(`msAll.${place}`, false));
  // Row 1230: with a view setting (the Dashboard's section) the number shown and the scrolling come from it, as the Use case summary does: Edit scrolls once a number is stored,
  // a number stored means no "Show all", and with none stored the first 5 and "Show all N milestones" stay as they were. No view (the Milestones page): as it was.
  const scrolls = view ? (Eye ? view.set || view.scroll : view.scroll) : false, high = view ? scrollRows({ ...view, scroll: scrolls }) : 0;
  const shown = !view ? railRows(rows, all) : scrolls ? rows : visibleItems(rows, view, view.set ? false : all);
  const more = view ? !scrolls && !view.set && rows.length > (view.n === "all" ? rows.length : view.n) : rows.length > RAIL;
  const cut = !!view && view.set && view.n !== "all" && view.n < rows.length;      // a number is stored and fewer than the rows: the notes below say so
  const note = !cut ? "" : Eye && Note ? Note(view.scroll, view.n, rows.length) : (view.scroll ? MS_VIEW_ON : MS_VIEW_OFF)(view.n, rows.length);
  const list = useRef(null);
  const fit = () => {      // the list is as tall as its first `high` rows, measured, so n rows fit exactly whatever their height
    const ul = list.current;
    if (!ul) return;
    const li = ul.querySelectorAll(":scope > li");
    ul.style.maxHeight = high && li.length > high && li[high].offsetTop > li[0].offsetTop ? `${li[high].offsetTop - li[0].offsetTop}px` : "";
  };
  useLayoutEffect(() => { fit(); });
  useLayoutEffect(() => { window.addEventListener("resize", fit); return () => window.removeEventListener("resize", fit); });
  const [det, setDet] = useState(() => !canFold || fromFile.value || recall(`msDet.${place}`, true) !== false);      // a published file starts open and keeps no choice (remembering there needs a ruling)
  const fold = () => { if (canFold && !fromFile.value) remember(`msDet.${place}`, !det); setDet(!det); };
  const toggle = () => { if (!fromFile.value) remember(`msAll.${place}`, !all); setAll(!all); };
  return (
    <div class="msl-box" data-place={place} style={vars} data-nodate={on("date") ? undefined : "1"}>
      <div class="msl-bar">
        {canFold ? (
          <button type="button" class="msl-det" data-msdet={place} aria-expanded={String(det)} aria-controls={`msl-${place}`} onClick={fold}>
            <Icon name="chevdown" /><span>{det ? "Hide milestone details" : "Show milestone details"}</span>
          </button>
        ) : null}
        {legend}
      </div>
      <div id={`msl-${place}`} hidden={!det}>
      {hd || (page ? null : <Heads place={place} />)}
      <ul class={`msl${high ? " msl-scroll" : ""}`} ref={list} {...(cut && scrolls ? { tabindex: "0", "aria-label": MS_REGION } : {})}>
        {shown.map((r) => {
          const out = !!(Eye && left && left.has(r.id));          // left out of the published page: said in words, never by colour alone
          return (
          // The li stays a list item; in the editor the button is its child (role and keys), so the list keeps its semantics.
          <li class={`msl-row${r.clientVisible ? "" : " out"}${open ? "" : " plain"}${Eye ? " has-eye" : ""}${Eye && More ? " has-more" : ""}${isChanged(r.id) ? " changed" : ""}`} key={r.id} data-ms={r.id} data-changed={isChanged(r.id) ? "1" : undefined}>
            <span class={`node c-${r.colour}${r.state === "Achieved" ? " fill" : ""}`} />
            <div class="msl-cells" {...(open ? { tabindex: "0", role: "button", "aria-label": `${r.name}, ${r.word}${out ? ", left out of the published page" : ""}${cols.filter((id) => !STD.includes(id)).map((id) => `, ${labelOf(id, place)} ${xText(id, r)}`).join("")}`, onClick: () => open(r.id), onKeyDown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(r.id); } } } : {})}>
              {page ? <span class={`msl-date${off("date")}`} data-col="date"><When r={r} /></span> : null}
              <span class="msl-name" data-col="name">{r.name}{isChanged(r.id) ? <> <span class="tag chg">{WORD}</span></> : null}{internalTag && !r.clientVisible ? <> <span class="tag">Internal only</span></> : null}{out ? <> <span class="tag hid" data-ms-left>Left out of the published page</span></> : null}</span>
              <span class={`mst c-${r.colour}`} data-col="state"><MsMark name={r.mark} />{r.word}</span>
              {page ? null : <span class={`msl-agr num${off("agreed")}`} data-col="agreed">{agreedText(r)}</span>}
              {page ? null : <span class={`msl-date${off("date")}`} data-col="date"><Expected r={r} /></span>}
              <span class={`msl-prog${off("prog")}`} data-col="prog" title="Progress"><MsProgress value={r.percent} dash={!page} /></span>
              {cols.filter((id) => !STD.includes(id)).map((id) => <span key={id} class="msl-x" data-col={id} data-label={labelOf(id, place)}>{xText(id, r)}</span>)}
              {page ? <Sub r={r} /> : null}
            </div>
            {Eye ? <Eye id={r.id} name={r.name} left={out} internal={!r.clientVisible} /> : null}
            {Eye && More ? <More row={r} /> : null}
          </li>
          );
        })}
      </ul>
      {menu}
      {note ? <p class="note muted" data-msl-note>{note}</p> : null}
      {more ? <button type="button" class="link msl-all" data-msall={place} onClick={toggle}>{railWord(rows.length, all)}</button> : null}
      </div>
    </div>
  );
}
