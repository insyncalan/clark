// Settings › Freshness (item 160): "Not reviewed after (days)", the project's own number (projects.review_after_days, item 171). Saved when
// the box is left or on Enter, as one change with Undo and a line in the history. A value that is not a whole number from 1 to 365
// is refused here in plain words, the box goes back to the number in use and nothing is sent. After a save the page reads the
// project again, so the peek's chip, the Freshness filter's words follow at once. Edit parts only.
import { useRef, useState } from "preact/hooks";
import { data } from "../stores/report.js";
import { change } from "../stores/changes.js";
import { REVIEW_DAYS } from "../filters.js";
import { plural } from "../workItems.js";

export const REFUSED = "Choose a whole number of days from 1 to 365. Nothing was changed.";      // changes.py BAD_REVIEW_DAYS, word for word
const LOW = 1, HIGH = 365;

/** The number typed, or null when it is not a whole number from 1 to 365 ("14", " 7 " are numbers; "0", "14.5", "abc", "" are not). */
export function daysOf(text) {
  const t = String(text == null ? "" : text).trim();
  if (!/^[0-9]+$/.test(t)) return null;
  const n = Number(t);
  return n >= LOW && n <= HIGH ? n : null;
}

export function ReviewDays() {
  const p = data.value && data.value.project, now = p && Number.isInteger(p.review_after_days) ? p.review_after_days : REVIEW_DAYS;
  const [typed, setTyped] = useState(null);          // null: the box shows the number in use
  const [said, setSaid] = useState("");
  const busy = useRef(false);                        // Enter then leaving the box is one save, not two
  const shown = typed === null ? String(now) : typed;

  const save = async () => {
    if (typed === null || busy.current) return;
    const n = daysOf(typed);
    if (n === null) { setTyped(null); setSaid(REFUSED); return; }
    setSaid("");
    if (n === now) { setTyped(null); return; }
    busy.current = true;
    await change({ kind: "projects", op: "update", changes: { review_after_days: n }, place: "menu" },
      `Not reviewed after: ${plural(n, "day")}.`);
    busy.current = false;
    setTyped(null);                                  // the box shows what clark kept (a refused change leaves the old number)
  };

  return (
    <section class="frame setting" id="freshness" aria-labelledby="review-days-h">
      <h2 id="review-days-h" tabIndex={-1}>Freshness</h2>
      <p class="muted">When an open item counts as not reviewed in this project. It sets the peek's note and the Freshness filter.</p>
      <div class="fld" data-review-days>
        <label for="review-days">Not reviewed after (days)</label>
        <input id="review-days" type="text" inputMode="numeric" value={shown} aria-describedby="review-days-line" aria-invalid={said ? "true" : undefined}
          onInput={(e) => { setTyped(e.currentTarget.value); }} onBlur={save}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); save(); } else if (e.key === "Escape") { setTyped(null); setSaid(""); } }} />
        <small id="review-days-line">A whole number from 1 to 365. The default is 14. Not in the published report.</small>
        <p class="fld-bad" role="alert" data-review-days-bad>{said}</p>
      </div>
    </section>
  );
}
