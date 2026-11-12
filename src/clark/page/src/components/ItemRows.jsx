// The rows under Risks and issues, Open actions and Decisions (prototype parity A-D5; row 1021): ONE line per item, a tinted letter icon
// (kind and status), the title, the owner, the date, the priority or "N d late", the ID on the right. The same rows in View, in Edit (edit/ItemRowsEdit.jsx draws
// them with every part editable) and in a published file; they are drawn from the rows the page already holds, so a published file
// needs nothing else. What a client reads is the client's own wording, or the item's own title when it has none; the rows
// listed are the ones marked for the client (the eye). An empty section keeps its heading and says so in a line in View (prototype views.js: "Nothing to show."); a
// published file leaves an empty section out, heading and all (Dashboard.jsx fileDraws), so a client never reads that line.
import { data, rows as allRows, fromFile, asAt, openPeek } from "../stores/report.js";
import { ownerOf, showDate, todayIso, dueField, isOpen, dayNumber, KIND_WORDS, kindLetter } from "../workItems.js";
import { sectionRows, listed, dateWord, clientPill, lateWord, keptIds } from "../logic/sectionRows.js";

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

// Row 1099: the page clark serves (View) reads each row's own description (a decision's text) on its one line; the client's wording is
// what a published file carries, and what Edit changes. An item with no description reads as its client wording.
export function viewWords(d) {
  const out = wordings(d);
  for (const [k, own] of [["actions", "description"], ["raid", "description"], ["decisions", "decision"]]) {
    for (const r of d[k] || []) { const t = String(r[own] || "").trim(); if (t && out[r.id]) out[r.id] = t; }
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

// Row 1021: one line per item, [icon] Title | Owner | Review by or Due | Priority or 'N d late' | Id, the same columns in every card.
// The icon is a small tinted square: its letter is the kind (R, I, A, D), its colour the status (r red, a amber, g green; b blue and n
// grey for a decision's or a closed item's). In the app its words are a tooltip (hover and keyboard focus) and its accessible name;
// in a published file they are also drawn as a small word beside it, because paper, a PDF and a Word copy have no hover.
// The tile's colour (final 1021 colours): Red Overdue/Red, Amber Due soon/Amber, Green On track/Open/Pending, Blue Completed/Made/Closed, grey
// Cancelled/Withdrawn/Not rated, and and an extra "u" class (a solid maroon tile that wins over the colour) on an open Urgent item, overdue or not.
export const isUrgent = (row) => row.priority === "Urgent" && isOpen(row);
export const toneOf = (row, pill) => {
  if (row.kind === "decision") return row.status === "Made" ? "b" : row.status === "Withdrawn" ? "n" : "g";
  if (row.status === "Closed") return "b";
  return pill.class === "b" ? "g" : pill.class;
};
const isLate = (row, today) => { const a = dayNumber(dueField(row)), b = dayNumber(today); return isOpen(row) && a !== null && b !== null && a < b; };
export const iconWords = (row, pill, today) => {
  const kind = KIND_WORDS[row.kind] || "Item", late = isLate(row, today) && pill.text !== "Overdue" ? "Overdue" : "";
  const parts = isUrgent(row) ? [pill.text, "Urgent", late] : [pill.text];      // an Urgent item that is also late keeps its maroon tile; the tooltip says both
  const words = parts.filter(Boolean);
  return { name: `${kind}, ${words.join(", ")}`, tip: `${kind} · ${words.join(" · ")}` };
};
export const dateHead = (type) => (type === "raid" ? "Review by" : type === "actions" ? "Due" : "Date");

export function ItemIcon({ row, pill, plain, today }) {
  const w = iconWords(row, pill, today ?? todayOf()), tone = `${toneOf(row, pill)}${isUrgent(row) ? " u" : ""}`;
  return plain
    ? <span class={`ico ${tone}`} aria-hidden="true">{kindLetter(row.kind)}</span>
    : <span class={`ico ${tone}`} role="img" tabindex="0" aria-label={w.name} data-tip={w.tip}>{kindLetter(row.kind)}</span>;
}

// The header row, once per card. A file has no Id column (a client is not given the item number).
export function Head({ type, id }) {
  return (
    <li class="wl-head" aria-hidden="true">
      <span class="c-ico">Status</span><span class="c-title">Title</span><span class="c-owner">Owner</span>
      <span class="c-date">{dateHead(type)}</span><span class="c-prio">Priority</span>{id ? <span class="c-id">Id</span> : null}
    </li>
  );
}

export const listClass = (type, mode) => `wl irows is-${mode}${type === "decisions" ? " is-dec" : ""}`;

function Row({ row, today, words, inFile, type }) {
  const pill = clientPill(row, today), who = ownerOf(row.owner), date = dueField(row);
  const title = words[row.id];
  const risk = row.kind === "risk" || row.kind === "issue";
  const late = inFile ? "" : lateWord(row, today);
  const open = inFile ? undefined : (e) => { if (ownClick(e)) openPeek(row.id, "item"); };
  return (
    <li class={`wl-row${inFile ? "" : " wl-open"}`} data-id={row.id} data-kind={row.kind} onClick={open}>
      <span class="c-ico"><ItemIcon row={row} pill={pill} today={today} />{inFile ? <span class={`ico-w ${toneOf(row, pill)}`}>{pill.text}</span> : null}</span>
      <span class="wl-title c-title" title={title}>{title}</span>
      <span class="c-owner" title={who.initials ? who.text : undefined}>
        {who.initials ? <><span class="av" aria-hidden="true">{who.initials}</span><span class="nm">{who.text}</span></> : <span class="nm muted">No owner</span>}
      </span>
      <span class="c-date num">{date ? `${type === "decisions" ? dateWord(row) + " " : ""}${showDate(date)}` : "No date"}</span>
      <span class="c-prio">{(risk || (inFile && isUrgent(row))) && row.priority ? <span class="prio">{row.priority}</span> : late ? <span class="late">{late}</span> : null}</span>
      {inFile ? null : <span class="c-id wl-id num"><button type="button" class="idl" aria-label={`Open ${row.id}`} onClick={() => openPeek(row.id, "item")}>{row.id}</button></span>}
    </li>
  );
}

export function ItemRows({ type }) {
  const inFile = fromFile.value, list = rowsFor(type), today = todayOf(), words = (inFile ? wordings : viewWords)(data.value || {});
  if (!list.length) return <p class="quiet" data-nothing>{NOTHING}</p>;
  return (
    <ul class={listClass(type, inFile ? "file" : "view")}>
      <Head type={type} id={!inFile} />
      {list.map((r) => <Row key={r.id} row={r} today={today} words={words} inFile={inFile} type={type} />)}
    </ul>
  );
}
