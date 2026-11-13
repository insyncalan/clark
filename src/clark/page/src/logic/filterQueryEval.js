// issue 662 step 3: a parsed filter line (filterQueryParse.js) applied to work items. A pure function over the items: no DOM, no store, no
// clock (today and the signed-in name come in through `ctx`). The line is compiled once into one test per term, and each item is
// then tested with no further parsing, so 1,000 items cost a few milliseconds.
//
//   ctx    { today: "YYYY-MM-DD", me: "Signed In Name" }   (the same ctx filterLine.js reads)
//   extra  custom fields [{key, name, none?, of(row, ctx) -> [values]}], the same list passed to schemaOf()
//
// Terms are ANDed. Inside one `field:a,b` the values are ORed. A token the parser marked as an error is not a term, so it filters
// nothing. `@me` is the signed-in name; where there is none it matches no item (and the term does not widen the result).
import { LINE_FIELDS, stored } from "./filterLine.js";
import { NONE } from "../filters.js";
import { parseQuery, schemaOf, ownSchema } from "./filterQueryParse.js";

const low = (s) => String(s == null ? "" : s).toLowerCase();
const has = Object.prototype.hasOwnProperty;

// A page's own schema (row 1085) answers for its fields alone; otherwise the Work items fields, then the custom ones.
function fieldDef(key, extra) {
  const own = ownSchema(extra);
  if (own) return own.fields.find((f) => f && f.key === key) || null;
  if (has.call(LINE_FIELDS, key)) return LINE_FIELDS[key];
  return (extra || []).find((f) => f && f.key === key) || null;
}
const textOf = (extra) => { const own = ownSchema(extra); return own && typeof own.text === "function" ? own.text : (row) => `${row.title || ""} ${row.id || ""}`; };
const valuesOf = (def, row, ctx) => { const v = def.of(row, ctx); return Array.isArray(v) ? v : []; };
// Nothing in the field: its "none" word is among the values, or (a field that cannot hold "none") it has no value at all.
const emptyIn = (def, row, ctx) => {
  const v = valuesOf(def, row, ctx);
  return def.none ? v.some((x) => x === NONE || x === "none") : v.length === 0;
};

// What one `field:a,b` term wants, in the words the field stores: the field's own spellings (next-7-days, shown, none), @me as the name.
function wanted(key, vals, ctx) {
  const me = low(ctx && ctx.me).trim();
  const out = new Set();
  for (const v of vals) {
    if (low(v) === "@me") { if (me) out.add(me); continue; }
    out.add(low(stored(key, v)));
  }
  return out;
}

function compileTerm(t, ctx, extra) {
  if (t.kind === "text") {
    const w = low(t.text), text = textOf(extra);
    return (row) => low(text(row)).includes(w);
  }
  if (t.kind === "state") {
    const states = t.states, is = LINE_FIELDS.is;
    return (row) => { const have = is.of(row, ctx); return states.some((s) => have.includes(s)) !== t.negate; };
  }
  if (t.kind === "presence") {
    const defs = t.fields.map((k) => fieldDef(k, extra)).filter(Boolean);
    return t.present ? (row) => defs.some((d) => !emptyIn(d, row, ctx)) : (row) => defs.some((d) => emptyIn(d, row, ctx));
  }
  if (t.kind === "field") {
    const def = fieldDef(t.field, extra);
    if (!def) return null;
    const want = wanted(t.field, t.values, ctx);
    const group = t.field === "usecase" ? [...want].flatMap((w) => [`use case ${w.replace(/^use\s*case\s*/, "")}`]) : [];     // 1 or 1.1 for "Use case 1"
    return (row) => {
      let hit = false;
      for (const h of valuesOf(def, row, ctx)) {
        const x = low(h);
        if (want.has(x) || group.some((g) => x === g || x.startsWith(`${g}.`))) { hit = true; break; }
      }
      return hit !== t.negate;
    };
  }
  return null;
}

/** One test for the whole line: row -> boolean. Errors and unknown fields are not terms, so they never narrow anything. */
export function compileQuery(parsed, ctx, extra) {
  const tests = parsed.terms.map((t) => compileTerm(t, ctx || {}, extra)).filter(Boolean);
  return (row) => { for (let i = 0; i < tests.length; i++) if (!tests[i](row)) return false; return true; };
}

/** The items a line shows, in their order. `query` is the line's text or what parseQuery returned for it. */
export function evaluateQuery(items, query, ctx, extra) {
  const parsed = typeof query === "string" || query == null ? parseQuery(query, schemaOf(extra)) : query;
  const test = compileQuery(parsed, ctx, extra);
  return (items || []).filter(test);
}
