// The status tracker (row 1230): one count for each state, at the bottom of the Dashboard's Milestones section, where the Legend was. It
// doubles as the key: each chip has the state's mark and word. A state with none is drawn dimmer, never left out, so the key stays whole.
// A published file says the client's words (Expected later, Late) and has no Cancelled chip, as the Legend had none.
import { MsMark } from "./MsMark.jsx";
import { STATES, CANCELLED, CLIENT_WORD, LOOK } from "../logic/milestones.js";

export function trackerCounts(rows, client) {
  const states = client ? STATES.filter((s) => s !== "Overdue") : [...STATES, CANCELLED];      // row 1543 AP4: no Late chip on the published page
  return states.map((s) => ({ state: s, word: client ? CLIENT_WORD[s] || s : s, mark: LOOK[s][1], colour: client && s === "Slipped" ? "grey" : LOOK[s][0], means: LOOK[s][2], n: rows.filter((r) => r.state === s).length }));
}

export function MsTracker({ rows, client }) {
  return (
    <div class="mtk" role="group" aria-label="Status summary and key" data-tracker>
      <span class="mtk-cap">Status</span>
      {trackerCounts(rows, client).map((c) => (
        <span key={c.state} class={`mtk-chip${c.n ? "" : " zero"}`} data-tracker-state={c.state} data-n={c.n} title={c.means}>
          <MsMark name={c.mark} /><b class="num">{c.n}</b> {c.word}
        </span>
      ))}
    </div>
  );
}
