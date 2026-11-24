// The rows under Risks and issues, Open actions and Decisions (prototype parity A-D5; row 1021): ONE line per item, a tinted letter icon
// (kind and status), the title, the owner, the date, the priority or "N d late", the ID on the right. The same rows in View, in Edit (edit/ItemRowsEdit.jsx draws
// them with every part editable) and in a published file; they are drawn from the rows the page already holds, so a published file
// needs nothing else. What a client reads is the client's own wording, or the item's own title when it has none; the rows
// listed are the ones marked for the client (the eye). An empty section keeps its heading and says so in a line in View (prototype views.js: "Nothing to show."); a
// published file leaves an empty section out, heading and all (Dashboard.jsx fileDraws), so a client never reads that line.
import { data, rows as allRows, fromFile, asAt, openPeek, openPeekEdit } from "../stores/report.js";
import { ownerOf, showDate, todayIso, dueField, isOpen, isLate, dayNumber, KIND_WORDS, kindLetter } from "../workItems.js";
import { classicTheme } from "./Contents.jsx";
import { richWords } from "../logic/richWords.js";
import { dashboardOrder, DASH_STD } from "../logic/tableColumns.js";
import { sectionRows, listed, dateWord, clientPill, lateWord, keptIds } from "../logic/sectionRows.js";

export const NOTHING = "Nothing to show.";

// The words a row is drawn with, by ID: the client's own wording, or, when an item shown to the client has none, the item's title: its
// description (the decision text for a decision), which is its visible name in the published lists. Internal fields (the latest update,
// notes) are never used. Row 851: the eye is the control, so a marked item is listed; a missing wording never takes it off the list.
// Row 1288: a row's wording is the Full editor's HTML, or the plain text an older clark stored: its words are what is listed.
export function wordings(d) {
  const out = {};
  for (const [k, own] of [["actions", "description"], ["raid", "description"], ["decisions", "decision"]]) {
    for (const r of d[k] || []) { const t = richWords(r.client_message).trim() || String(r[own] || "").trim(); if (t) out[r.id] = t; }
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
export const isUrgent = (row) => row.priority === "Urgent" && isOpen(row) && row.status !== "Completed";      // a Completed item is blue, never maroon
export const toneOf = (row, pill) => {
  if (row.kind === "decision") return row.status === "Made" ? "b" : row.status === "Withdrawn" ? "n" : "g";
  if (row.status === "Closed" || row.status === "Completed") return "b";
  return pill.class === "b" ? "g" : pill.class;
};
const COLOUR_WORDS = ["Red", "Amber", "Green"];      // the tile's colour words; the tooltip of an Urgent item drops them (the visible word stays as it is)
export const iconWords = (row, pill, today) => {
  const kind = KIND_WORDS[row.kind] || "Item", late = isLate(row, today) && pill.text !== "Overdue" ? "Overdue" : "";
  const own = row.kind !== "decision" && pill.text === row.status && pill.text !== "Delayed";      // a record's own status word (Blocked, In progress) wins; the tooltip still says Overdue
  // An Urgent item keeps its maroon tile and says Urgent after its status word (Blocked, Delayed, Overdue, Pending ...); only the colour word gives way to Urgent.
  const parts = isUrgent(row) ? [COLOUR_WORDS.includes(pill.text) ? "" : pill.text, "Urgent", late] : own ? [pill.text, late] : [pill.text];
  const words = parts.filter(Boolean);
  return { name: `${kind}, ${words.join(", ")}`, tip: `${kind} · ${words.join(" · ")}`, kind, words };
};
// Row 1321 (Classic only): the same tip drawn in parts (the kind, the other words, the dots between, "Overdue" marked) as real elements, so the card can weight them. data-tip keeps the whole string (screen readers, Cards, fallback), so this copy is aria-hidden.
export function TipParts({ say }) {
  if (!classicTheme() || !say.kind) return null;
  const all = [say.kind, ...say.words];
  return <span class="tip-parts" aria-hidden="true">{all.map((w, i) => <>{i ? <span class="tp-dot"> · </span> : null}<span class={i === 0 ? "tp-kind" : w === "Overdue" ? "tp-late" : "tp-word"}>{w}</span></>)}</span>;
}
export const dateHead = (type) => (type === "raid" ? "Review by" : type === "actions" ? "Due" : "Date");

export function ItemIcon({ row, pill, plain, today }) {
  const w = iconWords(row, pill, today ?? todayOf()), tone = `${toneOf(row, pill)}${isUrgent(row) ? " u" : ""}`;
  return plain
    ? <span class={`ico ${tone}`} aria-hidden="true">{kindLetter(row.kind)}</span>
    : <span class={`ico ${tone}`} role="img" tabindex="0" aria-label={w.name} data-tip={w.tip}>{kindLetter(row.kind)}<TipParts say={w} /></span>;
}

// Row 1534 (AP5): the columns in the order saved for this type on the Work items page, or the standard order. `ord` is true when the order is not the standard one: the list then
// carries data-ord and --cols-ord (the widths in that order), and each cell its standard place (--s), which the narrow layouts use to keep the standard look (shell.css).
export function columnsFor(type, id, classic = classicTheme()) {      // Classic only: Cards (no Theme layer) always draws the standard order
  const d = data.value, list = dashboardOrder(d && d.project ? d.project.column_orders : null, type, id, classic), std = DASH_STD.filter((c) => id || c !== "id");
  const ord = !list.every((c, i) => c === std[i]);
  return { list, ord, attrs: ord ? { "data-ord": "", style: `--cols-ord:${list.map((c) => (c === "title" ? "minmax(0, 1fr)" : `var(--w-${c})`)).join(" ")}` } : {} };
}
export const place = (ord, c) => (ord ? { "--s": DASH_STD.indexOf(c) } : undefined);

// The header row, once per card. A file has no Id column (a client is not given the item number).
export function Head({ type, id, cols }) {
  const { list, ord } = cols || columnsFor(type, id);
  const head = { ico: <span class="c-ico" style={place(ord, "ico")}>Status</span>, title: <span class="c-title" style={place(ord, "title")}>Title</span>, owner: <span class="c-owner" style={place(ord, "owner")}>Owner</span>,
    date: <span class="c-date" style={place(ord, "date")}>{dateHead(type)}</span>, prio: <span class="c-prio" style={place(ord, "prio")}>Priority</span>, id: <span class="c-id" style={place(ord, "id")}>Id</span> };
  return <li class="wl-head" aria-hidden="true">{list.map((c) => head[c])}</li>;
}

export const listClass = (type, mode) => `wl irows is-${mode}${type === "decisions" ? " is-dec" : ""}`;

function Row({ row, today, words, inFile, type, pick: Pick, scope, cols }) {
  const pill = clientPill(row, today), who = ownerOf(row.owner), date = dueField(row);
  const title = words[row.id];
  const risk = row.kind === "risk" || row.kind === "issue";
  const late = inFile ? "" : lateWord(row, today);
  const open = inFile ? undefined : (e) => { if (ownClick(e)) openPeek(row.id, "item"); };
  const P = (field, said, children, extra) => (Pick ? <Pick row={row} field={field} said={said} scope={scope} {...(extra || {})}>{children}</Pick> : children);      // row 1287: in View the Edit cell picker round the four values (status, owner, date, priority), never round the title
  const st = (c) => place(cols.ord, c);      // row 1534: the cells are drawn in the saved order (the Work items page's order for this type)
  const cell = {
    ico: <span class="c-ico" style={st("ico")}>{P("status", pill.text, <ItemIcon row={row} pill={pill} today={today} />, { keep: true })}{inFile ? <span class={`ico-w ${toneOf(row, pill)}`}>{pill.text}</span> : null}</span>,
    title: <span class="wl-title c-title" style={st("title")} title={title} onClick={Pick ? (e) => { e.stopPropagation(); if (!String(window.getSelection()).length) openPeekEdit(row.id); } : undefined}>{title}</span>,
    owner: <span class="c-owner" style={st("owner")} title={who.initials ? who.text : undefined}>
      {P("owner", who.initials ? who.text : "none", who.initials ? <><span class="av" aria-hidden="true">{who.initials}</span><span class="nm">{who.text}</span></> : <span class="nm muted">No owner</span>)}
    </span>,
    date: <span class="c-date num" style={st("date")}>{P("due", date ? showDate(date) : "none", date ? `${type === "decisions" ? dateWord(row) + " " : ""}${showDate(date)}` : "No date")}</span>,
    prio: <span class="c-prio" style={st("prio")}>{(risk || (inFile && isUrgent(row))) && row.priority ? P("priority", row.priority, <span class="prio">{row.priority}</span>) : late ? <span class="late">{late}</span> : null}</span>,
    id: <span class="c-id wl-id num" style={st("id")}><button type="button" class="idl" aria-label={`Open ${row.id}`} onClick={() => openPeek(row.id, "item")}>{row.id}</button></span>,
  };
  return (
    <li class={`wl-row${inFile ? "" : " wl-open"}`} data-id={row.id} data-kind={row.kind} onClick={open}>
      {cols.list.map((c) => cell[c])}
    </li>
  );
}

export function ItemRows({ type, pick, scope }) {
  const inFile = fromFile.value, list = rowsFor(type), today = todayOf(), words = (inFile ? wordings : viewWords)(data.value || {});
  if (!list.length) return <p class="quiet" data-nothing>{NOTHING}</p>;
  const cols = columnsFor(type, !inFile);
  return (
    <ul class={listClass(type, inFile ? "file" : "view")} {...cols.attrs}>
      <Head type={type} id={!inFile} cols={cols} />
      {list.map((r) => <Row key={r.id} row={r} today={today} words={words} inFile={inFile} type={type} pick={inFile ? null : pick} scope={scope} cols={cols} />)}
    </ul>
  );
}
