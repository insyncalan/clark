// Work items list (#96), store type "workitems": its view part. Live rows from Work items, chosen by the filter saved in Edit
// (./workItemsList.js has the rules). Full width: a table with the columns chosen for the section. Half width: two-line rows (the
// title, then the chosen columns on one line). Both are drawn and the section's slot shows one (shell.css), so nothing is measured.
// View: text nodes only, never dangerouslySetInnerHTML; only rows that would be published (the served page) or that the file
// carries (a published file). isEmpty: no row to show, or no filter saved yet; the section then stays out of View and the file.
import { asAt, fromFile } from "../stores/report.js";
import { KIND_WORDS, dueCell, pillOf, ownerOf, todayIso } from "../workItems.js";
import { listOf, drawRows, WORDS } from "./workItemsList.js";

export const READY = true;

export function today() {
  return (fromFile.value && asAt.value) || todayIso();
}

function cellText(row, col, now) {
  if (col === "type") return KIND_WORDS[row.kind] || row.kind;
  if (col === "id") return row.id;
  if (col === "owner") return ownerOf(row.owner).text;
  if (col === "due") { const d = dueCell(row, now); return d.words ? `${d.date} (${d.words})` : d.date; }
  if (col === "status") return pillOf(row, now).text;
  if (col === "workstream") return row.workstream || "—";
  return "";
}

function Cell({ row, col, now }) {
  if (col === "type") return <span class={`type k-${row.kind}`}>{KIND_WORDS[row.kind] || row.kind}</span>;
  if (col === "due") {
    const d = dueCell(row, now);
    return <><span class="num">{d.date}</span>{d.words ? <span class={`due-l${d.tone ? " " + d.tone : ""}`}>{d.words}</span> : null}</>;
  }
  if (col === "status") { const p = pillOf(row, now); return <span class={`pill ${p.class}`}>{p.text}</span>; }
  if (col === "owner") { const o = ownerOf(row.owner); return o.initials ? o.text : <span class="muted">{o.text}</span>; }
  return cellText(row, col, now);
}

// The rows, at both widths. `open(id)` (Edit only) makes each row open its peek: a click, or Enter on the focused row.
export function Rows({ rows, columns, now, open }) {
  const act = open ? (row) => ({ tabIndex: 0, role: "button", "aria-label": `Open ${row.id}: ${row.title || ""}`, onClick: () => open(row.id),
    onKeyDown: (e) => { if ((e.key === "Enter" || e.key === " ") && !e.defaultPrevented) { e.preventDefault(); open(row.id); } } }) : () => ({});
  const before = columns.filter((c) => c === "type" || c === "id"), after = columns.filter((c) => c !== "type" && c !== "id");
  return (
    <>
      <table class={`wil-table${open ? " wil-live" : ""}`}>
        <thead><tr>
          {before.map((c) => <th key={c} class={`wil-c-${c}`} scope="col">{WORDS.columns[c]}</th>)}
          <th class="wil-c-title" scope="col">Item</th>
          {after.map((c) => <th key={c} class={`wil-c-${c}`} scope="col">{WORDS.columns[c]}</th>)}
        </tr></thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} data-id={row.id} {...act(row)}>
              {before.map((c) => <td key={c} class={`wil-c-${c}`}><Cell row={row} col={c} now={now} /></td>)}
              <td class="wil-c-title">{row.title || ""}</td>
              {after.map((c) => <td key={c} class={`wil-c-${c}`}><Cell row={row} col={c} now={now} /></td>)}
            </tr>
          ))}
        </tbody>
      </table>
      <ul class={`wil-lines${open ? " wil-live" : ""}`}>
        {rows.map((row) => (
          <li key={row.id} data-id={row.id} {...act(row)}>
            <span class="wil-t">{row.title || ""}</span>
            <span class="wil-m">{columns.map((c) => cellText(row, c, now)).filter(Boolean).join(" · ")}</span>
          </li>
        ))}
      </ul>
    </>
  );
}

export function isEmpty(section, data) {
  return drawRows(listOf(section, data, today()).items, data).length === 0;
}

export function View({ section, data }) {
  const now = today();
  const list = listOf(section, data, now);
  const rows = drawRows(list.items, data);
  if (!rows.length) return null;
  return (
    <div class="wil" data-wil="">
      <Rows rows={rows} columns={list.columns} now={now} />
      {list.caption ? <p class="wil-cap">{list.caption}</p> : null}
    </div>
  );
}
