// The peek's Latest update and its 'Last updated' stamp, and the warning bar above the title (Edit only: a published file and View
// show the fields and nothing else). Every change is one request with one Undo (changeCell), and the data is read again after it so
// the stamp is the one clark wrote. The text is on the one rich editor (RichField, item 1005). Row 1077 (the owner's ruling): no chip
// writes the text for you; the box alone. Row 1179 (the owner, 14-11) lifts that for ONE control: the quiet "Draft with AI" button beside the heading
// (DraftAi.jsx), and the right-click AI menu on selected text in the box; nothing changes in the text before Accept. An item that is shown to the client carries a 'Shown to the client' label (its latest update is published). Item 1185: an action, a risk, an issue and (row 1195) a decision have a latest update (a milestone has its own box in MilestonePeek.jsx).
import { RichField } from "./RichField.jsx";
import { richOrPlain } from "../logic/richOrPlain.js";
import { data } from "../stores/report.js";
import { changeCell, say, refresh } from "../stores/changes.js";
import { showDate, todayIso } from "../workItems.js";
import { changeFor, tableOf } from "./itemEdit.js";
import { warnFor, stampText } from "./peekLatest.js";
import { Icon } from "../components/Icon.jsx";
import { PeekLatestHistory } from "./PeekLatestHistory.jsx";
import { DraftButton, DraftPanel, useDraftAi } from "./DraftAi.jsx";
import { richWords } from "../logic/richWords.js";
import { placeFor, keyForField } from "../logic/aiPlaces.js";

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

export function PeekLatest({ row }) {
  const rec = raw(row), has = true;
  const now = rec && rec.latest_update ? String(rec.latest_update) : "";
  const stamp = rec ? stampText(rec.updated_at) : "";
  const html = (() => { try { return richOrPlain(now); } catch (e) { return "<p>" + String(now).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") + "</p>"; } })();    // item 1005: the editor's HTML, or the plain text an older clark stored
  // The rich editor saves with Cmd/Ctrl+Enter and leaves with Esc. It closes only when clark has saved it: a refusal (the toast says why)
  // or no answer leaves it open with what was typed.
  const ai = useDraftAi(), place = placeFor(keyForField("latest_update"));      // "current", for all four kinds (the field name decides, not the kind)
  const save = (value) => changeCell(tableOf(row), row.id, { latest_update: value },
    { text: `Latest update of ${row.id} saved.`, back: `Latest update of ${row.id} is back as it was.`, place: "peek" })
    .then((reply) => { if (reply) refresh(); return reply; });
  return (
    <div class="pk-latest" data-pk-latest>
      {has ? <>
        <div class="pk-lab"><span id={`pk-latest-lab-${row.id}`}>Latest update</span>
          <DraftButton ai={ai} />
          {row.client ? <span class="pk-latest-client" data-pk-latest-client><Icon name="eye" cls="s" />Shown to the client</span> : null}</div>
        <DraftPanel ai={ai} place={place} text={richWords(now)} onAccept={(h) => save(h)} />
        <RichField field="latest_update" id={row.id} value={html} label="Latest update" empty="Add the latest update…" save={save} ai={place} viewId={`pk-latest-txt-${row.id}`} labelledBy={`pk-latest-lab-${row.id} pk-latest-txt-${row.id}`} />
      </> : null}
      {stamp ? <div class="pk-last" data-pk-last><Icon name="clock" cls="s" /> Last updated {stamp}</div> : null}
      {has ? <PeekLatestHistory key={`h-${row.id}`} id={row.id} /> : null}
    </div>
  );
}
