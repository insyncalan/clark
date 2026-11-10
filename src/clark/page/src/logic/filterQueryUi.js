// The filter line's box, as plain functions (issue 662, steps 4 and 5): what the typed text looks like (its highlighted pieces), the words
// for a token that cannot be used, the rows a line shows, and the list of suggestions with how a chosen one changes the text. No DOM,
// no store, no clock: the component (components/FilterLine.jsx) draws these and owns the timing. It reads the parser and the evaluation of
// issue 662 (filterQueryParse.js, filterQueryEval.js), so a field added to the schema, or passed in as `extra`, is understood here too.
import { LINE_FIELDS, FIELD_NOTES, NO_ME, unknownFilter, offers, isOn, word as typedWord, isStartingView } from "./filterLine.js";
import { NONE } from "../filters.js";
import { parseQuery, schemaOf, ownSchema, resolveField, squash, colonAt } from "./filterQueryParse.js";
import { evaluateQuery } from "./filterQueryEval.js";

const low = (s) => String(s == null ? "" : s).toLowerCase();
const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
const quoted = (v) => (/[\s,":]/.test(v) ? `"${String(v).replace(/"/g, "")}"` : String(v));

// ── The schema the page answers ───────────────────────────────────────────────────────────────────────────────────────────

const cache = { rows: null, key: "", schema: null, extra: null };
/** schemaOf() less the `is:` words this page cannot answer yet (the page turns them on with ctx.isReady), so such a word reads as an unknown state. */
export function pageSchema(rows, ctx, extra) {
  const c = ctx || {}, key = `${c.isReady ? 1 : 0}${c.quietReady ? 1 : 0}`;
  if (cache.rows === rows && cache.key === key && cache.extra === (extra || null) && cache.schema) return cache.schema;
  const base = schemaOf(extra || []);
  const schema = { ...base, states: base.states.filter((s) => isOn(s, c, rows)) };
  Object.assign(cache, { rows, key, schema, extra: extra || null });
  return schema;
}
export const parseFor = (line, rows, ctx, extra) => parseQuery(line, pageSchema(rows, ctx, extra));

/** The rows a line shows, in their order. */
export const rowsFor = (rows, line, ctx, extra) => evaluateQuery(rows, parseFor(line, rows, ctx, extra), ctx, extra);

// ── The words for a token that cannot be used ─────────────────────────────────────────────────────────────────────────────

/** The sentence for a token the parser could not use ("" when there is nothing to say). With a page's own schema (row 1085) the sentence
 *  names that page's fields. */
export function messageOf(e, extra) {
  if (!e) return "";
  const first = e.suggestions && e.suggestions[0], own = ownSchema(extra);
  switch (e.code) {
    case "unknown-field": if (!e.qualifier) return own ? unknownFilter(e.name, own.fields.map((f) => f.key), first ? first.key : "") : unknownFilter(e.name);      // a word before a colon: the line's own sentence; has: and no: keep theirs
      return first ? `Unknown field '${e.name}'. Did you mean ${first.name}?` : `Unknown field '${e.name}'.`;
    case "ambiguous-field": return `'${e.name}' could mean more than one field. Use the full name.`;
    case "unknown-state": return first ? `Unknown state '${e.name}'. Did you mean ${first.name}?` : `Unknown state '${e.name}'.`;
    case "missing-value": return `Add a value after '${e.name}:'.`;
    default: return "";
  }
}

/** The words of the empty state (the list shows them; they live here so the published file's code holds none of them). */
export const EMPTY = { none: "No work items match.", clear: "Clear filter" };

/** True when `@me` (or the older `me`) is asked of the owner and no name is set. */
export function wantsMe(parsed, ctx) {
  if (String((ctx && ctx.me) || "").trim()) return false;
  return parsed.terms.some((t) => t.kind === "field" && t.field === "owner" && t.values.some((v) => ["@me", "me"].includes(low(v))));
}
export { NO_ME };

// ── Colours of the single-select values ───────────────────────────────────────────────────────────────────────────────────
// The pill colours the list already uses: a priority is red, amber or green (workItems.colourOf); a status is as its pill reads.
const TONES = {
  priority: { urgent: "r", high: "r", medium: "a", low: "g" },
  status: { open: "b", pending: "b", delayed: "a", closed: "n", cancelled: "n", made: "g", withdrawn: "n" },
};
export const toneOf = (field, value) => (has(TONES, field) && has(TONES[field], low(value)) ? TONES[field][low(value)] : "");
// A page's own field (row 1085) names its own tones; a Work items field has the pill colours above.
const ownField = (extra, key) => { const own = ownSchema(extra); return own ? own.fields.find((f) => f && f.key === key) || null : null; };
const toneFor = (extra, field, value) => { const f = ownField(extra, field); return f ? (typeof f.tone === "function" ? f.tone(value) || "" : "") : toneOf(field, value); };

// ── The typed text, in pieces ─────────────────────────────────────────────────────────────────────────────────────────────

function splitCommas(s) {
  const out = []; let cur = "", q = false;
  for (const ch of s) { if (ch === '"') { q = !q; cur += ch; } else if (ch === "," && !q) { out.push(cur); cur = ""; } else cur += ch; }
  out.push(cur);
  return out;
}

/** The line cut into pieces to draw: [{text, cls: "gap" | "txt" | "fld" | "val" | "sep" | "err", tone?, message?, start?, end?}].
 *  Together the pieces are exactly the line. Field names are plain, values are chips, an unusable token is "err" with its words.
 *  `caret`: a token still being typed (a field name with nothing after the colon yet) is not marked while the caret is in it.
 *  `extra`: the page's own schema (row 1085), for its messages and tones; none for the Work items line. */
export function pieces(line, parsed, caret, extra) {
  const out = []; let at = 0;
  const push = (text, cls, more) => { if (text) out.push({ text, cls, ...more }); };
  for (const t of parsed.tokens) {
    if (t.start > at) push(line.slice(at, t.start), "gap");
    at = t.end;
    const typing = t.error && t.error.code === "missing-value" && caret !== undefined && caret >= t.start && caret <= t.end;
    if (t.error && !typing) { push(t.raw, "err", { message: messageOf(t.error, extra), start: t.start, end: t.end }); continue; }
    if (t.kind === "text" || typing) { push(t.raw, "txt"); continue; }
    const ci = colonAt(t.raw);
    push(t.raw.slice(0, ci + 1), "fld");
    splitCommas(t.raw.slice(ci + 1)).forEach((v, i) => {
      if (i) push(",", "sep");
      push(v, "val", { tone: t.kind === "field" ? toneFor(extra, t.field, v.replace(/"/g, "")) : "" });
    });
  }
  if (at < line.length) push(line.slice(at), "gap");
  return out;
}

// ── Saved views: the same line, however it is spaced or ordered ───────────────────────────────────────────────────────────

const keyOf = (p) => p.tokens.map((t) => {
  if (t.error || t.kind === "text") return `"${low(t.raw.replace(/"/g, ""))}`;
  const list = (t.values || t.states || t.fields || []).map(low).sort().join(",");
  return `${t.negate ? "-" : ""}${t.kind}:${t.field || ""}:${list}${t.kind === "presence" ? (t.present ? "+" : "-") : ""}`;
}).sort().join(" ");
/** True when the line is not the view's saved line (the dot on the tab). */
export function differsQuery(view, line, rows, ctx, extra) {
  if (!view) return false;
  return keyOf(parseFor(view.line, rows, ctx, extra)) !== keyOf(parseFor(line, rows, ctx, extra));
}
/** Why a saved view cannot be used, in the words the tab row already has, or "" when it can. */
export function troubleQuery(view, rows, ctx, extra) {
  if (!view) return "";
  const errors = parseFor(view.line, rows, ctx, extra).errors;
  if (!errors.length) return "";
  const first = /^(.+?[.?!])(\s|$)/.exec(messageOf(errors[0]));
  return `This view cannot be used any more. ${first ? first[1] : "Its words are not ones the filter line knows."} Rename it or delete it.`;
}
export const heldBackQuery = (view, rows, ctx, extra) => isStartingView(view) && troubleQuery(view, rows, ctx, extra) !== "";

// ── The Open / Closed / All and type switches, written on the text ────────────────────────────────────────────────────────

const RAID = "risk,issue,assumption,dependency";
const isModeTok = (t) => t.kind === "state" && !t.negate && t.states.every((s) => s === "open" || s === "closed");
const isTypeTok = (t) => t.kind === "field" && t.field === "type" && !t.negate;
function groups(line, rows, ctx, extra) {
  const p = parseFor(line, rows, ctx, extra);
  return { mode: p.tokens.filter(isModeTok).map((t) => t.raw), type: p.tokens.filter(isTypeTok).map((t) => t.raw), rest: p.tokens.filter((t) => !isModeTok(t) && !isTypeTok(t)).map((t) => t.raw) };
}
/** The empty state's words for a line (row 789): what was typed beyond the Open / Closed / All and type switches, said back with the view; the
 *  hint says what a plain word does. With nothing typed (an empty project view) the older words stand. */
export function emptyWords(line, rows, ctx, extra) {
  const g = groups(line, rows, ctx, extra), typed = g.rest.join(" ").trim();
  if (!typed) return { none: EMPTY.none, clear: EMPTY.clear, hint: "" };
  const open = g.mode.length === 1 && /^is:open$/i.test(g.mode[0]);
  return { none: `No ${open ? "open items" : "items"} match "${typed}".`, clear: "Clear search", hint: "Plain words search titles. Press / to come back here." };
}
const join = (g) => [...g.mode, ...g.type, ...g.rest].join(" ");
/** The line with the Open / Closed / All switch changed ("all": no `is:open` or `is:closed`); everything else in the line stays as typed. */
export function withMode(line, mode, rows, ctx, extra) {
  const g = groups(line, rows, ctx, extra);
  return join({ ...g, mode: mode === "open" || mode === "closed" ? [`is:${mode}`] : [] });
}
/** The line with the type switch changed ("all": no `type:`). */
export function withType(line, type, rows, ctx, extra) {
  const g = groups(line, rows, ctx, extra);
  const w = type === "risk" ? RAID : type === "action" || type === "decision" ? type : "";
  return join({ ...g, type: w ? [`type:${w}`] : [] });
}
/** The line with every token that `pred(token)` is true of taken out. */
export function withoutTokens(line, pred, rows, ctx, extra) {
  return parseFor(line, rows, ctx, extra).tokens.filter((t) => !pred(t)).map((t) => t.raw).join(" ");
}

// ── Autocomplete ──────────────────────────────────────────────────────────────────────────────────────────────────────────

/** The word the caret is in (or just after): {start, word}. White space inside quotes does not end a word. */
export function wordAt(text, caret) {
  const s = String(text || "").slice(0, caret === undefined ? undefined : caret);
  let start = 0, q = false;
  for (let i = 0; i < s.length; i++) { if (s[i] === '"') q = !q; else if (/\s/.test(s[i]) && !q) start = i + 1; }
  return { start, word: s.slice(start) };
}

const noteOf = (key) => (has(FIELD_NOTES, key) ? FIELD_NOTES[key] : "");
// Row 931: the icon (a name in components/Icon.jsx) on a field row and on the lead rows of a field; a custom field has the filter icon.
export const FIELD_ICONS = { is: "check", type: "table", status: "half", owner: "user", priority: "flash", due: "cal", workstream: "bars",
  usecase: "doc", milestone: "flag", client: "ext", has: "eye", no: "eyeoff" };
export const iconOf = (key) => (has(FIELD_ICONS, key) ? FIELD_ICONS[key] : "filter");
const fieldRow = (key, neg, note = noteOf(key), icon = iconOf(key)) => ({ kind: "field", ins: `${neg ? "-" : ""}${key}:`, label: `${neg ? "-" : ""}${key}:`, note, icon, close: false });

/** What to offer for the word the caret is in. [{kind: "field" | "lead" | "value", ins, label, note, tone?, close}]:
 *  - an empty word: every filterable field, `is:` first, then the built-in fields, the custom ones, `has:` and `no:`; narrowed as it is typed
 *  - after `field:`: "No X", "Has X", "Exclude X", then the field's values (a `close` row ends the word: a space follows, then the field list again)
 *  - after `is:`, `has:`, `no:`: the states, or the fields. */
export function suggestions(text, caret, rows, ctx, extra) {
  const schema = pageSchema(rows, ctx, extra), c = ctx || {}, own = ownSchema(extra);
  const { word } = wordAt(text, caret);
  const neg = word.startsWith("-"), body = neg ? word.slice(1) : word, ci = colonAt(body);
  if (ci < 0) {
    const n = squash(body);
    const fit = (key, name) => !n || squash(key).startsWith(n) || squash(name || key).startsWith(n);
    const out = [];
    if (schema.states.length && fit("is")) out.push(fieldRow("is", neg));          // a page's own schema with no states has no is:
    for (const f of [...schema.fields.filter((x) => !x.custom), ...schema.fields.filter((x) => x.custom)]) {
      const o = ownField(extra, f.key);
      if (fit(f.key, f.name)) out.push(o ? fieldRow(f.key, neg, o.note || "", o.icon || iconOf(f.key)) : fieldRow(f.key, neg));
    }
    if (!neg) for (const q of ["has", "no"]) if (fit(q)) out.push(own ? fieldRow(q, false, "") : fieldRow(q, false));   // the Work items note names owner and date: not this page's
    return out;
  }
  const name = body.slice(0, ci).replace(/"/g, "").trim(), rest = body.slice(ci + 1);
  const cut = rest.lastIndexOf(",") + 1, done = rest.slice(0, cut), part = low(rest.slice(cut).replace(/"/g, ""));
  const taken = done.split(",").map((v) => low(v.replace(/"/g, "").trim())).filter(Boolean);
  const pre = neg ? "-" : "", q = squash(name);
  if (q === "has" || q === "no") {
    const p = squash(part);
    return schema.fields.filter((f) => !taken.includes(squash(f.key)) && (!p || squash(f.key).startsWith(p) || squash(f.name).startsWith(p)))
      .map((f) => ({ kind: "value", ins: `${pre}${q}:${done}${f.key}`, label: f.key, note: f.name, icon: iconOf(f.key), close: true }));
  }
  if (q === "is") {
    return offers("is", rows, c).filter(([v]) => schema.states.includes(v) && !taken.includes(v) && (!part || v.startsWith(part)))
      .map(([v, l]) => ({ kind: "value", ins: `${pre}is:${done}${v}`, label: v, note: low(l) !== v ? l : "", close: true }));
  }
  const r = resolveField(name, schema);
  if (!r.field) return [];
  const k = r.field, F = schema.fields.find((f) => f.key === k);
  const out = [];
  if (!done && !part && !neg) {
    out.push({ kind: "lead", ins: `no:${k}`, label: `No ${F.name}`, note: "", icon: iconOf(k), close: true });
    out.push({ kind: "lead", ins: `has:${k}`, label: `Has ${F.name}`, note: "", icon: iconOf(k), close: true });
    out.push({ kind: "lead", ins: `-${k}:`, label: `Exclude ${F.name}`, note: "", icon: "circleminus", close: false });
  }
  const mine = ownField(extra, k);
  if (mine) {                                                                     // a page's own field: the values it offers, each with its own tone
    for (const [v, l] of typeof mine.offers === "function" ? mine.offers(rows, c) : []) {
      if (v === NONE || v === "none" || taken.includes(low(v))) continue;
      if (part && !low(v).includes(part) && !low(l).includes(part)) continue;
      out.push({ kind: "value", ins: `${pre}${k}:${done}${quoted(v)}`, label: v, note: l !== v ? l : "", tone: toneFor(extra, k, v), close: true });
    }
    return out;
  }
  if (!has(LINE_FIELDS, k)) return out;                                          // a custom field: the three lead rows only
  for (const [v, l] of offers(k, rows, c)) {
    if (v === NONE || v === "none") continue;                                    // "nothing there" is the lead row "No X"
    const typed = k === "owner" && v === "me" ? "@me" : typedWord(k, v);
    if (taken.includes(low(typed))) continue;
    if (part && !low(typed).includes(part) && !low(l).includes(part)) continue;
    out.push({ kind: "value", ins: `${pre}${k}:${done}${quoted(typed)}`, label: typed, note: l !== typed ? l : "", tone: toneOf(k, typed), close: true });
  }
  return out;
}

/** Item 1014: Backspace or Delete with the caret right after a half-typed `field:value` takes the whole word away. Returns the text and caret
 *  after it goes, or null when the caret is not at the end of such a word (a bare `field:`, a plain word, a caret inside the word, or Delete with a space after the caret: that takes the space). */
export function dropWordAt(text, caret, key) {
  const s = String(text || ""), { start, word } = wordAt(s, caret);
  if (!/^-?[a-z]+:./i.test(word) || (caret < s.length && (key === "Delete" || !/\s/.test(s[caret])))) return null;
  return { text: s.slice(0, start) + s.slice(caret).replace(/^\s+/, ""), caret: start };
}

/** The text and caret after choosing `opt` for the word the caret is in. A choice that ends the word adds one space after it. */
export function accept(text, caret, opt) {
  const { start } = wordAt(text, caret);
  let tail = String(text).slice(caret);
  if (opt.close && /^\s/.test(tail)) tail = tail.slice(1);
  const head = String(text).slice(0, start) + opt.ins + (opt.close ? " " : "");
  return { text: head + tail, caret: head.length };
}

// ── Chips: the words of the line that are complete filters (row 845) ───────────────────────────────────────────────────────
// The line stays one text (the saved views, the count and the parser read it); the box draws the complete filters as chips, each with its own
// remove button, and holds only the rest (plain words, a word still being typed, a word that cannot be used).

const isChipToken = (t) => !t.error && t.kind !== "text";
const spaceAt = (s, i) => i < s.length && /\s/.test(s[i]);

/** A line cut in two: its complete filters (each as typed) and the rest of the line (plain words and unusable words, in order). */
export function splitLine(line, rows, ctx, extra) {
  const toks = parseFor(line, rows, ctx, extra).tokens;
  return { chips: toks.filter(isChipToken).map((t) => t.raw), rest: toks.filter((t) => !isChipToken(t)).map((t) => t.raw).join(" ") };
}

/** The chips and the text in the box as one line. */
export function joinLine(chips, draft) {
  const d = draft || "";
  return d === "" ? chips.join(" ") : [...chips, d].join(" ");
}

/** Complete filters the caret has moved past (a space follows them) leave the text and become chips: {chips: [typed], text, caret}. */
export function commitDraft(text, caret, rows, ctx, extra) {
  const done = parseFor(text, rows, ctx, extra).tokens.filter((t) => isChipToken(t) && t.end < caret && spaceAt(text, t.end));
  if (!done.length) return { chips: [], text, caret };
  let out = "", at = 0, back = 0;
  for (const t of done) {
    let e = t.end;
    while (spaceAt(text, e)) e++;
    out += text.slice(at, t.start); at = e;
    back += Math.min(e, caret) - t.start;
  }
  return { chips: done.map((t) => t.raw), text: out + text.slice(at), caret: caret - back };
}

const keyOfToken = (t) => (t.kind === "field" ? t.field : t.kind === "state" ? "is" : `${t.present ? "has" : "no"}:${(t.fields || []).join(",")}`);

/** The suggestions with `n` on each row that closes a word: how many items the line would show with that choice in place of the chips on the
 *  same field (row 846; the other chips still count). */
export function withCounts(options, chips, rows, ctx, extra) {
  if (!options.some((o) => o.close)) return options;
  const held = chips.map((c) => ({ raw: c, tok: parseFor(c, rows, ctx, extra).tokens[0] }));
  return options.map((o) => {
    if (!o.close) return o;
    const t = parseFor(o.ins, rows, ctx, extra).tokens[0];
    if (!t || t.error || t.kind === "text") return o;
    const k = keyOfToken(t), keep = held.filter((h) => !(h.tok && !h.tok.error && keyOfToken(h.tok) === k)).map((h) => h.raw);
    return { ...o, n: rowsFor(rows, [...keep, o.ins].join(" "), ctx, extra).length };
  });
}

/** The word a chip's remove button names: the field's name, or the word typed before the colon (is, has, no). */
export function chipName(chip, rows, ctx, extra) {
  const t = parseFor(chip, rows, ctx, extra).tokens[0];
  if (t && t.kind === "field") { const f = pageSchema(rows, ctx, extra).fields.find((x) => x.key === t.field); return f ? f.name : t.field; }
  return String(chip).replace(/^-/, "").split(":")[0];
}
