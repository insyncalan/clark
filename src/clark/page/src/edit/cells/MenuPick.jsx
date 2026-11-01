// #80: a short list of values to choose one from (the Status and Priority pickers). A menu of radio items: focus goes to the
// value the item has now; Down and Up wrap, Home and End jump, Enter or Space picks, Esc leaves it as it was. A choice may carry
// a `note`, shown in small print under its word, and the list may be cut into labelled groups (see groups below).
import { useLayoutEffect, useRef } from "preact/hooks";
import { Pop, roam } from "./Pop.jsx";

export function MenuPick({ anchor, label, choices, current, onPick, onClose }) {
  const list = useRef(null);
  const uid = useRef(`mp${++made}`).current;
  const items = () => Array.from(list.current ? list.current.querySelectorAll("[role=menuitemradio]") : []);
  useLayoutEffect(() => {
    const all = items();
    const now = all.find((el) => el.getAttribute("aria-checked") === "true") || all[0];
    if (now) now.focus({ preventScroll: true });
  }, []);                                                 // eslint-disable-line react-hooks/exhaustive-deps
  const item = (c) => (
    <button type="button" role="menuitemradio" class="menu-item" key={c.value} data-value={c.value}
      aria-checked={(Array.isArray(current) ? current.includes(c.value) : c.value === current) ? "true" : "false"} onClick={() => onPick(c.value)}>
      <span class="mi-t">{c.text}</span>{c.note ? <small class="mi-note">{c.note}</small> : null}</button>
  );
  return (
    <Pop anchor={anchor} label={label} role="menu" cls="cmenu" onClose={onClose}>
      <div ref={list} onKeyDown={(e) => roam(e, items())}>
        {choices.length && choices[0].heading ? groups(choices).map((g, i) => (
          <div role="group" aria-labelledby={`${uid}-${i}`} key={g.heading}>
            <div class={g.hidden ? "sr-only" : "menu-head"} id={`${uid}-${i}`} role="presentation">{g.heading}</div>
            {g.items.map(item)}
          </div>
        )) : choices.map(item)}
      </div>
    </Pop>
  );
}

// D-12: a list that starts with a `{heading}` is cut into labelled groups at each heading (a screen reader hears the group's
// name; one radio in each group is ticked); arrow keys still move across all of them. `hidden` keeps a heading for a screen
// reader only.
function groups(choices) {
  const out = [];
  for (const c of choices) if (c.heading) out.push({ heading: c.heading, hidden: !!c.hidden, items: [] }); else out[out.length - 1].items.push(c);
  return out;
}
let made = 0;
