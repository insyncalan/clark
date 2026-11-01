// Key dates (#96), store type "keydates": its view part. Draws the dates soonest first, from the section's own content and the
// report's data only (no server call), so the published file and the served View read alike. Text nodes only, never
// dangerouslySetInnerHTML; days through ./safe.js. isEmpty: true leaves the section out of the served View and the published file.
import { fromFile, asAt } from "../stores/report.js";
import { todayIso } from "../logic/milestones.js";
import { linesOf, showDay } from "./keydates.js";

export const READY = true;

const options = () => ({ fromFile: fromFile.value, today: fromFile.value && asAt.value ? asAt.value : todayIso() });
export const isEmpty = (section, data) => linesOf(section, data, options()).length === 0;

export function View({ section, data }) {
  const lines = linesOf(section, data, options());
  if (!lines.length) return null;
  return (
    <ul class="tpl-dates" data-tpl="keydates">
      {lines.map((l) => (
        <li key={l.key} class={`tpl-dates-row${l.tone ? ` is-${l.tone}` : ""}`}>
          <span class="tpl-dates-day">{showDay(l.date)}</span>
          <span class="tpl-dates-label">{l.label}</span>
          {l.words ? <span class="tpl-dates-words">{l.words}</span> : null}
        </li>
      ))}
    </ul>
  );
}
