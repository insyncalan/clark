import { useEffect, useRef, useState } from "preact/hooks";
import { openFile } from "../router.js";
import { pastReportsOf } from "../logic/clientMenu.js";
import { data, asAt } from "../stores/report.js";

// A calendar date is shown DD-MM-YYYY (RULES.md); stored YYYY-MM-DD. Never shifted by a time zone.
const shownDate = (iso) => (/^\d{4}-\d\d-\d\d$/.test(iso) ? iso.slice(8) + "-" + iso.slice(5, 7) + "-" + iso.slice(0, 4) : iso);

// Cards only: row 1253 took the date button out of the Classic client bar, and the Cards theme is frozen, so its button lives here, unchanged.
// Row 1178: the published date in a client's header is a button. A click opens the browser's own calendar (a date box, showPicker). A published
// file has no clark behind it, so it cannot rebuild a day (the as-at rebuild needs the server): a picked day that has an earlier report in the
// same folder opens that report; any other day keeps this report and says so in one line.
export function CardsDate() {
  const [open, setOpen] = useState(false), [note, setNote] = useState(""), btn = useRef(null), box = useRef(null);
  useEffect(() => {
    if (!open || !box.current) return;
    box.current.focus();
    try { if (box.current.showPicker) box.current.showPicker(); } catch (e) { /* the box stays focused: its own keys still work */ }
  }, [open]);
  // A date box fires change for every typed digit that makes a whole date ("0002-05-05" after one digit of the year): only a year from 1990 on is a pick; a click on the button while the box is open closes it (no blur first).
  const picked = (day) => {
    setOpen(false);
    if (btn.current) btn.current.focus();
    if (!day || day === asAt.value) { setNote(""); return; }
    const hit = pastReportsOf(data.value).find((r) => r.iso === day);
    if (hit) { openFile(hit.href); return; }
    setNote("No report for " + shownDate(day) + ".");
  };
  return (
    <span class="asat-wrap">
      <button type="button" class="asat num" ref={btn} title="Click to change date" aria-haspopup="dialog" aria-expanded={open ? "true" : "false"} onMouseDown={(e) => { if (open) e.preventDefault(); }} onClick={() => { setNote(""); setOpen(!open); }}>As at {shownDate(asAt.value)}</button>
      {open ? <input type="date" class="asat-box" ref={box} aria-label="Date of the report" value={asAt.value} onChange={(e) => { if (/^(199\d|2\d{3})-/.test(e.target.value)) picked(e.target.value); }} onBlur={() => setOpen(false)} /> : null}
      {note ? <span class="asat-note" role="status">{note}</span> : null}
    </span>
  );
}
