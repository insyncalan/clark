// The peek's Latest update, its Draft button, the 'Last updated' stamp and the warning bar above the title, as plain functions
// with no DOM and no clock (the caller hands in today). The words and the rules follow the signed-off prototype (system/prototype/peek.js
// `warn`, `C.draftUpdate`); the data is clark's: an action's `latest_update` and every item's `updated_at`.
import { dayNumber, showDate, dueField, isOpen, plural } from "../workItems.js";
import { addDays, quickDates } from "./itemEdit.js";

const DAY = 86400000;
const NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
export const LATEST_MAX = 1000;                 // clark/changes.py LATEST_UPDATE_MAX

const weekday = (iso) => new Date(dayNumber(iso) * DAY).getUTCDay();         // 0 Sunday .. 6 Saturday

/**
 * The bar above an open item's title, or null. A date on a Saturday or a Sunday: Move to the Friday before or the Monday after.
 * An action past its date: Move to Friday (the next one, a week on if today is a Friday) or Move a week on (a week from today).
 * `moves` are [{label, date}]; each is one change with one Undo.
 */
export function warnFor(row, today) {
  const due = dueField(row), n = dayNumber(due), t = dayNumber(today);
  if (!due || n === null || t === null || !isOpen(row)) return null;
  const wd = weekday(due);
  if (wd === 0 || wd === 6) {
    const fri = addDays(due, wd === 0 ? -2 : -1), mon = addDays(due, wd === 0 ? 1 : 2);
    return { kind: "weekend", text: `Due on a ${NAMES[wd]} (${showDate(due)}): a working day is usually meant`,
      moves: [{ label: `Move to Friday ${showDate(fri)}`, date: fri }, { label: `Move to Monday ${showDate(mon)}`, date: mon }] };
  }
  if (row.kind === "action" && n < t) {
    const fri = quickDates(today)[2][1], week = addDays(today, 7);
    return { kind: "overdue", text: `${plural(t - n, "day")} overdue (due ${showDate(due)})`,
      moves: [{ label: `Move to Friday ${showDate(fri)}`, date: fri }, { label: "Move a week on", date: week }] };
  }
  return null;
}

const none = (owner) => { const o = String(owner == null ? "" : owner).trim(); return !o || o.toUpperCase() === "TBC"; };

/**
 * A latest update written from the item's own fields, by rules and not by AI: when it is due or since when it is overdue, who has it
 * and whether they have started, and the milestone it is needed for. `milestone` is {name, agreed} or null.
 */
export function draftFor({ due, status, owner, milestone }, today) {
  const late = due && isOpen({ status }) && dayNumber(due) !== null && dayNumber(today) !== null && dayNumber(due) < dayNumber(today);
  const parts = [late ? `Overdue since ${showDate(due)}.` : due ? `Due ${showDate(due)}.` : "",
    none(owner) ? "Needs an owner." : `${String(owner).trim()} is ${status === "Open" ? "yet to start" : "working on it"}.`];
  if (milestone && milestone.name) parts.push(`Needed for ${milestone.name.charAt(0).toLowerCase() + milestone.name.slice(1)}${milestone.agreed ? ` on ${showDate(milestone.agreed)}` : ""}.`);
  return parts.filter(Boolean).join(" ");
}

// A character no one can see (control, format such as a zero-width space or a right-to-left override, surrogate, private use, line and
// paragraph separators), as clark/changes.py refuses (ITEM_BAD_KINDS). A line break is allowed in a latest update, so "\n" is taken out first.
const HIDDEN = /[\p{Cc}\p{Cf}\p{Cs}\p{Co}\p{Zl}\p{Zp}]/u;

/** What the Latest update box can't take, in words, or "" when the text is fine: the same limit and the same hidden characters clark refuses. */
export function latestProblem(text) {
  const n = Array.from(text).length;
  if (n > LATEST_MAX) return `A latest update can be ${LATEST_MAX} characters at most, and this one has ${n}. It was not saved. Shorten it and try again.`;
  if (HIDDEN.test(text.replace(/\n/g, ""))) return "That update has a hidden character in it, often from copying and pasting. It was not saved. Type it again, then press Enter.";
  return "";
}

/** The text to save: line ends as \n, trimmed; "" clears it. */
export const cleanLatest = (text) => String(text == null ? "" : text).replace(/\r\n?/g, "\n").trim();

/** A stored time (UTC, "2026-10-28 09:00:00.483") as the time on this clock, "28-10-2026 13:00"; "" when it is not a time. */
export function stampText(stamp) {
  const m = /^(\d{4})-(\d\d)-(\d\d)[T ](\d\d):(\d\d)/.exec(String(stamp == null ? "" : stamp));
  if (!m) return "";
  const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5])), two = (v) => String(v).padStart(2, "0");
  if (Number.isNaN(d.getTime())) return "";
  return `${two(d.getDate())}-${two(d.getMonth() + 1)}-${String(d.getFullYear()).padStart(4, "0")} ${two(d.getHours())}:${two(d.getMinutes())}`;
}
