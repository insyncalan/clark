// The Gantt page's host on clark's real store (#926): the plan is data.gantt_lines, the settings are project fields, and every change goes
// through the existing change route (stores/changes.js: one request at a time, the reply redraws, the toast offers Undo). The wire format of a
// change is in ONE place: lineRequest() and settingsRequest() below. Not mounted anywhere yet: the data layer (kind 'gantt_lines' and the
// project fields) is built by another step, and the sections page scope too.
import { data, project } from "../../stores/report.js";
import { change, undoLast } from "../../stores/changes.js";
import { DEFAULT_SETTINGS, sortLines } from "./ganttPage.js";

const KIND = "gantt_lines";

// ops (logic/ganttPage.js diff) -> change requests
export function lineRequest(o) {
  if (o.op === "new") return { kind: KIND, op: "new", id: o.id, values: o.values, place: "cell" };
  if (o.op === "delete") return { kind: KIND, op: "delete", id: o.id, place: "cell" };
  return { kind: KIND, op: "update", id: o.id, changes: o.changes, place: "cell" };
}
export const settingsRequest = (changes) => ({ kind: "projects", op: "update", changes, place: "cell" });

export function createStoreHost() {
  const read = () => {
    const d = data.value || {};
    const p = d.project || {};
    const settings = { ...DEFAULT_SETTINGS };
    for (const k of Object.keys(DEFAULT_SETTINGS)) if (p[k] !== undefined && p[k] !== null) settings[k] = p[k];
    if (typeof settings.gantt_hidden_columns === "string") settings.gantt_hidden_columns = settings.gantt_hidden_columns.split(",").map((s) => s.trim()).filter(Boolean);
    return { project: p, settings, lines: sortLines(d.gantt_lines || []), toast: null };
  };
  return {
    ownUndoKey: false,
    read,
    subscribe: (fn) => {
      let first = true;
      const stop = data.subscribe(() => { if (first) { first = false; return; } fn(); });
      return stop;
    },
    async applyLines(ops, words) {
      for (const o of ops) await change(lineRequest(o), words);     // one request after another; the toast of the last one stays
      return { ok: true };
    },
    saveSettings: (changes, words) => change(settingsRequest(changes), words),
    undoLast: () => undoLast(project.value),
    dismiss() {},
  };
}
