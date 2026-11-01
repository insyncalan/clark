// Client Requested Report View (#192): Overall progress. The project's health and reason, Actual and Planned as two figures, and a bar
// filled to Actual with a marker at Planned. Every figure is worked out in logic/clientReport.js from the milestones; what each means
// is said there, not on the page (the client reads this page), and "Not set" is shown when there is nothing to measure (never an invented number).
// This file and Plans.jsx are the boundary the Progress tracker (#189) can replace: they draw only what progress() returns.
import { data, fromFile } from "../../stores/report.js";
import { HEALTH_WORDS } from "../../glanceTiles.js";
import { showDate } from "../../workItems.js";
import { progress, gapWords, clientRules } from "../../logic/clientReport.js";

const PILL = { g: "g", a: "a", r: "r" };

// The marker's label sits above the marker; near either end it is pulled in so it never leaves the bar.
const place = (planned) => (planned >= 88 ? " end" : planned <= 12 ? " start" : "");

export function Overall({ on }) {
  const d = data.value;
  const { overall, groups } = progress(d.milestones, on, true, clientRules(d, fromFile.value));   // the client's milestones and words, as the file shows them
  const lines = groups.reduce((n, g) => n + g.lines.length, 0);
  const health = d.project.health || "", rag = HEALTH_WORDS[health] || "n", reason = d.project.health_reason || "";
  const gap = gapWords(overall);
  return (
    <>
      <div class="glance cr-tiles">
        <div class="tcell health">
          <div class={`fig health-fig rag-${rag}`} data-fig="health">
            <span class="k"><i class="ragdot" aria-hidden="true"></i>Project health</span>
            <div class="hrow">
              <span class={`pill hpill ${PILL[rag] || "n"}`}>{health || "Not set"}</span>
              {reason ? <span class="hreason">{reason}</span> : null}
            </div>
          </div>
        </div>
        <div class="tcell"><div class="fig" data-fig="actual" role="group" aria-label={`Actual: ${overall ? overall.actual + "%" : "Not set"}`}>
          <span class="k">Actual</span><span class="v num">{overall ? `${overall.actual}%` : "Not set"}</span>
          <span class="dd">{overall ? `of ${lines} ${lines === 1 ? "milestone" : "milestones"}` : "No milestones yet"}</span>
        </div></div>
        <div class="tcell"><div class="fig" data-fig="planned" role="group" aria-label={`Planned: ${overall ? overall.planned + "%" : "Not set"}`}>
          <span class="k">Planned</span><span class="v num">{overall ? `${overall.planned}%` : "Not set"}</span>
          <span class="dd">{overall ? <>by <span class="num">{showDate(on)}</span></> : "No milestones yet"}</span>
        </div></div>
      </div>
      {overall ? (
        <>
          <div class="cr-bar-w">
            <div class="cr-bar" role="img" aria-label={`Actual ${overall.actual} percent against ${overall.planned} percent planned`} data-bar>
              <i class="fill" style={{ width: `${overall.actual}%` }}></i>
              <i class={`mk${place(overall.planned)}`} style={{ left: `${overall.planned}%` }}><span>Planned {overall.planned}%</span></i>
            </div>
            <div class="cr-scale" aria-hidden="true"><span>0%</span><span>100%</span></div>
          </div>
          <p class="cr-gap" data-gap>{gap}</p>
        </>
      ) : null}
    </>
  );
}
