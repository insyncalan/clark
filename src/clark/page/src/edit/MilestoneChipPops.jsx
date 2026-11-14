// Row 1184: the popovers of the milestone peek's four chips (State, Owner, Progress, Forecast date). `milestoneChipPops(m)` gives the
// { state, owner, progress, forecast } map MilestoneChips takes. Each pick is one changeMilestone with one Undo and the data read again;
// the sentences are the ones the old header line used ("State of ABC-M-001 changed to ...").
import { data, project, reread } from "../stores/report.js";
import { changeMilestone, say } from "../stores/changes.js";
import { Pop, roam } from "./cells/Pop.jsx";
import { OwnerPick } from "./cells/OwnerPick.jsx";
import { DuePick } from "./cells/DuePick.jsx";
import { Icon } from "../components/Icon.jsx";
import { iconClass } from "../iconColours.js";
import { STATE_ICON, percentOf } from "../components/PeekMilestoneChips.jsx";
import { PICKABLE, shownState, stateChange, textChange } from "./msPeek.js";
import { quickDates, people } from "./itemEdit.js";
import { showDate, todayIso } from "../workItems.js";

async function save(m, changes, words) {
  const res = await changeMilestone({ id: m.id, changes, place: "peek" }, words);
  if (!res.ok) { say("problem", res.message); return false; }
  await reread(project.value);
  return true;
}

function StatePop({ m, anchor, close }) {
  const today = todayIso(), now = shownState(m, today);
  const list = now === "Overdue" ? [...PICKABLE.slice(0, 4), "Overdue", "Achieved"] : PICKABLE;       // Overdue is listed only while it is the shown state: worked out, never picked
  const pick = (s) => {
    close(true);
    const c = stateChange(m, s, today);
    save(m, c, `State of ${m.id} changed to ${c.state || shownState({ ...m, ...c }, today)}.`);
  };
  let box = null;
  const items = () => Array.from(box ? box.querySelectorAll("[role=menuitemradio]:not([disabled])") : []);
  return (
    <Pop anchor={anchor} label={`State of ${m.id}`} role="menu" cls="cmenu pk-mspop" onClose={close}>
      <div ref={(el) => { box = el; if (el && !el.dataset.focused) { el.dataset.focused = "1"; const on = el.querySelector("[aria-checked=true]:not([disabled])") || el.querySelector("[role=menuitemradio]:not([disabled])"); if (on) on.focus({ preventScroll: true }); } }} onKeyDown={(e) => roam(e, items())}>
        {list.map((s) => {
          const [icon, tone] = STATE_ICON[s], off = !PICKABLE.includes(s);
          return (
            <button type="button" role="menuitemradio" class="menu-item" key={s} data-value={s} aria-checked={now === s ? "true" : "false"} disabled={off} aria-disabled={off ? "true" : undefined}
              onClick={() => pick(s)}><span class={`mi-i ${iconClass(tone)}`}><Icon name={icon} /></span><span class="mi-t">{s}</span></button>
          );
        })}
      </div>
    </Pop>
  );
}

function ProgressPop({ m, anchor, close }) {
  const now = percentOf(m);
  const pick = (n) => {
    close(true);
    if (n === now) return;
    save(m, { percent_complete: n }, `Progress of ${m.id} changed to ${n}%.`);
  };
  let box = null;
  const items = () => Array.from(box ? box.querySelectorAll("[data-block]") : []);
  return (
    <Pop anchor={anchor} label={`Progress of ${m.id}`} cls="pk-mspop pk-blocks-pop" onClose={close}>
      <div class="pk-blocks" role="group" aria-label={`Progress of ${m.id}`}
        ref={(el) => { box = el; if (el && !el.dataset.focused) { el.dataset.focused = "1"; const b = el.querySelector("[aria-pressed=true]") || el.querySelector("[data-block]"); if (b) b.focus({ preventScroll: true }); } }}
        onKeyDown={(e) => roam(e, items())}>
        {Array.from({ length: 10 }, (_, i) => (i + 1) * 10).map((n) => (
          <button type="button" key={n} class={`pk-block${now != null && n <= now ? " on" : ""}`} data-block={n} style={`--fill:${n}`} aria-pressed={now === n ? "true" : "false"}
            aria-label={`${n}%`} title={`${n}%`} onClick={() => pick(n)}><span>{n}</span></button>
        ))}
      </div>
    </Pop>
  );
}

/** The four popovers for a milestone `m`, each `({ anchor, close }) => element`. */
export function milestoneChipPops(m) {
  return {
    state: ({ anchor, close }) => <StatePop m={m} anchor={anchor} close={close} />,
    progress: ({ anchor, close }) => <ProgressPop m={m} anchor={anchor} close={close} />,
    owner: ({ anchor, close }) => {
      const pick = (v) => {
        const c = textChange("owner", m.owner, v);
        close(true);
        if (c) save(m, c, c.owner == null ? `Owner of ${m.id} cleared.` : `Owner of ${m.id} changed to ${c.owner}.`);
        return "";
      };
      return <OwnerPick row={{ id: m.id, kind: "milestone", owner: m.owner }} anchor={anchor} names={people(data.value)} onPick={pick} onClose={close} />;
    },
    forecast: ({ anchor, close }) => {
      const today = todayIso(), value = m.forecast_date || "";
      const pick = (day) => {
        close(true);
        const iso = day || null;
        if (iso === (value || null)) return;
        save(m, { forecast_date: iso }, iso ? `Forecast date of ${m.id} changed to ${showDate(iso)}.` : `Forecast date of ${m.id} cleared.`);
      };
      const quick = quickDates(today).concat(value ? [["No date", ""]] : []);
      return <DuePick row={{ id: m.id, kind: "action", due_date: value || null }} anchor={anchor} today={today} label={`Forecast date of ${m.id}`} quick={quick} onPick={pick} onClose={close} />;
    },
  };
}
