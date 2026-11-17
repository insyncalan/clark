// Row 1180: the peek's collapsible Details line and its footer. Self-contained; Peek.jsx places them. Details closed shows one summary
// line; open shows the rows (the caller passes them as children, label left and value right, each with its coloured icon).
// The open state is remembered for the next peek in this browser, with a fallback when storage is blocked.
import { useState } from "preact/hooks";
import { Icon } from "./Icon.jsx";

const KEY = "clark.peek.details";
const read = () => { try { return localStorage.getItem(KEY) !== "closed"; } catch (e) { return true; } };
const write = (open) => { try { localStorage.setItem(KEY, open ? "open" : "closed"); } catch (e) { /* storage blocked: the state lasts this peek only */ } };

/** Props: summary (array of strings, empty ones are dropped), children (the rows), id (for aria). */
export function PeekDetails({ summary = [], children, id = "pk-details" }) {
  const [open, setOpen] = useState(read);
  const line = summary.filter(Boolean).join(" · ");
  return (
    <section class="pk-details" data-open={open ? "1" : "0"}>
      <button type="button" class="pk-details-h" data-pk-details aria-expanded={open ? "true" : "false"} aria-controls={id} onClick={() => { write(!open); setOpen(!open); }}>
        <Icon name="chevdown" cls="s pk-details-car" />
        <span class="pk-details-t" data-pk-details-t>Details</span>
        {open ? null : <span class="pk-details-sum" data-pk-details-sum>{line}</span>}
      </button>
      {open ? <div id={id} class="pk-details-body" data-pk-details-rows>{children}</div> : null}
    </section>
  );
}
