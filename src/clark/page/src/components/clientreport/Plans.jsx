// Client Requested Report View (#192): Progress by plan. The plan lines are the project's milestones, in groups by workstream. Each
// group has a table (number, description, end date, status word with its mark, planned, achieved with a small bar) and its total.
// A line behind plan shows "▼n" and says "n points behind plan" to a screen reader; colour is never the only signal.
// This file and Overall.jsx are the boundary Parker's Progress tracker (#189) can replace: they draw only what progress() returns.
import { data, fromFile } from "../../stores/report.js";
import { showDate } from "../../workItems.js";
import { progress, behindWords } from "../../logic/clientReport.js";
import { MsMark } from "../MsMark.jsx";

const pct = (n) => (n === null || n === undefined ? "–" : `${n}%`);

function Achieved({ l }) {
  const behind = l.behind ? <span class="cr-behind" title={behindWords(l.behind)}><span aria-hidden="true">▼{l.behind}</span><span class="sr">{behindWords(l.behind)}</span></span> : null;
  if (l.achieved === null) return <span class="msl-prog"><span class="muted">Not set</span>{behind}</span>;
  return (
    <span class="msl-prog" title={`${l.achieved}% achieved`}>
      <span class="pbar"><i style={{ width: `${l.achieved}%` }}></i></span><b class="num">{l.achieved}%</b>{behind}
    </span>
  );
}

function Group({ g }) {
  return (
    <div class="cr-group" data-group={g.name}>
      <div class="cr-gh"><h3>{g.name}</h3><span class="cr-gt num">Total {pct(g.total.actual)} achieved · {pct(g.total.planned)} planned</span></div>
      <table class="cr-table">
        <thead><tr><th class="c-no" scope="col"><span class="sr">Number</span><span aria-hidden="true">#</span></th><th scope="col">Milestone</th><th class="c-end" scope="col">End</th><th class="c-st" scope="col">Status</th><th class="c-pl" scope="col">Planned</th><th class="c-ac" scope="col">Achieved</th></tr></thead>
        <tbody>
          {g.lines.map((l) => (
            <tr key={l.id} data-line={l.id}>
              <td class="c-no"><span class="cr-no num">{l.no}</span></td>
              <td class="c-tx">{l.text}</td>
              <td class="c-end num">{l.end ? showDate(l.end) : "–"}</td>
              <td class="c-st"><span class={`mst c-${l.colour}`}><MsMark name={l.mark} />{l.word}</span></td>
              <td class="c-pl num">{pct(l.planned)}</td>
              <td class="c-ac"><Achieved l={l} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Plans({ on }) {
  const { groups } = progress(data.value.milestones, on, fromFile.value);
  if (!groups.length) return <p class="muted" data-no-lines>No milestones are shown yet. The plan lines are the project's milestones.</p>;
  return <div class="cr-groups">{groups.map((g) => <Group key={g.name} g={g} />)}</div>;
}
