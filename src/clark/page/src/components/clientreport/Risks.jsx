// Client Requested Report View (#192): the Risks, delays and items to watch body. One row for each open risk or issue, as a
// word (Delay, Risk or Monitor) with the title, the owner and the date it should be back on track. The row's number and the
// Escalate answer are for the team, not the client (ruling on the 0.5.0 hand-check): neither is drawn, in View, in Edit or in a file.
// The response is a working note and is never shown. Worked out from the Risks and issues rows by logic/clientRisks.js; nothing here is typed or saved.
import { data, fromFile } from "../../stores/report.js";
import { showDate, ownerOf } from "../../workItems.js";
import { riskRows, MONITOR } from "../../logic/clientRisks.js";
import { clientRules } from "../../logic/clientReport.js";

const Dash = () => <span class="muted">{"—"}</span>;

export function Risks() {
  const rows = riskRows(data.value.raid, clientRules(data.value, fromFile.value));
  if (!rows.length) return <p class="quiet" data-empty="Risks">There are no open risks, delays or items to watch.</p>;
  return (
    <ul class="wl cr-wl" data-rows="Risks">
      {rows.map((r) => {
        const o = ownerOf(r.owner);
        return (
          <li class="wl-row" key={r.id} data-word={r.word}>
            <span class="wl-state"><span class={`pill ${r.tone}`}>{r.word}</span></span>
            <span class="wl-main">
              <span class="wl-title">{r.title}</span>
              <span class="wl-meta">
                <span class="who">{o.initials ? <span class="av" aria-hidden="true">{o.initials}</span> : null}<span>{o.text}</span></span>
                <span class="dot" aria-hidden="true">·</span>
                <span class="cr-back">{r.word === MONITOR ? "Review by" : "Back on track by"} {r.due ? <span class="num">{showDate(r.due)}</span> : <Dash />}</span>
              </span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}
