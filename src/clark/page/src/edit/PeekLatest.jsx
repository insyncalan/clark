// The peek's Latest update and its 'Last updated' stamp, and the warning bar above the title (Edit only: a published file and View
// show the fields and nothing else). Every change is one request with one Undo (changeCell), and the data is read again after it so
// the stamp is the one clark wrote. The text is on the one rich editor (RichField, item 1005). Item 1179 (row 1077 ruling 1 is lifted for this one
// button): 'Draft with AI' sits beside the heading and opens the AI menu; the same menu opens on a right-click of selected text. The suggestion
// shows in a card under the field and goes into the text only through the editor, on Accept. An item shown to the client carries a 'Shown to the
// client' label. An action, risk, issue and milestone have a latest update; a decision has the stamp only (hasField).
import { signal } from "@preact/signals";
import { useState } from "preact/hooks";
import { RichField } from "./RichField.jsx";
import { richOrPlain } from "../logic/richOrPlain.js";
import { data, token } from "../stores/report.js";
import { changeCell, say, refresh } from "../stores/changes.js";
import { showDate, todayIso } from "../workItems.js";
import { changeFor, tableOf } from "./itemEdit.js";
import { warnFor, stampText } from "./peekLatest.js";
import { Icon } from "../components/Icon.jsx";
import { AiCard } from "./AiCard.jsx";
import { realAiClient } from "./aiClient.js";
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

// Row 1180: the box holds an unsaved update while its editor is open and its text differs from the saved one. The peek reads this
// before it closes (PeekUnsavedBar below). Module-wide because only one peek is ever open.
export const latestDirty = signal(false);
const editorOf = () => document.querySelector("#peek [data-pk-latest] [data-rt] .ProseMirror, [data-pk-latest] [data-rt] [contenteditable=true]");
const fire = (el, init) => { if (el) el.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, cancelable: true, ...init })); };

/** The bar a close with an unsaved update shows: Save and close, Discard, Keep editing. Props: onClose() closes the peek; onDone() hides the bar. */
export function PeekUnsavedBar({ onClose, onDone }) {
  if (!latestDirty.value) return null;
  const done = () => { if (onDone) onDone(); };
  return (
    <div class="pk-unsaved" role="alert" data-pk-unsaved>
      <p class="pk-unsaved-t">You have an unsaved update.</p>
      <div class="pk-unsaved-b">
        <button type="button" data-pk-save-close data-pk-unsaved-save onClick={() => { fire(editorOf(), { key: "Enter", ctrlKey: true }); setTimeout(() => { latestDirty.value = false; done(); if (onClose) onClose(); }, 0); }}>Save and close</button>
        <button type="button" data-pk-discard data-pk-unsaved-discard onClick={() => { fire(editorOf(), { key: "Escape" }); latestDirty.value = false; done(); if (onClose) onClose(); }}>Discard</button>
        <button type="button" data-pk-keep data-pk-unsaved-keep onClick={() => { done(); const e = editorOf(); if (e) e.focus(); }}>Keep editing</button>
      </div>
    </div>
  );
}

const aiClient = realAiClient({ token });
const plain = (h) => String(h || "").replace(/<[^>]*>/g, "").replace(/\s+/g, " ").trim();

export function PeekLatest({ row }) {
  const [open, setOpen] = useState(false);
  const [menuAt, setMenuAt] = useState(null), [card, setCard] = useState(null), [wantOpen, setWantOpen] = useState(false);
  const rec = raw(row), hasHistory = row.kind === "action", hasField = row.kind !== "decision";
  const now = rec && rec.latest_update ? String(rec.latest_update) : "";
  const stamp = rec ? stampText(rec.updated_at) : "";
  const html = (() => { try { return richOrPlain(now); } catch (e) { return "<p>" + String(now).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") + "</p>"; } })();    // item 1005: the editor's HTML, or the plain text an older clark stored
  // The rich editor saves with Cmd/Ctrl+Enter and leaves with Esc. It closes only when clark has saved it: a refusal (the toast says why)
  // or no answer leaves it open with what was typed.
  const save = (value) => changeCell(tableOf(row), row.id, { latest_update: value },
    { text: `Latest update of ${row.id} saved.`, back: `Latest update of ${row.id} is back as it was.`, place: "peek" })
    .then((reply) => { if (reply) refresh(); return reply; });
  return (
    <div class="pk-latest" data-pk-latest
      onFocusIn={(e) => { if (e.target.closest("[data-rt]")) setOpen(true); }}
      onFocusOut={() => setTimeout(() => { if (!document.querySelector("[data-pk-latest] [data-rt]")) { setOpen(false); latestDirty.value = false; } }, 0)}
      onInput={() => { const e = editorOf(); latestDirty.value = !!e && plain(e.innerHTML) !== plain(html); }}>
      {hasField ? <>
      <div class="pk-lab"><span id={`pk-latest-lab-${row.id}`}>Latest update</span>
        <button type="button" class="pk-ai" data-pk-ai aria-label="Draft with AI" aria-haspopup="menu" aria-expanded={menuAt ? "true" : "false"}
          onMouseDown={(e) => e.preventDefault()}
          onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); setCard(null); setMenuAt({ x: r.left, y: r.bottom + 4 }); if (!editorOf()) setWantOpen(true); }}><Icon name="sparkle" cls="s" />Draft with AI</button>
        {row.client ? <span class="pk-latest-client" data-pk-latest-client><Icon name="eye" cls="s" />Shown to the client</span> : null}</div>
      <RichField field="latest_update" id={row.id} value={html} label="Latest update" empty="Add the latest update…" save={save} viewId={`pk-latest-txt-${row.id}`} labelledBy={`pk-latest-lab-${row.id} pk-latest-txt-${row.id}`}
        forceOpen={wantOpen} onClose={() => { setWantOpen(false); setMenuAt(null); }}
        ai={{ menu: menuAt, open: (pt) => { setCard(null); setMenuAt(pt); }, close: () => setMenuAt(null), pick: (req) => { setMenuAt(null); setCard({ ...req, n: Date.now() }); } }} />
      {card ? <div data-ai-card><AiCard key={card.n} client={aiClient} place="current" option={card.option} text={card.text} instruction={card.instruction}
        returnTo={() => { const e = editorOf(); if (e) e.focus(); }} onAccept={card.apply} onClose={() => setCard(null)} /></div> : null}
      </> : null}
      {stamp ? <div class="pk-last" data-pk-last><Icon name="clock" cls="s" /> Last updated {stamp}</div> : null}
      {open ? <p class="pk-latest-hint" data-pk-latest-hint data-pk-hint>Cmd or Ctrl and Enter saves.</p> : null}
      {hasHistory ? <PeekLatestHistory key={`h-${row.id}`} id={row.id} /> : null}
    </div>
  );
}
