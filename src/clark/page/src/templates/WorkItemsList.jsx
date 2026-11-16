// Work items list (#96), store type "workitems": its view part. Live rows from Work items, chosen by the filter saved in Edit
// (./workItemsList.js has the rules). Full width: a table with the columns chosen for the section. Half width: two-line rows (the
// title, then the chosen columns on one line). Both are drawn and the section's slot shows one (shell.css), so nothing is measured.
// View: text nodes only, never dangerouslySetInnerHTML; only rows that would be published (the served page) or that the file
// carries (a published file). isEmpty: no row to show, or no filter saved yet; the section then stays out of View and the file.
import { useState } from "preact/hooks";
import { asAt, fromFile } from "../stores/report.js";
import { KIND_WORDS, dueCell, pillOf, ownerOf, todayIso } from "../workItems.js";
import { listOf, drawRows, drawn, idsToShow, priorityCell, WORDS } from "./workItemsList.js";
import { clientPill } from "../logic/sectionRows.js";
import { ItemIcon } from "../components/ItemRows.jsx";

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
  if (col === "priority") { const p = priorityCell(row).text; return p && p !== "Not rated" ? p : row.kind === "risk" || row.kind === "issue" ? "Not rated" : "—"; }      // row 1268: a decision's is the one its peek sets
  if (col === "milestone") return row.milestone || "—";
  return "";
}

function Cell({ row, col, now }) {
  if (col === "type") return <span class={`type k-${row.kind}`}>{KIND_WORDS[row.kind] || row.kind}</span>;
  if (col === "due") {
    const d = dueCell(row, now);
    return <><span class="num">{d.date}</span>{d.words ? <span class={`due-l${d.tone ? " " + d.tone : ""}`}>{d.words}</span> : null}</>;
  }
  if (col === "status") { const p = clientPill(row, now); return <span class="wil-st"><svg class={`wil-half ic-${p.class}`} viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 3a9 9 0 0 1 0 18z" /></svg>{p.text}</span>; }      // row 1199: a half-circle, coloured as the status pill, before the status word
  if (col === "priority") { const p = priorityCell(row); const rated = p.text && (p.text !== "Not rated" || row.kind === "risk" || row.kind === "issue"); return rated ? <span class={`wil-pr${p.text === "Urgent" ? " u" : p.text === "High" ? " h" : ""}`}>{p.text}</span> : <span class="muted">—</span>; }      // row 1268: the rating chip, in the colour of the pills
  if (col === "owner") { const o = ownerOf(row.owner); return o.initials ? <span class="wil-own"><span class="av" aria-hidden="true">{o.initials}</span><span class="nm">{o.text}</span></span> : <span class="muted">{o.text}</span>; }      // row 1268: the avatar and the name, as the built-in rows
  return cellText(row, col, now);
}

// The rows, at both widths. `open(id)` (Edit only) makes each row open its peek: a click, or Enter on the focused row.
// `Eye` (Edit only): the Work items page's own Client-visible eye (edit/cells/Eye.jsx), drawn at the end of each row, so it means the same thing here.
export function Rows({ rows, columns, now, open, Eye }) {
  const act = open ? (row) => ({ tabIndex: 0, role: "button", "aria-label": `Open ${row.id}: ${row.title || ""}`, onClick: () => open(row.id),
    onKeyDown: (e) => { if (e.target.closest && e.target.closest("button")) return; if ((e.key === "Enter" || e.key === " ") && !e.defaultPrevented) { e.preventDefault(); open(row.id); } } }) : () => ({});
  // Row 1268: one line as the built-in rows: the letter tile, the title, the chosen columns, the ID last; an item the client eye has taken off is greyed.
  const before = columns.filter((c) => c === "type"), after = columns.filter((c) => c !== "type" && c !== "id").concat(columns.filter((c) => c === "id"));
  const off = (row) => (Eye && Eye.isOff && Eye.isOff(row) ? " wil-off" : "");
  const tile = (row) => <ItemIcon row={row} pill={clientPill(row, now)} today={now} plain={!!open} />;
  return (
    <>
      <table class={`wil-table${open ? " wil-live" : ""}`}>
        <thead><tr>
          <th class="wil-c-tile" scope="col" aria-label={WORDS.columns.type} />
          {before.map((c) => <th key={c} class={`wil-c-${c}`} scope="col">{WORDS.columns[c]}</th>)}
          <th class="wil-c-title" scope="col">Item</th>
          {after.map((c) => <th key={c} class={`wil-c-${c}`} scope="col">{WORDS.columns[c]}</th>)}
          {Eye ? <th class="wil-c-eye" scope="col"><span class="sr">{Eye.heading}</span></th> : null}
        </tr></thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} data-id={row.id} class={off(row).trim() || undefined} {...act(row)}>
              <td class="wil-c-tile">{tile(row)}</td>
              {before.map((c) => <td key={c} class={`wil-c-${c}`}><Cell row={row} col={c} now={now} /></td>)}
              <td class="wil-c-title">{row.title || ""}</td>
              {after.map((c) => <td key={c} class={`wil-c-${c}`}><Cell row={row} col={c} now={now} /></td>)}
              {Eye ? <td class="wil-c-eye"><Eye row={row} /></td> : null}
            </tr>
          ))}
        </tbody>
      </table>
      <ul class={`wil-lines${open ? " wil-live" : ""}`}>
        {rows.map((row) => (
          <li key={row.id} data-id={row.id} class={off(row).trim() || undefined} {...act(row)}>
            <span class="wil-tile">{tile(row)}</span>
            <span class="wil-t">{row.title || ""}</span>
            <span class="wil-m">{columns.map((c) => cellText(row, c, now)).filter(Boolean).join(" · ")}</span>
            {Eye ? <span class="wil-eye"><Eye row={row} /></span> : null}
          </li>
        ))}
      </ul>
    </>
  );
}

// Row 1199: the link under the table when the filter lists more rows than Most rows. Shown only on the page clark serves (View and Edit).
export function ShowAll({ list, all, onToggle }) {
  if (!list.more) return null;
  return <p class="wil-all"><button type="button" class="wil-all-b" data-wil-all="" aria-expanded={all ? "true" : "false"} onClick={onToggle}>{all ? `Show only ${list.max}` : "Show all items"}</button></p>;
}

export function isEmpty(section, data) {
  return drawRows(listOf(section, data, today()).items, data).length === 0;
}

export function View({ section, data }) {
  const [all, setAll] = useState(false);
  const now = today();
  const list = listOf(section, data, now);
  const rows = drawRows(idsToShow(list, all), drawn(data, !fromFile.value));
  if (!rows.length) return null;
  return (
    <div class="wil" data-wil="">
      <Rows rows={rows} columns={list.columns} now={now} />
      {fromFile.value ? null : <ShowAll list={list} all={all} onToggle={() => setAll(!all)} />}
      {list.caption ? <p class="wil-cap">{list.caption}</p> : null}
    </div>
  );
}
