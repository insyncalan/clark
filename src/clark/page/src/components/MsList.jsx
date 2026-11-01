// The milestone list in the design system's rail form (#44a; FR-52): 5 rows, then "Show all N milestones" / "Show the first 5",
// remembered for each place, under a "Hide milestone details" / "Show milestone details" toggle (also remembered for each place;
// not in a published file, which shows the list as it is). Each row: a point on the rail, the date and how it compares, the name, the state and progress.
// (The eye that hides a row from the published report is Edit only and comes with #67's write.)
import { useState } from "preact/hooks";
import { Icon } from "./Icon.jsx";
import { MsMark } from "./MsMark.jsx";
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

export function MsList({ rows, place, open, internalTag }) {
  const [all, setAll] = useState(() => !!recall(`msAll.${place}`, false));
  const shown = railRows(rows, all);
  const canFold = !!open;                    // a published file has nothing to open and remembers nothing: no toggle, the list as it is
  const [det, setDet] = useState(() => !canFold || recall(`msDet.${place}`, true) !== false);
  const fold = () => { remember(`msDet.${place}`, !det); setDet(!det); };
  const toggle = () => { remember(`msAll.${place}`, !all); setAll(!all); };
  return (
    <div class="msl-box" data-place={place}>
      {canFold ? (
        <button type="button" class="msl-det" data-msdet={place} aria-expanded={String(det)} aria-controls={`msl-${place}`} onClick={fold}>
          <Icon name="chevdown" /><span>{det ? "Hide milestone details" : "Show milestone details"}</span>
        </button>
      ) : null}
      <div id={`msl-${place}`} hidden={!det}>
      <ul class="msl">
        {shown.map((r) => (
          // The li stays a list item; in the editor the button is its child (role and keys), so the list keeps its semantics.
          <li class={`msl-row${r.clientVisible ? "" : " out"}${open ? "" : " plain"}`} key={r.id} data-ms={r.id}>
            <span class={`node c-${r.colour}${r.state === "Achieved" ? " fill" : ""}`} />
            <div class="msl-cells" {...(open ? { tabindex: "0", role: "button", "aria-label": `${r.name}, ${r.word}`, onClick: () => open(r.id), onKeyDown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(r.id); } } } : {})}>
              <span class="msl-date"><When r={r} /></span>
              <span class="msl-name">{r.name}{internalTag && !r.clientVisible ? <> <span class="tag">Internal only</span></> : null}</span>
              <span class={`mst c-${r.colour}`}><MsMark name={r.mark} />{r.word}</span>
              <span class="msl-prog" title="Progress">{r.percent === null || r.percent === undefined ? <span class="muted">Not set</span> : <><span class="pbar"><i style={{ width: `${r.percent}%` }} /></span><span class="num">{r.percent}%</span></>}</span>
            </div>
          </li>
        ))}
      </ul>
      {rows.length > RAIL ? <button type="button" class="link msl-all" data-msall={place} onClick={toggle}>{railWord(rows.length, all)}</button> : null}
      </div>
    </div>
  );
}
