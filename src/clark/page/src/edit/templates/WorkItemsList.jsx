// Work items list (#96), store type "workitems": its Edit part. The filter is set in place: every choice that is committed (a box
// ticked, a choice picked, the number or the caption left with Enter or Tab) saves the whole filter as ONE change (one step, one
// Undo, place "report"). Under it, the rows it lists now, exactly as View and the published page will show them; each row opens
// its peek (a click, or Enter). An empty match says so here, and only here: View and the published page leave the section out.
import { StartPrompt } from "../StartPrompt.jsx";
import { startOr } from "../startingText.js";
import { useRef, useState } from "preact/hooks";
import { ColsPanel } from "../ColumnsMenu.jsx";      // row 1286 (B-M5b): the Columns menu, kept inside a short window
import { Icon } from "../../components/Icon.jsx";
import { columnIcon } from "../../menuIcons.js";
import { data, openPeek, rows as reportRows, filterCtx } from "../../stores/report.js";
import { LineBox } from "../../components/FilterLine.jsx";
import { change, say } from "../../stores/changes.js";
import { Rows, Listing, Foot, today, classicTheme } from "../../templates/WorkItemsList.jsx";
import { sortChoices, COLUMNS, MAX_ROWS, MAX_CAPTION, WORDS, defaults, filterOf, bodyOf,
  editListOf, drawRows, drawn, idsToShow } from "../../templates/workItemsList.js";
import { Eye } from "../cells/Eye.jsx";
import { Cell } from "../cells/Cell.jsx";
import { useColWidths, useColOrder } from "../colWidths.jsx";

import { NewTile } from "../../components/NewTile.jsx";
import { addItem, ADDABLE } from "../addItem.js";
import { plural } from "../../workItems.js";
import { lineOf, readLine } from "../../templates/workItemsLine.js";
import { Tabs } from "./WorkItemsTabs.jsx";

export const SAVED = "Work items list changed.";
export const COLUMNS_MENU = "Columns";      // row 1268: the label of the menu a right click on a column heading opens
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

export const CONFIGURE_LABEL = "Configure this list";      // row 1268: the words of the approved mock-up

// Row 1268, the approved Add: a + that opens a short menu (Action, Risk, Issue, Decision); a pick makes the item at once and opens its peek.
export const ADD_WORD = "Add work item";
export const ADD_ITEMS = ADDABLE.map((k) => ({ kind: k, word: k[0].toUpperCase() + k.slice(1) }));
const RAID = ["risk", "action", "issue", "decision"];      // row 1195: the approved mock-up's order, drawn only under the Classic layer (Cards keeps ADDABLE's order)
const RAID_ITEMS = RAID.map((k) => ({ kind: k, word: k[0].toUpperCase() + k.slice(1) }));
const addOne = (kind) => addItem(kind, "report", true);

export function Edit({ section }) {
  const [cfg, setCfg] = useState(false);          // row 1268: the Configure box (the gear) is open
  const gearRef = useRef(null);
  const cw = useColWidths(`wil-${section.id}`, classicTheme());      // row 1268, item 12: the page's column widths, kept for this list
  const ord = useColOrder(`wil-${section.id}`);     // row 1195: the order of the columns (Classic), kept for this list
  const [tick, setTick] = useState(0);              // a refused save draws the form again from what is saved
  const d = data.value || {};
  const saved = filterOf(section);
  const filter = saved || defaults();
  const id = `wil-${section.id}`;
  const ucName = Object.fromEntries((d.use_cases || []).map((u) => [u.id, u.ref ? `${u.ref} ${u.title || ""}`.trim() : (u.title || u.id)]));
  const nameOf = (f, v) => ucName[v] || v;
  const known = (d.use_cases || []).map((u) => ({ id: u.id, names: [u.title, u.ref, u.ref ? `${u.ref} ${u.title || ""}`.trim() : ""].filter(Boolean) }));

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
  const toggleColumn = (field, v) => {
    const cur = latest();
    const next = cur.columns.includes(v) ? cur.columns.filter((x) => x !== v) : COLUMNS.filter((c) => c === v || cur.columns.includes(c));
    if (!next.length) { say("problem", "Choose at least one column to show."); setTick((n) => n + 1); return; }
    save({ ...cur, columns: next });
  };
  // Row 1268: a right click on a column heading (or Shift+F10) opens one menu of the columns, each ticked when shown, ID among them; a press does what its box in Configure does.
  const [at, setAt] = useState(null);
  const headProps = {
    onContextMenu: (e) => { e.preventDefault(); setAt(e.target.closest("th") || e.currentTarget); },
    onKeyDown: (e) => { if (e.key === "ContextMenu" || (e.key === "F10" && e.shiftKey)) { e.preventDefault(); setAt(e.target.closest("th") || e.currentTarget); } },
  };
  const colMenu = at ? (
    <ColsPanel label={COLUMNS_MENU} cls="cols-menu" anchor={at} fixed="start" onClose={() => setAt(null)}>
      {COLUMNS.map((c) => { const on = filter.columns.includes(c); return (
        <button key={c} type="button" role="menuitemcheckbox" aria-checked={on ? "true" : "false"} data-col-name={WORDS.columns[c]} tabIndex={-1} onClick={() => toggleColumn("columns", c)}>
          <Icon name={columnIcon(c)} cls="mi" /><span class="ck" aria-hidden="true">{on ? "\u2713" : ""}</span><span class="cols-name">{WORDS.columns[c]}</span>
        </button>); })}
    </ColsPanel>
  ) : null;
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
  // The filter line is the Work items page's own box (components/FilterLine.jsx LineBox: chips, suggestions, count, x), row 1268. The typed
  // line is read onto the filter about 400 ms after the last key and saved as ONE change; a word the list cannot use is said in plain
  // words and nothing is saved. A chip's x takes that one choice off (the box applies the shorter line).
  const applyLine = (text) => {
    const cur = latest();
    if (text.trim() === lineOf(cur, nameOf)) return;
    const r = readLine(text, cur, known);
    if (r.problem) { say("problem", r.problem); return; }
    save(r.filter);
  };
  const keys = (e) => {
    if (e.key === "Enter") { e.preventDefault(); e.currentTarget.blur(); }
    else if (e.key === "Escape") { e.preventDefault(); e.currentTarget.value = e.currentTarget.name === "max" ? String(filter.max) : filter.caption; e.currentTarget.blur(); }
  };

  const now = today();
  const list = editListOf(section, d, now);
  const rows = drawRows(idsToShow(list, true), drawn(d, true));
  return (
    <div class="wil wil-edit" key={tick} data-wil-edit="" data-wil-id={id}>
      {saved ? null : <><StartPrompt id="work-items" /><p class="quiet wil-say" data-wil-say="not-yet">{NOT_YET}</p></>}
      <div class="wil-line" data-wil-line="">
        <LineBox line={lineOf(filter, nameOf)} now={() => lineOf(latest(), nameOf)} apply={applyLine} rows={reportRows.value} ctx={filterCtx()}
          ids={{ input: `${id}-line`, list: `${id}-line-list`, count: `${id}-line-count`, x: `${id}-line-x`, msg: `${id}-line-msg`, gloss: `${id}-line-gloss`, opt: `${id}-line-o` }} label="Filter" />
      </div>
      <Tabs add={<div class="wil-add" data-wil-add=""><NewTile word={ADD_WORD} kind="" items={classicTheme() ? RAID_ITEMS : ADD_ITEMS} onAdd={addOne} id={`${id}-add`} iconOnly /></div>} section={section} filter={filter} d={d} now={now} known={known} nameOf={nameOf} apply={(next) => save({ ...latest(), ...next })} />
      <div class="wil-form">
        <div class="wil-cw" data-wil-cw="" onKeyDown={(e) => { if (e.key === "Escape" && cfg) { e.preventDefault(); e.stopPropagation(); setCfg(false); if (gearRef.current) gearRef.current.focus(); } }}>
          <button type="button" class="wil-gear" ref={gearRef} data-wil-gear="" aria-haspopup="dialog" aria-expanded={cfg ? "true" : "false"} aria-label={CONFIGURE_LABEL} title="Configure" onClick={() => setCfg(!cfg)}>
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></svg>
          </button>
          <div class="wil-cfg" role={cfg ? "dialog" : undefined} aria-label={CONFIGURE_LABEL} hidden={!cfg}>
            <h4>{CONFIGURE_LABEL}</h4>
          <Choice id={id} label="Sort by" field="sort" values={sortChoices(classicTheme(), filter.sort)} words={WORDS.sort} value={filter.sort} onPick={pick} />
          <label class="wil-sel" data-field="max"><span>Most rows</span>
            <input type="number" name="max" min="1" max={MAX_ROWS} step="1" value={filter.max} onChange={commitMax} onKeyDown={keys} />
          </label>
          <Boxes id={id} legend="Columns at full width" field="columns" values={COLUMNS} words={(v) => WORDS.columns[v]} chosen={filter.columns} onToggle={toggleColumn} />
            <label class="wil-sel wil-capf" data-field="caption"><span>Footnote (optional)</span>
              <input type="text" name="caption" placeholder={startOr("Shown above the list", "work-items", "caption")} value={filter.caption} onInput={capInput} onChange={commitCaption} onKeyDown={keys} />
            </label>
            <div class="wil-cacts"><button type="button" data-wil-cfgdone="" onClick={() => { setCfg(false); if (gearRef.current) gearRef.current.focus(); }}>Done</button></div>
          </div>
        </div>
      </div>
      <p class="quiet" data-wil-say="count">{saved ? `${plural(rows.length, "work item")} listed now. ${ONLY_SHOWN}` : ONLY_SHOWN}</p>
      {saved && !rows.length ? <p class="wil-none" data-wil-say="none" role="status">{NO_MATCH}</p> : null}
      {saved && rows.length && rows.length === list.off.length ? <p class="wil-none" data-wil-say="all-hidden" role="status">{ALL_HIDDEN}</p> : null}
      {saved && list.caption && rows.length ? <p class="wil-cap">{list.caption}</p> : null}
      {saved && rows.length ? <Listing max={list.max} count={rows.length} sid={section.id}><Rows rows={rows} columns={list.columns} now={now} open={(rid) => openPeek(rid, "item")} Eye={Eye} Cell={Cell} cw={cw} ord={ord} head={headProps} /></Listing> : null}
      {colMenu}
      {saved && rows.length ? <Foot section={section} total={rows.length} max={list.max} edit nameOf={nameOf} /> : null}
    </div>
  );
}
