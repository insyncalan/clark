// Work items list (#96), store type "workitems": its Edit part. The filter is set in place: every choice that is committed (a box
// ticked, a choice picked, the number or the caption left with Enter or Tab) saves the whole filter as ONE change (one step, one
// Undo, place "report"). Under it, the rows it lists now, exactly as View and the published page will show them; each row opens
// its peek (a click, or Enter). An empty match says so here, and only here: View and the published page leave the section out.
import { useRef, useState } from "preact/hooks";
import { data, openPeek, openWork, rows as allRows, filterCtx } from "../../stores/report.js";
import { LineBox } from "../../components/FilterLine.jsx";
import { MenuPanel } from "../../components/Menu.jsx";
import { addItem, ADDABLE } from "../addItem.js";
import { change, say } from "../../stores/changes.js";
import { Rows, Window, Foot, today, shownColumns } from "../../templates/WorkItemsList.jsx";
import { workState } from "../../templates/workItemsReview.js";
import { KINDS, MODES, STATUSES, DUE, PRIORITIES, NONE, SORTS, COLUMNS, DESIGN_COLUMNS, MAX_ROWS, MAX_CAPTION, WORDS, defaults, filterOf, bodyOf,
  editListOf, drawRows, offered, drawn } from "../../templates/workItemsList.js";
import { Eye } from "../cells/Eye.jsx";
import { plural } from "../../workItems.js";
import { lineOf, readLine } from "../../templates/workItemsLine.js";

export const SAVED = "Work items list changed.";
export const NOT_YET = "No filter is set for this section yet. Set one below and it shows here.";
export const NO_MATCH = "No work items match this filter, so this section is left out of the published page. Change the filter to list some.";
export const ONLY_SHOWN = "Only work items that go in the published page are listed.";
export const ALL_HIDDEN = "Every work item listed here is hidden from the client, so this section is left out of the published page. Turn an eye on to list one.";
export const BAD_MAX = `Show between 1 and ${MAX_ROWS} work items. Type a number in that range.`;
export const LONG_CAPTION = `The caption can be at most ${MAX_CAPTION} characters. Shorten it and save again.`;

const points = (t) => [...t].length;

function Boxes({ id, legend, field, values, words, chosen, onToggle }) {
  return (
    <fieldset class="wil-f" data-field={field}>
      <legend>{legend}</legend>
      <div class="wil-opts">
        {values.map((v) => (
          <label key={v}><input type="checkbox" name={`${id}-${field}`} value={v} checked={chosen.includes(v)} onChange={() => onToggle(field, v)} />{words(v)}</label>
        ))}
        {values.length ? null : <span class="muted">No values to choose yet.</span>}
      </div>
    </fieldset>
  );
}

function Choice({ id, label, field, values, words, value, onPick }) {
  return (
    <label class="wil-sel" data-field={field}>
      <span>{label}</span>
      <select id={`${id}-${field}`} value={value} onChange={(e) => onPick(field, e.currentTarget.value)}>
        {values.map((v) => <option key={v} value={v}>{words[v]}</option>)}
      </select>
    </label>
  );
}

export const LINE_HINT = "Type a filter, for example: type:risk status:Open owner:\"Pat Demo\"  Press Enter to save it.";

export function Edit({ section }) {
  const [plus, setPlus] = useState(null);           // the dashed + Add menu: Action, Risk, Issue, Decision; a choice makes the item and opens its Peek
  const [at, setAt] = useState(null);              // the columns menu (a right click on the heading row), kept in step with the Columns boxes
  const [tick, setTick] = useState(0);              // a refused save draws the form again from what is saved
  const d = data.value || {};
  const saved = filterOf(section);
  const filter = saved || defaults();
  const id = `wil-${section.id}`;
  const ucName = Object.fromEntries((d.use_cases || []).map((u) => [u.id, u.ref ? `${u.ref} ${u.title || ""}`.trim() : (u.title || u.id)]));
  const nameOf = (f, v) => ucName[v] || v;
  const known = (d.use_cases || []).map((u) => ({ id: u.id, names: [u.title, u.ref, u.ref ? `${u.ref} ${u.title || ""}`.trim() : ""].filter(Boolean) }));
  const none = (f) => (v) => (v === NONE ? WORDS.none[f] : f === "use_case" ? (ucName[v] || v) : v);

  // The latest filter the page meant to save, kept while saves are still waiting: a second choice made before the first reply is
  // built on the first, not on the body last read. Once nothing is waiting, the saved body is the truth again.
  const meant = useRef(null), waiting = useRef(0);
  const latest = () => (waiting.current > 0 && meant.current ? meant.current : filter);
  const save = (next) => {
    meant.current = next; waiting.current += 1;
    return change({ op: "update", id: section.id, changes: { body: bodyOf(next) }, place: "report" }, SAVED)
      .then((reply) => { if (!reply) setTick((n) => n + 1); return reply; })
      .finally(() => { waiting.current -= 1; if (waiting.current <= 0) meant.current = null; });
  };
  const toggle = (field, v) => {
    const cur = latest(), have = cur[field];
    save({ ...cur, [field]: have.includes(v) ? have.filter((x) => x !== v) : [...have, v] });
  };
  const toggleColumn = (field, v) => {
    const cur = latest();
    const next = cur.columns.includes(v) ? cur.columns.filter((x) => x !== v) : COLUMNS.filter((c) => c === v || cur.columns.includes(c));      // a Type column is the letter tile now: it stays in a saved list but is no choice
    if (!next.length) { say("problem", "Choose at least one column to show."); setTick((n) => n + 1); return; }
    save({ ...cur, columns: next });
  };
  const pick = (field, v) => save({ ...latest(), [field]: v });
  const commitMax = (e) => {
    const el = e.currentTarget, n = Number(el.value);
    if (n === filter.max && saved) return;
    if (!Number.isInteger(n) || n < 1 || n > MAX_ROWS) { say("problem", BAD_MAX); el.value = String(filter.max); return; }
    save({ ...latest(), max: n });
  };
  const commitCaption = (e) => {
    const el = e.currentTarget, text = el.value.split(/\s+/).filter(Boolean).join(" ");
    if (text === filter.caption) { el.value = filter.caption; return; }
    if (points(text) > MAX_CAPTION) { say("problem", LONG_CAPTION); return; }
    save({ ...latest(), caption: text });
  };
  // Counted as the store counts: one emoji is one character, not two.
  const capInput = (e) => { if (points(e.currentTarget.value) > MAX_CAPTION) say("problem", LONG_CAPTION); };
  // The filter line: Enter (or leaving the box) reads the typed words onto the filter and saves it as ONE change; a word the list cannot
  // use is said in plain words and nothing is saved. A chip's x takes that one choice off.
  // Item 1268: the box is the Work items page's own (components/FilterLine.jsx LineBox), not a copy: the same chips, suggestions, count and keys.
  const applyLine = (text) => {
    const cur = latest();
    if (String(text).trim() === lineOf(cur, nameOf)) return;
    const r = readLine(text, cur, known);
    if (r.problem) { say("problem", r.problem); return; }
    save(r.filter);
  };
  const BOX = { input: `${id}-q`, list: `${id}-q-list`, count: `${id}-q-count`, x: `${id}-q-x`, msg: `${id}-q-msg`, gloss: `${id}-q-gloss`, opt: `${id}-qo` };
  const keys = (e) => {
    if (e.key === "Enter") { e.preventDefault(); e.currentTarget.blur(); }
    else if (e.key === "Escape") { e.preventDefault(); e.currentTarget.value = e.currentTarget.name === "max" ? String(filter.max) : filter.caption; e.currentTarget.blur(); }
  };

  const now = today();
  const list = editListOf(section, d, now);
  const rows = drawRows(list.all || list.items, drawn(d, true));
  const cols = shownColumns(filter.columns);
  const head = { onContextMenu: (e) => { e.preventDefault(); setAt(e.target.closest("[data-col]") || e.currentTarget); } };
  return (
    <div class="wil wil-edit" key={tick} data-wil-edit="" data-wil-id={id}>
      {saved ? null : <p class="quiet wil-say" data-wil-say="not-yet">{NOT_YET}</p>}
      <div class="wil-line" data-wil-line="">
        <LineBox line={lineOf(filter, nameOf)} now={() => lineOf(latest(), nameOf)} apply={applyLine} rows={allRows.value} ctx={filterCtx()} ids={BOX} label="Filter work items" />
      </div>
      <div class="wil-form">
      <details class="wil-more" data-wil-more="">
      <summary>Choose from lists</summary>
      <div class="wil-form-in">
        <Boxes id={id} legend="Kinds" field="kinds" values={KINDS} words={(v) => WORDS.kinds[v]} chosen={filter.kinds} onToggle={toggle} />
        <Choice id={id} label="Show" field="mode" values={MODES} words={WORDS.mode} value={filter.mode} onPick={pick} />
        <Boxes id={id} legend="Due" field="due" values={DUE} words={(v) => WORDS.due[v]} chosen={filter.due} onToggle={toggle} />
        <Boxes id={id} legend="Status" field="status" values={STATUSES} words={(v) => v} chosen={filter.status} onToggle={toggle} />
        <Boxes id={id} legend="Priority" field="priority" values={[...PRIORITIES, NONE]} words={none("priority")} chosen={filter.priority} onToggle={toggle} />
        <Boxes id={id} legend="Owner" field="owner" values={offered("owner", d, filter.owner)} words={none("owner")} chosen={filter.owner} onToggle={toggle} />
        <Boxes id={id} legend="Workstream" field="workstream" values={offered("workstream", d, filter.workstream)} words={none("workstream")} chosen={filter.workstream} onToggle={toggle} />
        <fieldset class="wil-f" data-field="recent"><legend>Decisions</legend>
          <div class="wil-opts"><label><input type="checkbox" name={`${id}-recent`} checked={!!filter.recent} onChange={() => save({ ...latest(), recent: !latest().recent })} />Pending, and made in the last 14 days</label></div>
        </fieldset>
        <Boxes id={id} legend="Use case" field="use_case" values={offered("use_case", d, filter.use_case)} words={none("use_case")} chosen={filter.use_case} onToggle={toggle} />
      </div>
      </details>
        <Choice id={id} label="Sort by" field="sort" values={SORTS} words={WORDS.sort} value={filter.sort} onPick={pick} />
        <label class="wil-sel" data-field="max"><span>Most rows</span>
          <input type="number" name="max" min="1" max={MAX_ROWS} step="1" value={filter.max} onChange={commitMax} onKeyDown={keys} />
        </label>
        <Boxes id={id} legend="Columns at full width" field="columns" values={DESIGN_COLUMNS} words={(v) => WORDS.columns[v]} chosen={filter.columns} onToggle={toggleColumn} />
      </div>
      <p class="quiet" data-wil-say="count">{saved ? `${plural(rows.length, "work item")} listed now. ${ONLY_SHOWN}` : ONLY_SHOWN}</p>
      {saved && !rows.length ? <p class="wil-none" data-wil-say="none" role="status">{NO_MATCH}</p> : null}
      {saved && rows.length && rows.length === list.off.length ? <p class="wil-none" data-wil-say="all-hidden" role="status">{ALL_HIDDEN}</p> : null}
      {saved ? (
        <div class="wil-views" data-wil-views="">
          <button type="button" class="wil-add" data-wil-add="" aria-haspopup="menu" aria-label="Add a work item" onClick={(e) => setPlus(e.currentTarget)}>+</button>
          {plus ? (
            <MenuPanel label="Add" cls="cols-menu" anchor={plus} fixed="start" onClose={() => setPlus(null)}>
              {ADDABLE.map((k) => <button key={k} type="button" role="menuitem" tabIndex={-1} data-add-kind={k} onClick={() => { setPlus(null); addItem(k); }}>{k[0].toUpperCase() + k.slice(1)}</button>)}
            </MenuPanel>
          ) : null}
        </div>
      ) : null}
      {saved && rows.length ? <Window max={list.max} total={rows.length}><Rows rows={rows} columns={list.columns} now={now} open={(rid) => openPeek(rid, "item")} Eye={Eye} off={list.off} headProps={head} /></Window> : null}
      {saved && rows.length ? <Foot shown={Math.min(list.max, rows.length)} total={rows.length} onReview={() => openWork(workState(filter))} /> : null}
      {at ? (
        <MenuPanel label="Columns" cls="cols-menu" anchor={at} fixed="start" onClose={() => setAt(null)}>
          {DESIGN_COLUMNS.map((c) => (
            <button key={c} type="button" role="menuitemcheckbox" aria-checked={cols.includes(c) ? "true" : "false"} data-col-name={WORDS.columns[c]} tabIndex={-1} onClick={() => toggleColumn("columns", c)}>
              <span class="ck" aria-hidden="true">{cols.includes(c) ? "✓" : ""}</span><span class="cols-name">{WORDS.columns[c]}</span>
            </button>
          ))}
        </MenuPanel>
      ) : null}
      {saved && list.caption && rows.length ? <p class="wil-cap">{list.caption}</p> : null}
      <div class="wil-capbox">
        <label class="wil-sel wil-capf" data-field="caption"><span>Caption (optional)</span>
          <input type="text" name="caption" value={filter.caption} onInput={capInput} onChange={commitCaption} onKeyDown={keys} />
        </label>
      </div>
    </div>
  );
}
