// Show archived on Work items (B-5, item 126, item 450 rows 38 and 39; Edit parts only, so a published file has none: it carries no archived
// row and never reads the choice). As in the prototype (views.js, the Work items bar): a "Show archived N" pill in the bar, beside View,
// that remembers the choice for each project in this browser (localStorage, wrapped: it can throw or be blocked, and the page then
// keeps the choice for the visit only). On, a muted table under the list of the archived actions, risks, issues and decisions, each
// marked Archived. A row opens in the side peek (row 39; prototype views.js:1006-10, peek.js:409-30): the peek's own fields, read only
// (nothing to type into, no words box, no tabs), a note that says why, and one Restore, which puts the item back in one step with
// Undo and leaves the peek open on it, now editable.
// The list is read from GET /api/data?archived=only when the page opens the project and again whenever the project's data is
// read again (after a restore or an undo), so the count is always the database's. ArchivedItems, under the list, does the read;
// ArchivedPill, in the bar, shows its count. The rows stay in this file's own state, never in the page's data, so an archived row
// cannot reach the Plan, the published file, the export or Ask; the archived peek is drawn from that state too.
import { signal } from "@preact/signals";
import { useEffect, useLayoutEffect, useRef } from "preact/hooks";
import { project, data, peek, openPeek, closePeek } from "../stores/report.js";
import { width, wide } from "../stores/peekState.js";
import { getArchived } from "../api.js";
import { restoreItem } from "../stores/changes.js";
import { rowsFor } from "../logic/board.js";
import { KIND_WORDS, dueCell, ownerOf, metaOf, todayIso } from "../workItems.js";
import { ItemFields, Edge } from "../components/Peek.jsx";
import { slideOut } from "../peek/exit.js";
import { Icon } from "../components/Icon.jsx";

const KEY = (code) => `clark.workArchived.${code}`;
const kept = signal({});                   // project code -> on, once read or set in this visit
const read = signal({ code: "", rows: null }); // the archived rows of one project; rows null until read, [] when there is none
const openId = signal("");                 // the archived item open in the peek, or "" (memory only: no address, no Back entry)

export const NOTE = "Archived, so it is read-only. It is out of the lists, the counts and the published page; nothing in it was deleted.";
export const FOOT = "Restore it to make a change";

function storedOn(code) {
  try { return window.localStorage.getItem(KEY(code)) === "on"; } catch (e) { return false; }
}
export function archivedOn(code) {
  const k = kept.value;
  return Object.prototype.hasOwnProperty.call(k, code) ? k[code] : storedOn(code);
}
function setOn(code, on) {
  kept.value = { ...kept.value, [code]: on };
  try { if (on) window.localStorage.setItem(KEY(code), "on"); else window.localStorage.removeItem(KEY(code)); } catch (e) { /* kept for the visit only */ }
  if (!on) openId.value = "";
}
const rowsOf = (code) => (read.value.code === code ? read.value.rows : null);

// One archived item in the peek: an open live peek closes first (only one peek at a time).
function openArchived(id) {
  if (peek.value) closePeek();
  openId.value = id;
}

export function ArchivedPill() {
  const code = project.value, rows = rowsOf(code);
  if (!code || rows === null) return null;
  const on = archivedOn(code);
  return (
    <button type="button" class="arch-pill" id="showArchived" aria-pressed={on ? "true" : "false"} aria-controls="archived" onClick={() => setOn(code, !on)}>
      Show archived <em class="num" key={rows.length}>{rows.length}</em>
    </button>
  );
}

// Up and Down step through the archived rows; Enter or Space opens one in the peek.
function rowKeys(e, id) {
  const tr = e.currentTarget;
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openArchived(id); return; }
  if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
  const to = e.key === "ArrowDown" ? tr.nextElementSibling : tr.previousElementSibling;
  if (to) { e.preventDefault(); to.focus(); }
}

export function ArchivedItems({ pill }) {
  const code = project.value, d = data.value;
  useEffect(() => {
    let live = true;
    getArchived(code).then((r) => { if (live) read.value = { code, rows: r.ok ? rowsFor(r.data) : [] }; });
    return () => { live = false; };
  }, [code, d]);
  useEffect(() => () => { openId.value = ""; }, [code]);   // another project, or leaving the page: no archived peek left open
  const rows = rowsOf(code);
  if (rows === null) return null;
  const n = rows.length, today = todayIso(), on = archivedOn(code), at = openId.value;
  const row = at ? rows.find((r) => r.id === at) : null;
  return (
    <div class="archived" id="archived" data-edit-only>
      {pill ? <div class="wbar"><ArchivedPill /></div> : null}   {/* no live items, so no bar: the pill stands on its own */}
      {on ? (
        <div id="archived-list" class="arch-box" tabIndex={-1} role="region" aria-label="Archived work items">
          <h2 class="arch-h">Archived <span class="muted">{`${n} item${n === 1 ? "" : "s"}`}</span></h2>
          {n === 0 ? <p class="muted">No archived work items.</p> : (
            <table class="items arch">
              <thead><tr><th class="c-type">Type</th><th class="c-item">Item</th><th class="c-owner">Owner</th><th class="c-due">Due</th><th class="c-status">Status</th></tr></thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={r.id} data-arch-id={r.id} class={`arch-row${r.id === at ? " sel" : ""}`} tabIndex={i === 0 ? 0 : -1} aria-label={`Open ${r.id}, archived, read only`}
                    onClick={() => { if (!String(window.getSelection()).length) openArchived(r.id); }} onKeyDown={(e) => rowKeys(e, r.id)}>
                    <td class="c-type"><span class={`type k-${r.kind}`}>{KIND_WORDS[r.kind] || r.kind}</span></td>
                    <td class="c-item"><span class="t">{r.title}</span><span class="meta">{metaOf(r)}<span class="tag arch">Archived</span></span></td>
                    <td class="c-owner">{ownerOf(r.owner).text}</td>
                    <td class="c-due"><span class="num">{dueCell(r, today).date}</span></td>
                    <td class="c-status">{r.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ) : null}
      {on && row ? <ArchivedPeek row={row} /> : null}
    </div>
  );
}

// The archived item in the side peek: the live peek's frame, edge and fields (components/Peek.jsx), read only, with one Restore.
// Esc and Close shut it and put the focus back on its row; Restore leaves the peek open on the item, now in the lists and editable.
function ArchivedPeek({ row }) {
  const box = useRef(null), back = useRef(null);
  const blocked = !!peek.value;                         // a live peek still closing (its Back is on its way): this one waits
  const shut = (focus = true) => {
    slideOut(box.current);
    const id = openId.value;
    openId.value = "";
    if (!focus) return;
    // Its row; if that row has gone, the opener; then the list's first row, the Show archived pill, the list itself. Never the body.
    setTimeout(() => {
      const opener = back.current && back.current.isConnected && back.current !== document.body ? back.current : null;
      const to = [document.querySelector(`#archived-list tr[data-arch-id="${CSS.escape(id)}"]`), opener,
        document.querySelector("#archived-list tr.arch-row"), document.querySelector("#showArchived"), document.querySelector("#archived-list")];
      for (const el of to) {
        if (!el || !el.focus) continue;
        el.focus();
        if (document.activeElement === el) return;
      }
    }, 0);
  };
  useEffect(() => {                                     // focus goes in on opening and on every other row
    if (blocked) return;
    if (!back.current) back.current = document.activeElement;
    const t = setTimeout(() => { const c = box.current && box.current.querySelector("[data-pk-close]"); if (c) c.focus(); }, 0);
    return () => clearTimeout(t);
  }, [row.id, blocked]);                                // eslint-disable-line react-hooks/exhaustive-deps
  const was = useRef(blocked);
  // A live peek opened over it (a row of the list): this one is gone. In the same step, not after the next frame: on a slow machine
  // that frame came after a click on another archived row, and this then shut the peek that click had just opened.
  useLayoutEffect(() => {
    if (peek.value && !was.current) openId.value = "";
    was.current = !!peek.value;
  }, [!!peek.value]);                                   // eslint-disable-line react-hooks/exhaustive-deps
  // Esc: inside the peek it is the peek's (the list around it never sees it); elsewhere, as the live peek, unless a menu has it.
  const esc = (e) => {
    if (e.key !== "Escape" || e.isComposing || document.querySelector("[role=menu]")) return false;
    e.preventDefault();
    shut();
    return true;
  };
  useEffect(() => {
    const onKey = (e) => { if (!e.defaultPrevented) esc(e); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [row.id]);                                         // eslint-disable-line react-hooks/exhaustive-deps
  if (blocked) return null;
  const restore = () => restoreItem(row.table, row.id).then((reply) => {
    if (!reply) return;
    openId.value = "";
    openPeek(row.id, "item");                           // back in the lists: the same item, in the live peek, editable
  });
  return (
    <aside class={`peek pk-arch${wide.value ? " wide" : ""}`} id="peek-archived" ref={box} aria-label={`${row.id} details, archived`} data-peek-archived={row.id}
      onKeyDown={(e) => { if (esc(e)) e.stopPropagation(); }} style={wide.value ? "" : `width:${Math.min(width.value, document.documentElement.clientWidth)}px`}>
      <Edge />
      <div class="pk-bar">
        <span class="pk-id num">{row.id}</span>
        <span class="tag arch">Archived</span>
        <span class="pk-sp" />
        <button type="button" class="pkp-btn" data-pk-wide aria-pressed={wide.value} title={wide.value ? "Return the panel to its usual width" : "Make this panel fill the screen"} aria-label={wide.value ? "Return the panel to its usual width" : "Make this panel fill the screen"} onClick={() => { wide.value = !wide.value; }}><Icon name="expand" /></button>
        <button type="button" class="pkp-btn" data-pk-close title="Close this panel" aria-label="Close this panel" onClick={() => shut()}><Icon name="x" /></button>
      </div>
      <div class="pk-archnote"><p>{NOTE}</p><button type="button" class="btn pri" id="pk-restore" aria-label={`Restore ${row.id}`} onClick={restore}>Restore</button></div>
      <h2 class="pk-title">{row.title}</h2>
      <div class="pk-body pk-ro" data-pk-body>
        <ItemFields row={row} editing />
      </div>
      <p class="pk-arch-foot muted">{FOOT}</p>
    </aside>
  );
}
