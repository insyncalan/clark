// Client Requested Report View (#192): the Highlights and Planned for next week bodies, the half-width pair. Their words are the
// dashboard's own text sections ("This week" and "Next week"), typed there and never copied: this page only reads them. The words are
// drawn as the page's cleaner makes them (never the stored text as it is): in the live page through tools.RichRead (edit/, which holds
// cleanHtml), and in Edit through the dashboard's own editor (tools.RichField) once that is switched on. A published file's text was
// cleaned when it was published and is drawn as the dashboard draws it.
import { data, mode, fromFile } from "../../stores/report.js";
import { sectionFor } from "../../logic/clientReport.js";

const HIGHLIGHTS = /highlight|this week/i;
const NEXT = /next week/i;


function Words({ pattern, fallback, tools }) {
  const sec = sectionFor(data.value.report_sections, pattern, data.value.report_hidden);
  if (!sec) return <p class="quiet" data-empty="no-section">{`Nothing here yet. Add a "${fallback}" text section on the Dashboard and write it there.`}</p>;
  const empty = `Nothing written yet. Write it in the "${sec.title}" section on the Dashboard.`;
  const editing = !!(tools && tools.Gutter) && mode.value === "edit" && !fromFile.value;
  if (editing && tools.richOn && tools.richOn("body")) return <tools.RichField field="body" id={sec.id} value={sec.body} label={`${sec.title} text`} empty={empty} />;
  if (fromFile.value) return typeof sec.body === "string" && sec.body ? <div class="sec-body prose" dangerouslySetInnerHTML={{ __html: sec.body }} /> : <p class="quiet">{empty}</p>;
  if (tools && tools.RichRead) return <tools.RichRead html={sec.body} empty={empty} />;
  return <p class="quiet">{empty}</p>;
}

export function Highlights({ tools }) {
  return <Words pattern={HIGHLIGHTS} fallback="This week" tools={tools} />;
}

export function NextWeek({ tools }) {
  return <Words pattern={NEXT} fallback="Next week" tools={tools} />;
}
