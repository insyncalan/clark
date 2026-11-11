// Archived work on Work items (item 1067, after item 126 and item 450 rows 38 and 39; Edit parts only, so a published file has none: it carries
// no archived row and never reads this). There is no pill: the filter word is:archived in the filter line is the way in. While the line
// asks for it, the archived actions, risks, issues and decisions of the project (the other words of the line still narrow them) are drawn
// in place of the live list, muted, each marked Archived. A row opens in the side peek (prototype views.js:1006-10, peek.js:409-30): the
// peek's own fields, read only (nothing to type into, no words box, no tabs), a note that says why, and one Restore, which puts the
// item back in one step with Undo and leaves the peek open on it, now editable.
// The list is read from GET /api/data?archived=only when the list is drawn and again whenever the project's data is read again (after
// a restore or an undo), so it is always the database's. The rows stay in this file's own state, never in the page's data, so an
// archived row cannot reach the Plan, the published file, the export, the counts or Ask; the archived peek is drawn from that state too.
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

const read = signal({ code: "", rows: null }); // the archived rows of one project; rows null until read, [] when there is none
const openId = signal("");                 // the archived item open in the peek, or "" (memory only: no address, no Back entry)

export const NOTE = "Archived, so it is read-only. It is out of the lists, the counts and the published page; nothing in it was deleted.";
export const FOOT = "Restore it to make a change";

const rowsOf = (code) => (read.value.code === code ? read.value.rows : null);

// One archived item in the peek: an open live peek closes first (only one peek at a time).
function openArchived(id) {
  if (peek.value) closePeek();
  openId.value = id;
}

// Up and Down step through the archived rows; Enter or Space opens one in the peek.
function rowKeys(e, id) {
  const tr = e.currentTarget;
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openArchived(id); return; }
  if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
  const to = e.key === "ArrowDown" ? tr.nextElementSibling : tr.previousElementSibling;
  if (to) { e.preventDefault(); to.focus(); }
}

// `rowsShown(rows)` narrows the archived rows by the rest of the filter line; it is the page's own, handed in by Work items.
export function ArchivedItems({ narrow }) {
  const code = project.value, d = data.value;
  useEffect(() => {
    let live = true;
    getArchived(code).then((r) => { if (live) read.value = { code, rows: r.ok ? rowsFor(r.data) : [] }; });
    return () => { live = false; };
  }, [code, d]);
  useEffect(() => () => { openId.value = ""; }, [code]);   // another project, or leaving the page: no archived peek left open
  const all = rowsOf(code);
  if (all === null) return null;
  const rows = narrow ? narrow(all.map((r) => ({ ...r, archived: 1 }))) : all;   // marked, so that is:archived itself matches them
  const n = rows.length, today = todayIso(), at = openId.value;
  const row = at ? rows.find((r) => r.id === at) : null;
  return (
    <div class="archived" id="archived" data-edit-only>
      {(
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
      )}
      {row ? <ArchivedPeek row={row} /> : null}
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
    // Its row; if that row has gone, the opener; then the list's first row, the filter line, the list itself. Never the body.
    setTimeout(() => {
      const opener = back.current && back.current.isConnected && back.current !== document.body ? back.current : null;
      const to = [document.querySelector(`#archived-list tr[data-arch-id="${CSS.escape(id)}"]`), opener,
        document.querySelector("#archived-list tr.arch-row"), document.querySelector("#fline-input"), document.querySelector("#archived-list")];
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
  useLayoutEffect(() => {                               // (in the step that draws the live peek, not a frame later) a live peek opened over it (a row of the list): this one is gone
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
