// An archived milestone, read only, in the peek's own place and shape (system/prototype/peek.js archHtml, #166): its facts, a plain
// line saying why nothing here can be changed, and Restore. Restore is Edit only (ruled B-30: View changes nothing and its changes
// have no Undo to offer), so in View the line says where to go. One step, one Undo (stores/changes.js restoreMilestone); on success
// the peek closes and focus goes to the Show archived button. Esc and Close close it, and focus goes back to the name that opened it.
import { useEffect, useRef } from "preact/hooks";
import { data, project, mode, peek } from "../stores/report.js";
import { width, wide } from "../stores/peekState.js";
import { restoreMilestone } from "../stores/changes.js";
import { stateOf, showDate, todayIso } from "../logic/milestones.js";
import { Icon } from "../components/Icon.jsx";
import { archivedOpen, linkedCount } from "./archivedState.js";

const DASH = "—";
const say = (v) => (v === null || v === undefined || v === "" ? DASH : String(v));

export function close() {
  const open = archivedOpen.peek();
  archivedOpen.value = null;
  if (open && open.opener) setTimeout(() => { const el = open.opener; if (el && el.isConnected && el.focus) el.focus(); }, 0);
}

export function ArchivedPeek() {
  const open = archivedOpen.value, box = useRef(null);
  const here = !!open && open.code === project.value;
  // The page's own peek and this one never stand together: when the page's opens, this one shuts (a peek that was already open when this
  // one was asked for is closed by the Archived box, and may take a moment to go); a project change shuts this one too.
  const was = useRef(!!peek.value);
  useEffect(() => { if (open && !here) archivedOpen.value = null; }, [open, here]);
  useEffect(() => { if (peek.value && !was.current && archivedOpen.peek()) archivedOpen.value = null; was.current = !!peek.value; }, [peek.value]);
  useEffect(() => {
    if (!open || !here) return undefined;
    const b = box.current && box.current.querySelector("[data-pk-close]");
    if (b) b.focus();
    const onKey = (e) => {
      if (e.key !== "Escape" || e.defaultPrevented || e.isComposing || document.querySelector("[role=menu]")) return;
      e.preventDefault();
      close();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open && open.row.id, here]);                          // eslint-disable-line react-hooks/exhaustive-deps
  if (!open || !here || !data.value) return null;
  const r = open.row, editing = mode.value === "edit", linked = linkedCount(data.value, r.id);
  const facts = [
    ["State", stateOf(r, todayIso())], ["Agreed", r.baseline_date ? showDate(r.baseline_date) : "No agreed date"],
    ["Forecast", r.forecast_date || r.baseline_date ? showDate(r.forecast_date || r.baseline_date) : "No date"], ["Progress", r.percent_complete === null || r.percent_complete === undefined ? "Not set" : `${r.percent_complete}%`],
    ["Owner", r.owner || "Not set"], ["Workstream", r.workstream], ["Linked work items", String(linked)],
  ];
  const restore = () => restoreMilestone(r.id, r.name).then((reply) => {
    if (!reply) return reply;
    archivedOpen.value = null;
    setTimeout(() => { const b = document.getElementById("ms-archived-pill"); if (b) b.focus(); }, 0);
    return reply;
  });
  return (
    <aside class={`peek pk-ro${wide.value ? " wide" : ""}`} id="archived-peek" ref={box} aria-label={`${r.name}, archived`} data-archived-peek={r.id}
      style={wide.value ? "" : `width:${Math.min(width.value, document.documentElement.clientWidth)}px`}>
      <div class="pk-bar">
        <span class="pk-id num">{r.id}</span>
        <span class="tag">Archived</span>
        <span class="pk-sp" />
        <button type="button" class="pkp-btn" data-pk-close title="Close this panel" aria-label="Close this panel" onClick={close}><Icon name="x" /></button>
      </div>
      <h2 class="pk-title">{r.name}</h2>
      <div class="pk-archnote">
        <p>Archived, so it is read only. It is out of the lists, the counts and the published page; nothing in it was deleted.</p>
        {editing ? <button type="button" class="btn pri" data-pk-restore data-edit-only aria-label={`Restore ${r.name}`} onClick={restore}>Restore</button>
          : <p class="muted" data-pk-note>To put it back, switch to Edit.</p>}
      </div>
      <dl class="pk-fields">
        {facts.map(([k, v]) => <div class="pk-row" key={k}><dt>{k}</dt><dd>{say(v)}</dd></div>)}
      </dl>
    </aside>
  );
}
