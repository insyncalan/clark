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
import { showDate, railRows, railWord, RAIL } from "../logic/milestones.js";
import { recall, remember } from "../logic/remember.js";

// The date is the first line of the row; its second line (Agreed, or Expected date and days later in red) is `Sub`, a small line under the
// date and the name (row 1020).
function When({ r }) {
  if (r.state === "Achieved" && r.achieved) return <b class="num">{showDate(r.achieved)}</b>;
  if (r.state === "Achieved") return <b class="num">&mdash;</b>;
  return <b class="num">{showDate(r.baseline || r.forecast)}</b>;
}

function Sub({ r }) {
  let text = "", late = false;
  if (r.state === "Achieved" && r.achieved) text = r.achievedNote || "Achieved";
  else if (r.state === "Achieved") text = "Achieved, date not recorded";
  else if (r.state === "Forecast") text = "Forecast, not agreed";
  else if (r.slip) { text = `Expected ${showDate(r.expected)} · ${r.slipText}`; late = true; }
  else text = r.baseline ? "Agreed" : "No agreed date";
  return <small class={`msl-sub${late ? " late" : ""}`}>{text}</small>;
}

// Progress: a bar (its length is the share done) and the number as text, so it is never colour alone. The bar is a picture only; the
// text carries the name for a screen reader. Anything that is not a number from 0 to 100 reads as not set and draws no bar.
// The milestone peek's header line draws the same (Peek.jsx, row 1078).
export function MsProgress({ value }) {
  const n = value === null || value === undefined || value === "" ? NaN : Number(value);
  if (!Number.isFinite(n)) return <span class="muted">Not set</span>;
  const pct = Math.max(0, Math.min(100, Math.round(n)));
  return <><span class="pbar" aria-hidden="true"><i style={{ width: `${pct}%` }} /></span><span class="num"><span class="sr">Progress </span>{pct}%</span></>;
}

// Edit only (row 1104): a heading row over the columns, each with a drag handle (edit/colWidths.jsx), and `--msl-cols` set to the chosen widths.
// `CW` is that hook; with none (a published file, View) the list is drawn as it was, with no heading row.
const HEADS = [["date", "Date"], ["name", "Milestone"], ["state", "State"], ["prog", "Progress"]];
const WIDE = ["minmax(150px, 190px)", "minmax(160px, 1fr)", "150px", "130px"], WIDER = ["minmax(240px, 17rem)", "minmax(160px, 1fr)", "150px", "130px"];
const tracks = (def, ids, cw) => def.map((t, i) => (cw.px(ids[i]) !== null ? `${cw.px(ids[i])}px` : t)).join(" ");      // a chosen width in place of the default track
function Sized({ CW, place, children }) {
  const cw = CW("milestones");
  const ids = HEADS.map((h) => h[0]), set = ids.some((id) => cw.px(id) !== null);
  const vars = set ? { "--msl-cols": tracks(WIDE, ids, cw), "--msl-cols-w": tracks(WIDER, ids, cw) } : undefined;
  return children(vars, <div class={`msl-hd${set ? " set" : ""}`} aria-hidden="true" data-msl-hd={place}><div class="msl-hc">{HEADS.map(([id, w]) => <span key={id} {...cw.head(id, w, true)}>{w}{cw.grip(id, w)}</span>)}</div></div>);
}

export function MsList({ CW, ...rest }) { return CW ? <Sized CW={CW} place={rest.place}>{(vars, hd) => <MsRows {...rest} vars={vars} hd={hd} />}</Sized> : <MsRows {...rest} />; }

function MsRows({ rows, place, open, internalTag, Eye, left, legend, canFold = true, vars, hd }) {
  const [all, setAll] = useState(() => !fromFile.value && !!recall(`msAll.${place}`, false));
  const shown = railRows(rows, all);
  const [det, setDet] = useState(() => !canFold || recall(`msDet.${place}`, true) !== false);
  const fold = () => { remember(`msDet.${place}`, !det); setDet(!det); };
  const toggle = () => { if (!fromFile.value) remember(`msAll.${place}`, !all); setAll(!all); };
  return (
    <div class="msl-box" data-place={place} style={vars}>
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
          <li class={`msl-row${r.clientVisible ? "" : " out"}${open ? "" : " plain"}${Eye ? " has-eye" : ""}${isChanged(r.id) ? " changed" : ""}`} key={r.id} data-ms={r.id} data-changed={isChanged(r.id) ? "1" : undefined}>
            <span class={`node c-${r.colour}${r.state === "Achieved" ? " fill" : ""}`} />
            <div class="msl-cells" {...(open ? { tabindex: "0", role: "button", "aria-label": `${r.name}, ${r.word}${out ? ", left out of the published page" : ""}`, onClick: () => open(r.id), onKeyDown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(r.id); } } } : {})}>
              <span class="msl-date"><When r={r} /></span>
              <span class="msl-name">{r.name}{isChanged(r.id) ? <> <span class="tag chg">{WORD}</span></> : null}{internalTag && !r.clientVisible ? <> <span class="tag">Internal only</span></> : null}{out ? <> <span class="tag hid" data-ms-left>Left out of the published page</span></> : null}</span>
              <span class={`mst c-${r.colour}`}><MsMark name={r.mark} />{r.word}</span>
              <span class="msl-prog" title="Progress"><MsProgress value={r.percent} /></span>
              <Sub r={r} />
            </div>
            {Eye ? <Eye id={r.id} name={r.name} left={out} internal={!r.clientVisible} /> : null}
          </li>
          );
        })}
      </ul>
      {rows.length > RAIL ? <button type="button" class="link msl-all" data-msall={place} onClick={toggle}>{railWord(rows.length, all)}</button> : null}
      </div>
    </div>
  );
}
