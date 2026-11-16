// Report headline (row 1261, slice 1), store type "reportheadline": its view part. Draws one flat block: the health pill (word, never
// colour alone), the headline and the supporting sentence, all as text nodes. isEmpty: no health, no headline and no sentence (the section
// is then left out of the served View and the published file alike). Its Edit part is edit/templates/ReportHeadline.jsx; the content
// rules are section_kinds/reportheadline.py.
import { source } from "./notes.js";

export const READY = true;
const HEALTHS = { on_track: ["On track", "g"], at_risk: ["At risk", "a"], off_track: ["Off track", "r"] };
const text = (v) => (typeof v === "string" ? v.trim() : "");

// The stored fields with every default filled (the same reading as section_kinds/reportheadline.py upgrade).
export function tidyReportHeadline(v) {
  const o = v && typeof v === "object" ? v : {};
  return { health: Object.prototype.hasOwnProperty.call(HEALTHS, o.health) ? o.health : "", headline: text(o.headline), sentence: text(o.sentence) };
}
export const isEmpty = (section) => { const c = tidyReportHeadline(source(section)); return !c.health && !c.headline && !c.sentence; };

export function View({ section }) {
  const c = tidyReportHeadline(source(section));
  const h = HEALTHS[c.health];
  return (
    <div class="tpl-rh">
      {h ? <span class={`pill hpill tpl-rh-pill ${h[1]}`}>{h[0]}</span> : null}
      <div class="tpl-rh-text">
        {c.headline ? <p class="tpl-rh-h">{c.headline}</p> : null}
        {c.sentence ? <p class="tpl-rh-p">{c.sentence}</p> : null}
      </div>
    </div>
  );
}
