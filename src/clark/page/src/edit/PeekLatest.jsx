// The peek's Latest update and its 'Last updated' stamp, and the warning bar above the title (Edit only: a published file and View
// show the fields and nothing else). Every change is one request with one Undo (changeCell), and the data is read again after it so
// the stamp is the one clark wrote. The text is on the one rich editor (RichField, item 1005). Row 1077 (the owner's ruling): no chip
// writes the text for you; the box alone. An action that is shown to the client carries a 'Shown to the client' label (its latest update is published). An action has a latest update; a risk, issue or decision has the stamp only.
import { RichField } from "./RichField.jsx";
import { richOrPlain } from "../logic/richOrPlain.js";
import { data } from "../stores/report.js";
import { changeCell, say, refresh } from "../stores/changes.js";
import { showDate, todayIso } from "../workItems.js";
import { changeFor, tableOf } from "./itemEdit.js";
import { warnFor, stampText } from "./peekLatest.js";
import { Icon } from "../components/Icon.jsx";
import { PeekLatestHistory } from "./PeekLatestHistory.jsx";

const raw = (row) => ((data.value && data.value[tableOf(row)]) || []).find((r) => r.id === row.id) || null;
const toClose = () => { const el = document.activeElement; if (!el || el === document.body || !el.isConnected) { const c = document.querySelector("#peek [data-pk-close]"); if (c) c.focus(); } };

// A date moved from the bar: one change, one Undo, the toast says where it went.
function move(row, date) {
  const c = changeFor(row, "due", date, todayIso());
  if (!c || c.error) { say("problem", c ? c.error : "That is already the date."); return; }
  changeCell(tableOf(row), row.id, c.changes, { text: `${row.id} moved to ${showDate(date)}.`, back: c.back, place: "peek" }).then(() => refresh()).then(toClose);
}

export function PeekWarn({ row }) {
  const w = warnFor(row, todayIso());
  if (!w) return null;
  return (
    <div class="pk-warnbar" data-pk-warn={w.kind}>
      <p class="pk-warn"><Icon name="flash" cls="s" />{w.text}</p>
      <div class="pk-fix">{w.moves.map((m) => <button key={m.date} type="button" data-pk-move={m.date} onClick={() => move(row, m.date)}>{m.label}</button>)}</div>
    </div>
  );
}

// Row 811: the switch that lists an action, risk or issue under "Needs from you" (a decision has no such flag).
// One change with one Undo; the switch shows what clark stored, so a refusal leaves it as it was.
export function PeekNeeded({ row }) {
  const rec = raw(row), on = !!(rec && rec.client_action);
  const was = "Marked as needed from the client", now = "No longer marked as needed from the client";
  const flip = () => changeCell(tableOf(row), row.id, { client_action: on ? 0 : 1 },
    { text: on ? now : was, back: on ? was : now, place: "peek" }).then(() => refresh());
  return (
    <label class="sw pk-act" data-pk-needed>
      <button type="button" class="switch" role="switch" aria-checked={on ? "true" : "false"} aria-label="Needed from the client" onClick={flip}></button>
      <span>Needed from the client<small>Lists it under “Needs from you” when the report has that section</small></span>
    </label>
  );
}

export function PeekLatest({ row }) {
  const rec = raw(row), action = row.kind === "action";
  const now = rec && rec.latest_update ? String(rec.latest_update) : "";
  const stamp = rec ? stampText(rec.updated_at) : "";
  const html = (() => { try { return richOrPlain(now); } catch (e) { return "<p>" + String(now).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") + "</p>"; } })();    // item 1005: the editor's HTML, or the plain text an older clark stored
  // The rich editor saves with Cmd/Ctrl+Enter and leaves with Esc. It closes only when clark has saved it: a refusal (the toast says why)
  // or no answer leaves it open with what was typed.
  const save = (value) => changeCell("actions", row.id, { latest_update: value },
    { text: `Latest update of ${row.id} saved.`, back: `Latest update of ${row.id} is back as it was.`, place: "peek" })
    .then((reply) => { if (reply) refresh(); return reply; });
  return (
    <div class="pk-latest" data-pk-latest>
      {action ? <>
        <div class="pk-lab"><span id={`pk-latest-lab-${row.id}`}>Latest update</span>
          {row.client ? <span class="pk-latest-client" data-pk-latest-client><Icon name="eye" cls="s" />Shown to the client</span> : null}</div>
        <RichField field="latest_update" id={row.id} value={html} label="Latest update" empty="Add the latest update…" save={save} viewId={`pk-latest-txt-${row.id}`} labelledBy={`pk-latest-lab-${row.id} pk-latest-txt-${row.id}`} />
      </> : null}
      {stamp ? <div class="pk-last" data-pk-last><Icon name="clock" cls="s" /> Last updated {stamp}</div> : null}
      {action ? <PeekLatestHistory key={`h-${row.id}`} id={row.id} /> : null}
    </div>
  );
}
