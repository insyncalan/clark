// The week picker beside "Week ending" (item 344, follow-on 3 of the item 125 design note): its words and its options, as plain functions
// with no DOM, so a test can run them alone. The options follow the prototype (system/prototype/past.js, C.pastPickHtml): a first
// "Published weeks" line, then each publication newest first as "DD-MM-YYYY · Publication N" (the week ending it was for), then
// "Dashboard as at a day…". Two publications for one week are two lines. The rows are the Published reports list's (past_reports.py).
export const LABEL = "Open a published week";
export const FIRST = "Published weeks";
export const AS_AT = "Dashboard as at a day…";
export const REBUILT = "rebuilt";             // a publication whose page was not kept opens as the Dashboard as at its day
export const OPENING = "Opening Publication {n} as it was published.";

const shown = (iso) => (/^\d{4}-\d\d-\d\d$/.test(iso || "") ? iso.slice(8) + "-" + iso.slice(5, 7) + "-" + iso.slice(0, 4) : "");
const isDay = (iso) => /^\d{4}-\d\d-\d\d$/.test(iso || "");

/** One option per publication that can be opened: a kept page opens as it was published; one that was not kept opens as the
 *  Dashboard as at the day it was published, rebuilt from the change history, and says so. One with neither is left out. */
export function options(publications) {
  const out = [];
  for (const p of Array.isArray(publications) ? publications : []) {
    if (!p || !Number.isInteger(p.number) || p.number < 1) continue;
    const kept = p.kept === true;
    if (!kept && !isDay(p.day)) continue;
    const week = shown(p.week) || shown(p.day);
    out.push({ value: String(p.number), number: p.number, kept, day: isDay(p.day) ? p.day : "",
               text: `${week} · Publication ${p.number}${kept ? "" : " · " + REBUILT}` });
  }
  return out;
}

export const opening = (n) => OPENING.replace("{n}", String(n));
