// Row 1085: the Use cases page's filter line. The box is the Work items one (components/FilterLine.jsx LineBox: the same chips, token drawing,
// count, x, suggestions and keys), drawn here over this page's own line (logic/useCasesList.js LINE: status:, commitment:, milestone:, on: and plain
// words) and this page's own remembered state, so nothing typed here reaches the Work items line or its memory. No Try row (the approved design
// takes it away). An Edit part: the published file has no Use cases page.
import { LineBox } from "../components/FilterLine.jsx";
import { LINE } from "./useCasesLine.js";

// The box's element ids: the input keeps the old search box's id (it is that box's successor, and the tests and the keys know it by that name).
const IDS = { input: "ucl-q", list: "ucl-q-list", count: "ucl-q-count", x: "ucl-q-x", msg: "ucl-q-msg", gloss: "ucl-q-gloss", opt: "ucl-qo" };
const CTX = {};

/** `f` is the page's state, `rows` its rows, `now()` reads the line as it is this moment and `apply(text)` makes `text` the line. */
export function UseCasesFilter({ f, rows, now, apply }) {
  return <LineBox line={f.line} now={now} apply={apply} rows={rows} ctx={CTX} extra={LINE} ids={IDS} label="Search use cases" />;
}
