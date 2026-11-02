// The milestone list in the design system's rail form (#44a; FR-52): 5 rows, then "Show all N milestones" / "Show the first 5",
// remembered for each place. Each row: a point on the rail, the date and how it compares, the name, the state and progress.
// In Edit each row also has the eye (`Eye`, edit/MsEye.jsx), a button beside the row that leaves it out of the published page; a row
// that is left out says so in words (`left`: the set of ids). View and a published file pass neither.
import { useState } from "preact/hooks";
import { MsMark } from "./MsMark.jsx";
import { isChanged, WORD } from "../stores/changed.js";
import { showDate, railRows, railWord, RAIL } from "../logic/milestones.js";
import { recall, remember } from "../logic/remember.js";

function When({ r }) {
  if (r.state === "Achieved" && r.achieved) return <><b class="num">{showDate(r.achieved)}</b><small>{r.achievedNote || "Achieved"}</small></>;
  if (r.state === "Achieved") return <><b class="num">&mdash;</b><small>Achieved, date not recorded</small></>;
  const date = r.baseline || r.forecast;
  if (r.state === "Forecast") return <><b class="num">{showDate(date)}</b><small>Forecast, not agreed</small></>;
  return (
    <>
      <b class="num">{showDate(date)}</b>
      <small class={r.slip ? "late" : ""}>{r.slip ? `Expected ${showDate(r.expected)} · ${r.slipText}` : r.baseline ? "Agreed" : "No agreed date"}</small>
    </>
  );
}

// Progress: a bar (its length is the share done) and the number as text, so it is never colour alone. The bar is a picture only; the
// text carries the name for a screen reader. Anything that is not a number from 0 to 100 reads as not set and draws no bar.
function Progress({ value }) {
  const n = value === null || value === undefined || value === "" ? NaN : Number(value);
  if (!Number.isFinite(n)) return <span class="muted">Not set</span>;
  const pct = Math.max(0, Math.min(100, Math.round(n)));
  return <><span class="pbar" aria-hidden="true"><i style={{ width: `${pct}%` }} /></span><span class="num"><span class="sr">Progress </span>{pct}%</span></>;
}

export function MsList({ rows, place, open, internalTag, Eye, left }) {
  const [all, setAll] = useState(() => !!recall(`msAll.${place}`, false));
  const shown = railRows(rows, all);
  const toggle = () => { remember(`msAll.${place}`, !all); setAll(!all); };
  return (
    <div class="msl-box" data-place={place}>
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
              <span class="msl-prog" title="Progress"><Progress value={r.percent} /></span>
            </div>
            {Eye ? <Eye id={r.id} name={r.name} left={out} /> : null}
          </li>
          );
        })}
      </ul>
      {rows.length > RAIL ? <button type="button" class="link msl-all" data-msall={place} onClick={toggle}>{railWord(rows.length, all)}</button> : null}
    </div>
  );
}
