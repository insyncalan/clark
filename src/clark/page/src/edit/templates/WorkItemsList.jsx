// Work items list (#96), store type "workitems": its Edit part. The filter is set in place: every choice that is committed (a box
// ticked, a choice picked, the number or the caption left with Enter or Tab) saves the whole filter as ONE change (one step, one
// Undo, place "report"). Under it, the rows it lists now, exactly as View and the published page will show them; each row opens
// its peek (a click, or Enter). An empty match says so here, and only here: View and the published page leave the section out.
import { useRef, useState } from "preact/hooks";
import { data, openPeek } from "../../stores/report.js";
import { change, say } from "../../stores/changes.js";
import { Rows, today } from "../../templates/WorkItemsList.jsx";
import { KINDS, MODES, STATUSES, DUE, PRIORITIES, NONE, SORTS, COLUMNS, MAX_ROWS, MAX_CAPTION, WORDS, defaults, filterOf, bodyOf,
  listOf, drawRows, offered } from "../../templates/workItemsList.js";
import { plural } from "../../workItems.js";

export const SAVED = "Work items list changed.";
export const NOT_YET = "This list shows nothing until its filter is saved. Change any choice below to start it.";
export const NO_MATCH = "No work items match this filter, so this section is left out of the published page. Change the filter to list some.";
export const ONLY_SHOWN = "Only work items that go in the published page are listed.";
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

export function Edit({ section }) {
  const [tick, setTick] = useState(0);              // a refused save draws the form again from what is saved
  const d = data.value || {};
  const saved = filterOf(section);
  const filter = saved || defaults();
  const id = `wil-${section.id}`;
  const ucName = Object.fromEntries((d.use_cases || []).map((u) => [u.id, u.ref ? `${u.ref} ${u.title || ""}`.trim() : (u.title || u.id)]));
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
    const next = cur.columns.includes(v) ? cur.columns.filter((x) => x !== v) : COLUMNS.filter((c) => c === v || cur.columns.includes(c));
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
  const keys = (e) => {
    if (e.key === "Enter") { e.preventDefault(); e.currentTarget.blur(); }
    else if (e.key === "Escape") { e.preventDefault(); e.currentTarget.value = e.currentTarget.name === "max" ? String(filter.max) : filter.caption; e.currentTarget.blur(); }
  };

  const now = today();
  const list = listOf(section, d, now);
  const rows = drawRows(list.items, d);
  return (
    <div class="wil wil-edit" key={tick} data-wil-edit="">
      {saved ? null : <p class="quiet wil-say" data-wil-say="not-yet">{NOT_YET}</p>}
      <div class="wil-form">
        <Boxes id={id} legend="Kinds" field="kinds" values={KINDS} words={(v) => WORDS.kinds[v]} chosen={filter.kinds} onToggle={toggle} />
        <Choice id={id} label="Show" field="mode" values={MODES} words={WORDS.mode} value={filter.mode} onPick={pick} />
        <Boxes id={id} legend="Due" field="due" values={DUE} words={(v) => WORDS.due[v]} chosen={filter.due} onToggle={toggle} />
        <Boxes id={id} legend="Status" field="status" values={STATUSES} words={(v) => v} chosen={filter.status} onToggle={toggle} />
        <Boxes id={id} legend="Priority" field="priority" values={[...PRIORITIES, NONE]} words={none("priority")} chosen={filter.priority} onToggle={toggle} />
        <Boxes id={id} legend="Owner" field="owner" values={offered("owner", d, filter.owner)} words={none("owner")} chosen={filter.owner} onToggle={toggle} />
        <Boxes id={id} legend="Workstream" field="workstream" values={offered("workstream", d, filter.workstream)} words={none("workstream")} chosen={filter.workstream} onToggle={toggle} />
        <Boxes id={id} legend="Use case" field="use_case" values={offered("use_case", d, filter.use_case)} words={none("use_case")} chosen={filter.use_case} onToggle={toggle} />
        <Choice id={id} label="Sort by" field="sort" values={SORTS} words={WORDS.sort} value={filter.sort} onPick={pick} />
        <label class="wil-sel" data-field="max"><span>Most rows</span>
          <input type="number" name="max" min="1" max={MAX_ROWS} step="1" value={filter.max} onChange={commitMax} onKeyDown={keys} />
        </label>
        <Boxes id={id} legend="Columns at full width" field="columns" values={COLUMNS} words={(v) => WORDS.columns[v]} chosen={filter.columns} onToggle={toggleColumn} />
        <label class="wil-sel wil-capf" data-field="caption"><span>Caption (optional)</span>
          <input type="text" name="caption" value={filter.caption} onInput={capInput} onChange={commitCaption} onKeyDown={keys} />
        </label>
      </div>
      <p class="quiet" data-wil-say="count">{saved ? `${plural(rows.length, "work item")} listed now. ${ONLY_SHOWN}` : ONLY_SHOWN}</p>
      {saved && !rows.length ? <p class="wil-none" data-wil-say="none" role="status">{NO_MATCH}</p> : null}
      {saved && rows.length ? <Rows rows={rows} columns={list.columns} now={now} open={(rid) => openPeek(rid, "item")} /> : null}
      {saved && list.caption && rows.length ? <p class="wil-cap">{list.caption}</p> : null}
    </div>
  );
}
