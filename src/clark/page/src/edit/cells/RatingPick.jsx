// Item 210 (option C): the Priority picker of a risk or an issue. Its priority is worked out by clark from its impact and likelihood,
// so the picker offers those two, each High, Medium or Low, as two labelled groups of one menu with a tick in each. A pick
// changes one of them (one step, with Undo in the toast) and the cell then shows the priority clark worked out. Keys as MenuPick:
// focus starts on the ticked impact; Down and Up wrap across both groups, Home and End jump, Enter or Space picks, Esc leaves it.
import { useLayoutEffect, useRef } from "preact/hooks";
import { Pop, roam } from "./Pop.jsx";
import { ratingGroups } from "../itemEdit.js";
import { Icon } from "../../components/Icon.jsx";
import { iconClass } from "../../iconColours.js";
import { priorityIcon } from "../../menuIcons.js";

let made = 0;

export function RatingPick({ row, anchor, onPick, onClose }) {
  const list = useRef(null);
  const uid = useRef(`rp${++made}`).current;
  const items = () => Array.from(list.current ? list.current.querySelectorAll("[role=menuitemradio]") : []);
  useLayoutEffect(() => {
    const all = items();
    const now = all.find((el) => el.getAttribute("aria-checked") === "true") || all[0];
    if (now) now.focus({ preventScroll: true });
  }, []);                                                 // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <Pop anchor={anchor} label={`Priority of ${row.id}: set from impact and likelihood`} role="menu" cls="cmenu rpick" onClose={onClose}>
      <div ref={list} onKeyDown={(e) => roam(e, items())}>
        {ratingGroups(row).map((g, i) => (
          <div role="group" aria-labelledby={`${uid}-${i}`} key={g.field} data-group={g.field}>
            <div class="rp-head" id={`${uid}-${i}`} role="presentation">{g.heading}</div>
            {g.choices.map((c) => (
              <button type="button" role="menuitemradio" class="menu-item" key={c.value} data-value={c.value}
                aria-checked={c.text === g.current ? "true" : "false"} onClick={() => onPick(c.value)}>
                <span class={`mi-i ${iconClass(priorityIcon(c.text).tone)}`}><Icon name={priorityIcon(c.text).icon} /></span><span class="mi-t">{c.text}</span></button>
            ))}
          </div>
        ))}
      </div>
    </Pop>
  );
}
