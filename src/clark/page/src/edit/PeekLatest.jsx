// The peek's Latest update and its 'Last updated' stamp, and the warning bar above the title (Edit only: a published file and View
// show the fields and nothing else). Every change is one request with one Undo (changeCell), and the data is read again after it so
// the stamp is the one clark wrote. The text is on the one rich editor (RichField, item 1005). Row 1077 (the owner's ruling): no chip
// writes the text for you; the box alone. Row 1179 (the owner, 14-11) lifts that for ONE control: the quiet "Draft with AI" button beside the heading
// (DraftAi.jsx), and the right-click AI menu on selected text in the box; nothing changes in the text before Accept. An item that is shown to the client carries a 'Shown to the client' label (its latest update is published). Item 1185: an action, a risk, an issue and (row 1195) a decision have a latest update (a milestone has its own box in MilestonePeek.jsx).
import { signal } from "@preact/signals";
import { useState, useRef, useEffect } from "preact/hooks";
import { RichField } from "./RichField.jsx";
import { richOrPlain } from "../logic/richOrPlain.js";
import { data, project } from "../stores/report.js";
import { readActivity } from "./activityApi.js";
import { changeCell, say, refresh } from "../stores/changes.js";
import { showDate, todayIso } from "../workItems.js";
import { changeFor, tableOf } from "./itemEdit.js";
import { warnFor, stampText } from "./peekLatest.js";
import { Icon } from "../components/Icon.jsx";
import { classicTheme } from "../components/Contents.jsx";
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

// Row 1180: the box holds an unsaved update while its editor is open and its text differs from the saved one. The peek reads this
// before it closes (PeekUnsavedBar below). Module-wide because only one peek is ever open.
export const latestDirty = signal(false);
const editorOf = () => document.querySelector("#peek [data-pk-latest] [data-rt] .ProseMirror");
// A bar button never takes the focus from the box: leaving the box would save the update before the choice is made.
const hold = (e) => e.preventDefault();
// The save the box last started (null when none): Save and close waits for its answer before it closes.
let lastSave = null;
const fire = (el, init) => { if (el) el.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, cancelable: true, ...init })); };

/** The bar a close with an unsaved update shows: Save and close, Discard, Keep editing. Props: onClose() closes the peek; onDone() hides the bar. */
export function PeekUnsavedBar({ onClose, onDone }) {
  const first = useRef(null);
  const root = useRef(null);
  // The toolbar stays at the top while the body scrolls: a bar that opens behind it cannot be pressed, so the body scrolls until the bar is clear of it.
  useEffect(() => {
    const el = root.current, tb = document.querySelector("#peek .pk-tb");
    if (!el || !tb) return;
    const over = tb.getBoundingClientRect().bottom - el.getBoundingClientRect().top;
    if (over <= 0) return;
    let s = el.parentElement;
    while (s && s.scrollHeight <= s.clientHeight) s = s.parentElement;
    if (s) s.scrollTop -= over + 4;
  }, [latestDirty.value]);
  // The bar is an alert (read out as it appears). The focus stays in the box: moving it out would leave the box, and leaving the box saves the update. A mouse press on the bar keeps the focus in the editor for the same reason.
  if (!latestDirty.value) return null;
  const done = () => { if (onDone) onDone(); };
  return (
    <div class="pk-unsaved" role="alert" data-pk-unsaved ref={root} onMouseDown={(e) => e.preventDefault()}>
      <p class="pk-unsaved-t">You have an unsaved update.</p>
      <div class="pk-unsaved-b">
        <button type="button" ref={first} data-pk-save-close data-pk-unsaved-save onMouseDown={hold} onClick={() => { lastSave = null; fire(editorOf(), { key: "Enter", ctrlKey: true }); const p = lastSave; if (!p) { latestDirty.value = false; done(); if (onClose) onClose(); return; } p.then((reply) => { if (reply) { latestDirty.value = false; done(); if (onClose) onClose(); } else if (!editorOf()) { /* a refusal that left no editor: nothing to keep */ done(); } else { done(); editorOf().focus(); } }); }}>Save and close</button>
        <button type="button" data-pk-discard data-pk-unsaved-discard onMouseDown={hold} onClick={() => { fire(editorOf(), { key: "Escape" }); latestDirty.value = false; done(); if (onClose) onClose(); }}>Discard</button>
        <button type="button" data-pk-keep data-pk-unsaved-keep onMouseDown={hold} onClick={() => { done(); const e = editorOf(); if (e) e.focus(); }}>Keep editing</button>
      </div>
    </div>
  );
}

const plain = (h) => String(h || "").replace(/<[^>]*>/g, "").replace(/\s+/g, " ").trim();
let savedHtml = "";
/** Read when the peek is asked to close (Close, Esc): is the open editor's text different from the saved one? Also sets the flag the bar shows on, so a change made without a DOM input event counts too. */
export function isLatestDirty() {
  const e = editorOf();
  latestDirty.value = !!e && plain(e.innerHTML) !== plain(savedHtml);
  return latestDirty.value;
}

export function PeekLatest({ row }) {
  const rec = raw(row);
  const save = (value) => changeCell(tableOf(row), row.id, { latest_update: value },
    { text: `Latest update of ${row.id} saved.`, back: `Latest update of ${row.id} is back as it was.`, place: "peek" })
    .then((reply) => { if (reply) refresh(); return reply; });
  return <LatestBox id={row.id} now={rec && rec.latest_update ? String(rec.latest_update) : ""} stamp={rec ? stampText(rec.updated_at) : ""} shown={!!row.client} save={save} />;
}

// Row 1470: who wrote the update, the item's Source and the Created entry, read from the item's history (the one read the peek's tabs use).
// Nothing is invented: a name or a Source that clark did not record is left out, the date and time are always drawn.
const isUpdateRow = (r) => r.field === "Latest update" && r.kind !== "Created" && r.kind !== "Comment";
export function stampParts(view) {
  const rows = view && Array.isArray(view.rows) ? view.rows : [];
  const up = rows.find(isUpdateRow), made = rows.slice().reverse().find((r) => r.kind === "Created");
  const createdBy = made && made.who ? String(made.who).trim() : "";
  let source = view && typeof view.source === "string" ? view.source.trim() : "";
  if (createdBy && source.endsWith(" by " + createdBy)) source = source.slice(0, -(createdBy.length + 4)).trim();       // the Source line is "<words> by <who made it>": the stamp has the words alone
  return { who: up ? String(up.who || "").trim() : "",       // no update row: clark never recorded who wrote the text, so the creator is not credited as the updater (ruling 23-11 10:25)
     source, made: made ? { who: createdBy, when: String(made.when_text || "").split(" - ")[0] } : null };
}
/** "Last updated 18-11-2026 16:40 by Name · Source: words": the name and the Source only when known. */
export function stampLine(stamp, who, source) {
  return `Last updated ${stamp}${who ? ` by ${who}` : ""}${source ? ` · Source: ${source}` : ""}`;
}
/** The Created entry an item never updated shows in its Latest box: "Created by Name, 10-11-2026 09:12 · Source: words" (parts left out when unknown). */
export function createdLine(made, source) {
  if (!made) return "";
  return <><b data-pk-created>Created</b>{`${made.who ? ` by ${made.who}` : ""}${made.when ? `${made.who ? "," : ""} ${made.when}` : ""}${source ? ` · Source: ${source}` : ""}`}</>;      // the word Created is bold (NEW-WORDS 21-11 items 16-17)
}

/** The box itself, for any kind (row 1184: a milestone's too). `save(value)` sends one change and resolves to its answer (falsy: refused or none). */
export function LatestBox({ id, now, stamp, shown, save: send, placeholder = "What changed? Add the latest update…" }) {
  const [open, setOpen] = useState(false);
  const [view, setView] = useState(undefined);                       // undefined until the history is read (Classic draws its stamp then, so the name and Source do not pop in); null when it could not be read
  const d = data.value;                                                // a change anywhere replaces the data, so the stamp reads again
  useEffect(() => {
    let live = true;
    readActivity(project.value, id).then((r) => { if (live) setView(r.ok ? r.view : null); });
    return () => { live = false; };
  }, [id, d]);                                                        // eslint-disable-line react-hooks/exhaustive-deps
  const classic = classicTheme();                                     // row 1470 is Classic only: Cards keeps its lowercase stamp and its plain empty box
  const parts = stampParts(view);
  const never = classic && !String(now || "").trim();
  const created = never ? createdLine(parts.made, parts.source) : "";
  const html = (() => { try { return richOrPlain(now); } catch (e) { return "<p>" + String(now).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") + "</p>"; } })();    // item 1005: the editor's HTML, or the plain text an older clark stored
  // The rich editor saves with Cmd/Ctrl+Enter and leaves with Esc. It closes only when clark has saved it: a refusal (the toast says why)
  // or no answer leaves it open with what was typed.
  savedHtml = html;
  const ai = useDraftAi(), place = placeFor(keyForField("latest_update"));      // "current", for all four kinds (the field name decides, not the kind)
  const save = (value) => (lastSave = send(value));
  return (
    <div class="pk-latest" data-pk-latest
      onFocusIn={(e) => { if (e.target.closest("[data-rt]")) setOpen(true); }}
      onFocusOut={() => setTimeout(() => { if (!document.querySelector("[data-pk-latest] [data-rt]")) { setOpen(false); latestDirty.value = false; } }, 0)}
      onInput={() => { const e = editorOf(); latestDirty.value = !!e && plain(e.innerHTML) !== plain(html); }}>
      <div class="pk-lab"><span id={`pk-latest-lab-${id}`}>Latest update</span>
        <DraftButton ai={ai} />
        {shown ? <span class="pk-latest-client" data-pk-latest-client><Icon name="eye" cls="s" />Shown to the client</span> : null}</div>
      <DraftPanel ai={ai} place={place} text={richWords(now)} onAccept={(h) => save(h)} />
      <div class="pk-lbox" data-pk-lbox>
        <RichField field="latest_update" id={id} value={html} label="Latest update" empty={created || placeholder} save={save} ai={place} viewId={`pk-latest-txt-${id}`} labelledBy={`pk-latest-lab-${id} pk-latest-txt-${id}`} />
        <div class="pk-lfoot" data-pk-latest-hint data-pk-hint><span><kbd class="pk-key">⌘ Enter</kbd> to save</span></div>
      </div>
      {stamp && !never && (view !== undefined || !classic) ? <div class="pk-last" data-pk-last>{classic ? stampLine(stamp, parts.who, parts.source) : `last updated ${stamp}`}</div> : null}
      <PeekLatestHistory key={`h-${id}`} id={id} />
    </div>
  );
}
