// The peek's warning above the title (Edit only): an open action that is late, or an open item whose date falls on a weekend,
// with the one-click moves that put it right. Plain functions with no DOM and no clock (the caller hands in today, YYYY-MM-DD).
import { dayNumber, dueField, isOpen, plural, showDate } from "../workItems.js";
import { addDays } from "./itemEdit.js";

const DAY = 86400000;
const NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const weekday = (iso) => new Date(dayNumber(iso) * DAY).getUTCDay();         // 0 Sunday .. 6 Saturday

/** The next Friday that is not before `today` (today itself when it is a Friday). */
export function fridayFrom(today) { return addDays(today, (5 - weekday(today) + 7) % 7); }

const fix = (label, iso, dated = true) => ({ label: dated ? `${label} ${showDate(iso)}` : label, iso });

/**
 * The warning for a row, or null. {tone: "late" | "weekend", text, fixes: [{label, iso}]}. Only an open row with a real due date
 * has one. A late action says how late; a date on a Saturday or Sunday says so and offers the Friday before and the Monday after
 * (for a late action the moves are to the next Friday and a week on, so a move never lands in the past).
 */
export function warningFor(row, today) {
  const iso = dueField(row), a = dayNumber(iso), t = dayNumber(today);
  if (a === null || t === null || !isOpen(row)) return null;
  const dow = weekday(iso), weekend = dow === 0 || dow === 6;
  const late = row.kind === "action" && a < t;
  const when = `${NAMES[dow]} ${showDate(iso)}`;
  if (late) {
    return { tone: "late", text: `${plural(t - a, "day")} overdue (due ${weekend ? when + ", a weekend: a working day is usually meant" : showDate(iso)})`,
      fixes: [fix("Move to Friday", fridayFrom(today)), fix("Move a week on", addDays(today, 7), false)] };
  }
  if (!weekend) return null;
  return { tone: "weekend", text: `Due on a ${NAMES[dow]} (${showDate(iso)}): a working day is usually meant`,
    fixes: [fix("Move to Friday", addDays(iso, dow === 0 ? -2 : -1)), fix("Move to Monday", addDays(iso, dow === 0 ? 1 : 2))] };
}
