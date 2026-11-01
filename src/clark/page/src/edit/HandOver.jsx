// #199: Hand over. On Work items in Edit, with the Owner filter on, the Hand over button starts pick mode: a tick box on each open item
// (a click on a row, or Space on it, ticks it; nothing else happens on a row), All, None, a count "N of M selected", a "Hand over to"
// box, Hand over and Cancel. The box suggests the people list when it has anyone on it (clark then takes only a person on it), else
// the names already on the project; a name that is none of those is pointed out under the box. Hand over sends one request to clark
// through the bulk change's path (changeBulk, op "handover"): one step, one Undo, every item checked there first, those that can't
// take it left out and named in the toast. Above 25 a question comes first. While pick mode is on the row keys of selecting several
// and of changing one (Shift+arrows, Ctrl or Cmd+A, O S P T C, the right-click menu) are off: Bulk.jsx and WorkItems.jsx ask
// handing() first. When pick mode ends the keyboard goes back to the Hand over button. Nothing here deletes or archives. The rules
// are in ../logic/handOver.js.
import { useLayoutEffect, useRef } from "preact/hooks";
import { effect } from "@preact/signals";
import { data, filterState, mode, fromFile, view, project } from "../stores/report.js";
import { changeBulk } from "../stores/changes.js";
import { workSelection } from "../stores/selection.js";
import { handOver, handing, ticks, peopleList, focusBack } from "../stores/handover.js";
import { itemRows, announce } from "../stores/work.js";
import { readPeople } from "../api.js";
import { people } from "./itemEdit.js";
import { ask } from "./Bulk.jsx";
import * as H from "../logic/handOver.js";

const OVERLAY = ".bask-back, .cpop, .ddmenu, .dpick, .fbox, [role='dialog']:not([data-peek]), [role='alertdialog'], dialog[open]";
const editing = () => mode.value === "edit" && !fromFile.value;

/** Turn pick mode on: nothing ticked, the usual selection cleared, the people list read again. */
export function start() {
  if (!editing() || handing()) return;
  workSelection.clear();
  ticks.clear();
  handOver.value = { to: "" };
  announce.value = "Hand over: tick the items to give to someone else.";
  readPeople().then((list) => { peopleList.value = list; });
}

/** Turn pick mode off and drop the ticks. `back`: put the keyboard back on the Hand over button once it is drawn again. */
export function stop(back = true) {
  if (!handing()) return;
  focusBack.value = !!back;
  handOver.value = null;
  ticks.clear();
}

/** Send the hand over of what is ticked. Asks first above 25. Pick mode ends when something changed; when nothing could, it stays
 *  so the person can untick or choose someone else. */
export function handOverNow() {
  const st = handOver.value;
  if (!st) return Promise.resolve(null);
  const ids = ticks.ids.value.slice(), to = st.to, rows = itemRows.value;
  if (H.why(ids.length, to)) return Promise.resolve(null);
  const go = (confirm) => changeBulk(H.requestFor(rows, ids, to, { confirm }), H.backWords).then((r) => {
    if (r && !r.ok && r.code === "confirm") { ask(H.confirmWords(r.count || ids.length, to), () => go(true)); return null; }
    if (r && r.ok && r.reply.changed.length) stop(true);
    return r && r.ok ? r.reply : null;
  });
  if (H.needsConfirm(ids.length)) { ask(H.confirmWords(ids.length, to), () => go(true)); return Promise.resolve(null); }
  return go(false);
}

/** The Hand over button, beside Add: in Edit, with the Owner filter on, while pick mode is off. */
export function HandOverButton() {
  const btn = useRef(null);
  const shown = editing() && !handing() && H.ownerFilterOn(filterState.value);
  useLayoutEffect(() => {
    if (shown && focusBack.value && btn.current) { focusBack.value = false; btn.current.focus({ preventScroll: true }); }
  });
  if (!shown) return null;
  return <button type="button" class="btn" id="hand-over" ref={btn} onClick={start}>Hand over</button>;
}

/** The bar above the list while pick mode is on. `rows` are the rows the filters show. */
export function HandOverBar({ rows }) {
  const st = handOver.value, input = useRef(null);
  const open = H.offered(rows), ids = open.map((r) => r.id);
  const listed = peopleList.value.some((p) => !p.archived), names = H.names(peopleList.value, people(data.value));
  const n = ticks.size.value, to = st ? st.to : "", why = H.why(n, to), hint = why ? "" : H.hint(to, names, listed);
  useLayoutEffect(() => { if (input.current) input.current.focus({ preventScroll: true }); }, []);
  useLayoutEffect(() => { ticks.sync(ids, ids); });                       // an item the filters no longer show leaves the ticks
  if (!st) return null;
  const go = () => { if (!why) handOverNow(); };
  const said = [why ? "hand-why" : "", hint ? "hand-hint" : ""].filter(Boolean).join(" ");
  return (
    <>
      <div class="selbar handbar" role="region" aria-label="Hand over" id="hand-bar">
        <span class="sb-n num" id="hand-count">{H.countWords(n, ids.length)}</span>
        <button type="button" class="link" id="hand-all" onClick={() => ticks.selectAll(ids)}>All</button>
        {n > 0 ? <button type="button" class="link" id="hand-none" onClick={() => ticks.clear()}>None</button> : null}
        <label class="hb-to">Hand over to
          <input type="text" id="hand-to" ref={input} value={to} list="hand-people" autocomplete="off" maxlength={200} aria-describedby={said || undefined}
            onInput={(e) => { handOver.value = { ...handOver.value, to: e.currentTarget.value }; }}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); go(); } }} />
        </label>
        <datalist id="hand-people">{names.map((x) => <option key={x} value={x} />)}</datalist>
        <button type="button" class="btn pri" id="hand-go" aria-disabled={why ? "true" : undefined} onClick={go}>Hand over</button>
        <button type="button" class="btn" id="hand-cancel" onClick={() => stop()}>Cancel</button>
      </div>
      {why ? <p class="muted sb-why" id="hand-why">{why}</p> : null}
      {hint ? <p class="muted sb-why" id="hand-hint">{hint}</p> : null}
      {ticks.note.value ? <p class="muted sel-note" id="hand-note">{ticks.note.value}</p> : null}
      <p class="sr" role="status" aria-live="polite" id="hand-live">{ticks.live.value}</p>
    </>
  );
}

let installed = false;
/** Once, from Work items: Esc cancels pick mode, and a change of tab or project, or leaving Edit, ends it. */
export function installHandOver() {
  if (installed || typeof document === "undefined") return;
  installed = true;
  let where = `${view.value}\u0001${project.value}`;
  effect(() => {
    const now = `${view.value}\u0001${project.value}`;
    if (now !== where) { where = now; stop(false); }
  });
  effect(() => { if (!editing()) stop(false); });                         // back to View: nothing is being handed over
  window.addEventListener("keydown", (e) => {
    if (e.key !== "Escape" || e.defaultPrevented || !handing() || view.value !== "work") return;
    if (document.querySelector(OVERLAY)) return;                           // the question or a picker takes Esc first
    e.preventDefault();
    stop();
  });
}

export const HAND_OVER = { Button: HandOverButton, Bar: HandOverBar, install: installHandOver };
