// The peek's 'Last updated' stamp and the warning bar above the title, as plain functions with no DOM and no clock (the caller hands
// in today). The words and the rules follow the signed-off prototype (system/prototype/peek.js `warn`); the data is clark's: every
// item's `updated_at`. (Row 1077: the Draft chip and the helper that wrote its words left; the owner's ruling removed it from every peek.)
import { dayNumber, showDate, dueField, isOpen, plural } from "../workItems.js";
import { addDays, quickDates } from "./itemEdit.js";

const DAY = 86400000;
const NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

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
  if (row.kind === "action" && n < t && row.status !== "Completed") {
    const fri = quickDates(today)[2][1], week = addDays(today, 7);
    return { kind: "overdue", text: `${plural(t - n, "day")} overdue (due ${showDate(due)})`,
      moves: [{ label: `Move to Friday ${showDate(fri)}`, date: fri }, { label: "Move a week on", date: week }] };
  }
  return null;
}

/** A stored time (UTC, "2026-10-28 09:00:00.483") as the time on this clock, "28-10-2026 13:00"; "" when it is not a time. */
export function stampText(stamp) {
  const m = /^(\d{4})-(\d\d)-(\d\d)[T ](\d\d):(\d\d)/.exec(String(stamp == null ? "" : stamp));
  if (!m) return "";
  const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5])), two = (v) => String(v).padStart(2, "0");
  if (Number.isNaN(d.getTime())) return "";
  return `${two(d.getDate())}-${two(d.getMonth() + 1)}-${String(d.getFullYear()).padStart(4, "0")} ${two(d.getHours())}:${two(d.getMinutes())}`;
}
