// The rows under Risks and issues, Open actions and Decisions (prototype parity A-D5): a state pill, the item, a quiet line of who
// and when (and the priority on a risk or issue), the ID on the right. The same rows in View, in Edit and in a published file; they
// are drawn from the rows the page already holds, so a published file needs nothing else. What a client reads is the client's own
// wording when the item has one, else the item's text. Putting an item on the page or taking it off is a later change (Edit).
import { data, rows as allRows, fromFile, asAt } from "../stores/report.js";
import { pillOf, dueCell, ownerOf, showDate, todayIso, dueField } from "../workItems.js";
import { sectionRows, dateWord } from "../logic/sectionRows.js";

const NOTHING = "Nothing to show this week.";

// The client's own wording for an item, by ID (the page's rows hold the item's text only).
function wordings(d) {
  const out = {};
  for (const k of ["actions", "raid"]) for (const r of d[k] || []) if (r.client_message) out[r.id] = r.client_message;
  return out;
}

export const todayOf = () => (fromFile.value && asAt.value ? asAt.value : todayIso());

export function rowsFor(type) {
  return data.value ? sectionRows(type, allRows.value, todayOf(), fromFile.value) : [];
}

function Row({ row, today, words }) {
  const pill = pillOf(row, today), due = dueCell(row, today), who = ownerOf(row.owner), date = dueField(row);
  const title = row.kind !== "decision" && words[row.id] ? words[row.id] : row.title;
  const risk = row.kind === "risk" || row.kind === "issue";
  return (
    <li class="wl-row" data-id={row.id} data-kind={row.kind}>
      <span class="wl-state"><span class={`pill ${pill.class}`}>{pill.text}</span></span>
      <span class="wl-main">
        <span class="wl-title">{risk ? <span class="tag">{row.kind === "issue" ? "Issue" : "Risk"}</span> : null}{risk ? " " : ""}{title}</span>
        <span class="wl-meta">
          {who.initials ? <span class="av" aria-hidden="true">{who.initials}</span> : null}
          <span class={who.initials ? "" : "muted"}>{who.initials ? who.text : "No owner"}</span>
          <span class="dot" aria-hidden="true">{"·"}</span>
          <span class="num">{date ? `${dateWord(row)} ${showDate(date)}` : "No date"}</span>
          {row.kind === "action" && due.words ? <span class={due.tone ? "late" : ""}>{due.words}</span> : null}
          {risk && row.priority ? <span class="prio">{`Priority ${row.priority}`}</span> : null}
        </span>
      </span>
      <span class="wl-id num">{row.id}</span>
    </li>
  );
}

export function ItemRows({ type }) {
  const list = rowsFor(type), today = todayOf(), words = wordings(data.value);
  if (!list.length) return <p class="quiet">{NOTHING}</p>;
  return <ul class="wl">{list.map((r) => <Row key={r.id} row={r} today={today} words={words} />)}</ul>;
}
