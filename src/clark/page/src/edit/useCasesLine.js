// Row 1085: the Use cases page's filter line, its tabs' counts and the rows it shows. An Edit part (the published file has no Use cases page and
// no filter line): it reads the filter line's parser, so its words stay out of the published bundle (logic/useCasesList.js is shared with it).
import { NONE } from "../filters.js";
import * as Q from "../logic/filterQueryUi.js";
import { compileQuery } from "../logic/filterQueryEval.js";
import { STATUS_WORDS, RAG, ON_WORDS, TABS, pickRows } from "../logic/useCasesList.js";

// ---- the filter line (row 1085) ----
// The page's own line, read by the Work items box (components/FilterLine.jsx LineBox) with this schema and no other: status:, commitment: and
// milestone: as the issue names them, on: for the eye (yes or no), and plain words that search the row's text (the reference, the name, the
// headline, where it stands, the commitment and the milestone names: `row.text`). Nothing of the Work items line is known here, and the line is
// kept with this page's state, never in the Work items line's memory.
const uniq = (xs) => [...new Set(xs.filter(Boolean))];
export const LINE = {
  fields: [
    { key: "status", name: "Status", of: (r) => [r.status], offers: () => STATUS_WORDS.map((w) => [w, w]), tone: (v) => RAG[STATUS_WORDS.find((w) => w.toLowerCase() === String(v).toLowerCase())] || "", icon: "half" },
    { key: "commitment", name: "Commitment", none: true, of: (r) => [r.commitment || NONE], offers: (rows) => uniq(rows.map((r) => r.commitment)).map((w) => [w, w]), icon: "flag" },
    { key: "milestone", name: "Milestone", none: true, of: (r) => (r.ms.length ? r.ms.map((m) => m.name) : [NONE]), offers: (rows) => uniq(rows.flatMap((r) => r.ms.map((m) => m.name))).map((w) => [w, w]), icon: "flag" },
    { key: "on", name: ON_WORDS, of: (r) => [r.on ? "yes" : "no"], offers: () => [["yes", "yes"], ["no", "no"]], icon: "eye" },
  ],
  states: [],
  text: (r) => r.text,
};
const CTX = {};
const parsedOf = (line, rows) => Q.parseFor(line, rows, CTX, LINE);
/** One test for the line: row -> true when the line keeps it. A word the line cannot use filters nothing. */
export const lineTest = (line, rows) => compileQuery(parsedOf(line, rows), CTX, LINE);
/** The line in two: its complete filters and the plain words (what the empty state says back). */
export const lineParts = (line, rows) => { const s = Q.splitLine(line, rows, CTX, LINE); return { chips: s.chips, words: parsedOf(s.rest, rows).text.join(" ") }; };


/** Each tab's count: the rows the line keeps that the tab keeps too (the counts follow the box, as the switch's did). */
export function tabCounts(rows, f) {
  const base = rows.filter(lineTest(f.line, rows));
  return Object.fromEntries(TABS.map(([id, , keeps]) => [id, base.filter(keeps).length]));
}

/** The rows the filters keep, in the chosen order (the sort is stable, so ties keep the data's order). */
export function shownOf(rows, f) {
  return pickRows(rows, f, lineTest(f.line, rows));
}
