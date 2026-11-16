// Work items list (#96), store type "workitems": its view part. Live rows from Work items, chosen by the filter saved in Edit
// (./workItemsList.js has the rules). Full width: a table with the columns chosen for the section. Half width: two-line rows (the
// title, then the chosen columns on one line). Both are drawn and the section's slot shows one (shell.css), so nothing is measured.
// View: text nodes only, never dangerouslySetInnerHTML; only rows that would be published (the served page) or that the file
// carries (a published file). isEmpty: no row to show, or no filter saved yet; the section then stays out of View and the file.
import { useLayoutEffect, useRef } from "preact/hooks";
import { asAt, fromFile, openPeek, openWork } from "../stores/report.js";
import { ownerOf, dueField, showDate, todayIso } from "../workItems.js";
import { listOf, drawRows, drawn, WORDS, filterOf, columnsFor } from "./workItemsList.js";
import { workState } from "./workItemsReview.js";
import { clientPill } from "../logic/sectionRows.js";
import { ItemIcon, toneOf } from "../components/ItemRows.jsx";

export const READY = true;

export function today() {
  return (fromFile.value && asAt.value) || todayIso();
}

// Item 1268 (the approved design): the rows look as the built-in sections' rows do: a letter tile, the title, the owner with an avatar,
// the date, the priority and the ID, one line each. The columns are the ones the list shows (a Type column is the tile), in the page's order.
const GRID = { status: "120px", owner: "160px", due: "112px", priority: "84px", workstream: "130px", milestone: "130px", id: "92px" };
export const shownColumns = (columns) => columnsFor(columns);

function Cell({ row, col, now }) {
  if (col === "owner") { const o = ownerOf(row.owner); return o.initials ? <span class="c-owner wil-c-owner" title={o.text}><span class="av" aria-hidden="true">{o.initials}</span><span class="nm">{o.text}</span></span> : <span class="c-owner wil-c-owner"><span class="nm muted">No owner</span></span>; }
  if (col === "due") { const d = dueField(row); return <span class="c-date num wil-c-due">{d ? showDate(d) : "No date"}</span>; }
  if (col === "priority") return <span class="c-prio wil-c-priority">{row.priority ? <span class="prio">{row.priority}</span> : null}</span>;
  if (col === "status") { const p = clientPill(row, now); return <span class="wil-st wil-c-status"><svg class={`wil-half ic-${p.class}`} viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 3a9 9 0 0 1 0 18z" /></svg>{p.text}</span>; }      // row 1199: a half-circle, coloured as the status pill, before the status word
  if (col === "id") return <span class="c-id num wil-c-id">{row.id}</span>;
  return <span class={`c-x wil-c-${col}`}>{(col === "workstream" ? row.workstream : row.milestone) || "—"}</span>;
}

// The one line of a row that the second line of the half width repeats in words: status, owner, date and ID, never broken.
function Meta({ row, columns, now }) {
  const bits = columns.filter((c) => c !== "priority").map((c) => {
    if (c === "status") return clientPill(row, now).text;
    if (c === "owner") return ownerOf(row.owner).text;
    if (c === "due") { const d = dueField(row); return d ? showDate(d) : "No date"; }
    if (c === "id") return row.id;
    return (c === "workstream" ? row.workstream : row.milestone) || "";
  }).filter(Boolean);
  return <span class="wil-m">{bits.map((b, i) => <span key={i} class="wil-bit">{b}</span>)}</span>;
}

// The rows, at both widths. `open(id)` makes each row open its peek: a click, or Enter on the focused row (the page clark serves and a file
// open it read only for a client; Edit's is the editable one, Peek.jsx decides). `Eye` (Edit only): the Work items page's own Client-visible eye,
// drawn at the end of each row. `off`: the ids the client's eye has taken off, drawn greyed. `headProps`: props for the heading row (Edit's columns menu).
export function Rows({ rows, columns, now, open, Eye, off, headProps }) {
  const act = open ? (row) => ({ tabIndex: 0, role: "button", "aria-label": `Open ${row.id}: ${row.title || ""}`, onClick: (e) => { if (e.target.closest && e.target.closest("button, a, input")) return; open(row.id); },
    onKeyDown: (e) => { if (e.target.closest && e.target.closest("button")) return; if ((e.key === "Enter" || e.key === " ") && !e.defaultPrevented) { e.preventDefault(); open(row.id); } } }) : () => ({});
  const cols = shownColumns(columns);
  const grid = { "--cols": `28px minmax(0, 1fr) ${cols.map((c) => GRID[c]).join(" ")}${Eye ? " 36px" : ""}` };
  const gone = off ? new Set(off) : new Set();
  const tile = (row) => { const pill = clientPill(row, now); return <ItemIcon row={row} pill={pill} today={now} plain />; };
  return (
    <>
      <ul class={`wl irows wil-grid${open ? " wil-live" : ""}`} style={grid}>
        <li class="wl-head" {...(headProps || {})}>
          <span class="c-ico" aria-hidden="true"></span><span class="c-title">Item</span>
          {cols.map((c) => <span key={c} class={`wil-h wil-c-${c}`} data-col={c}>{WORDS.columns[c]}</span>)}
          {Eye ? <span class="wil-c-eye"><span class="sr">{Eye.heading}</span></span> : null}
        </li>
        {rows.map((row) => (
          <li key={row.id} class={`wl-row${open ? " wl-open" : ""}${gone.has(row.id) ? " wil-off" : ""}`} data-id={row.id} data-kind={row.kind} {...act(row)}>
            <span class="c-ico">{tile(row)}</span>
            <span class="wl-title c-title" title={row.title || ""}>{row.title || ""}</span>
            {cols.map((c) => <Cell key={c} row={row} col={c} now={now} />)}
            {Eye ? <span class="wil-c-eye"><Eye row={row} /></span> : null}
          </li>
        ))}
      </ul>
      <ul class={`wil-lines${open ? " wil-live" : ""}`}>
        {rows.map((row) => (
          <li key={row.id} class={gone.has(row.id) ? "wil-off" : ""} data-id={row.id} {...act(row)}>
            <span class="wil-l1">{tile(row)}<span class="wil-t" title={row.title || ""}>{row.title || ""}</span>{row.priority ? <span class="prio">{row.priority}</span> : null}{Eye ? <span class="wil-eye"><Eye row={row} /></span> : null}</span>
            <Meta row={row} columns={cols} now={now} />
          </li>
        ))}
      </ul>
    </>
  );
}

// Item 1268: Most rows is the window the list shows; the list holds every filtered row and scrolls behind it. The window ends on a row's
// edge (measured, so nothing is cut), at full and at half width. The footer says how many are showing and opens Work items on the same filter.
export function Window({ children, max, total }) {
  const box = useRef(null);
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return undefined;
    const fit = () => {
      const rows = [...el.querySelectorAll(":scope > ul:not([hidden]) > li")].filter((r) => r.offsetParent !== null && !r.classList.contains("wl-head"));
      if (total <= max || rows.length <= max) { el.style.maxHeight = ""; return; }
      const top = el.getBoundingClientRect().top - el.scrollTop;
      const next = rows[max].getBoundingClientRect().top - top;
      el.style.maxHeight = `${Math.round(next)}px`;
    };
    fit();
    window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  });
  return <div class="wil-scroll" ref={box} data-wil-scroll="">{children}</div>;
}

export function Foot({ shown, total, onReview }) {
  if (!total) return null;
  return (
    <p class="wil-foot" data-wil-foot="">
      <span class="wil-count">{total > shown ? `Showing ${shown} of ${total}, scroll for the rest` : `Showing ${total} of ${total}`}</span>
      <button type="button" class="wil-review" data-wil-review="" onClick={onReview}>{`Review all ${total} items`}</button>
    </p>
  );
}

export function isEmpty(section, data) {
  return drawRows(listOf(section, data, today()).items, data).length === 0;
}

export function View({ section, data }) {
  const now = today();
  const list = listOf(section, data, now);
  const ids = list.all || list.items;
  const rows = drawRows(ids, drawn(data, !fromFile.value));
  if (!rows.length) return null;
  const review = () => openWork(workState(filterOf(section)));
  return (
    <div class="wil" data-wil="">
      <Window max={list.max || rows.length} total={rows.length}>
        <Rows rows={rows} columns={list.columns} now={now} open={(rid) => openPeek(rid, "item")} />
      </Window>
      <Foot shown={Math.min(list.max || rows.length, rows.length)} total={rows.length} onReview={review} />
      {list.caption ? <p class="wil-cap">{list.caption}</p> : null}
    </div>
  );
}
