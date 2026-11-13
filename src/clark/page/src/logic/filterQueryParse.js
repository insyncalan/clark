// issue 662 step 2: the parser of the filter line's text. A pure function: no DOM, no store, no clock. It lives next to filterLine.js
// (which keeps working for the tabs and views) and reads the same field list the columns and the line use (LINE_FIELDS), so a
// field added there, or passed in as `extra`, is understood with no change here.
//
//   free text            matches the title (case-insensitive substring; "two words" in quotes is one phrase)
//   field:value          one value        field names are case-insensitive: Status:x, "Use case":x, use-case:x, usecase:x
//   field:a,b            comma is OR within the field
//   field:a other:b      space is AND across tokens
//   -field:value         excludes
//   has:field  no:field  the field has something / nothing in it (a list of fields, has:owner,due, is OR)
//   is:open  -is:closed  a built-in state of the item
//   field:"two words"    values with spaces are quoted; @me is the signed-in person
//
// AN UNKNOWN OR AMBIGUOUS FIELD NAME IS NEVER GUESSED. The token comes back with an `error` ({code, name, suggestions, ...}) and the
// evaluation skips it, so it filters nothing. Aliases (ws, prio, state) are not read: a name is a field only when it is, ignoring case,
// spaces, hyphens and underscores, the key or the name of exactly one field. Nothing here is a sentence for the screen: errors carry
// codes and data, and the words are chosen where they are shown.
import { LINE_FIELDS, CLIENT_FIELDS, CLIENT_IS } from "./filterLine.js";
import { isPublished } from "../filters.js";

export const QUALIFIERS = ["is", "has", "no"];
export const STATES = ["open", "closed", "overdue", "quiet", "incomplete", "needed", "archived"];

const low = (s) => String(s == null ? "" : s).toLowerCase();
/** A name as compared: lower case with spaces, hyphens, underscores and the like taken out ("Use case", use-case, usecase). */
export const squash = (s) => low(s).replace(/[^a-z0-9]/g, "");

/** Row 1085: `extra` may be a page's own schema in place of the custom-field list: {fields: [{key, name, none?, of(row, ctx), offers?(rows, ctx), tone?(value), icon?, note?}],
 *  states?: [], text?(row)}. A line read with it knows only those fields (none of the Work items ones) and searches `text(row)` with plain words. */
export const ownSchema = (extra) => (extra && !Array.isArray(extra) && Array.isArray(extra.fields) ? extra : null);

/** The fields a line may name: [{key, name, custom}], from LINE_FIELDS (all but `is`, which is a qualifier) and `extra` custom fields
 *  [{key, name, none?, of(row, ctx)}]. In the published file only the fields a client may use. With a page's own schema, its fields alone. */
export function schemaOf(extra = []) {
  const own = ownSchema(extra);
  if (own) return { fields: own.fields.map((f) => ({ key: f.key, name: f.name, custom: true })), states: Array.isArray(own.states) ? own.states.slice() : [] };
  const fields = Object.keys(LINE_FIELDS).filter((k) => k !== "is" && (!isPublished() || CLIENT_FIELDS.includes(k)))
    .map((k) => ({ key: k, name: LINE_FIELDS[k].name, custom: false }));
  for (const f of extra || []) if (f && f.key && f.name) fields.push({ key: f.key, name: f.name, custom: true });
  const states = isPublished() ? STATES.filter((s) => CLIENT_IS.includes(s)) : STATES.slice();
  return { fields, states };
}

function distance(a, b) {
  const m = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]);
  for (let j = 1; j <= b.length; j++) m[0][j] = j;
  for (let i = 1; i <= a.length; i++) for (let j = 1; j <= b.length; j++) m[i][j] = Math.min(m[i - 1][j] + 1, m[i][j - 1] + 1, m[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
  return m[a.length][b.length];
}

/** The names closest to a word that is not one: [{key, name}], best first, at most `max`. Never applied, only offered. */
const MAX_SUGGEST_NAME = 60;
export function suggestFields(name, schema, max = 3) {
  const n = squash(name);
  if (!n || n.length > MAX_SUGGEST_NAME) return [];      // a very long word is never a near miss, and measuring it is slow
  const scored = schema.fields.map((f) => {
    const cands = [squash(f.key), squash(f.name)];
    const d = Math.min(...cands.map((c) => distance(n, c)));
    const near = cands.some((c) => (n.length >= 2 && c.startsWith(n)) || (c.length >= 3 && n.startsWith(c)) || (n.length >= 3 && c.includes(n)));
    return { f, d, near };
  }).filter((x) => x.near || x.d <= Math.max(1, Math.floor(n.length / 3)));
  scored.sort((a, b) => a.d - b.d);
  return scored.slice(0, max).map((x) => ({ key: x.f.key, name: x.f.name }));
}

/** A field name, read: {field: key} when it is exactly one field, {ambiguous: [keys]} when it is more than one (a custom field called
 *  Status, two custom fields called alike, or a field called Is, Has or No), else {unknown: true}. */
export function resolveField(name, schema) {
  const n = squash(name);
  const hits = schema.fields.filter((f) => squash(f.key) === n || squash(f.name) === n).map((f) => f.key);
  const uniq = [...new Set(hits)];
  const reserved = QUALIFIERS.includes(n);
  if (uniq.length + (reserved ? 1 : 0) > 1) return { ambiguous: [...(reserved ? [n] : []), ...uniq] };
  if (uniq.length === 1) return { field: uniq[0] };
  return { unknown: true };
}

// Cut a line into raw tokens at white space outside quotes. Each keeps its place in the line (start, end) for the underline.
function cut(line) {
  const out = []; let i = 0;
  const n = line.length;
  while (i < n) {
    if (/\s/.test(line[i])) { i++; continue; }
    const start = i; let q = false;
    while (i < n && (q || !/\s/.test(line[i]))) { if (line[i] === '"') q = !q; i++; }
    out.push({ raw: line.slice(start, i), start, end: i });
  }
  return out;
}
const unquote = (s) => s.replace(/"/g, "");
// The first colon outside quotes, or -1.
export function colonAt(s) {
  let q = false;
  for (let i = 0; i < s.length; i++) { if (s[i] === '"') q = !q; else if (s[i] === ":" && !q) return i; }
  return -1;
}
// Split at commas outside quotes; the quotes come off, empty values go.
function values(s) {
  const out = []; let cur = "", q = false;
  for (const ch of s) { if (ch === '"') q = !q; else if (ch === "," && !q) { out.push(cur); cur = ""; } else cur += ch; }
  out.push(cur);
  return out.map((v) => v.trim()).filter(Boolean);
}

function read(tok, schema) {
  const at = { raw: tok.raw, start: tok.start, end: tok.end };
  const ci = colonAt(tok.raw);
  if (ci <= 0) return { ...at, kind: "text", text: unquote(tok.raw), error: null };      // no colon (or one at the very start): plain words
  let negate = false, head = tok.raw.slice(0, ci);
  if (head.startsWith("-") && head.length > 1) { negate = true; head = head.slice(1); }
  const name = unquote(head).trim(), rest = tok.raw.slice(ci + 1), vals = values(rest);
  if (!name) return { ...at, kind: "text", text: unquote(tok.raw), error: null };
  const fail = (code, more) => ({ ...at, kind: "error", negate, name, error: { code, name, ...at, ...more } });
  const q = low(name);

  if (QUALIFIERS.includes(squash(name)) && schema.fields.some((f) => squash(f.key) === squash(name) || squash(f.name) === squash(name))) {
    return fail("ambiguous-field", { candidates: resolveField(name, schema).ambiguous });      // a field called Is, Has or No: which one was meant?
  }
  if (q === "has" || q === "no") {
    if (!vals.length) return fail("missing-value", { qualifier: q });
    const keys = [], bad = [];
    for (const v of vals) {
      const r = resolveField(v, schema);
      if (r.field) keys.push(r.field); else bad.push({ name: v, r });
    }
    if (bad.length) {
      const b = bad[0];
      return fail(b.r.ambiguous ? "ambiguous-field" : "unknown-field", { name: b.name, qualifier: q, ...(b.r.ambiguous ? { candidates: b.r.ambiguous } : { suggestions: suggestFields(b.name, schema) }) });
    }
    // no:owner = nothing there; has:owner = something there; a leading - flips it.
    return { ...at, kind: "presence", fields: [...new Set(keys)], present: (q === "has") !== negate, negate, error: null };
  }
  if (q === "is") {
    if (!vals.length) return fail("missing-value", { qualifier: "is" });
    const states = vals.map(low), bad = states.find((s) => !schema.states.includes(s));
    if (bad !== undefined) {
      const s = suggestFields(bad, { fields: schema.states.map((x) => ({ key: x, name: x })) });
      return fail("unknown-state", { name: bad, qualifier: "is", suggestions: s });
    }
    return { ...at, kind: "state", states: [...new Set(states)], negate, error: null };
  }
  const r = resolveField(name, schema);
  if (r.ambiguous) return fail("ambiguous-field", { candidates: r.ambiguous });
  if (r.unknown) return fail("unknown-field", { suggestions: suggestFields(name, schema) });
  if (!vals.length) return fail("missing-value", { field: r.field });
  return { ...at, kind: "field", field: r.field, values: vals, negate, error: null };
}

/** A line, read. {tokens, errors, terms, text}.
 *  tokens: every word in order, each {kind: "text" | "field" | "presence" | "state" | "error", raw, start, end, error, ...parts}
 *  errors: the tokens that could not be used, each {code: "unknown-field" | "ambiguous-field" | "unknown-state" | "missing-value",
 *          name, raw, start, end, suggestions | candidates}; they filter nothing
 *  terms:  the tokens that apply (all but the errors), the input of the evaluation
 *  text:   the plain words (the free text) in order */
export function parseQuery(line, schema) {
  const s = schema || schemaOf();
  const src = String(line == null ? "" : line);
  const tokens = cut(src).map((t) => read(t, s));
  return {
    tokens,
    errors: tokens.filter((t) => t.error).map((t) => t.error),
    terms: tokens.filter((t) => !t.error),
    text: tokens.filter((t) => t.kind === "text").map((t) => t.text),
  };
}
