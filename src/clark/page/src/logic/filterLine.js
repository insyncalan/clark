// The one filter line for Work items (#153; the prototype is #145): pure functions with no DOM and no clock (today and the
// signed-in name are passed in). The line is plain text, read and written here, and every part of it can be shown as a chip:
//
//   type:action   status:Open,Pending   -status:Closed   no:owner   due:overdue   owner:"First Last"   supplier   is:quiet
//
// A field and its values are written `field:value,value` (either); a leading `-` means not; `no:field` finds the items with
// nothing in that field; plain words search titles (and IDs). A word the line cannot use is never applied and never empties
// the list: it comes back as one plain sentence saying what can be used (see `parse().errors`).
//
// The line and the older filter state (filters.js: the Open / Closed / All switch, the type switch and eight filter boxes) are
// two spellings of the same thing: `fromState` and `toState` go between them, so the At a glance tiles open a line that shows
// what they counted and every older filter stays reachable. The address key `f` (filters.js encode / decode) is unchanged.
//
// Also here: saved views per project (lists, add, rename, archive, and whether the line differs from the saved one) and the
// session memory of the line per project. Views are archived, never deleted.
import { dayNumber, dueField, isOpen } from "../workItems.js";
import { initial, FIELDS as STATE_FIELDS, NONE, dueBucket, hasReviewDates } from "../filters.js";

// ── The words a person reads ─────────────────────────────────────────────────────────────────────────────────────────────

export const NO_ME = "Set your name in Settings to see your actions.";
export const BASE = "is:open";                       // the line a Work items page starts on, and the one Clear all goes back to
export const PLACEHOLDER = "Filter by keyword or by field";
export const QUIET_DAYS = 14;
const MAX_LIST = 8;

const list = (a, and = "and") => (a.length < 2 ? a.join("") : `${a.slice(0, -1).join(", ")} ${and} ${a[a.length - 1]}`);
// Every lookup keyed by what a person typed goes through `own`, so a word such as constructor or __proto__ is just an unknown word.
const own = (o, k) => (Object.prototype.hasOwnProperty.call(o, k) ? o[k] : undefined);
const low = (s) => String(s == null ? "" : s).toLowerCase();
const quote = (v) => (/[\s,":]/.test(v) ? `"${String(v).replace(/"/g, "")}"` : String(v));

// ── The fields ───────────────────────────────────────────────────────────────────────────────────────────────────────────
// For each field: its name as a person reads it, the state field it is in filters.js (null: only the line has it), whether an
// item can have nothing there (so `no:` works), and `of(row, ctx)`, the values the row has, in the words the line stores them
// in (the same as filters.js stores them: "(none)" for nothing, "soon" for the next seven days, "yes" or "no" for the client).

const KINDS = [["action", "Action"], ["risk", "Risk"], ["issue", "Issue"], ["assumption", "Assumption"], ["dependency", "Dependency"], ["decision", "Decision"]];
const RAID_KINDS = ["risk", "issue", "assumption", "dependency"];
const STATUSES = ["Open", "Pending", "Delayed", "Closed", "Cancelled"];
const DECISION_STATUSES = ["Made", "Withdrawn"];
const PRIORITIES = ["Urgent", "High", "Medium", "Low"];
const DUE_WORDS = [["overdue", "Overdue (the date has passed)"], ["today", "Today"], ["next-7-days", "In the next 7 days"], ["later", "Later than 7 days"], ["none", "No date"]];
const IS_WORDS = [["open", "Open"], ["closed", "Closed"], ["overdue", "Open and overdue"], ["quiet", `Not reviewed in ${QUIET_DAYS} days`],
  ["incomplete", "No owner or no date"], ["needed", "Needed from the client"], ["archived", "Archived"]];
// `is:` words that match nothing until the page supplies the data behind them. The page turns them on with `ctx.isReady: true`;
// until then they are not offered and, typed, say so in plain words. Each is [what the page calls it].
// `is:quiet` is the Freshness filter's "not reviewed" (counted from the same date fields, but 14 days or more), so it is on as soon as some row carries
// a date to count from (hasReviewDates), or when the page says so; `is:incomplete` needs only the owner and the date, so it is always on.
const NOT_YET = { needed: "Work needed from the client", archived: "Archived work" };
const QUIET_OFF = "Not reviewed in 14 days";
const quietOn = (rows, ctx) => !!(ctx && ctx.isReady) || (rows || []).some((r) => r && r.reviewed) || hasReviewDates(rows);
const isOn = (v, ctx, rows) => (v === "quiet" ? quietOn(rows, ctx) : !own(NOT_YET, v) || !!(ctx && ctx.isReady));
const PLURAL = { owner: "owners", workstream: "workstreams", usecase: "use cases", milestone: "milestones" };
const CLIENT_WORDS = [["shown", "Shown to the client"], ["internal", "Internal only"]];
const GLOSS = { quiet: `Not reviewed in ${QUIET_DAYS} days`, incomplete: "No owner or no date" };

const text = (v) => (v == null ? "" : String(v).trim());
const blank = (v) => !text(v) || low(text(v)) === "tbc";

function dueValues(row, ctx) {
  const a = dayNumber(dueField(row)), t = dayNumber(ctx.today);
  if (a === null || t === null) return ["none"];
  if (!isOpen(row)) return [];
  const n = a - t;
  return n < 0 ? ["overdue"] : n === 0 ? ["today", "soon"] : n <= 7 ? ["soon"] : ["later"];
}

// `is:quiet` is 14 days or more (a review exactly 14 days ago is quiet, 13 is not). The Freshness filter (filters.js notReviewed) keeps
// its own rule, "more than 14", so the line counts from the same date fields with its own comparison.
function quietRow(row, today) {
  if (!isOpen(row)) return false;
  if (typeof row.not_reviewed === "boolean") return row.not_reviewed;
  const since = dayNumber(row.last_reviewed || row.reviewed || row.raised), t = dayNumber(today);
  return since !== null && t !== null && t - since >= QUIET_DAYS;
}

function isValues(row, ctx) {
  const out = [isOpen(row) ? "open" : "closed"];
  if (dueBucket(row, ctx.today) === "overdue") out.push("overdue");
  if (isOpen(row)) {
    if (quietRow(row, ctx.today)) out.push("quiet");
    // A missing date counts only for an action or a decision (a risk or an issue often has none); a missing owner counts for every type.
    const needsDate = row.kind === "action" || row.kind === "decision";
    if (blank(row.owner) || (needsDate && dayNumber(dueField(row)) === null)) out.push("incomplete");
  }
  if (row.client_action) out.push("needed");
  if (row.archived) out.push("archived");
  return out;
}

export const LINE_FIELDS = {
  type: { name: "Type", state: "type", of: (r) => [r.kind] },
  status: { name: "Status", state: "status", of: (r) => [r.status || NONE] },
  owner: { name: "Owner", state: "owner", none: true, of: (r, c) => { const o = text(r.owner); return o ? [o, ...(c.me && low(o) === low(c.me) ? ["me"] : [])] : [NONE]; } },
  priority: { name: "Priority", state: "priority", none: true, of: (r) => [r.priority || NONE] },
  due: { name: "Due", state: "due", none: true, of: dueValues },
  workstream: { name: "Workstream", state: "workstream", none: true, of: (r) => [r.workstream || NONE] },
  usecase: { name: "Use case", state: "use_case", none: true, of: (r) => [r.uc || NONE] },
  milestone: { name: "Milestone", state: "milestone", none: true, of: (r) => [r.milestone || NONE] },
  client: { name: "Client", state: "client", of: (r) => [r.client ? "yes" : "no"] },
  is: { name: "Is", state: null, of: isValues },
};
export const NAMES = Object.keys(LINE_FIELDS);
export const NONE_OK = NAMES.filter((k) => LINE_FIELDS[k].none);
const ALIAS = { ws: "workstream", uc: "usecase", "use-case": "usecase", usecases: "usecase", ms: "milestone", prio: "priority", state: "status" };
// What a person types for a value that is stored in another word.
const TYPED = {
  due: { "next-7-days": "soon", "no-date": "none" },
  client: { shown: "yes", internal: "no" },
  owner: { none: NONE }, priority: { none: NONE }, workstream: { none: NONE }, usecase: { none: NONE }, milestone: { none: NONE },
};
const SHOWN = { due: { soon: "next-7-days" }, client: { yes: "shown", no: "internal" } };
const word = (field, v) => (v === NONE || (field === "due" && v === "none") ? "none" : (own(SHOWN, field) && own(SHOWN[field], v)) || v);
const stored = (field, w) => { const m = TYPED[field]; return m && Object.prototype.hasOwnProperty.call(m, low(w)) ? m[low(w)] : w; };

// The page may also pass the project's own lists in ctx: `workstreams` (names, in the project's order) and `milestones` (names, or
// {name, date}, which are put in date order). They come first; any other value the rows have follows.
const sortText = (a, b) => (a < b ? -1 : a > b ? 1 : 0);
function inOrder(first, extra) {
  const seen = new Set(), out = [];
  for (const v of [...first, ...extra.slice().sort(sortText)]) if (v && !seen.has(v)) { seen.add(v); out.push(v); }
  return out;
}
const projectWorkstreams = (ctx) => (Array.isArray(ctx.workstreams) ? ctx.workstreams.map(text).filter(Boolean) : []);
function projectMilestones(ctx) {
  if (!Array.isArray(ctx.milestones)) return [];
  const ms = ctx.milestones.map((m, i) => ({ name: text(m && typeof m === "object" ? m.name : m), at: m && typeof m === "object" ? dayNumber(m.date) : null, i })).filter((m) => m.name);
  return ms.sort((a, b) => (a.at === null) - (b.at === null) || (a.at === null ? 0 : a.at - b.at) || a.i - b.i).map((m) => m.name);
}
// Counts of the work done, for a test that the cost does not grow with the line (see ctx.work in parse).
const tick = (ctx, name) => { if (ctx && ctx.work && typeof ctx.work === "object") ctx.work[name] = (ctx.work[name] || 0) + 1; };

/** The values the line offers for a field, as [stored value, label]: the fixed ones, then those the rows have. */
export function offers(field, rows, ctx = {}) {
  tick(ctx, "offers");
  const dyn = (get) => [...new Set((rows || []).map(get).filter(Boolean))].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
  const noneRow = (get) => (rows || []).some((r) => !get(r));
  switch (field) {
    case "type": return KINDS.map(([v, l]) => [v, l]);
    case "status": {
      const all = [...STATUSES, ...((rows || []).some((r) => r.kind === "decision") ? DECISION_STATUSES : [])];    // every status the types in the project can have
      return [...all, ...dyn((r) => r.status).filter((s) => !all.includes(s))].map((s) => [s, s]);
    }
    case "priority": return [...PRIORITIES.map((p) => [p, p]), ...(noneRow((r) => r.priority) ? [[NONE, "No priority"]] : [])];
    case "due": return DUE_WORDS.map(([w, l]) => [stored("due", w), l]);
    case "client": return CLIENT_WORDS.map(([w, l]) => [stored("client", w), l]);
    case "is": return IS_WORDS.filter(([v]) => isOn(v, ctx, rows));
    case "owner": return [["me", ctx.me ? `Me (${ctx.me})` : "Me (set your name in Settings)"], ...dyn((r) => text(r.owner)).map((o) => [o, o]), ...(noneRow((r) => text(r.owner)) ? [[NONE, "No owner"]] : [])];
    case "workstream": return [...inOrder(projectWorkstreams(ctx), dyn((r) => r.workstream)).map((o) => [o, o]), ...(noneRow((r) => r.workstream) ? [[NONE, "No workstream"]] : [])];
    case "usecase": return [...dyn((r) => r.uc).map((o) => [o, o]), ...(noneRow((r) => r.uc) ? [[NONE, "No use case"]] : [])];
    case "milestone": return [...inOrder(projectMilestones(ctx), dyn((r) => r.milestone)).map((o) => [o, o]), ...(noneRow((r) => r.milestone) ? [[NONE, "No milestone"]] : [])];
    default: return [];
  }
}

const none = (field) => (field === "due" ? "none" : NONE);       // the stored word for "nothing there"
const labelOf = (field, v, rows, ctx, memo) => { const o = (memo ? memo.offers(field) : offers(field, rows, ctx)).find((x) => low(x[0]) === low(v)); return o ? o[1] : v; };

// What one read of a line works out once per field (the offers and the values the rows have), so a long line costs one pass over
// the rows per field, not one per word.
function memoOf(rows, ctx) {
  const offered = new Map(), known = new Map();
  return {
    offers(k) { if (!offered.has(k)) offered.set(k, offers(k, rows, ctx)); return offered.get(k); },
    known(k) {
      if (!known.has(k)) {
        tick(ctx, "known");
        const m = new Map();
        this.offers(k).forEach(([v]) => m.set(low(v), v));
        (rows || []).forEach((r) => LINE_FIELDS[k].of(r, ctx || {}).forEach((v) => m.has(low(v)) || m.set(low(v), v)));
        if (LINE_FIELDS[k].none) m.set(low(none(k)), none(k));
        known.set(k, m);
      }
      return known.get(k);
    },
  };
}

// ── Reading a line ───────────────────────────────────────────────────────────────────────────────────────────────────────

/** A line split into its words; a quoted stretch stays whole, and a quote can follow a colon or a comma: owner:"First Last". */
export function words(line) {
  const out = []; let cur = "", q = false;
  for (const ch of String(line == null ? "" : line)) {
    if (ch === '"') { q = !q; cur += ch; } else if (/\s/.test(ch) && !q) { if (cur) out.push(cur); cur = ""; } else cur += ch;
  }
  if (cur) out.push(cur);
  return out;
}
function splitValues(s) {
  const out = []; let cur = "", q = false;
  for (const ch of s) { if (ch === '"') q = !q; else if (ch === "," && !q) { out.push(cur); cur = ""; } else cur += ch; }
  out.push(cur);
  return out.map((v) => v.trim()).filter(Boolean);
}
const isFieldWord = (w) => /^-?[A-Za-z][\w-]*:/.test(w);
const fieldOf = (name) => { const k = low(name); return own(LINE_FIELDS, k) ? k : own(ALIAS, k) || null; };

function distance(a, b) {
  const m = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]);
  for (let j = 1; j <= b.length; j++) m[0][j] = j;
  for (let i = 1; i <= a.length; i++) for (let j = 1; j <= b.length; j++) m[i][j] = Math.min(m[i - 1][j] + 1, m[i][j - 1] + 1, m[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
  return m[a.length][b.length];
}
function nearest(name) {
  const n = low(name);
  const best = [...NAMES, ...Object.keys(ALIAS)].map((k) => [k, distance(n, k)]).sort((a, b) => a[1] - b[1])[0];
  return best && best[1] <= 2 ? fieldOf(best[0]) : (n.length >= 2 && NAMES.find((k) => k.startsWith(n))) || null;
}

/** The sentence for a value that is not one of the choices. */
export function badValue(field, bad, rows, ctx, memo) {
  const offer = (memo ? memo.offers(field) : offers(field, rows, ctx)).filter((o) => o[0] !== NONE).map((o) => word(field, o[0]));
  const name = LINE_FIELDS[field].name;
  const tail = offer.length > MAX_LIST ? `Try ${offer.slice(0, MAX_LIST).map(quote).join(", ")} and others. Type ${field}: to see them all.` : `Try ${list(offer.map(quote), "or")}.`;
  if (!offer.filter((o) => o !== "me").length) return `This project has no ${PLURAL[field] || `${name.toLowerCase()}s`} yet.`;
  const named = ["status", "owner", "priority", "workstream", "usecase", "milestone"].includes(field);
  if (named) return `No ${name.toLowerCase()} is called ${bad}. ${tail}`;
  return `“${bad}” is not a value for ${name}.${field === "due" && low(bad) === "soon" ? " Say next-7-days instead." : ""} ${tail}`;
}

// A use case is typed as the page names it ("Use case 1.1"), by its number alone (1.1), or by the group (1: Use case 1 and 1.1, 1.2...).
function useCases(typed, known) {
  const ref = low(text(typed)).replace(/^use\s*case\s*/, "");
  if (!ref) return [];
  const one = `use case ${ref}`, group = `${one}.`;
  return [...known.keys()].filter((key) => key === one || key.startsWith(group)).map((key) => known.get(key));
}

function readWord(w, rows, ctx, memo) {
  if (!isFieldWord(w)) return { word: w.replace(/"/g, "") };
  const not = w.startsWith("-"), body = not ? w.slice(1) : w, i = body.indexOf(":");
  const name = body.slice(0, i), rest = body.slice(i + 1);
  if (low(name) === "no") {
    const bare = rest.replace(/"/g, "");
    if (!bare) return { err: `Say which field: no:owner finds items with no owner. It works with ${list(NONE_OK)}.` };
    const k = fieldOf(bare);
    if (!k) return { err: `There is no “${bare}” field. no: works with ${list(NONE_OK)}.` };
    if (!LINE_FIELDS[k].none) return { err: `Every item has a ${LINE_FIELDS[k].name.toLowerCase()}, so no:${k} would find nothing. no: works with ${list(NONE_OK)}.` };
    return { chip: { field: k, values: [none(k)], not } };
  }
  const k = fieldOf(name);
  if (!k) {
    const n = nearest(name);
    return { err: `There is no “${name}” filter.${n ? ` Did you mean ${n}?` : ""} You can filter by ${list(NAMES.map((x) => `${x}:`))}, or type plain words to search titles.`, near: n };
  }
  const typed = splitValues(rest);
  if (!typed.length) {
    const first = (memo ? memo.offers(k) : offers(k, rows, ctx)).find((o) => o[0] !== NONE);
    return { err: `Say what ${LINE_FIELDS[k].name.toLowerCase()} to find, for example ${k}:${quote(first ? word(k, first[0]) : "value")}.`, field: k, partial: true };
  }
  const known = (memo || memoOf(rows, ctx)).known(k);
  if (k === "is") {
    const off = typed.find((t) => (low(t) === "quiet" || own(NOT_YET, low(t))) && !isOn(low(t), ctx, rows));
    if (off) return { err: `${low(off) === "quiet" ? QUIET_OFF : own(NOT_YET, low(off))} is not available on this page yet.`, field: k };
  }
  const values = [], bad = [], tokens = [];
  let byNumber = false;       // a use case typed by its number (1.1) or group (1) is written back as typed
  for (const t of typed) {
    const s = stored(k, t), hit = k === "due" && low(t) === "soon" ? undefined : known.get(low(s));     // "soon" is how it is stored; it is typed next-7-days
    const group = hit === undefined && k === "usecase" ? useCases(t, known) : [];
    if (group.length) { group.forEach((g) => values.includes(g) || values.push(g)); tokens.push(quote(t.replace(/"/g, ""))); byNumber = true; }
    else if (hit === undefined) bad.push(t);
    else { if (!values.includes(hit)) values.push(hit); tokens.push(quote(word(k, hit))); }
  }
  if (bad.length) return { err: badValue(k, bad[0], rows, ctx, memo || undefined), field: k };
  return { chip: byNumber ? { field: k, values, not, tokens } : { field: k, values, not } };
}

// Two chips on one field: negated ones join ("-status:Closed -status:Cancelled" leaves out both); a later one replaces an earlier
// one otherwise. `is:` chips are separate conditions that must all hold.
function merge(chips) {
  const out = [];
  for (const c of chips) {
    if (c.field === "is") { out.push({ ...c }); continue; }
    const at = out.findIndex((x) => x.field === c.field && x.not === c.not);
    if (at < 0) out.push({ ...c });
    else if (c.not) {
      const both = [...(out[at].tokens || []), ...(c.tokens || [])];
      out[at] = { ...out[at], values: [...new Set([...out[at].values, ...c.values])], ...(both.length ? { tokens: [...new Set(both)] } : {}) };
    }
    else out[at] = { ...c };
  }
  return out;
}

function dress(c, rows, ctx, memo) {
  const F = LINE_FIELDS[c.field], labels = c.values.map((v) => labelOf(c.field, v, rows, ctx, memo));
  const only = c.values.length === 1 && c.values[0] === none(c.field) && !!F.none;
  const textOf = (c.not ? "-" : "") + (only ? `no:${c.field}` : `${c.field}:${(c.tokens || c.values.map((v) => quote(word(c.field, v)))).join(",")}`);
  let say;
  if (only) say = c.not ? `${F.name} is set` : `No ${F.name.toLowerCase()}`;
  else if (c.field === "is") say = (c.not ? "Leaves out: " : "") + list(c.values.map((v) => own(GLOSS, v) || labelOf("is", v, rows, ctx, memo)), "or");
  else say = `${F.name} ${c.not ? "is not" : "is"} ${list(labels, "or")}`;
  return { ...c, name: F.name, labels, text: textOf, say, glosses: c.values.filter((v) => own(GLOSS, v)).map((v) => ({ value: v, gloss: GLOSS[v] })) };
}

/** A line, read. {chips, words, errors, notes}: chips are the conditions (each with its words and a plain sentence), words are
 *  the plain words that search titles, errors are the words that could not be used (never applied), notes are things worth saying
 *  beside a correct line (owner:me with no name set). */
export function parse(line, rows, ctx) {
  const c = ctx || {}, out = { chips: [], words: [], errors: [], notes: [] };
  const found = [], memo = memoOf(rows, c);     // ctx.work, when given, counts the offers and known-value maps built
  for (const w of words(line)) {
    const r = readWord(w, rows, c, memo);
    if (r.err) out.errors.push({ raw: w, msg: r.err, near: r.near || null, partial: !!r.partial });
    else if (r.chip) found.push(r.chip);
    else if (r.word) out.words.push(r.word);
  }
  out.chips = merge(found).map((x) => dress(x, rows, c, memo));
  if (!text(c.me) && out.chips.some((x) => x.field === "owner" && x.values.some((v) => low(v) === "me"))) out.notes.push(NO_ME);
  return out;
}

/** The text of a parsed line (or of chips and words): the line as it is written back, normalised. */
export function format(parts) {
  return [...parts.chips.map((c) => (c.text !== undefined ? c.text : dress(c, [], {}).text)), ...parts.words.map((w) => (/[\s"]/.test(w) || isFieldWord(w) ? `"${w.replace(/"/g, "")}"` : w))].join(" ");
}
export function normalise(line, rows, ctx) { return format(parse(line, rows, ctx)); }

/** The line with its last word dropped when it has no space after it yet: the part still being typed. */
export function settled(line) {
  const s = String(line == null ? "" : line);
  if (!s || /\s$/.test(s)) return s;
  const ws = words(s);
  return ws.length ? s.slice(0, s.length - ws[ws.length - 1].length) : s;
}

// ── Using a line ─────────────────────────────────────────────────────────────────────────────────────────────────────────

const hasValue = (have, want) => have.some((h) => want.some((w) => low(w) === low(h)));
export function matchRow(parsed, row, ctx) {
  for (const c of parsed.chips) if (hasValue(LINE_FIELDS[c.field].of(row, ctx), c.values) === c.not) return false;
  if (parsed.words.length) {
    const hay = low(`${row.title || ""} ${row.id || ""}`);
    if (!parsed.words.every((w) => hay.includes(low(w)))) return false;
  }
  return true;
}
/** The rows the line shows. A line with errors still applies what it understood: a word with an error is left out, never applied. */
export function apply(rows, line, ctx) {
  const c = ctx || {}, p = typeof line === "string" ? parse(line, rows, c) : line;
  return (rows || []).filter((r) => matchRow(p, r, c));
}

/** Clear all is offered when the line is not the line a page starts on. */
export function canClear(line, rows, ctx) { return normalise(line, rows, ctx) !== BASE; }

export function removeChip(line, index, rows, ctx) {
  const p = parse(line, rows, ctx);
  if (index < 0 || index >= p.chips.length) return format(p);
  return format({ chips: p.chips.filter((_, i) => i !== index), words: p.words });
}
/** Backspace in an empty box: the last chip goes. The line is unchanged when it has no chip. */
export function removeLast(line, rows, ctx) {
  const p = parse(line, rows, ctx);
  return p.chips.length ? removeChip(line, p.chips.length - 1, rows, ctx) : format(p);
}
/** Add a chip's text (or words) to a line: an earlier chip on the same field is replaced as the line reads it. */
export function addText(line, extra, rows, ctx) { return normalise(`${String(line || "").trim()} ${extra}`, rows, ctx); }

// ── Suggestions ──────────────────────────────────────────────────────────────────────────────────────────────────────────

/** What to offer for the word being typed: the fields first, then the field's values with how many of the rows have each.
 *  [{kind: "field" | "value", ins (the text to put in place of the word), label, note, n (values only)}]. */
export function suggest(wordTyped, rows, ctx) {
  const c = ctx || {}, w = wordTyped || "", not = w.startsWith("-"), body = not ? w.slice(1) : w;
  const count = (k, v) => (rows || []).filter((r) => hasValue(LINE_FIELDS[k].of(r, c), [v])).length;
  if (!body.includes(":")) {
    const n = low(body);
    if (w && !/^[a-z-]*$/i.test(w)) return [];
    const fs = NAMES.filter((k) => k.startsWith(n)).map((k) => ({ kind: "field", ins: `${not ? "-" : ""}${k}:`, label: `${not ? "-" : ""}${k}:`, note: not ? `${LINE_FIELDS[k].name} is not…` : LINE_FIELDS[k].name }));
    const nos = !not && n && "no:".startsWith(n) ? [{ kind: "field", ins: "no:", label: "no:", note: "Has no owner, date…" }] : [];
    return [...fs, ...nos];
  }
  const i = body.indexOf(":"), name = body.slice(0, i), rest = body.slice(i + 1);
  const lead = rest.lastIndexOf(",") + 1, done = rest.slice(0, lead), part = low(rest.slice(lead).replace(/"/g, ""));
  if (low(name) === "no") {
    return NONE_OK.filter((k) => k.startsWith(part)).map((k) => ({ kind: "value", ins: `${not ? "-" : ""}no:${k}`, label: k, note: `No ${LINE_FIELDS[k].name.toLowerCase()}`, n: count(k, none(k)) }));
  }
  const k = fieldOf(name);
  if (!k) return [];
  const chosen = splitValues(done).map(low);                   // a value already in the list is not offered again
  return offers(k, rows, c)
    .filter(([v]) => !chosen.includes(low(word(k, v))))
    .filter(([v, l]) => low(word(k, v)).includes(part) || low(l).includes(part))
    .map(([v, l]) => ({ kind: "value", ins: `${not ? "-" : ""}${k}:${done}${quote(word(k, v))}`, label: word(k, v), note: l !== word(k, v) ? l : "", n: count(k, v), gloss: k === "is" ? own(GLOSS, v) || "" : "" }));
}

/** The hint chips under the focused line: a few to start from, each with a plain meaning for its tooltip. */
export const HINTS = [
  { text: "status:", gloss: "Open, Pending, Delayed, Closed or Cancelled" },
  { text: "owner:me", gloss: "Your own items (needs your name in Settings)" },
  { text: "due:overdue", gloss: "Open items whose date has passed" },
  { text: "-status:Closed", gloss: "Leave closed items out" },
  { text: "no:owner", gloss: "Items with no owner" },
  { text: "is:incomplete", gloss: GLOSS.incomplete },
];
/** The hint chips to show: HINTS, with is:quiet added once the page turns the `is:` data on (ctx.isReady). */
export const hints = (ctx) => (ctx && (ctx.isReady || ctx.quietReady) ? [...HINTS.slice(0, 5), { text: "is:quiet", gloss: GLOSS.quiet }, ...HINTS.slice(5)] : HINTS.slice());

// ── The line and the older filter state ──────────────────────────────────────────────────────────────────────────────────

const IS_ALL = Object.fromEntries(IS_WORDS.map(([v]) => [v, true]));
const RAID_SET = RAID_KINDS.slice().sort().join(",");

// The older Freshness values (filters.js: stale, incomplete) and the two words the line keeps for them.
const FRESH_WORDS = { stale: "quiet", incomplete: "incomplete" };
const FRESH_BACK = { quiet: "stale", incomplete: "incomplete" };
const OLD_IS = { stale: "quiet", gap: "incomplete" };

/** The older state (filters.js) as a line, and what could not be carried over: {line, dropped}. Never throws: a field, value or
 *  word the line has no place for is left out and named in `dropped`, in plain words, so the page can say so. */
export function fromStateNote(state) {
  const dropped = [], t = [];
  const drop = (what) => { if (dropped.length < 20) dropped.push(what); };
  try {
    const s = state && typeof state === "object" ? state : initial();
    const f = s.filters && typeof s.filters === "object" && !Array.isArray(s.filters) ? s.filters : {};
    const nots = s.not && typeof s.not === "object" ? s.not : {};
    if (s.mode === "open") t.push("is:open"); else if (s.mode === "closed") t.push("is:closed");
    else if (s.mode !== "all" && s.mode !== undefined) drop(`the ${String(s.mode).slice(0, 40)} switch`);
    // `is` holds extra `is:` words, each its own condition: the Freshness tile is { mode: "open", is: ["quiet"] } (stale is read as quiet, gap as incomplete).
    for (const w of Array.isArray(s.is) ? s.is : []) { const v = own(OLD_IS, w) || w; if (typeof v === "string" && own(IS_ALL, v)) t.push(`is:${v}`); else drop(`the ${String(w).slice(0, 40)} filter`); }
    if (s.type === "action" || s.type === "decision") t.push(`type:${s.type}`);
    else if (s.type === "risk") t.push(`type:${RAID_KINDS.join(",")}`);
    else if (s.type !== "all" && s.type !== undefined) drop(`the ${String(s.type).slice(0, 40)} type`);
    for (const key of Object.keys(f)) if (!STATE_FIELDS.includes(key)) drop(`the ${key.slice(0, 40)} filter`);
    for (const k of STATE_FIELDS) {
      const raw = f[k];
      if (raw === undefined || (Array.isArray(raw) && !raw.length)) continue;
      if (!Array.isArray(raw)) { drop(`the ${k} filter`); continue; }
      const not = !!nots[k];
      if (k === "reviewed") {      // Freshness: the two plain values become the line's two words
        const vals = raw.filter((v) => typeof v === "string" && own(FRESH_WORDS, v));
        raw.forEach((v) => { if (!(typeof v === "string" && own(FRESH_WORDS, v))) drop(`the ${String(v).slice(0, 40)} Freshness value`); });
        if (vals.length) t.push(dress({ field: "is", values: [...new Set(vals.map((v) => FRESH_WORDS[v]))], not }, [], {}).text);
        continue;
      }
      const vals = raw.filter((v) => typeof v === "string" && v);
      if (vals.length !== raw.length) drop(`a value in the ${k} filter`);
      if (vals.length) t.push(dress({ field: k === "use_case" ? "usecase" : k, values: vals, not }, [], {}).text);
    }
  } catch (e) {
    return { line: BASE, dropped: ["a filter this page could not read"] };
  }
  return { line: t.join(" "), dropped };
}
/** The older state (filters.js) as a line. Every filter in it is in the line; see fromStateNote for what is left out. */
export function fromState(state) { return fromStateNote(state).line; }

/** A line as the older state, as far as the older state can say it: {state, exact, rest}. `rest` lists the chips and words the
 *  older state cannot hold (a search word, `today`, `is:quiet`, a second `is:`), and `exact` is true when there are none. */
export function toState(line, rows, ctx) {
  const p = parse(line, rows, ctx), st = initial(), rest = [];
  st.mode = "all";
  for (const c of p.chips) {
    if (c.field === "is" && !c.not && c.values.length === 1 && (c.values[0] === "open" || c.values[0] === "closed") && st.mode === "all") { st.mode = c.values[0]; continue; }
    if (c.field === "type" && !c.not && st.type === "all") {
      const v = c.values.slice().sort().join(",");
      if (c.values.length === 1 && (c.values[0] === "action" || c.values[0] === "decision")) { st.type = c.values[0]; continue; }
      if (v === RAID_SET) { st.type = "risk"; continue; }
    }
    if (c.field === "is" && !st.filters.reviewed && c.values.length && c.values.every((v) => own(FRESH_BACK, v))) {      // Freshness
      st.filters.reviewed = [...new Set(c.values.map((v) => FRESH_BACK[v]))];
      if (c.not) st.not.reviewed = true;
      continue;
    }
    const sf = LINE_FIELDS[c.field].state;
    if (sf && sf !== "type" && !st.filters[sf] && !(c.field === "due" && c.values.includes("today"))) {
      st.filters[sf] = c.values.slice();
      if (c.not) st.not[sf] = true;
      continue;
    }
    rest.push(c.text);
  }
  for (const w of p.words) rest.push(w);
  return { state: st, exact: rest.length === 0, rest };
}

// ── Saved views, per project ─────────────────────────────────────────────────────────────────────────────────────────────
// A view is {id, name, line, archived?}. Nothing is ever deleted: a view is archived (hidden from the tabs) and can be restored.

export const DEFAULT_VIEWS = [
  { id: "open", name: "Open items", line: "is:open" },
  { id: "overdue", name: "Overdue", line: "is:open due:overdue" },
  { id: "client", name: "Waiting on the client", line: "is:open is:needed" },
  { id: "mine", name: "My actions", line: "is:open type:action owner:me" },
];
export const MAX_VIEWS = 20;
export const MAX_NAME = 40;

export const visibleViews = (views) => (views || []).filter((v) => !v.archived);
export const archivedViews = (views) => (views || []).filter((v) => v.archived);
export const findView = (views, id) => (views || []).find((v) => v.id === id) || null;

/** True when the line is not the saved line (the dot on the tab). Compared as the line reads, so spacing and order of words do not count. */
export function differs(view, line, rows, ctx) {
  if (!view) return false;
  const a = parse(view.line, rows, ctx), b = parse(line, rows, ctx);
  const key = (p) => [...p.chips.map((c) => `${c.not ? "-" : ""}${c.field}:${c.values.map(low).sort().join(",")}`), ...p.words.map((w) => `"${low(w)}`)].sort().join(" ");
  return key(a) !== key(b);
}

const cleanName = (n) => text(n).replace(/\s+/g, " ");
function nameProblem(views, name, exceptId) {
  const n = cleanName(name);
  if (!n) return "Give the view a name.";
  if (n.length > MAX_NAME) return `Keep the name to ${MAX_NAME} characters or fewer.`;
  if ((views || []).some((v) => !v.archived && v.id !== exceptId && low(v.name) === low(n))) return `A view called ${n} already exists. Choose another name.`;
  return "";
}
const nextId = (views) => { let n = (views || []).length + 1; const ids = new Set((views || []).map((v) => v.id)); while (ids.has(`v${n}`)) n++; return `v${n}`; };

/** Save the line as a new view. {ok, views, id} or {ok: false, message}; the list given is never changed. */
export function addView(views, name, line) {
  const vs = views || [], bad = nameProblem(vs, name, null);
  if (bad) return { ok: false, message: bad };
  if (visibleViews(vs).length >= MAX_VIEWS) return { ok: false, message: `You can keep ${MAX_VIEWS} saved views. Archive one to make room.` };
  const id = nextId(vs);
  return { ok: true, id, views: [...vs, { id, name: cleanName(name), line: String(line || "") }] };
}
/** Save the current line over a view (Save). */
export function saveView(views, id, line) {
  if (!findView(views, id)) return { ok: false, message: "That view is not there any more." };
  return { ok: true, views: views.map((v) => (v.id === id ? { ...v, line: String(line || "") } : v)) };
}
export function renameView(views, id, name) {
  if (!findView(views, id)) return { ok: false, message: "That view is not there any more." };
  const bad = nameProblem(views, name, id);
  return bad ? { ok: false, message: bad } : { ok: true, views: views.map((v) => (v.id === id ? { ...v, name: cleanName(name) } : v)) };
}
/** Take a view off the tabs. It is kept (archived), and restoreView brings it back. */
export function archiveView(views, id) {
  if (!findView(views, id)) return { ok: false, message: "That view is not there any more." };
  return { ok: true, views: views.map((v) => (v.id === id ? { ...v, archived: true } : v)) };
}
export function restoreView(views, id) {
  const v = findView(views, id);
  if (!v) return { ok: false, message: "That view is not there any more." };
  const bad = nameProblem(views, v.name, id);
  return bad ? { ok: false, message: bad } : { ok: true, views: views.map((x) => (x.id === id ? { ...x, archived: false } : x)) };
}
/** How many rows a view shows, for its tab. */
export const viewCount = (view, rows, ctx) => apply(rows, view.line, ctx).length;

// ── Remembering ──────────────────────────────────────────────────────────────────────────────────────────────────────────
// Storage is passed in (the session's for the line, the browser's own for the views), so a browser that refuses it still works: every
// read and write is guarded and a failed read gives the start.

export const LINE_KEY = "clark.fline";
export const VIEWS_KEY = "clark.fviews";

function readAll(storage, key) {
  try {
    const v = JSON.parse(storage.getItem(key) || "{}");
    return v && typeof v === "object" && !Array.isArray(v) ? v : {};
  } catch (e) { return {}; }
}
function writeAll(storage, key, all) { try { storage.setItem(key, JSON.stringify(all)); return true; } catch (e) { return false; } }

/** The line kept for a project in this session, or the start line. */
export function lineGet(storage, project) {
  if (!storage) return BASE;
  const v = readAll(storage, LINE_KEY)[project];
  return typeof v === "string" && v.length <= 600 ? v : BASE;
}
export function linePut(storage, project, line) {
  if (!storage) return false;
  const all = readAll(storage, LINE_KEY);
  all[project] = String(line == null ? "" : line).slice(0, 600);
  return writeAll(storage, LINE_KEY, all);
}
const sane = (v) => v && typeof v.id === "string" && typeof v.name === "string" && typeof v.line === "string";
/** A project's saved views: its own, or the ones every project starts with. */
export function viewsGet(storage, project) {
  const mine = storage ? readAll(storage, VIEWS_KEY)[project] : null;
  return Array.isArray(mine) && mine.every(sane) ? mine : DEFAULT_VIEWS.map((v) => ({ ...v }));
}
export function viewsPut(storage, project, views) {
  if (!storage) return false;
  const all = readAll(storage, VIEWS_KEY);
  all[project] = views;
  return writeAll(storage, VIEWS_KEY, all);
}
