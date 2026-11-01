// Client Requested Report View (#192): the project in the weekly format a client has asked for. A page of its own, beside the
// Dashboard, Work items and Milestones, in the same frame and the same section look. The sections come in one fixed order:
// Overall progress, Progress by plan, the delivery template's place (#190, on hold), Highlights and Planned for next week
// (a half-width pair), Risks, delays and items to watch. Each section's body is its own file under clientreport/, so one part
// can be replaced (the Progress tracker, #189) without touching the others.
// The page is drawn in View and in Edit; it is the live page only: a published file's tab list does not carry it (publish.py).
import { data, asAt, fromFile } from "../stores/report.js";
import { showDate, todayIso } from "../workItems.js";
import { Overall } from "./clientreport/Overall.jsx";
import { Plans } from "./clientreport/Plans.jsx";
import { Delivery } from "./clientreport/Delivery.jsx";
import { Highlights, NextWeek } from "./clientreport/Pair.jsx";
import { Risks } from "./clientreport/Risks.jsx";

// The fixed order, and where each section sits: full row, or the left or right half of a pair.
export const SECTIONS = [
  { id: "progress", title: "Overall progress", slot: "full", Body: Overall },
  { id: "plans", title: "Progress by plan", slot: "full", Body: Plans },
  { id: "delivery", title: "Delivery progress", slot: "full", Body: Delivery },
  { id: "highlights", title: "Highlights", slot: "left", Body: Highlights },
  { id: "nextweek", title: "Planned for next week", slot: "right", Body: NextWeek },
  { id: "raid", title: "Risks, delays and items to watch", slot: "full", Body: Risks },
];

/** The date the status is as at: the project's week ending, else the published date, else today (YYYY-MM-DD). */
export function statusDate(project, asAtValue, isFile) {
  const w = project && project.week_ending;
  if (typeof w === "string" && w) return w;
  return isFile && asAtValue ? asAtValue : todayIso();
}

export function ClientReport({ tools }) {
  const d = data.value;
  const client = d.project.client_name;
  const on = statusDate(d.project, asAt.value, fromFile.value);
  return (
    <section class="frame report client-report" id="clientreport">
      <h1>{d.project.name}</h1>
      <p class="cr-cover"><b>WEEKLY PROGRESS SNAPSHOT</b> · Status as at <span class="num">{showDate(on)}</span>{client ? ` · for ${client}` : ""}</p>
      <div class="secs">
        {SECTIONS.map((s) => (
          <article key={s.id} class={`sec slot-${s.slot}`} id={`cr-${s.id}`} data-sec={s.id}>
            <header class="sec-head"><h2 class="sec-h">{s.title}</h2></header>
            <s.Body tools={tools} on={on} />
          </article>
        ))}
      </div>
    </section>
  );
}
