// The peek's Latest update with its Draft button and its 'Last updated' stamp, and the warning bar above the title (Edit only: a
// published file and View show the fields and nothing else). Every change is one request with one Undo (changeCell), and the data is
// read again after it so the stamp is the one clark wrote. Draft writes the text from the item's own fields (peekLatest.js draftFor),
// with no AI. The text is on the one rich editor (RichField, item 1005). An action that is shown to the client carries a 'Shown to the client' label (its latest update is published). An action has a latest update; a risk, issue or decision has the stamp only.
import { useState } from "preact/hooks";
import { RichField } from "./RichField.jsx";
import { richOrPlain } from "../logic/richOrPlain.js";
import { richWords } from "../logic/richWords.js";
import { data } from "../stores/report.js";
import { changeCell, say, refresh } from "../stores/changes.js";
import { showDate, todayIso } from "../workItems.js";
import { changeFor, tableOf } from "./itemEdit.js";
import { warnFor, draftFor, cleanLatest, stampText } from "./peekLatest.js";
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
  const flip = () => changeCell(tableOf(row), row.id, { client_action: on ? 0 : 1 },
    { text: "Needed from the client", back: "Needed from the client", place: "peek" }).then(() => refresh());
  return (
    <label class="sw pk-act" data-pk-needed>
      <button type="button" class="switch" role="switch" aria-checked={on ? "true" : "false"} aria-label="Needed from the client" onClick={flip}></button>
      <span>Needed from the client<small>Lists it under “Needs from you”</small></span>
    </label>
  );
}

export function PeekLatest({ row }) {
  const rec = raw(row), action = row.kind === "action";
  const [reopen, setReopen] = useState(false);                       // item 549: Draft pressed with the box open puts the new box open, with the caret in it
  const [rev, setRev] = useState(0);                                   // a new key after Draft, so an open editor is left and drawn from what clark stored
  const now = rec && rec.latest_update ? String(rec.latest_update) : "";
  const stamp = rec ? stampText(rec.updated_at) : "";
  const html = (() => { try { return richOrPlain(now); } catch (e) { return "<p>" + String(now).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") + "</p>"; } })();    // item 1005: the editor's HTML, or the plain text an older clark stored
  // The rich editor saves with Cmd/Ctrl+Enter and leaves with Esc. It closes only when clark has saved it: a refusal (the toast says why)
  // or no answer leaves it open with what was typed.
  const save = (value) => changeCell("actions", row.id, { latest_update: value },
    { text: `Latest update of ${row.id} saved.`, back: `Latest update of ${row.id} is back as it was.`, place: "peek" })
    .then((reply) => { if (reply) refresh(); return reply; });
  const draft = () => {
    const a = raw(row), ms = a && a.milestone && ((data.value && data.value.milestones) || []).find((m) => m.id === a.milestone);
    const words = draftFor({ due: row.due_date, status: row.status, owner: row.owner, milestone: ms ? { name: ms.name, agreed: ms.baseline_date } : null }, todayIso());
    if (words === cleanLatest(richWords(now))) { say("note", "The latest update already says that."); return; }
    const focused = document.activeElement;
    const inBox = !!(focused && focused.closest && focused.closest(".ProseMirror"));    // read before the wait: the caret is where it was when Draft was pressed
    // The editor is left only once clark has stored the draft and the page has read it again, so the new box is drawn from the drafted
    // words (never the old text, which the next blur would save over the draft). A refused Draft leaves the box and what was typed as they are.
    changeCell("actions", row.id, { latest_update: words }, { text: "Latest update drafted from the item's own fields.", back: `Latest update of ${row.id} is back as it was.`, place: "draft" })
      .then(async (reply) => { if (!reply) return; await refresh(); setReopen(inBox); setRev((n) => n + 1); });
  };
  return (
    <div class="pk-latest" data-pk-latest>
      {action ? <>
        <div class="pk-lab"><span id={`pk-latest-lab-${row.id}`}>Latest update</span> <button type="button" class="pk-draft" data-pk-draft onMouseDown={(e) => e.preventDefault()} onClick={draft}><Icon name="sparkle" cls="s" />Draft</button>
          {row.client ? <span class="pk-latest-client" data-pk-latest-client><Icon name="eye" cls="s" />Shown to the client</span> : null}</div>
        <RichField key={rev} forceOpen={reopen} field="latest_update" id={row.id} value={html} label="Latest update" empty="Add the latest update…" save={save} viewId={`pk-latest-txt-${row.id}`} labelledBy={`pk-latest-lab-${row.id} pk-latest-txt-${row.id}`} />
      </> : null}
      {action ? <PeekLatestHistory key={`h-${row.id}`} id={row.id} /> : null}
      {stamp ? <div class="pk-last" data-pk-last><Icon name="clock" cls="s" /> Last updated {stamp}</div> : null}
    </div>
  );
}
