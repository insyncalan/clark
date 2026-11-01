// and no clock: today is always passed in. The behaviour follows the prototype (views.js: FIELDS, dueBucket, workList,
// filterPop, syncBars), rewritten here. Where this differs from the prototype, the comment says so.
//
// A state is plain data (so it can be encoded, compared and kept):
//   { mode: "open" | "closed" | "all",           the Open / Closed / All switch
//     type: "all" | "action" | "risk" | "decision",   the type switch (Risks and issues holds risks, issues, assumptions, dependencies)
//     filters: { workstream: [..], status: [..], due: [..], owner: [..], priority: [..], use_case: [..], milestone: [..], client: [..], reviewed: [..] },
//     not: { owner: true, .. } }                 a field set to "is not" instead of "is any of"
// Each filter is a set of chosen values (a list with no repeats). Every function returns a new state; none changes its input.
import { dayNumber, dueField, isOpen, plural } from "./workItems.js";

export const FIELDS = ["workstream", "status", "due", "owner", "priority", "use_case", "milestone", "client", "reviewed"];
export const NAMES = { workstream: "Workstream", status: "Status", due: "Due", owner: "Owner", priority: "Priority", use_case: "Use case", milestone: "Milestone", client: "Client", reviewed: "Freshness" };
export const MODES = [["open", "Open"], ["closed", "Closed"], ["all", "All"]];
export const TYPES = [["all", "All"], ["action", "Actions"], ["risk", "Risks and issues"], ["decision", "Decisions"]];
const RISKS_AND_ISSUES = ["risk", "issue", "assumption", "dependency"];
export const NONE = "(none)";
const NO_WORDS = { workstream: "No workstream", status: "No status", owner: "No owner", priority: "No priority", use_case: "No use case", milestone: "No milestone" };
// The prototype's four Due buckets, its words and its order. "This week" and "Next 7 days" are one bucket here: Due in 7 days.
export const DUE = [["overdue", "Overdue"], ["soon", "Due in 7 days"], ["none", "No date"], ["later", "Later"]];
const PRIORITIES = ["Urgent", "High", "Medium", "Low"];
const CLIENT = [["yes", "Shown to the client"], ["no", "Internal only"]];

// #119 (pure part): "Not reviewed in N days". The page has no history yet, so the rule reads dates an item carries when the data
// has them: `not_reviewed` (true or false, worked out on the server by freshness.py) wins; else `last_reviewed`, else `raised`
// (YYYY-MM-DD only: workItems.js dayNumber reads no week date, compact form or time part, as freshness.py DAY). Trap: `raised` is
// read here as a row's own first-seen date; if work-item rows ever get a typed `raised`, rename this key (for example first_seen).
// With none of these nothing is flagged. Plain calendar days, the same rule as src/clark/freshness.py: more than N
// days (exactly N is not yet), open items only.
export const REVIEW_DAYS = 14;
export const staleWords = (days = REVIEW_DAYS) => "Not reviewed in " + plural(days, "day");       // the filter's value and the peek's chip say it the same way
const REVIEWED = [["stale", staleWords()], ["incomplete", "No owner or no date"]];
export function notReviewed(row, today, days = REVIEW_DAYS) {
  if (!isOpen(row)) return false;
  if (typeof row.not_reviewed === "boolean") return row.not_reviewed;
  const since = dayNumber(row.last_reviewed || row.raised), t = dayNumber(today);
  return since !== null && t !== null && t - since > days;
}

// #159: an open item with no owner (blank or TBC) is "incomplete" in the Freshness filter, and so is an open action or decision with no
// date (a risk, issue, assumption or dependency often has none, so a missing date counts only for actions and decisions). A row can be both incomplete and
// not reviewed, so Freshness holds a list of values per row (freshnessValues) and every other filter keeps one.
export function hasGap(row) {
  if (!isOpen(row)) return false;
  const owner = String(row.owner == null ? "" : row.owner).trim().toUpperCase();
  const needsDate = row.kind === "action" || row.kind === "decision";
  return owner === "" || owner === "TBC" || (needsDate && !dueField(row));
}
export function freshnessValues(row, today) {
  const out = [];
  if (notReviewed(row, today)) out.push("stale");
  if (hasGap(row)) out.push("incomplete");
  return out;
}
const memberOf = (row, field, v, today) => (field === "reviewed" ? freshnessValues(row, today).includes(v) : valueOf(row, field, today) === v);

// The filters the bar offers. Freshness is left out until some row carries a date it can use (raised, last_reviewed or
// not_reviewed), so nobody can pick a filter that can never match. A Freshness filter already on (from an address) stays listed.
export function hasReviewDates(rows) {
  return (rows || []).some((r) => r && (typeof r.not_reviewed === "boolean" || r.last_reviewed || r.raised));
}
// The published file (#69): everything on its page is already the client's, so it has no Client filter and no Freshness filter (the
// seven the client gets: Workstream, Status, Due, Owner, Priority, Use case, Milestone), and a finished item dated in the past is
// "Earlier" (a finished item is never overdue). The page switches this on once, when it opens a published file; the editor never
// does. It is the only module-level state here.
let published = false;
export function setPublished(on) { published = !!on; }
export function fieldList() { return published ? FIELDS.filter((f) => f !== "client" && f !== "reviewed") : FIELDS; }
export function dueBuckets() { return published ? [...DUE, ["past", "Earlier"]] : DUE; }

export function offeredFields(rows, state) {
  if (published) return fieldList();
  const keep = hasReviewDates(rows) || (state && isActive(state, "reviewed"));
  return FIELDS.filter((f) => f !== "reviewed" || keep);
}

export function initial() { return { mode: "open", type: "all", filters: {}, not: {} }; }
// Clear all: the editor goes back to the start. A published file keeps the type and Open / Closed / All the client chose and clears
// the filters only (its search words are the page's own and are cleared there).
export function clearAll(state) {
  if (!published || !state) return initial();
  const s = copy(state);
  s.filters = {}; s.not = {};
  return s;
}

// Due, in the prototype's buckets: before today is Overdue, today to 7 days on is Due in 7 days, later is Later, no (real) date is
// No date. One difference: a closed row with a date is in none of them, so Overdue never lists work that is done (the prototype's did).
export function dueBucket(row, today) {
  const a = dayNumber(dueField(row)), t = dayNumber(today);
  if (a === null || t === null) return "none";
  if (!isOpen(row)) return published ? (a < t ? "past" : "later") : "";
  return a < t ? "overdue" : a - t <= 7 ? "soon" : "later";
}

export function valueOf(row, field, today) {
  switch (field) {
    case "workstream": return row.workstream || NONE;
    case "status": return row.status || NONE;
    case "due": return dueBucket(row, today);
    case "owner": return (row.owner && String(row.owner).trim()) || NONE;
    case "priority": return row.priority || NONE;
    case "use_case": return row.uc || NONE;
    case "milestone": return row.milestone || NONE;
    case "client": return row.client ? "yes" : "no";
    case "reviewed": return notReviewed(row, today) ? "stale" : "";
    default: return "";
  }
}

export function labelOf(field, value) {
  if (value === NONE) return NO_WORDS[field] || NONE;
  if (field === "due") return (dueBuckets().find((d) => d[0] === value) || [0, value])[1];
  if (field === "reviewed") return (REVIEWED.find((d) => d[0] === value) || [0, value])[1];
  if (field === "client") return (CLIENT.find((d) => d[0] === value) || [0, value])[1];
  return value;
}

export function inType(row, type) {
  if (type === "all") return true;
  return type === "risk" ? RISKS_AND_ISSUES.includes(row.kind) : row.kind === type;
}

function inFilters(row, state, today, skip) {
  for (const f of fieldList()) {
    if (f === skip) continue;
    const chosen = state.filters[f];
    if (!chosen || !chosen.length) continue;
    const hit = f === "reviewed" ? chosen.some((v) => memberOf(row, f, v, today)) : chosen.includes(valueOf(row, f, today));
    if (hit === !!state.not[f]) return false;
  }
  return true;
}

const inMode = (row, mode) => mode === "all" || (mode === "open" ? isOpen(row) : !isOpen(row));

export function applyFilters(rows, state, today) {
  return rows.filter((r) => inType(r, state.type) && inMode(r, state.mode) && inFilters(r, state, today));
}

// The counts on the Open / Closed / All switch. They are worked out with the type and every other filter applied but not the mode,
// so the count of the mode that is on is always the number of rows in the list. (The prototype counted the whole project and
// ignored the filters, which left the switch saying 17 above a list of 3.)
export function counts(rows, state, today) {
  const c = { open: 0, closed: 0, all: 0 };
  for (const r of rows) {
    if (!inType(r, state.type) || !inFilters(r, state, today)) continue;
    c.all++;
    c[isOpen(r) ? "open" : "closed"]++;
  }
  return c;
}

// The count on the type switch: the same way, with the mode and the filters applied but not the type.
export function typeCounts(rows, state, today) {
  const c = {};
  for (const [t] of TYPES) c[t] = 0;
  for (const r of rows) {
    if (!inMode(r, state.mode) || !inFilters(r, state, today)) continue;
    for (const [t] of TYPES) if (inType(r, t)) c[t]++;
  }
  return c;
}

const byText = (a, b) => (a < b ? -1 : a > b ? 1 : 0);

// The choices in one filter's box, each with how many rows it would give: counted among the rows the switches show, with the
// other filters ignored (as the prototype did; it ignored the type too, which gave counts the list could not match). Values the
// user has chosen are always listed, even when no row has them now, so they can be un-ticked.
export function options(rows, field, state, today) {
  const st = state || initial();
  const scope = state ? rows.filter((r) => inType(r, st.type) && inMode(r, st.mode)) : rows;
  const tally = new Map();
  const count = (v) => scope.reduce((n, r) => n + (memberOf(r, field, v, today) ? 1 : 0), 0);
  let values;
  if (field === "due") values = dueBuckets().map((d) => d[0]);
  else if (field === "client") values = CLIENT.map((d) => d[0]);
  else if (field === "reviewed") values = REVIEWED.map((d) => d[0]);
  else {
    const seen = [...new Set(rows.map((r) => valueOf(r, field, today)))].filter((v) => v !== NONE);
    if (field === "priority") { for (const p of PRIORITIES) if (!seen.includes(p)) seen.push(p); }
    seen.sort(field === "priority" ? (a, b) => (PRIORITIES.indexOf(a) + 1 || 99) - (PRIORITIES.indexOf(b) + 1 || 99) || byText(a, b) : byText);
    values = seen;
    if (field !== "status" && rows.some((r) => valueOf(r, field, today) === NONE)) values.push(NONE);
  }
  for (const v of st.filters[field] || []) if (!values.includes(v)) values.push(v);
  for (const v of values) tally.set(v, count(v));
  return values.map((v) => ({ value: v, label: labelOf(field, v), count: tally.get(v), chosen: (st.filters[field] || []).includes(v) }));
}

export function isActive(state, field) { return !!(state.filters[field] && state.filters[field].length); }

export function activeFields(state) { return fieldList().filter((f) => isActive(state, f)); }

// What shows beside the count: one chip for each active filter, "Due: Overdue", "Owner is not: Sam Rivers, Priya Nair".
export function chips(state) {
  return activeFields(state).map((f) => {
    const values = state.filters[f].map((v) => ({ value: v, label: labelOf(f, v) }));
    return { field: f, name: NAMES[f], not: !!state.not[f], values, text: `${NAMES[f]}${state.not[f] ? " is not" : ""}: ${values.map((v) => v.label).join(", ")}` };
  });
}

// Clear all is offered when anything differs from the start: a filter, a type, or Closed / All.
export function canClear(state) { return activeFields(state).length > 0 || (!published && (state.type !== "all" || state.mode !== "open")); }

// The words beside the chips: "17 open items", "1 closed item", "3 items".
export function countText(n, mode) {
  const what = mode === "open" ? "open " : mode === "closed" ? "closed " : "";
  return plural(n, `${what}item`);
}

// ---- changing a state: each returns a new one ----
const copy = (s) => ({ mode: s.mode, type: s.type, filters: { ...s.filters }, not: { ...s.not } });

export function setMode(state, mode) { const s = copy(state); if (MODES.some((m) => m[0] === mode)) s.mode = mode; return s; }
export function setType(state, type) { const s = copy(state); if (TYPES.some((t) => t[0] === type)) s.type = type; return s; }

export function setFilter(state, field, values, not) {
  if (!fieldList().includes(field)) return state;
  const s = copy(state), list = [...new Set(values)];
  if (list.length) { s.filters[field] = list; if (not) s.not[field] = true; else delete s.not[field]; }
  else { delete s.filters[field]; delete s.not[field]; }
  return s;
}

export function toggleValue(state, field, value) {
  const now = state.filters[field] || [];
  return setFilter(state, field, now.includes(value) ? now.filter((v) => v !== value) : [...now, value], !!state.not[field]);
}

export function setNot(state, field, not) { return setFilter(state, field, state.filters[field] || [], not); }
export function removeFilter(state, field) { return setFilter(state, field, [], false); }

// ---- the address ----
// The text kept in the router's `f` key (router.js, #63): "#work&p=TUL&f=mode:closed;type:action;not:owner;owner:Sam%20Rivers,Priya%20Nair".
// The router never reads `f`: this file encodes and decodes it. The start state is "" (no `f`). Items are joined by ";", a key and its
// values by ":", values by ",". Each value goes through encodeURIComponent, so a value never holds a raw "," ";" ":" "=" "&" "#" or "%",
// and the text uses only characters the router carries as they stand (letters, digits and - . _ ~ ! ' ( ) * ; : ,). A filter change
// REPLACES the address (stores/report.js), never adds a step.
// The router trusts `f` only up to 600 characters. MAX_F is that number. The page checks fits() before it keeps a change and, if the
// change would not fit, refuses it with a plain line (nothing changes). encode() cuts anyway (the last values first) so it never gives
// a text the router would drop, whatever it is handed.
export const MAX_F = 600;

// A value as it goes in the text, or "" when it can't be written: one with a control character (the router drops such an `f`), or an
// unpaired surrogate (encodeURIComponent throws on it).
function esc(v) {
  const s = String(v);
  if (!s || /[\u0000-\u001f\u007f-\u009f]/.test(s)) return "";
  try { return encodeURIComponent(s); } catch (e) { return ""; }
}

function items(state) {
  const out = [];                                      // [text, number of values it holds] in the order they are written
  if (state.mode !== "open") out.push(`mode:${state.mode}`);
  if (state.type !== "all") out.push(`type:${state.type}`);
  const nots = activeFields(state).filter((f) => state.not[f]);
  if (nots.length) out.push(`not:${nots.join(",")}`);
  for (const f of activeFields(state)) {
    const vals = state.filters[f].map(esc).filter(Boolean);
    if (vals.length) out.push(`${f}:${vals.join(",")}`);
  }
  return out;
}

const whole = (state) => items(state).join(";");

/** The state as text for `f`, "" for the start state. Pure and total. At most MAX_F characters (values at the end are cut first). */
export function encode(state) {
  const s = state && typeof state === "object" && state.filters && state.not ? state : initial();
  let text = whole(s);
  if (text.length <= MAX_F) return text;
  let cut = copy(s);
  for (let guard = 0; text.length > MAX_F && guard < 10000; guard++) {
    const f = [...fieldList()].reverse().find((x) => isActive(cut, x));
    if (!f) return "";                                  // only mode, type and "not" are left and they still do not fit: nothing fits
    cut = setFilter(cut, f, cut.filters[f].slice(0, -1), !!cut.not[f]);
    text = whole(cut);
  }
  return text.length <= MAX_F ? text : "";
}

/** True when the whole state fits in the address, with nothing cut and nothing left out. */
export function fits(state) {
  const s = state && typeof state === "object" && state.filters && state.not ? state : initial();
  const every = activeFields(s).every((f) => s.filters[f].every((v) => esc(v)));
  return every && whole(s).length <= MAX_F;
}

/** The state from that text. Total: any text at all (garbage, a non-string, half a percent-escape) gives a state and never throws;
 *  what it does not understand is ignored, so an old or hand-made address never breaks the page. It reads only this text, so it
 *  can never change the page or the project. */
export function decode(text) {
  const s = initial();
  if (typeof text !== "string" || !text) return s;
  const part = new Map();                              // not an object: a key like "__proto__" is only a key
  for (const p of text.slice(0, 4 * MAX_F).split(";")) {
    const i = p.indexOf(":");
    if (i > 0 && !part.has(p.slice(0, i))) part.set(p.slice(0, i), p.slice(i + 1));
  }
  const safe = (v) => { try { return decodeURIComponent(v); } catch (e) { return ""; } };
  const mode = part.get("mode"), type = part.get("type");
  if (MODES.some((m) => m[0] === mode)) s.mode = mode;
  if (TYPES.some((t) => t[0] === type)) s.type = type;
  const nots = (part.get("not") || "").split(",");
  for (const f of fieldList()) {
    if (!part.has(f)) continue;
    const vals = part.get(f).split(",").map(safe).filter((v) => v !== "" && !/[\u0000-\u001f\u007f-\u009f]/.test(v));
    if (vals.length) { s.filters[f] = [...new Set(vals)]; if (nots.includes(f)) s.not[f] = true; }
  }
  return s;
}

// ---- the Add button (#64a): the words follow the type switch ----
// On Work items: Add item (All; a menu of every type), Add action, Add risk or issue (a menu of two), Add decision.
const KIND_ADD = { action: "Add action", risk: "Add risk", issue: "Add issue", decision: "Add decision" };
export function addPlan(type) {
  if (type === "action") return { word: "Add action", kind: "action", menu: null };
  if (type === "decision") return { word: "Add decision", kind: "decision", menu: null };
  const menu = (kinds) => kinds.map((k) => ({ kind: k, word: KIND_ADD[k] }));
  if (type === "risk") return { word: "Add risk or issue", kind: null, menu: menu(["risk", "issue"]) };
  return { word: "Add item", kind: null, menu: menu(["action", "risk", "issue", "decision"]) };
}
