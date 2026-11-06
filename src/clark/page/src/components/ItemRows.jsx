// The rows under Risks and issues, Open actions and Decisions (prototype parity A-D5): a status pill, the item, a quiet line of who
// and when (and the priority on a risk or issue), the ID on the right. The same rows in View, in Edit (edit/ItemRowsEdit.jsx draws
// them with every part editable) and in a published file; they are drawn from the rows the page already holds, so a published file
// needs nothing else. What a client reads is the client's own wording, or the item's own title when it has none; the rows
// listed are the ones marked for the client (the eye). An empty section keeps its heading and says so in a line in View (prototype views.js: "Nothing to show."); a
// published file leaves an empty section out, heading and all (Dashboard.jsx fileDraws), so a client never reads that line.
import { data, rows as allRows, fromFile, asAt, openPeek } from "../stores/report.js";
import { dueCell, ownerOf, showDate, todayIso, dueField } from "../workItems.js";
import { sectionRows, listed, dateWord, clientPill, keptIds } from "../logic/sectionRows.js";

export const NOTHING = "Nothing to show.";

// The words a row is drawn with, by ID: the client's own wording, or, when an item shown to the client has none, the item's title: its
// description (the decision text for a decision), which is its visible name in the published lists. Internal fields (the latest update,
// notes) are never used. Row 851: the eye is the control, so a marked item is listed; a missing wording never takes it off the list.
export function wordings(d) {
  const out = {};
  for (const [k, own] of [["actions", "description"], ["raid", "description"], ["decisions", "decision"]]) {
    for (const r of d[k] || []) { const t = String(r.client_message || "").trim() || String(r[own] || "").trim(); if (t) out[r.id] = t; }
  }
  return out;
}

export const todayOf = () => (fromFile.value && asAt.value ? asAt.value : todayIso());

// Every row the section could list, marked for the client or not, taken off the page or not (Edit counts them: "Showing N of M").
export function candidates(type) {
  if (!data.value) return [];
  const words = wordings(data.value), today = todayOf();
  return allRows.value.filter((r) => listed(type, r, today) && words[r.id]);
}

// The rows a section lists, less the ones with no client wording (a decision's wording is its client_message too), and, on the
// page clark serves, less the ones the report would not publish (taken off with the eye, or kept out by a label).
export function rowsFor(type) {
  if (!data.value) return [];
  const words = wordings(data.value), kept = fromFile.value ? null : keptIds(data.value);
  return sectionRows(type, allRows.value, todayOf(), fromFile.value).filter((r) => words[r.id] && (!kept || kept.has(r.id)));
}

// Open the row's item in the peek; a click on a button or a field inside the row does its own job, and so does selecting text.
const ownClick = (e) => !e.target.closest("button, a, input") && !String(window.getSelection()).length;

function Row({ row, today, words, inFile }) {
  const pill = clientPill(row, today), due = dueCell(row, today), who = ownerOf(row.owner), date = dueField(row);
  const title = words[row.id];
  const risk = row.kind === "risk" || row.kind === "issue";
  const open = inFile ? undefined : (e) => { if (ownClick(e)) openPeek(row.id, "item"); };
  return (
    <li class={`wl-row${inFile ? "" : " wl-open"}`} data-id={row.id} data-kind={row.kind} onClick={open}>
      <span class="wl-state"><span class={`pill ${pill.class}`}>{pill.text}</span></span>
      <span class="wl-main">
        <span class="wl-title">{risk ? <span class="tag">{row.kind === "issue" ? "Issue" : "Risk"}</span> : null}{risk ? " " : ""}{title}</span>
        <span class="wl-meta">
          {who.initials ? <span class="av" aria-hidden="true">{who.initials}</span> : null}
          <span class={who.initials ? "" : "muted"}>{who.initials ? who.text : "No owner"}</span>
          <span class="dot" aria-hidden="true">{"·"}</span>
          <span class="num">{date ? `${dateWord(row)} ${showDate(date)}` : "No date"}</span>
          {row.kind === "action" && due.words && !inFile ? <span class={due.tone ? "late" : ""}>{due.words}</span> : null}
          {risk && row.priority ? <><span class="dot" aria-hidden="true">{"·"}</span><span class="prio">{row.priority}</span></> : null}
        </span>
      </span>
      {inFile ? null : <span class="wl-id num"><button type="button" class="idl" aria-label={`Open ${row.id}`} onClick={() => openPeek(row.id, "item")}>{row.id}</button></span>}
    </li>
  );
}

export function ItemRows({ type }) {
  const list = rowsFor(type), today = todayOf(), words = wordings(data.value || {});
  if (!list.length) return <p class="quiet" data-nothing>{NOTHING}</p>;
  return <ul class="wl">{list.map((r) => <Row key={r.id} row={r} today={today} words={words} inFile={fromFile.value} />)}</ul>;
}
