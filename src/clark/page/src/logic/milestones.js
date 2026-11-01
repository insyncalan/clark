// The Milestones view's rules as plain functions with no DOM and no clock (#44a Plan). They are the page's copy of what
// clark/milestones.py (#32) and clark/milestone_rows.py (#44) work out, so the editor and a published file draw the same marks;
// tests/test_milestones_page.py checks every value against those two modules. A row is a milestones row from GET /api/data (the
// editor) or from a published file's data block (which has already worked out `state`, and has no internal note).
// Dates are YYYY-MM-DD in every value and DD-MM-YYYY in every sentence (showDate).
import { dayNumber, showDate, todayIso } from "../workItems.js";

export { showDate, todayIso };

export const STATES = ["Achieved", "On track", "At risk", "Slipped", "Overdue", "Forecast"];
const RANK = { Achieved: 0, "On track": 1, "At risk": 2, Slipped: 3, Overdue: 4 };
export const CLIENT_WORD = { Achieved: "Achieved", "On track": "On track", "At risk": "At risk", Slipped: "Expected later", Overdue: "Late", Forecast: "Forecast" };
export const CANCELLED = "Cancelled";
// State -> colour name, shape name, meaning (the prototype's and creaite's marks; the page maps names to tokens in CSS).
export const LOOK = {
  Achieved: ["green", "tick-circle", "Done, on the date it was achieved"],
  "On track": ["green", "dot", "Expected on its agreed date"],
  "At risk": ["amber", "triangle", "Marked at risk by the project team"],
  Slipped: ["red", "diamond", "Now expected after its agreed date"],
  Overdue: ["red", "cross-circle", "Its agreed date has passed"],
  Forecast: ["blue", "dashed-circle", "A date not yet agreed"],
  [CANCELLED]: ["grey", "dash", "No longer going ahead"],
};
export const ZOOM_MIN = 0.7, ZOOM_MAX = 3.0;
const LEAD_DAYS = 20, TAIL_DAYS = 45, DAY = 86400000;
export const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

export const plural = (n, word) => `${n} ${word}${Math.abs(n) === 1 ? "" : "s"}`;
export const isoOf = (n) => new Date(n * DAY).toISOString().slice(0, 10);
export const addDays = (iso, k) => isoOf(dayNumber(iso) + k);

// What the dates say (creaite's suggested_state): Achieved when Done, Overdue when the agreed date has passed, Slipped when the
// forecast is later than the agreed date, On track otherwise.
export function suggestedState(r, on) {
  if (r.status === "Done") return "Achieved";
  const base = r.baseline_date, fc = r.forecast_date || base;
  if (base && base < on) return "Overdue";
  if (base && fc && fc > base) return "Slipped";
  return "On track";
}

export function stateOf(r, on) {
  if (r.status === "Done") return "Achieved";
  if (r.state_set && r.state) return r.state;
  return suggestedState(r, on);
}

// Days a Planned milestone runs past its agreed date (the expected date less the agreed date); null when it is not Planned or has
// no agreed date that is a real date (an unreadable date gives no slip, so no 'N days later'). The expected date is the later of
// the forecast (or agreed date) and, once the agreed date has passed, today.
export function expectedDate(r, on) {
  if ((r.status || "Planned") !== "Planned" || dayNumber(r.baseline_date) === null) return null;
  const base = r.baseline_date, fc = r.forecast_date || base, floor = base < on ? on : base;
  return fc > floor ? fc : floor;
}
export function slipDays(r, on) {
  const e = expectedDate(r, on);
  if (e === null || dayNumber(e) === null) return null;   // a forecast that is not a real date gives no slip either
  return dayNumber(e) - dayNumber(r.baseline_date);
}

// The solid mark sits on the agreed date (the achieved date once achieved; the forecast when there is no agreed date); a slipped
// milestone also has a ghost on its expected date and a dashed line back (FR-50, FR-51). A Forecast or achieved one has neither.
export function marksOf(r, state, slip, expected) {
  const base = r.baseline_date, fc = r.forecast_date, done = r.actual_date;
  let solid = null;
  if (r.status === "Done" && (done || base)) solid = { date: done || base, kind: done ? "achieved" : "agreed" };
  else if (base) solid = { date: base, kind: "agreed" };
  else if (fc) solid = { date: fc, kind: "forecast" };
  let ghost = null, line = null;
  if (slip && slip > 0 && state !== "Forecast" && solid && solid.kind === "agreed") {
    ghost = { date: expected, label: `Expected ${showDate(expected)}` };
    line = { from: base, to: expected, days: slip };
  }
  return { solid, ghost, line };
}

function achievedNote(r) {
  if (r.status !== "Done" || !r.actual_date) return "";
  if (!r.baseline_date) return `Achieved on ${showDate(r.actual_date)}`;
  const late = dayNumber(r.actual_date) - dayNumber(r.baseline_date);
  if (late === 0) return "Achieved on the agreed date";
  return late > 0 ? `Achieved ${plural(late, "day")} after the agreed date` : `Achieved ${plural(-late, "day")} early`;
}

const sortKey = (a, b) => {
  const da = a.baseline || a.forecast, db = b.baseline || b.forecast;
  if ((da === null || da === undefined) !== (db === null || db === undefined)) return da ? -1 : 1;
  if (da !== db) return da < db ? -1 : 1;
  if (a.sort_order !== b.sort_order) return a.sort_order - b.sort_order;
  return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
};

/** Display rows, sorted by agreed date (none: by forecast, then last), then sort order, then id. `client` is a published file:
 *  its rows keep the state the file worked out (the server's own count at publication), Cancelled ones are left out and the word
 *  is the client's. The editor works the state out from the dates and what the user set. */
export function milestoneRows(list, today, client) {
  const out = [];
  for (const r of list || []) {
    if (r.archived) continue;
    const cancelled = r.status === CANCELLED;
    if (cancelled && client) continue;
    const state = cancelled ? CANCELLED : client && r.state ? r.state : stateOf(r, today);
    const slip = cancelled || state === "Forecast" ? null : slipDays(r, today);
    const expected = slip ? expectedDate(r, today) : null;
    const look = LOOK[state] || LOOK.Forecast;
    out.push({
      id: r.id, name: r.name, owner: r.owner || "", status: r.status || "Planned", state,
      word: cancelled ? CANCELLED : client ? CLIENT_WORD[state] || state : state,
      colour: look[0], mark: look[1], baseline: r.baseline_date || null, forecast: r.forecast_date || null,
      achieved: r.status === "Done" ? r.actual_date || null : null, achievedNote: achievedNote(r),
      percent: r.percent_complete === undefined ? null : r.percent_complete, slip, slipText: slip ? `${plural(slip, "day")} later` : null,
      expected, marks: marksOf(r, state, slip, expected), clientVisible: r.client_visible === undefined ? true : !!r.client_visible,
      sort_order: r.sort_order || 0,
    });
  }
  return out.sort(sortKey);
}

export const clampZoom = (z) => { const n = Number(z); return Number.isFinite(n) ? Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, n)) : 1; };

// A date the axis and the Calendar draw: a real day in the years 2000 to 2100. Anything else (a typo such as 0026 or 2126, or a
// year past 9999) is not drawn; the Timeline says so in one plain note instead (FAR_NOTE) so one stray date cannot stretch the axis.
export const YEAR_MIN = 2000, YEAR_MAX = 2100, MAX_TICKS = 200;
export const FAR_NOTE = "Left off the timeline because the date looks wrong";
export const inRange = (iso) => typeof iso === "string" && dayNumber(iso) !== null && +iso.slice(0, 4) >= YEAR_MIN && +iso.slice(0, 4) <= YEAR_MAX;
const allMarks = (rows) => rows.flatMap((r) => [r.marks.solid, r.marks.ghost]).filter(Boolean);
export const markDates = (rows) => allMarks(rows).map((m) => m.date).filter(inRange);
// The rows with a mark outside the range: the Timeline leaves them off its axis and names them in the note.
export const farRows = (rows) => rows.filter((r) => [r.marks.solid, r.marks.ghost].some((m) => m && !inRange(m.date)));

// The axis: the first of the month 20 days before the earliest mark (or today) to the first of the month 45 days after the latest.
export function timelineSpan(rows, today) {
  const dates = markDates(rows).concat(today).sort();
  const first = (iso) => { const d = new Date(dayNumber(iso) * DAY); return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 1) / DAY; };
  return { start: isoOf(first(addDays(dates[0], -LEAD_DAYS))), end: isoOf(first(addDays(dates[dates.length - 1], TAIL_DAYS))) };
}

// The first of each month from `start` up to (not including) `end`.
export function monthStarts(start, end) {
  const out = [];
  let y = +start.slice(0, 4), m = +start.slice(5, 7);
  while (`${y}-${String(m).padStart(2, "0")}-01` < end) { out.push(`${y}-${String(m).padStart(2, "0")}-01`); m++; if (m > 12) { m = 1; y++; } }
  if (out.length <= MAX_TICKS) return out;
  const every = Math.ceil(out.length / MAX_TICKS);       // never more than MAX_TICKS names on the axis
  return out.filter((_, i) => i % every === 0);
}

const monthEnd = (y, m) => isoOf(Date.UTC(y, m, 1) / DAY - 1);

export function bucketKey(kind, iso) {
  const n = dayNumber(iso);
  if (kind === "week") return isoOf(n - ((new Date(n * DAY).getUTCDay() + 6) % 7));
  if (kind === "month") return iso.slice(0, 7);
  if (kind === "quarter") return `${iso.slice(0, 4)}-Q${Math.floor((+iso.slice(5, 7) - 1) / 3) + 1}`;
  throw new Error("kind must be week, month or quarter");
}

/** The weeks (Monday to Sunday), months or quarters that hold any day from `start` to `end`, whole, in order: {key, start, end,
 *  label} (a quarter also has its three `months`). */
export function buckets(kind, start, end) {
  if (!["week", "month", "quarter"].includes(kind)) throw new Error("kind must be week, month or quarter");
  if (dayNumber(start) > dayNumber(end)) return [];
  const out = [], last = bucketKey(kind, end);
  let key = bucketKey(kind, start);
  for (;;) {
    let b, next;
    if (kind === "week") {
      const s = dayNumber(key);
      b = { key, start: key, end: isoOf(s + 6), label: `Week of ${showDate(key)}` };
      next = isoOf(s + 7);
    } else if (kind === "month") {
      const y = +key.slice(0, 4), m = +key.slice(5, 7);
      b = { key, start: `${key}-01`, end: monthEnd(y, m), label: `${MONTHS[m - 1]} ${y}` };
      next = `${m === 12 ? y + 1 : y}-${String(m % 12 + 1).padStart(2, "0")}`;
    } else {
      const y = +key.slice(0, 4), q = +key.slice(-1), first = (q - 1) * 3 + 1;
      b = { key, start: `${y}-${String(first).padStart(2, "0")}-01`, end: monthEnd(y, first + 2), label: `Q${q} ${y}`,
        months: [0, 1, 2].map((i) => `${y}-${String(first + i).padStart(2, "0")}`) };
      next = `${q === 4 ? y + 1 : y}-Q${q % 4 + 1}`;
    }
    out.push(b);
    if (key === last) return out;
    key = next;
  }
}

/** {date: [chip]}: a chip on each solid mark, then a ghost chip on each slipped milestone's expected date. */
export function calendarChips(rows) {
  const out = {};
  for (const ghost of [false, true]) {
    for (const r of rows) {
      const m = r.marks[ghost ? "ghost" : "solid"];
      if (m) (out[m.date] = out[m.date] || []).push({ id: r.id, name: r.name, state: r.state, word: r.word, colour: r.colour, mark: r.mark, ghost, date: m.date });
    }
  }
  return out;
}

/** The Legend: the six states in order, then Expected and Today. A published file says the client's word. */
export function legend(client) {
  const out = STATES.map((s) => ({ state: s, word: client ? CLIENT_WORD[s] : s, colour: LOOK[s][0], mark: LOOK[s][1], means: LOOK[s][2] }));
  out.push({ state: "Expected", word: "Expected", colour: null, mark: "ghost", means: "Where a slipped milestone is now expected; a dashed line joins it to its agreed date" });
  out.push({ state: "Today", word: "Today", colour: null, mark: "today-line", means: "The line on the timeline; the blue date on the calendar" });
  return out;
}

// The rail list shows 5, then "Show all N milestones" / "Show the first 5".
export const RAIL = 5;
export function railRows(rows, all) { return all || rows.length <= RAIL ? rows : rows.slice(0, RAIL); }
export const railWord = (n, all) => (all ? "Show the first 5" : `Show all ${n} milestones`);

/** Label rows that would overlap are put on lower lines (the prototype's place()): returns each label's line, in x order. Each label is
 *  centred on its x; `width` is one number or one width for each label, and `gap` is the clear space kept between neighbours. */
export function labelLines(xs, width, gap = 0) {
  const ends = [];
  return xs.map((x, i) => {
    const w = (Array.isArray(width) ? width[i] : width) + gap;
    let r = 0;
    while (ends[r] !== undefined && ends[r] > x - w / 2) r++;
    ends[r] = x + w / 2;
    return r;
  });
}

// The Milestones page's one-sentence summary (#458; the prototype's, views.js): the last milestone's date (and where it is now
// expected), then how many are achieved and how many are still to come. Cancelled ones are not counted. null when there is none.
// `agreed` is false for a last milestone that has only a forecast, so the page does not call that date agreed.
export function headLine(rows) {
  const live = (rows || []).filter((r) => r.state !== CANCELLED);
  if (!live.length) return null;
  const last = live[live.length - 1], achieved = live.filter((r) => r.state === "Achieved").length;
  return { name: last.name, date: last.baseline || last.forecast, agreed: !!last.baseline, expected: last.slip > 0 ? last.expected : null, achieved, toCome: live.length - achieved };
}
