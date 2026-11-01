// Client Requested Report View (#192): the project in the weekly format a client has asked for. A page of its own, beside the
// Dashboard, Work items and Milestones, in the same frame and the same section look, under a dark cover band (the project, the
// week line and, in an own look, a picture and a logo). The sections come in one fixed order: Overall progress, Progress by plan,
// Highlights and Planned for next week (a half-width pair), Risks, delays and items to watch. Each section's body is its own
// file under clientreport/, so one part can be replaced (the Progress tracker, #189) without touching the others.
// The page is drawn in View and in Edit, and a published file carries it as a tab (publish.py): there it reads only what the file
// holds. Nothing on it is an instruction to the author or an explanation of how a figure is worked out: the client reads it.
import { data, asAt, fromFile } from "../stores/report.js";
import { showDate, todayIso } from "../workItems.js";
import { Overall } from "./clientreport/Overall.jsx";
import { Plans } from "./clientreport/Plans.jsx";
import { Highlights, NextWeek } from "./clientreport/Pair.jsx";
import { Risks } from "./clientreport/Risks.jsx";

// The fixed order, and where each section sits: full row, or the left or right half of a pair.
export const SECTIONS = [
  { id: "progress", title: "Overall progress", slot: "full", Body: Overall },
  { id: "plans", title: "Progress by plan", slot: "full", Body: Plans },
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
      <header class="cr-band">
        <h1>{d.project.name}</h1>
        <p class="cr-cover"><b>WEEKLY PROGRESS SNAPSHOT</b> · Status as at <span class="num">{showDate(on)}</span>{client ? ` · for ${client}` : ""}</p>
      </header>
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
