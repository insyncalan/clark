// The bar above the rows holds 'Hide milestone details' (left) and the Legend (right, passed in as `legend`) on one row (row 1020).
// The milestone list in the design system's rail form (#44a; FR-52): 5 rows, then "Show all N milestones" / "Show the first 5",
// remembered for each place, under a "Hide milestone details" / "Show milestone details" toggle (also remembered for each place;
// not in a published file, which shows the list as it is). Each row: a point on the rail, the date and how it compares, the name, the state and progress.
// In Edit each row also has the eye (`Eye`, edit/MsEye.jsx), a button beside the row that leaves it out of the published page; a row
// that is left out says so in words (`left`: the set of ids). View and a published file pass neither.
import { useState } from "preact/hooks";
import { Icon } from "./Icon.jsx";
import { MsMark } from "./MsMark.jsx";
import { isChanged, WORD } from "../stores/changed.js";
import { fromFile } from "../stores/report.js";
import { showDate, subLine, railRows, railWord, RAIL } from "../logic/milestones.js";
import { recall, remember } from "../logic/remember.js";
import { defsOf, standardIds } from "../logic/tableColumns.js";

// The date is the first line of the row; its second line (Agreed, or Expected date and days later in red) is `Sub`, a small line under the
// date and the name (row 1020).
function When({ r }) {
  if (r.state === "Achieved" && r.achieved) return <b class="num">{showDate(r.achieved)}</b>;
  if (r.state === "Achieved") return <b class="num">&mdash;</b>;
  return <b class="num">{showDate(r.baseline || r.forecast)}</b>;
}

function Sub({ r }) {
  const { text, late } = subLine(r);
  return <small class={`msl-sub${late ? " late" : ""}`}>{text}</small>;
}

// Progress: a bar (its length is the share done) and the number as text, so it is never colour alone. The bar is a picture only; the
// text carries the name for a screen reader. Anything that is not a number from 0 to 100 reads as not set and draws no bar.
// The milestone peek's header line draws the same (Peek.jsx, row 1078).
export function MsProgress({ value }) {
  const n = value === null || value === undefined || value === "" ? NaN : Number(value);
  if (!Number.isFinite(n)) return <span class="muted">Progress not set</span>;
  const pct = Math.max(0, Math.min(100, Math.round(n)));
  return <><span class="pbar" aria-hidden="true"><i style={{ width: `${pct}%` }} /></span><span class="num"><span class="sr">Progress </span>{pct}%</span></>;
}

// Edit only (row 1104): a heading row over the columns, each with a drag handle (edit/colWidths.jsx), and `--msl-cols` set to the chosen widths.
// `CW` is that hook; with none (a published file, View) the list is drawn as it was, with no heading row.
// Row 1222: `CM` (edit/ColumnsMenu.jsx) chooses which columns: the heading row's Columns button (outside the hidden heading row, so a keyboard reaches it) opens the menu.
// A column that is off keeps its cell in the row, marked `cols-off`, so the narrow stacked layout (no columns, no heading row) still shows the standard four.
const TRACK = { date: "minmax(150px, 190px)", name: "minmax(160px, 1fr)", state: "150px", prog: "130px", id: "70px", description: "minmax(140px, 1fr)", workstream: "110px", owner: "110px", agreed: "100px", forecast: "100px", order: "64px", reason: "minmax(120px, 1fr)" };
const WIDER = { ...TRACK, date: "minmax(240px, 17rem)" };
const STD = standardIds("milestones");
const labelOf = (id) => (defsOf("milestones").find((c) => c.id === id) || {}).label || id;
const track = (map, id, cw) => (cw.px(id) !== null ? `${cw.px(id)}px` : map[id]);
function Sized({ CW, CM, place, children }) {
  const cw = CW("milestones"), cm = CM ? CM("milestones") : null, shown = cm ? cm.shown : STD;
  const set = shown.some((id) => cw.px(id) !== null), custom = shown.length !== STD.length || shown.some((id, i) => id !== STD[i]);
  const vars = set || custom ? { "--msl-cols": shown.map((id) => track(TRACK, id, cw)).join(" "), "--msl-cols-w": shown.map((id) => track(WIDER, id, cw)).join(" ") } : undefined;
  const hd = (
    <div class="msl-hdw" {...(cm ? cm.rowProps : {})}>
      <div class={`msl-hd${set || custom ? " set" : ""}`} aria-hidden="true" data-msl-hd={place}><div class="msl-hc">{shown.map((id) => <span key={id} data-col={id} {...cw.head(id, labelOf(id), true)}>{labelOf(id)}{cw.grip(id, labelOf(id))}</span>)}</div></div>
      {cm ? cm.button("ms") : null}
    </div>
  );
  return children(vars, hd, shown, cm ? cm.menu : null);
}

export function MsList({ CW, CM, ...rest }) { return CW ? <Sized CW={CW} CM={CM} place={rest.place}>{(vars, hd, shown, menu) => <MsRows {...rest} vars={vars} hd={hd} cols={shown} menu={menu} />}</Sized> : <MsRows {...rest} />; }

const XCELL = { id: (r) => r.id, description: (r) => r.description, workstream: (r) => r.workstream, owner: (r) => r.owner, agreed: (r) => (r.baseline ? showDate(r.baseline) : ""),
  forecast: (r) => (r.forecast ? showDate(r.forecast) : ""), order: (r) => String(r.sort_order), reason: (r) => r.reason };
const xText = (id, r) => { const t = String((XCELL[id] || (() => ""))(r) || "").trim(); return t || "—"; };

function MsRows({ rows, place, open, internalTag, Eye, More, left, legend, canFold = true, vars, hd, cols = STD, menu }) {
  const on = (id) => cols.includes(id), off = (id) => (on(id) ? "" : " cols-off");
  const [all, setAll] = useState(() => !fromFile.value && !!recall(`msAll.${place}`, false));
  const shown = railRows(rows, all);
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
      {hd}
      <ul class="msl">
        {shown.map((r) => {
          const out = !!(Eye && left && left.has(r.id));          // left out of the published page: said in words, never by colour alone
          return (
          // The li stays a list item; in the editor the button is its child (role and keys), so the list keeps its semantics.
          <li class={`msl-row${r.clientVisible ? "" : " out"}${open ? "" : " plain"}${Eye ? " has-eye" : ""}${Eye && More ? " has-more" : ""}${isChanged(r.id) ? " changed" : ""}`} key={r.id} data-ms={r.id} data-changed={isChanged(r.id) ? "1" : undefined}>
            <span class={`node c-${r.colour}${r.state === "Achieved" ? " fill" : ""}`} />
            <div class="msl-cells" {...(open ? { tabindex: "0", role: "button", "aria-label": `${r.name}, ${r.word}${out ? ", left out of the published page" : ""}${cols.filter((id) => !STD.includes(id)).map((id) => `, ${labelOf(id)} ${xText(id, r)}`).join("")}`, onClick: () => open(r.id), onKeyDown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(r.id); } } } : {})}>
              <span class={`msl-date${off("date")}`} data-col="date"><When r={r} /></span>
              <span class="msl-name" data-col="name">{r.name}{isChanged(r.id) ? <> <span class="tag chg">{WORD}</span></> : null}{internalTag && !r.clientVisible ? <> <span class="tag">Internal only</span></> : null}{out ? <> <span class="tag hid" data-ms-left>Left out of the published page</span></> : null}</span>
              <span class={`mst c-${r.colour}`} data-col="state"><MsMark name={r.mark} />{r.word}</span>
              <span class={`msl-prog${off("prog")}`} data-col="prog" title="Progress"><MsProgress value={r.percent} /></span>
              {cols.filter((id) => !STD.includes(id)).map((id) => <span key={id} class="msl-x" data-col={id} data-label={labelOf(id)}>{xText(id, r)}</span>)}
              <Sub r={r} />
            </div>
            {Eye ? <Eye id={r.id} name={r.name} left={out} internal={!r.clientVisible} /> : null}
            {Eye && More ? <More row={r} /> : null}
          </li>
          );
        })}
      </ul>
      {menu}
      {rows.length > RAIL ? <button type="button" class="link msl-all" data-msall={place} onClick={toggle}>{railWord(rows.length, all)}</button> : null}
      </div>
    </div>
  );
}
