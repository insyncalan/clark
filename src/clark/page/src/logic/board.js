// The Work items board's rules, as plain functions with no DOM and no clock (#68; spec docs/handoff/design-68-81-board.md).
// Group by -> columns (and optional swimlanes), the card, and `moveFor`: what a move of a card to a column (and lane) asks
// the server for, or why it can't be done. The page's drop indicator, its Move to... menu and its drop all use moveFor, so
// they cannot disagree. A refusal is made here, in plain words, before anything reaches the server; the server still checks
// everything again (src/clark/changes.py). The remembered state is at the foot. There is no op here that takes an item away.
import { KIND_WORDS, dayNumber, dueCell, dueField, isOpen, ownerOf, pillOf, rowsOf } from "../workItems.js";

// Where on the page the change was made: the step's place. The store, changes.PLACES and the schema's CHECK know "board"
// since #126 (the tests follow changes.PLACES by themselves).
export const PLACE = "board";

export const NONE = "__none";           // the key of every "missing value" column and lane
export const GROUPS = [
  { id: "workstream", label: "Workstream" }, { id: "status", label: "Status" }, { id: "due", label: "Due" },
  { id: "owner", label: "Owner" }, { id: "priority", label: "Priority" }, { id: "milestone", label: "Milestone" },
  { id: "type", label: "Type" }, { id: "nothing", label: "Nothing" },
];
export const LANE_GROUPS = ["workstream", "type"];
const GROUP_IDS = GROUPS.map((g) => g.id);
const MISSING = { workstream: "No workstream", owner: "No owner", priority: "Not rated", milestone: "No milestone", due: "No date" };
const STATUSES = { action: ["Open", "Delayed", "Closed", "Cancelled"], decision: ["Pending", "Made", "Withdrawn"] };
const STATUS_ORDER = ["Open", "Delayed", "Pending", "Closed", "Made", "Cancelled", "Withdrawn"];
const STATUS_TONE = { Open: "blue", Pending: "blue", Delayed: "amber", Made: "green" };
const PRIORITIES = ["Urgent", "High", "Medium", "Low"];
const PRIORITY_TONE = { Urgent: "red", High: "amber", Medium: "blue", Low: "green" };
const DUE = [["overdue", "Overdue", "red"], ["this_week", "This week", "amber"], ["next_week", "Next week", "blue"], ["later", "Later", "green"], [NONE, "No date", "grey"]];
const DUE_LABEL = { this_week: "This week", next_week: "Next week", later: "Later" };
const TYPES = [["actions", "Actions"], ["raid", "Risks and issues"], ["decisions", "Decisions"]];
const A = { action: "An action", risk: "A risk", issue: "An issue", assumption: "An assumption", dependency: "A dependency", decision: "A decision" };

export const WORDS = {
  decided: "A decision that is made or withdrawn can't be moved. Record a new decision that replaces it.",
  withdrawn: "A decision that has been withdrawn can't be moved. It can go back to Pending, or record a new decision.",
  withdrawnDue: "A decision that has been withdrawn has no due date, so it has nothing to move.",
  strangePriority: "That priority isn't one a card can be given.",
  decidedDue: "A decision that has been made has no due date, so it has nothing to move.",
  madeStays: "A decision that has been made can't go back to Pending. Record a new decision that replaces it.",   // as changes.MADE_STAYS
  noWorkstream: "A decision isn't part of a workstream.",
  noMilestone: "A decision isn't tied to a milestone.",
  noPriority: "A decision has no priority.",
  riskPriority: "A risk or issue's priority comes from its impact and likelihood. Change those in its details.",
  overdue: "Overdue is worked out from the due date. Drop the card on This week, Next week or Later and choose a date.",
  notRated: "An action can't be moved to Not rated. Choose Urgent, High, Medium or Low.",
  pastDate: "Pick today or a later date.",
  notADate: "That isn't a date. Pick a day from the calendar.",
  strangeWorkstream: "That workstream isn't available.",
  strangeMilestone: "That milestone isn't in this project.",
  sameField: "Swimlanes and columns can't use the same grouping. Choose a different swimlane.",
};

const kindOf = (row) => (row.kind === "decision" ? "decision" : row.kind === "action" ? "action" : "raid");
const decided = (row) => row.kind === "decision" && row.status !== "Pending";
const withdrawn = (row) => row.kind === "decision" && row.status === "Withdrawn";
const none = (v) => v == null || v === "";
const isNoOwner = (v) => none(v) || String(v).trim().toUpperCase() === "TBC";
const list = (xs) => (xs.length < 2 ? xs.join("") : `${xs.slice(0, -1).join(", ")} or ${xs[xs.length - 1]}`);

export function groupLabel(id) { return (GROUPS.find((g) => g.id === id) || {}).label || ""; }
export function statusesOf(row) { return row.kind === "decision" ? STATUSES.decision : row.kind === "action" ? STATUSES.action : ["Open", "Closed", "Cancelled"]; }

// ── Rows ──────────────────────────────────────────────────────────────────────

// workItems.rowsOf, plus what a move needs and rowsOf drops: the table and the milestone's id (rowsOf keeps only its name).
export function rowsFor(data) {
  const ids = {};
  for (const [t, key] of [["actions", "action"], ["raid", "raid"], ["decisions", "decision"]]) for (const r of data[t] || []) ids[r.id] = { table: t, milestone_id: r.milestone || null };
  return rowsOf(data).map((r) => ({ ...r, table: ids[r.id].table, milestone_id: r.kind === "decision" ? null : ids[r.id].milestone_id }));
}

// What the grouping needs besides the rows: the project, today, the signed-in person, the active workstreams and the milestones.
export function ctxFor(data, { project, today, me = "", kinds = null } = {}) {
  return {
    project, today, me, kinds,
    workstreams: (data.workstreams || []).filter((w) => w.status === "Active" || w.active === 1).map((w) => w.name),
    milestones: (data.milestones || []).slice().sort((a, b) => String(a.baseline_date || "").localeCompare(String(b.baseline_date || "")) || (a.id < b.id ? -1 : 1))
      .map((m) => ({ id: m.id, name: m.name })),
  };
}

// ── Days ──────────────────────────────────────────────────────────────────────

const isoOf = (n) => new Date(n * 86400000).toISOString().slice(0, 10);
const weekdayOf = (n) => ((new Date(n * 86400000).getUTCDay() + 6) % 7) + 1;      // Monday 1 to Sunday 7
const sundayOf = (n) => n + (7 - weekdayOf(n));                                    // the week ends on Sunday

function bucketOf(a, t) {
  if (a < t) return "overdue";
  const end = sundayOf(t);
  return a <= end ? "this_week" : a <= end + 7 ? "next_week" : "later";
}
function dueKey(row, today) {
  const iso = dueField(row), a = dayNumber(iso), t = dayNumber(today);
  if (a === null || t === null || decided(row)) return NONE;
  return bucketOf(a, t);
}

// ── Which column holds a card ────────────────────────────────────────────────

export function cellOf(group, row, ctx) {
  switch (group) {
    case "workstream": return none(row.workstream) ? NONE : row.workstream;
    case "status": return row.status;
    case "due": return dueKey(row, ctx.today);
    case "owner": return isNoOwner(row.owner) ? NONE : String(row.owner).trim();
    case "priority": return row.kind === "decision" || none(row.priority) ? NONE : row.priority;
    case "milestone": return row.milestone_id || NONE;
    case "type": return row.table;
    default: return "all";
  }
}

// The columns (or lanes) of a grouping, in order, each {key, label, tone, extra}. Every value gets one so no card can vanish;
// the missing-value column ("Not rated", "No owner", ...) is last. `nodrop` marks one a card can never be dropped on.
export function columnsFor(group, rows, ctx) {
  const base = baseColumns(group, rows, ctx);
  if (group === "nothing" || group === "owner" || group === "type") return base;
  // The safety net: a card whose value has no column (a milestone left out of the list, an old status or priority) gets one of
  // its own, which nothing can be dropped on, so no card ever disappears. It sits before the missing-value column.
  const have = new Set(base.map((c) => c.key)), odd = [];
  for (const r of rows) {
    const k = cellOf(group, r, ctx);
    if (have.has(k)) continue;
    have.add(k);
    odd.push(group === "milestone" ? col2(k, "Archived or missing milestone") : group === "status" ? col2(k, `${k} (old status)`) : col2(k, `${k} (not a priority)`));
  }
  if (!odd.length) return base;
  const at = base.findIndex((c) => c.extra);
  return at < 0 ? base.concat(odd) : base.slice(0, at).concat(odd, base.slice(at));
}
const col2 = (key, label) => ({ key, label, tone: "grey", nodrop: true });

function baseColumns(group, rows, ctx) {
  const col = (key, label, tone = "", more = {}) => ({ key, label, tone, ...more });
  const seen = (g) => new Set(rows.map((r) => cellOf(g, r, ctx)));
  if (group === "workstream") {
    const names = ctx.workstreams.slice(), out = names.map((n) => col(n, n));
    for (const k of seen("workstream")) if (k !== NONE && !names.includes(k)) out.push(col(k, k, "", { nodrop: true }));
    return out.concat(col(NONE, MISSING.workstream, "grey", { extra: true }));
  }
  if (group === "status") {
    const kinds = ctx.kinds || ["action", "risk", "decision"];
    const have = new Set(rows.map((r) => r.status));
    for (const k of kinds) for (const s of k === "decision" ? STATUSES.decision : k === "action" ? STATUSES.action : ["Open", "Closed", "Cancelled"]) have.add(s);
    return STATUS_ORDER.filter((s) => have.has(s)).map((s) => col(s, s, STATUS_TONE[s] || "grey"));
  }
  if (group === "due") return DUE.map(([k, label, tone]) => col(k, label, tone, k === "overdue" ? { nodrop: true } : k === NONE ? { extra: true } : {}));
  if (group === "owner") {
    const count = {};
    for (const r of rows) { const k = cellOf("owner", r, ctx); if (k !== NONE) count[k] = (count[k] || 0) + 1; }
    for (const p of ctx.people || []) if (!(p in count) && !isNoOwner(p)) count[p] = 0;
    const names = Object.keys(count).sort((a, b) => (b === ctx.me) - (a === ctx.me) || count[b] - count[a] || (a < b ? -1 : a > b ? 1 : 0));
    return names.map((n) => col(n, n === ctx.me ? `${n} (me)` : n)).concat(col(NONE, MISSING.owner, "grey", { extra: true }));
  }
  if (group === "priority") return PRIORITIES.map((p) => col(p, p, PRIORITY_TONE[p])).concat(col(NONE, MISSING.priority, "grey", { extra: true, nodrop: true }));
  if (group === "milestone") {
    const out = ctx.milestones.map((m) => col(m.id, m.name));
    return out.concat(col(NONE, MISSING.milestone, "grey", { extra: true }));
  }
  if (group === "type") return TYPES.map(([k, label]) => col(k, label));
  return [col("all", "All work items")];
}

// ── The card ──────────────────────────────────────────────────────────────────

export function cardOf(row, today) {
  const o = ownerOf(row.owner);
  return {
    id: row.id, table: row.table, type: KIND_WORDS[row.kind] || row.kind, typeClass: `k-${row.kind}`,
    client: !!row.client,                       // display only: the eye shows when the item is shown to the client
    title: row.title, owner: o.text, initials: o.initials, due: dueCell(row, today), state: pillOf(row, today), open: isOpen(row),
  };
}

// The board: {lanes: [{key, label, count, columns: [{key, label, tone, extra, nodrop, count, cards}]}]}. `lane` is a group id
// (workstream or type) or null; the group already chosen is not a lane. Counts are the cards shown (rows are already filtered).
export function build(rows, { group, lane = null, ctx }) {
  const g = group === "nothing" ? "status" : group;
  const l = lane && lane !== g && LANE_GROUPS.includes(lane) ? lane : null;
  const cols = columnsFor(g, rows, ctx);
  const lanes = l === null ? [{ key: null, label: "", cols: null }]
    : columnsFor(l, rows, ctx).filter((x) => x.key !== NONE || rows.some((r) => cellOf(l, r, ctx) === NONE)).map((x) => ({ key: x.key, label: x.label, cols: null }));
  return {
    group: g, lane: l,
    lanes: lanes.map((ln) => {
      const mine = l === null ? rows : rows.filter((r) => cellOf(l, r, ctx) === ln.key);
      const columns = cols.map((c) => { const cards = mine.filter((r) => cellOf(g, r, ctx) === c.key).map((r) => cardOf(r, ctx.today)); return { ...c, count: cards.length, cards }; });
      return { key: ln.key, label: ln.label, count: mine.length, columns };
    }),
  };
}

// ── Moving a card ─────────────────────────────────────────────────────────────

const refuse = (message, half) => ({ ok: false, message, half });
const yes = (changes, more = {}) => ({ ok: true, changes, ...more });
const same = { ok: true, noop: true };

// One half of a move: the card to a column (or a lane) of `group` with key `key`. {ok, changes, needsDate?, note?}, {ok: false,
// message} or {ok: true, noop: true}. The order is the spec's: what the card can never do first, then the target.
function half(row, group, key, ctx) {
  const kind = kindOf(row), a = A[row.kind] || "A work item";
  if (group === "type") return refuse(`${a} can't change its type.`);
  if (group === "due") return dueHalf(row, key, ctx);
  if (withdrawn(row)) {
    if (group === "status" && key === "Pending") return yes({ status: "Pending" });          // the store allows a withdrawn decision back
    return refuse(WORDS.withdrawn);
  }
  if (decided(row)) return refuse(group === "status" && key === "Pending" ? WORDS.madeStays : WORDS.decided);
  switch (group) {
    case "workstream":
      if (kind === "decision") return refuse(WORDS.noWorkstream);
      if (key !== NONE && !ctx.workstreams.includes(key)) return refuse(WORDS.strangeWorkstream);
      return yes({ workstream: key === NONE ? null : key });
    case "milestone":
      if (kind === "decision") return refuse(WORDS.noMilestone);
      if (key !== NONE && !ctx.milestones.some((m) => m.id === key)) return refuse(WORDS.strangeMilestone);
      return yes({ milestone: key === NONE ? null : key });
    case "owner":
      if (kind === "decision") return yes({ made_by: key === NONE ? null : key });
      return yes({ owner: key === NONE ? "TBC" : key });
    case "priority":
      if (kind === "decision") return refuse(WORDS.noPriority);
      if (kind === "raid") return refuse(WORDS.riskPriority);
      if (key === NONE) return refuse(WORDS.notRated);
      return PRIORITIES.includes(key) ? yes({ priority: key }) : refuse(WORDS.strangePriority);
    case "status": {
      const ok = statusesOf(row);
      if (!ok.includes(key)) return refuse(`${a} can't be ${key}. It can be ${list(ok)}.`);
      if (kind === "decision" && key === "Made") return yes({ status: "Made", date: ctx.today }, { note: "Made, dated today", undoable: false });
      return yes({ status: key });
    }
    default: return refuse("A card can't be moved there.");
  }
}

function dueHalf(row, key, ctx) {
  if (withdrawn(row)) return refuse(WORDS.withdrawnDue);
  if (decided(row)) return refuse(WORDS.decidedDue);
  const field = row.kind === "decision" ? "needed_by" : "due_date";
  if (key === "overdue") return refuse(WORDS.overdue);
  if (key === NONE) return yes({ [field]: null });
  const t = dayNumber(ctx.today);
  if (t === null) return refuse(WORDS.notADate);
  const friday = (n) => Math.max(sundayOf(n) - 2, t);        // that week's Friday, or today when it has gone
  const day = key === "this_week" ? friday(t) : key === "next_week" ? sundayOf(t) + 5 : sundayOf(t) + 12;
  return yes({}, { needsDate: { field, min: ctx.today, suggested: isoOf(day), column: key } });
}

// A cell: {group, key, lane: {group, key} | null}. fromCell is where the card is; toCell where it is dropped.
// Returns {ok: true, noop: true} (nothing to do, no message), {ok: true, request, needsDate?, note?} or {ok: false, message}.
// `undoable: false` marks a move the store won't put back (a decision made can't go back to Pending), so no Undo is offered.
// `request` is exactly what changes.make_change takes; with `needsDate` ({field, min, suggested}) the date is still to be
// picked and `dateMove` finishes it.
export function moveFor(row, fromCell, toCell, ctx) {
  const parts = [];
  if (toCell.group && toCell.group === (toCell.lane && toCell.lane.group)) return refuse(WORDS.sameField);
  if (!fromCell || fromCell.group !== toCell.group || fromCell.key !== toCell.key) parts.push(["column", toCell.group, toCell.key]);
  const fl = fromCell && fromCell.lane, tl = toCell.lane;
  if (tl && (!fl || fl.group !== tl.group || fl.key !== tl.key)) parts.push(["lane", tl.group, tl.key]);
  if (!parts.length) return same;
  const results = parts.map(([name, g, k]) => [name, half(row, g, k, ctx)]);
  const bad = results.find(([, r]) => !r.ok);
  if (bad) return refuse(parts.length > 1 ? `Nothing was moved. The card can't go in that ${bad[0] === "lane" ? "swimlane" : bad[0]}. ${bad[1].message}` : bad[1].message, bad[0]);
  const changes = {};
  let needsDate = null, note = null, undoable = true;
  for (const [, r] of results) { Object.assign(changes, r.changes); needsDate = needsDate || r.needsDate || null; note = note || r.note || null; undoable = undoable && r.undoable !== false; }
  const request = { project: ctx.project, kind: row.table, op: "update", id: row.id, changes, place: PLACE };
  return { ok: true, request, ...(needsDate ? { needsDate } : {}), ...(note ? { note } : {}), ...(undoable ? {} : { undoable: false }) };
}

// The date picked for a move that needs one: refused if it isn't a real day or is in the past ("due never in the past" is the
// page's rule; the server takes any real date, so the peek can enter an old one).
export function dateMove(move, date, today) {
  if (!move.ok || !move.needsDate) return move;
  const d = dayNumber(date), t = dayNumber(today);
  if (d === null) return refuse(WORDS.notADate);
  if (t !== null && d < t) return refuse(WORDS.pastDate);
  const want = move.needsDate.column;
  if (want && t !== null && bucketOf(d, t) !== want) return refuse(`That date isn't in the "${DUE_LABEL[want] || "that"}" column. Pick a day in it, or drop the card on the column that holds that date.`);
  const { needsDate, ...rest } = move;
  return { ...rest, request: { ...move.request, changes: { ...move.request.changes, [needsDate.field]: date } } };
}

// The columns a card can be moved to (for the Move to... menu and the drop indicator): those moveFor accepts, not where it is.
export function targetsFor(row, fromCell, columns, ctx) {
  return columns.filter((c) => {
    const r = moveFor(row, fromCell, { group: fromCell.group, key: c.key, lane: fromCell.lane }, ctx);
    return r.ok && !r.noop;
  });
}

// The words that say a move happened (the toast), from the request.
export function movedWords(move, row) {
  const c = move.request.changes, bits = [];
  if ("status" in c) bits.push(move.note || c.status);
  if ("workstream" in c) bits.push(c.workstream ? `in the ${c.workstream} workstream` : "in no workstream");
  if ("owner" in c || "made_by" in c) { const o = c.owner !== undefined ? c.owner : c.made_by; bits.push(!o || o === "TBC" ? "with no owner" : `with ${o}`); }
  if ("priority" in c) bits.push(`${c.priority} priority`);
  if ("milestone" in c) bits.push(c.milestone ? "with a milestone" : "with no milestone");
  if ("due_date" in c || "needed_by" in c) { const d = c.due_date !== undefined ? c.due_date : c.needed_by; bits.push(d ? `due ${d.split("-").reverse().join("-")}` : "with no due date"); }
  return `${row.id} is now ${bits.join(", ")}.`;
}

// ── What is remembered (per project, in this browser) ─────────────────────────
// One key, an object by project code, every read and write in try/catch; the page works with defaults when storage is blocked.
// Not the address (spec section 5): none of this goes in a link. The pure functions take the storage so a test can pass any.

export const STORAGE_KEY = "clark.work.v1";
const memory = {};
const memoryStorage = { getItem: (k) => (k in memory ? memory[k] : null), setItem: (k, v) => { memory[k] = String(v); } };

export function browserStorage() {
  try { return window.localStorage || memoryStorage; } catch (e) { return memoryStorage; }
}

export const DEFAULT_STATE = { view: "table", group: "workstream", lane: null, collapsed: [] };

// Anything stored is untrusted: clamp it to what the board understands.
export function cleanState(raw) {
  const o = raw && typeof raw === "object" && !Array.isArray(raw) ? raw : {};
  const group = GROUP_IDS.includes(o.group) ? o.group : DEFAULT_STATE.group;
  const lane = LANE_GROUPS.includes(o.lane) && o.lane !== (group === "nothing" ? "status" : group) ? o.lane : null;
  const collapsed = Array.isArray(o.collapsed) ? o.collapsed.filter((x) => typeof x === "string" && x.length <= 120).slice(0, 200) : [];
  return { view: o.view === "board" ? "board" : "table", group, lane, collapsed };
}

export function readState(project, storage = browserStorage()) {
  try {
    const all = JSON.parse(storage.getItem(STORAGE_KEY) || "{}");
    return cleanState(all && typeof all === "object" ? all[project] : null);
  } catch (e) { return cleanState(null); }
}

// Saves what changed for a project and gives the new state; false in `saved` when storage refused (the view still works).
export function writeState(project, patch, storage = browserStorage()) {
  const now = cleanState({ ...readState(project, storage), ...patch });
  try {
    let all = {};
    try { all = JSON.parse(storage.getItem(STORAGE_KEY) || "{}") || {}; } catch (e) { all = {}; }
    if (typeof all !== "object" || Array.isArray(all)) all = {};
    all[project] = now;
    storage.setItem(STORAGE_KEY, JSON.stringify(all));
    return { state: now, saved: true };
  } catch (e) { return { state: now, saved: false }; }
}

// On the board "Nothing" is not offered: a saved "Nothing" reads as Status.
export function boardGroup(group) { return group === "nothing" ? "status" : group; }

const collapseKey = (group, key) => `${boardGroup(group)}:${key}`;
export function isCollapsed(state, group, key) { return state.collapsed.includes(collapseKey(group, key)); }
export function toggleCollapsed(state, group, key) {
  const k = collapseKey(group, key);
  return { ...state, collapsed: state.collapsed.includes(k) ? state.collapsed.filter((x) => x !== k) : state.collapsed.concat(k) };
}
// A saved collapsed column whose grouping or value has gone is ignored, never an error: the keys that still match a column.
export function collapsedNow(state, group, columns) {
  const have = new Set(columns.map((c) => collapseKey(group, c.key)));
  return state.collapsed.filter((k) => have.has(k)).map((k) => k.slice(k.indexOf(":") + 1));
}
