// The Legend (#44a): a small word at the right; its card opens on hover and on keyboard focus (plain CSS) and lists the six states,
// Expected and Today. Escape shuts the card and puts focus back on the Legend button; the card opens again on the next hover, or
// the next focus after focus has left the Legend. A published file says the client's words (Expected later, Late, Forecast).
import { useRef, useState } from "preact/hooks";
import { MsMark } from "./MsMark.jsx";
import { legend } from "../logic/milestones.js";

export function MsLegend({ client, id }) {
  const items = legend(client);
  const [shut, setShut] = useState(false);
  const button = useRef(null);
  const onKey = (e) => {
    if (e.key !== "Escape" || shut) return;
    e.preventDefault();
    setShut(true);
    if (button.current) button.current.focus();
  };
  const row = (it) => (
    <li key={it.state} data-legend={it.state}>
      <span class="mlg-m">{it.mark === "ghost" ? <i class="mlg-ghost" /> : it.mark === "today-line" ? <i class="mlg-today" /> : <MsMark name={it.mark} />}</span>
      <span><b>{it.word}</b> <span>{it.means}</span></span>
    </li>
  );
  return (
    <div class={`mlg${shut ? " mlg-shut" : ""}`} onKeyDown={onKey} onMouseLeave={() => setShut(false)}
      onFocusOut={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setShut(false); }}>
      <button ref={button} type="button" class="mlg-b" aria-describedby={`mlg-${id}`}>Legend</button>
      <div class="mlg-p" role="tooltip" id={`mlg-${id}`}>
        <ul>{items.slice(0, 6).map(row)}</ul>
        <ul class="mlg-sym">{items.slice(6).map(row)}</ul>
      </div>
    </div>
  );
}
