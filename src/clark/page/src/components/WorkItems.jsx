// The Work items list (#36, read only; #64a filters and Add): one project's actions, risks, issues, assumptions, dependencies and
// decisions from GET /api/data, one flat table: type, item, owner, due date in words, priority, status. The list rules are in
// ../workItems.js, the filter rules in ../filters.js. A filter change redraws the list region and the switches' words only.
import { signal } from "@preact/signals";
import { data, rows as allRows, filterState, setFilterState, filterNote } from "../stores/report.js";
import { KIND_WORDS, sortRows, dueCell, pillOf, ownerOf, metaOf, isOpen, todayIso } from "../workItems.js";
import { applyFilters, chips, canClear, countText, clearAll, removeFilter, addPlan } from "../filters.js";
import { Switches, FilterBar } from "./WorkFilters.jsx";
import { NewTile } from "./NewTile.jsx";

// Adding an item is not built yet (#65 to #67): the Add button says so, in words, and records what was asked for.
const asked = signal("");
function onAdd(kind) { asked.value = `Add ${kind || "item"} is coming with a later release. Nothing was added.`; }

function Owner({ name }) {
  const o = ownerOf(name);
  return o.initials
    ? <span class="who"><span class="av" aria-hidden="true">{o.initials}</span><span>{o.text}</span></span>
    : <span class="muted">{o.text}</span>;
}

function Row({ row, today }) {
  const due = dueCell(row, today), pill = pillOf(row, today);
  return (
    <tr data-id={row.id} data-kind={row.kind} class={isOpen(row) ? "" : "done"}>
      <td class="c-type"><span class={`type k-${row.kind}`}>{KIND_WORDS[row.kind] || row.kind}</span></td>
      <td class="c-item">
        <span class="t">{row.title}</span>
        <span class="meta">{metaOf(row)}{row.client ? <span class="tag cl">Shown to client</span> : null}</span>
      </td>
      <td class="c-owner"><Owner name={row.owner} /></td>
      <td class="c-due"><span class="num">{due.date}</span>{due.words ? <span class={`due-l${due.tone ? " " + due.tone : ""}`}>{due.words}</span> : null}</td>
      <td class="c-prio">{row.priority || <span class="muted">{"—"}</span>}</td>
      <td class="c-status"><span class={`pill ${pill.class}`}>{pill.text}</span></td>
    </tr>
  );
}

// The part a filter change redraws: the count, the chips with Clear all, and the table.
function List() {
  const st = filterState.value, today = todayIso();
  const shown = sortRows(applyFilters(allRows.value, st, today), today);
  const cs = chips(st);
  const clear = () => setFilterState(clearAll());
  return (
    <div id="work-list">
      <div class="factive">
        <span id="work-count" class="num">{countText(shown.length, st.mode)}</span>
        {cs.map((c) => (
          <span class="fchip" key={c.field} data-chip={c.field}>{c.text}
            <button type="button" data-fx={c.field} aria-label={`Remove the ${c.name} filter`} onClick={() => setFilterState(removeFilter(filterState.value, c.field))}>{"×"}</button>
          </span>
        ))}
        {canClear(st) ? <button type="button" class="link" id="clearAll" onClick={clear}>Clear all</button> : null}
      </div>
      {shown.length === 0
        ? <div class="empty"><p class="muted">No items match these filters.</p>{canClear(st) ? <button type="button" class="btn" id="clearAll2" onClick={clear}>Clear all</button> : null}</div>
        : <table class="items">
            <thead><tr><th class="c-type">Type</th><th class="c-item">Item</th><th class="c-owner">Owner</th><th class="c-due">Due</th><th class="c-prio">Priority</th><th class="c-status">Status</th></tr></thead>
            <tbody>{shown.map((r) => <Row key={r.id} row={r} today={today} />)}</tbody>
          </table>}
    </div>
  );
}

export function WorkItems() {
  const d = data.value, plan = addPlan(filterState.value.type);
  return (
    <section class="frame work" id="work">
      <p class="crumbs">{d.project.name}</p>
      <div class="head">
        <h1>Work items</h1>
        <NewTile word={plan.word} kind={plan.kind} items={plan.menu} onAdd={onAdd} />
      </div>
      <p class="muted note" role="status" id="work-note">{filterNote.value || asked.value}</p>
      {allRows.value.length === 0
        ? <p class="muted">This project has no work items yet. Use {plan.word} to add the first.</p>
        : <>
            <Switches />
            <FilterBar />
            <List />
          </>}
    </section>
  );
}
