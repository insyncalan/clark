// Work items list (#96), store type "workitems": its view part. Live rows from Work items, chosen by the filter saved in Edit
// (./workItemsList.js has the rules). Full width: a table with the columns chosen for the section. Half width: two-line rows (the
// title, then the chosen columns on one line). Both are drawn and the section's slot shows one (shell.css), so nothing is measured.
// View: a row opens the peek (row 1268); text nodes only, never dangerouslySetInnerHTML; only rows that would be published (the served page) or that the file
// carries (a published file). isEmpty: no row to show, or no filter saved yet; the section then stays out of View and the file.
import { signal } from "@preact/signals";
import { useRef, useLayoutEffect } from "preact/hooks";
import { asAt, fromFile, openPeek, openWork } from "../stores/report.js";
import { KIND_WORDS, dueCell, pillOf, ownerOf, todayIso } from "../workItems.js";
import { listOf, drawRows, drawn, idsToShow, filterOf, footWords, reviewWords, pageState, priorityCell, WORDS } from "./workItemsList.js";
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

// Row 1195: a rating worth a chip: a word, and "Not rated" only on a risk or an issue (the others show a bare dash, which the half row does not draw).
const ratedRow = (row) => { const p = priorityCell(row); return !!(p.text && (p.text !== "Not rated" || row.kind === "risk" || row.kind === "issue")); };

function Cell({ row, col, now }) {
  if (col === "type") return <span class={`type k-${row.kind}`}>{KIND_WORDS[row.kind] || row.kind}</span>;
  if (col === "due") {
    const d = dueCell(row, now);
    return <><span class="num">{d.date}</span>{d.words ? <span class={`due-l${d.tone ? " " + d.tone : ""}`}>{d.words}</span> : null}</>;
  }
  if (col === "status") { const p = clientPill(row, now); return <span class="wil-st"><svg class={`wil-half ic-${p.class}`} viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 3a9 9 0 0 1 0 18z" /></svg>{p.text}</span>; }      // row 1199: a half-circle, coloured as the status pill, before the status word
  if (col === "priority") { const p = priorityCell(row); const rated = p.text && (p.text !== "Not rated" || row.kind === "risk" || row.kind === "issue"); return rated ? <span class={`wil-pr${p.text === "Urgent" ? " u" : p.text === "High" ? " h" : ""}`} data-pri={classicTheme() ? p.text : undefined}>{p.text}</span> : <span class="muted">—</span>; }      // row 1268: the rating chip, in the colour of the pills
  if (col === "owner") { const o = ownerOf(row.owner); return o.initials ? <span class="wil-own"><span class="av" aria-hidden="true">{o.initials}</span><span class="nm">{o.text}</span></span> : <span class="muted">{o.text}</span>; }      // row 1268: the avatar and the name, as the built-in rows
  return cellText(row, col, now);
}

// The rows, at both widths. `open(id)` (Edit only) makes each row open its peek: a click, or Enter on the focused row.
// `Eye` (Edit only): the Work items page's own Client-visible eye (edit/cells/Eye.jsx), drawn at the end of each row, so it means the same thing here.
// Row 1268, item 12 (Edit only): `Cell` is the Work items page's own in-place picker (edit/cells/Cell.jsx) round the Owner, Due, Status and Priority cells,
// and `cw` the page's own column widths (edit/colWidths.jsx: drag a heading's edge, Alt with Left or Right). View and a published file pass neither.
// Row 1195: the page layers a Theme in <style id="theme"> (clark.page.layer_theme); Cards layers nothing, so there is no such element.
export const classicTheme = () => typeof document !== "undefined" && !!document.getElementById("theme");
const PICKED = { owner: "owner", due: "due", status: "status", priority: "priority" };
export function Rows({ rows, columns, now, open, Eye, head, Cell: Pick, cw, ord }) {
  const act = open ? (row) => ({ tabIndex: 0, role: "button", "aria-label": `Open ${row.id}: ${row.title || ""}`, onClick: () => open(row.id),
    onKeyDown: (e) => { if (e.target.closest && e.target.closest("button")) return; if ((e.key === "Enter" || e.key === " ") && !e.defaultPrevented) { e.preventDefault(); open(row.id); } } }) : () => ({});
  // Row 1195 (Classic, Edit): the headings after Item can be dragged or moved with Alt and an arrow (edit/colWidths.jsx useColOrder); the order is kept on this computer.
  const moved = ord && classicTheme() ? ord.apply(columns.filter((c) => c !== "type" && c !== "id").concat(columns.filter((c) => c === "id"))) : null;
  const th = (c, text) => <th key={c} class={`wil-c-${c}${moved ? ord.cls(c) : ""}`} scope="col" style={cw ? cw.style(c) : undefined} {...(cw ? cw.head(c, text) : {})} {...(moved ? ord.props(c, moved) : {})}>{text}{cw ? cw.grip(c, text) : null}</th>;
  const cellOf = (row, c) => (Pick && PICKED[c] ? <Pick row={row} field={PICKED[c]} keep={c === "status"}><Cell row={row} col={c} now={now} /></Pick> : <Cell row={row} col={c} now={now} />);
  // Row 1268: one line as the built-in rows: the letter tile, the title, the chosen columns, the ID last; an item the client eye has taken off is greyed.
  const before = columns.filter((c) => c === "type"), after = moved || columns.filter((c) => c !== "type" && c !== "id").concat(columns.filter((c) => c === "id"));
  // Row 1195: the Classic theme colours the letter tile by the kind, so a row carries its kind as a class there; the Cards page gets exactly the markup it had.
  const kinds = classicTheme();      // also: Classic draws the mock-up's half row (the rating beside the title, the other columns as separate words on the second line)
  const off = (row) => `${kinds ? ` wil-k-${row.kind}` : ""}${Eye && Eye.isOff && Eye.isOff(row) ? " wil-off" : ""}`;
  const tile = (row) => <ItemIcon row={row} pill={clientPill(row, now)} today={now} plain={!!open} />;
  return (
    <>
      <table class={`wil-table${open ? " wil-live" : ""}`}>
        <thead><tr {...(head || {})}>
          <th class="wil-c-tile" scope="col" aria-label={WORDS.columns.type} />
          {before.map((c) => th(c, WORDS.columns[c]))}
          <th class="wil-c-title" scope="col" style={cw ? cw.style("title") : undefined} {...(cw ? cw.head("title", "Item") : {})}>Item{cw ? cw.grip("title", "Item") : null}</th>
          {after.map((c) => th(c, WORDS.columns[c]))}
          {Eye ? <th class="wil-c-eye" scope="col"><span class="sr">{Eye.heading}</span></th> : null}
        </tr></thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} data-id={row.id} class={off(row).trim() || undefined} {...act(row)}>
              <td class="wil-c-tile">{tile(row)}</td>
              {before.map((c) => <td key={c} class={`wil-c-${c}`}>{cellOf(row, c)}</td>)}
              <td class="wil-c-title">{row.title || ""}</td>
              {after.map((c) => <td key={c} class={`wil-c-${c}`}>{cellOf(row, c)}</td>)}
              {Eye ? <td class="wil-c-eye"><Eye row={row} />{Eye.Ask ? <Eye.Ask row={row} /> : null}</td> : null}
            </tr>
          ))}
        </tbody>
      </table>
      <ul class={`wil-lines${open ? " wil-live" : ""}`}>
        {rows.map((row) => (
          <li key={row.id} data-id={row.id} class={off(row).trim() || undefined} {...act(row)}>
            <span class="wil-tile">{tile(row)}</span>
            <span class="wil-t">{row.title || ""}</span>
            {kinds && columns.includes("priority") && ratedRow(row) ? <span class="wil-hpr"><Cell row={row} col="priority" now={now} /></span> : null}
            {kinds ? <span class="wil-m">{columns.filter((c) => c !== "type" && c !== "priority").map((c) => cellText(row, c, now)).filter(Boolean).map((t, i) => <span key={i}>{t}</span>)}</span>
              : <span class="wil-m">{columns.map((c) => cellText(row, c, now)).filter(Boolean).join(" · ")}</span>}
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

// Row 1268: the rows scroll inside a box as tall as the first Most rows (measured from the drawn rows, as the mock-up's fitScroll does), so
// every row the filter lists is on the page and the rest are a scroll away. Only the table or the lines are visible at a time (shell.css), so
// the one with a height is measured. No limit when there are no more rows than Most rows.
export function Scroller({ max, count, children, all }) {
  const box = useRef(null);
  const scrolls = classicTheme() ? count > max && !all : count > max;      // row 1195 (Classic only): open (Show all items) the box no longer scrolls, so it is neither a region nor a tab stop; Cards keeps the old expression
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    el.style.maxHeight = "";
    if (count <= max || all) return;      // row 1195 (Classic): Show all items has opened the box to every row
    const vis = [...el.querySelectorAll(".wil-table tbody tr, .wil-lines li")].filter((r) => r.offsetHeight > 0);
    const head = el.querySelector(".wil-table thead");
    const h = vis.slice(0, max).reduce((n, r) => n + r.offsetHeight, 0) + (head && head.offsetHeight > 0 ? head.offsetHeight : 0);
    if (h > 0) el.style.maxHeight = `${h}px`;
  });
  return <div class="wil-scroll" data-wil-scroll="" ref={box} tabIndex={scrolls ? 0 : undefined} role={scrolls ? "region" : undefined} aria-label={scrolls ? "Work items, scroll for more" : undefined}>{children}</div>;
}

// Row 1195 (Classic only, the README's "Show all items"): the scrolling rows and, under them (View and Edit, never a published file), the link when there are more rows than Most rows; open, the box
// shows every row and the link reads "Show only N". The Cards page gets the Scroller alone, exactly as before.
const openLists = signal({});      // row 1195: the lists whose Show all items is open, by section id, so the Foot reads Showing N of N
export function Listing({ max, count, sid, children }) {
  const all = !!openLists.value[sid];
  const setAll = (v) => { openLists.value = { ...openLists.value, [sid]: v }; };
  const on = classicTheme() && !fromFile.value && count > max;      // the served page only, as the Foot is: a published file has no link
  return <><Scroller max={max} count={count} all={on && all}>{children}</Scroller>{on ? <ShowAll list={{ more: true, max }} all={all} onToggle={() => setAll(!all)} /> : null}</>;
}

// The foot under the rows (the served page only): "Showing N of M" in Edit, and the link to the Work items page on the same filter.
export function Foot({ section, total, max, edit, nameOf }) {
  const open = !!openLists.value[section.id] && classicTheme() && !fromFile.value;
  const filter = filterOf(section);
  if (!filter || !total) return null;
  return (
    <div class="wil-foot" data-wil-foot="">
      {edit || (classicTheme() && !fromFile.value) ? <span data-wil-count="">{footWords(total, max, open, classicTheme())}</span> : <span></span>}
      <button type="button" class="wil-review" data-wil-review="" onClick={() => openWork(pageState(filter, nameOf))}>{reviewWords(total)}</button>
    </div>
  );
}

export const NONE_WORDS = "No work items match this filter.";      // row 1195 (Classic View): the mock-up's words, WO-M8425
export function isEmpty(section, data) {
  if (classicTheme() && !fromFile.value && filterOf(section)) return false;      // row 1195 (Classic, the served View): a saved filter with no row says so, it is not left out; the published file still leaves it out
  return drawRows(listOf(section, data, today()).items, data).length === 0;
}

// Row 1225: View draws plain headings (no drag, no grip, no tab stop); only Edit has the width and order tools (edit/colWidths.jsx).

export function View({ section, data }) {
  const now = today();
  const list = listOf(section, data, now);
  const rows = drawRows(idsToShow(list, !fromFile.value), drawn(data, !fromFile.value));
  if (!rows.length) return classicTheme() && !fromFile.value && filterOf(section) ? <div class="wil" data-wil=""><p class="wil-none" data-wil-none="" role="status">{NONE_WORDS}</p></div> : null;
  const draw = (cw, ord) => (
    <div class="wil" data-wil="">
      {list.caption ? <p class="wil-cap">{list.caption}</p> : null}
      <Listing max={list.max || rows.length} count={rows.length} sid={section.id}><Rows rows={rows} columns={list.columns} now={now} open={(rid) => openPeek(rid, "item")} cw={cw} ord={ord} /></Listing>      {/* row 1268: a row opens the peek in View and in a published file: read only there (Peek draws no control unless the page is editing), editable in Edit */}
      {fromFile.value ? null : <Foot section={section} total={rows.length} max={list.max} edit={false} />}
    </div>
  );
  return draw(undefined, undefined);
}
