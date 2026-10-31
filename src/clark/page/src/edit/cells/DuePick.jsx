// #80: the date picker of clark's own (the Due cell; a decision's needed-by or decision date), in one panel: a month with ‹ ›,
// then quick choices. No browser date popup is used, so nothing opens over it and a single Esc closes it, leaving the date as it
// was (#91, #92). Keys: the arrows move a day or a week, Page Up and Page Down a month, Home and End the week's first and last day,
// Enter or Space picks. The same props as StatusPick, plus `today`, so the peek (#42) can use it as it is.
import { useLayoutEffect, useRef, useState } from "preact/hooks";
import { Pop } from "./Pop.jsx";
import { addDays, addMonths, monthCells, monthTitle, quickDates, canClearDue, fieldName } from "../itemEdit.js";
import { dueField, showDate, dayNumber } from "../../workItems.js";

const WEEK = [["M", "Monday"], ["T", "Tuesday"], ["W", "Wednesday"], ["T", "Thursday"], ["F", "Friday"], ["S", "Saturday"], ["S", "Sunday"]];

export function DuePick({ row, anchor, today, onPick, onClose }) {
  const value = dayNumber(dueField(row)) === null ? "" : dueField(row);
  const [at, setAt] = useState(value || today);
  const [month, setMonth] = useState((value || today).slice(0, 7));
  const grid = useRef(null), moved = useRef(true);       // true: focus goes to the day when the panel opens
  const now = useRef(at);                                  // the day as the keys last left it, before the redraw has caught up
  const what = fieldName(row, "due");
  useLayoutEffect(() => {                                  // after a key moved the day (not after ‹ or ›, which keep focus)
    const el = moved.current && grid.current && grid.current.querySelector(`[data-day="${at}"]`);
    moved.current = false;
    if (el) el.focus({ preventScroll: true });
  }, [at, month]);
  const go = (day) => { moved.current = true; now.current = day; setAt(day); setMonth(day.slice(0, 7)); };
  const keys = (e) => {
    const from = now.current;
    const wd = (new Date(dayNumber(from) * 86400000).getUTCDay() + 6) % 7;      // 0 Monday .. 6 Sunday
    const step = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7, Home: -wd, End: 6 - wd }[e.key];
    if (step !== undefined) { e.preventDefault(); go(addDays(from, step)); return; }
    if (e.key === "PageUp" || e.key === "PageDown") {
      e.preventDefault();
      const ym = addMonths(from.slice(0, 7), e.key === "PageUp" ? -1 : 1), last = monthCells(ym).filter(Boolean).pop();
      const day = `${ym}-${from.slice(8)}`;
      go(day > last ? last : day);
    }
  };
  const flip = (n) => { const ym = addMonths(month, n); now.current = `${ym}-01`; setMonth(ym); setAt(`${ym}-01`); };
  const quick = quickDates(today).concat(canClearDue(row) ? [["No date", ""]] : []);
  return (
    <Pop anchor={anchor} label={`${what} of ${row.id}`} cls="cdate" onClose={onClose}>
      <div class="cp-h">
        <button type="button" class="cp-m" data-month="-1" aria-label="Previous month" onClick={() => flip(-1)}>{"‹"}</button>
        <b class="cp-t" aria-live="polite">{monthTitle(month)}</b>
        <button type="button" class="cp-m" data-month="1" aria-label="Next month" onClick={() => flip(1)}>{"›"}</button>
      </div>
      <div class="cp-g" ref={grid} role="group" aria-label={monthTitle(month)} onKeyDown={keys}>
        {WEEK.map(([w, name], i) => <span class="cp-w" key={`w${i}`} title={name} aria-hidden="true">{w}</span>)}
        {monthCells(month).map((day, i) => (day
          ? <button type="button" key={day} data-day={day} tabIndex={day === at ? 0 : -1}
              class={`${day === today ? "today " : ""}${day === value ? "sel" : ""}`.trim() || undefined}
              aria-pressed={day === value ? "true" : "false"} aria-current={day === today ? "date" : undefined}
              aria-label={`${showDate(day)}${day === today ? ", today" : ""}`} onClick={() => onPick(day)}>{+day.slice(8)}</button>
          : <span key={`b${i}`} />))}
      </div>
      <div class="cp-q">
        {quick.map(([text, day]) => (
          <button type="button" key={text} data-quick={day} onClick={() => onPick(day)}>
            <span>{text}</span>{day ? <small class="num">{showDate(day)}</small> : null}
          </button>
        ))}
      </div>
    </Pop>
  );
}
