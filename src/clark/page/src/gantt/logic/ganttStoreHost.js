// The Gantt page's host on clark's real store (row 926): the plan is data.gantt_lines, the settings are project fields, and every change goes
// through the existing change route (stores/changes.js: one request at a time, the reply redraws, the toast offers Undo and a refusal is a toast
// too). The wire format of a change is in ONE place: lineRequests() and settingsRequest() below. The server keeps a line's id as CODE-GNT-001 and the
// page shows GNT-001: the code is put back here on the way out. Dates are YYYY-MM-DD, `show` is 0 or 1, depends travels as a list of ids.
// The server numbers the lines itself (a new line goes after the line named in `after`, a move names the line it goes before), so the page's own
// place numbers (sort_order) are never sent: they are turned into `after` and `before` here.
import { data, project } from "../../stores/report.js";
import { change, undoLast } from "../../stores/changes.js";
import { ROWS_FIELD, list, strip, readStore } from "./ganttFileHost.js";

const KIND = "gantt_lines";
const SERVER_DOES = new Set(["parent", "depends"]);      // a delete takes the id out of these in its own step

const codeOf = () => (data.value && data.value.project && data.value.project.code) || project.value || "";
const full = (code, id) => (id ? `${code}-${id}` : id);

function wire(code, key, v, made) {
  const id = (x) => full(code, made.get(x) || x);
  if (key === "parent") return v ? id(v) : null;
  if (key === "depends") return list(v).map(id);
  if (key === "pct") return Math.max(0, Math.min(100, Math.round(Number(v) || 0)));
  if (key === "effort" || key === "budget") return v === "" || v === null || v === undefined ? null : Number(v);
  if (key === "show") return v && v !== "0" ? 1 : 0;
  return v;
}

// The new order the page asked for: every line that stays (stored or new) by the place number the page gave it (it numbers the whole list 1, 2, 3 ...).
function wantedOrder(stored, ops) {
  const rank = new Map(stored.map((l) => [l.id, Number(l.sort_order) || 0]));
  for (const o of ops) {
    if (o.op === "new" && o.values) rank.set(o.id, Number(o.values.sort_order) || 0);
    else if (o.op === "update" && o.changes && o.changes.sort_order !== undefined) rank.set(o.id, Number(o.changes.sort_order) || 0);
  }
  const gone = new Set(ops.filter((o) => o.op === "delete").map((o) => o.id));
  return [...rank.entries()].filter(([id]) => !gone.has(id)).sort((a, b) => a[1] - b[1]).map(([id]) => id);
}

// The page's steps (logic/ganttPage.js diff) as change requests, in the order they are sent. Each is a function of `made` (page id -> real id of a
// line made by an earlier request) because a new line's id is the server's.
export function lineRequests(code, stored, ops) {
  const want = wantedOrder(stored, ops);
  const hasNew = ops.some((o) => o.op === "new"), hasDelete = ops.some((o) => o.op === "delete");
  const out = [];
  for (const o of ops) {
    if (o.op !== "new") continue;
    const at = want.indexOf(o.id);
    out.push((made) => {
      const values = {};
      for (const [k, v] of Object.entries(o.values)) {
        if (k === "sort_order") continue;
        if (v === "" || v === null || v === undefined || (Array.isArray(v) && !v.length)) { if (k === "show") values.show = 0; continue; }      // left out, the server fills in what it knows
        values[k] = wire(code, k, v, made);
      }
      if (!values.start) delete values.end;          // no start (a plan with no line yet): the server gives both, from today
      const above = at > 0 ? want[at - 1] : null;
      return { req: { kind: KIND, op: "new", values, after: above ? full(code, made.get(above) || above) : null, place: "cell" }, madeAs: o.id, top: at === 0 && stored.length ? stored[0].id : null };
    });
  }
  for (const o of ops) {
    if (o.op !== "update") continue;
    const keys = Object.keys(o.changes).filter((k) => k !== "sort_order" && !(hasDelete && SERVER_DOES.has(k)));
    if (!keys.length) continue;
    out.push((made) => ({ req: { kind: KIND, op: "update", id: full(code, made.get(o.id) || o.id), changes: Object.fromEntries(keys.map((k) => [k, wire(code, k, o.changes[k], made)])), place: "cell" } }));
  }
  if (!hasNew) {          // lines that only changed their place: the server moves them one at a time
    const now = stored.filter((l) => want.includes(l.id)).map((l) => l.id);
    for (let i = 0; i < want.length; i++) {
      if (now[i] === want[i]) continue;
      const id = want[i], before = now[i];
      now.splice(now.indexOf(id), 1);
      now.splice(i, 0, id);
      out.push(() => ({ req: { kind: KIND, op: "move", id: full(code, id), before: full(code, before), place: "cell" } }));
    }
  }
  for (const o of ops) if (o.op === "delete") out.push(() => ({ req: { kind: KIND, op: "delete", id: full(code, o.id), place: "cell" } }));
  return out;
}

export function settingsRequest(changes) {
  const out = {};
  for (const [k, v] of Object.entries(changes)) {
    if (k === "gantt_plan_rows") out[ROWS_FIELD] = v === null || v === undefined ? null : Math.round(Number(v));
    else if (k === "gantt_hidden_columns") out[k] = list(v).join(",");
    else out[k] = v;
  }
  return { kind: "projects", op: "update", changes: out, place: "cell" };
}

export function createStoreHost() {
  const read = () => readStore(data.value);
  return {
    ownUndoKey: false,
    serverUndo: true,          // the table's own Undo asks the app's (the server's history), not a list kept in the table
    read,
    subscribe: (fn) => {
      let first = true;
      return data.subscribe(() => { if (first) { first = false; return; } fn(); });
    },
    async applyLines(ops, words) {
      const code = codeOf();
      const made = new Map();
      for (const make of lineRequests(code, read().lines, ops)) {
        const { req, madeAs, top } = make(made);
        const reply = await change(req, words);              // one request after another; the toast of the last one stays
        if (!reply) return { ok: false };                    // refused: the toast says why, and nothing after it is sent
        if (madeAs) {
          made.set(madeAs, strip(code, reply.ref));
          if (top && !(await change({ kind: KIND, op: "move", id: reply.ref, before: full(code, top), place: "cell" }, words))) return { ok: false };      // at the very top: made at the end, then moved before the first
        }
      }
      return { ok: true };
    },
    saveSettings: (changes, words) => change(settingsRequest(changes), words),
    undoLast: () => undoLast(project.value),
    dismiss() {},
  };
}
