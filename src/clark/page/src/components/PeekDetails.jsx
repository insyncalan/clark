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
    <section class="pk-details" data-pk-details data-open={open ? "1" : "0"}>
      <button type="button" class="pk-details-h" aria-expanded={open} aria-controls={id} onClick={() => { write(!open); setOpen(!open); }}>
        <span class="pk-details-t">Details</span>
        {open ? null : <span class="pk-details-sum" data-pk-details-sum>{line}</span>}
        <Icon name="chevdown" cls="s pk-details-car" />
      </button>
      <div id={id} class="pk-details-body" data-pk-details-rows hidden={!open}>{children}</div>
    </section>
  );
}

/** The footer: the key tag and the input that focuses on "/". Props: onAsk() is called when the input is used (the caller opens the words box). */
export function PeekFooter({ onAsk }) {
  return (
    <footer class="pk-foot" data-pk-foot>
      <kbd class="pk-foot-key" aria-hidden="true">/</kbd>
      <button type="button" class="pk-foot-in" data-pk-foot-in data-pk-ask onClick={() => { if (onAsk) onAsk(); }}>Ask clark to update for you</button>
    </footer>
  );
}
