// #80: a short list of values to choose one from (the Status and Priority pickers). A menu of radio items: focus goes to the
// value the item has now; Down and Up wrap, Home and End jump, Enter or Space picks, Esc leaves it as it was. A choice may carry
// a `note`, shown in small print under its word.
import { useLayoutEffect, useRef } from "preact/hooks";
import { Pop, roam } from "./Pop.jsx";

export function MenuPick({ anchor, label, choices, current, onPick, onClose }) {
  const list = useRef(null);
  const items = () => Array.from(list.current ? list.current.querySelectorAll("[role=menuitemradio]") : []);
  useLayoutEffect(() => {
    const all = items();
    const now = all.find((el) => el.getAttribute("aria-checked") === "true") || all[0];
    if (now) now.focus({ preventScroll: true });
  }, []);                                                 // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <Pop anchor={anchor} label={label} role="menu" cls="cmenu" onClose={onClose}>
      <div ref={list} onKeyDown={(e) => roam(e, items())}>
        {choices.map((c) => (
          <button type="button" role="menuitemradio" class="menu-item" key={c.value} data-value={c.value}
            aria-checked={c.value === current ? "true" : "false"} onClick={() => onPick(c.value)}>
            <span class="mi-t">{c.text}</span>{c.note ? <small class="mi-note">{c.note}</small> : null}</button>
        ))}
      </div>
    </Pop>
  );
}
