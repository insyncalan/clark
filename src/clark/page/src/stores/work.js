// What the Work items page remembers and shows beyond its filters (#68, #81): the layout (table or board), Group by, the
// swimlanes and the collapsed columns, per project, kept in this browser (logic/board.js owns the rules and the storage key).
// Not in the address and not in the database. Full screen is not remembered: it is a moment, not a taste.
import { signal, computed } from "@preact/signals";
import { project, data, fromFile, query, found } from "./report.js";
import { readState, writeState, rowsFor, ctxFor, browserStorage } from "../logic/board.js";
import { searchRows } from "../clientView.js";

// A published file keeps its own choices under its own key (stores/clientMemory.js), never the editor's: here it uses memory only.
const mem = {};
const memoryOnly = { getItem: (k) => (k in mem ? mem[k] : null), setItem: (k, v) => { mem[k] = String(v); } };
const storage = () => (fromFile.value ? memoryOnly : browserStorage());
const kept = {};                                       // project -> state, so a browser that refuses storage still changes the view
const tick = signal(0);

export const work = computed(() => { void tick.value; const code = project.value; return kept[code] || readState(code, storage()); });

export function setWork(patch) {
  const code = project.value;
  kept[code] = writeState(code, { ...work.value, ...patch }, storage()).state;
  tick.value++;
}

export const full = signal(false);                     // the board fills the window (#81)
export const announce = signal("");                    // what a screen reader is told when the view changes

// The rows with what a move needs (table and milestone id), and the context the grouping needs.
export const itemRows = computed(() => (data.value ? searchRows(rowsFor(data.value), found.value, query.value) : []));
// The type switch narrows the status columns to the kinds shown (null: every kind).
export const kindsFor = (type) => ({ action: ["action"], risk: ["risk"], decision: ["decision"] }[type] || null);
export function contextFor(today, type) {
  return ctxFor(data.value || {}, { project: project.value, today, kinds: kindsFor(type) });
}
