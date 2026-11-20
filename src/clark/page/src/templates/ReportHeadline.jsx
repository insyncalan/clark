// Report headline (row 1261, slice 1), store type "reportheadline": its view part. Draws one flat block: the health pill (word, never
// colour alone), the headline and the supporting sentence, all as text nodes. isEmpty: no health, no headline and no sentence (the section
// is then left out of the served View and the published file alike). Its Edit part is edit/templates/ReportHeadline.jsx; the content
// rules are section_kinds/reportheadline.py.
import { source } from "./notes.js";

export const READY = true;
const HEALTHS = { on_track: ["On track", "g"], at_risk: ["At risk", "a"], off_track: ["Off track", "r"] };
const NOT_SET = ["Not set", "n"];
// The pill's icon (the mock-up's shapes, 14 by 14): check circle, triangle, cross circle, ring. The word beside it carries the meaning.
const ICONS = {
  on_track: ["check-circle", <><circle cx="7" cy="7" r="7" fill="currentColor" /><path d="M4 7l2 2 4-4.5" stroke="var(--pill-bg)" stroke-width="1.8" fill="none" /></>],
  at_risk: ["triangle", <path d="M7 1.5 13 12H1z" fill="currentColor" />],
  off_track: ["cross-circle", <><circle cx="7" cy="7" r="7" fill="currentColor" /><path d="M4.5 4.5l5 5M9.5 4.5l-5 5" stroke="var(--pill-bg)" stroke-width="1.8" /></>],
  "": ["ring", <circle cx="7" cy="7" r="5.5" fill="none" stroke="currentColor" stroke-width="2" />],
};
// The pill's icon alone (the Edit pill draws the same shape as the View capsule).
export const HealthIcon = ({ health }) => { const [icon, shape] = ICONS[health] || ICONS[""]; return <svg class="i" width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" data-hl={icon}>{shape}</svg>; };
const dmy = (iso) => (/^\d{4}-\d\d-\d\d$/.test(iso) ? iso.slice(8) + "-" + iso.slice(5, 7) + "-" + iso.slice(0, 4) : iso);

// The meta line: "<project> for <client> · Week ending <date>"; the client only when the Settings Client field is filled, each part only when known.
export function metaLine(project) {
  const p = project || {};
  const name = text(p.name), client = text(p.client_name), week = text(p.week_ending);
  const who = name ? (client ? `${name} for ${client}` : name) : "";
  return [who, week ? `Week ending ${dmy(week)}` : ""].filter(Boolean).join(" \u00b7 ");
}
const text = (v) => (typeof v === "string" ? v.trim() : "");

// The stored fields with every default filled (the same reading as section_kinds/reportheadline.py upgrade).
export function tidyReportHeadline(v) {
  const o = v && typeof v === "object" ? v : {};
  return { health: Object.prototype.hasOwnProperty.call(HEALTHS, o.health) ? o.health : "", headline: text(o.headline), sentence: text(o.sentence), pill: o.pill !== false };      // pill: the eye (row 1261), only false when the author hid it; an older body has no field and shows it
}
export const isEmpty = (section) => { const c = tidyReportHeadline(source(section)); return !(c.health && c.pill) && !c.headline && !c.sentence; };

export function View({ section, data }) {
  const c = tidyReportHeadline(source(section));
  const h = HEALTHS[c.health] || NOT_SET;
  const [icon, shape] = ICONS[c.health];
  const pill = c.pill ? <span class={`pill hpill tpl-rh-pill ${h[1]}`}><svg class="i" width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" data-hl={icon}>{shape}</svg>{h[0]}</span> : null;
  const meta = metaLine(data && data.project);
  return (
    <div class="tpl-rh-block">
      <p class="tpl-rh-title">Weekly report</p>
      {meta ? <p class="tpl-rh-meta">{meta}</p> : null}
    <div class={`tpl-rh${c.pill ? "" : " nopill"}`}>
      {pill}
      <div class="tpl-rh-text">
        {c.headline ? <p class="tpl-rh-h">{c.headline}</p> : null}
        {c.sentence ? <p class="tpl-rh-p">{c.sentence}</p> : null}
      </div>
    </div>
    </div>
  );
}
