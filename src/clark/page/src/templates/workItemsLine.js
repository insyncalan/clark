// Work items list: the filter LINE for the Edit part (row 1113). The same words the Work items page's filter line reads
// (logic/filterQueryParse.js does the reading), turned into the saved filter's own choices and back. Pure: no DOM, no store.
//   type:risk,issue   status:Open   owner:"Pat Demo"   workstream:x   usecase:UC1   priority:High   due:overdue   is:open  is:closed
// A word this list cannot use (a field it has no choice for, a minus sign, has: or no:, free text) is named back, never guessed.
import { parseQuery, schemaOf } from "../logic/filterQueryParse.js";
import { KINDS, STATUSES, DUE, PRIORITIES, NONE, WORDS } from "./workItemsList.js";

const low = (s) => String(s == null ? "" : s).toLowerCase();
const squash = (s) => low(s).replace(/[^a-z0-9]/g, "");
const DUE_WORD = { overdue: "overdue", soon: "soon", "next7days": "soon", "in7days": "soon", none: "none", nodate: "none", later: "later" };
const FIELD = { type: "kinds", status: "status", owner: "owner", workstream: "workstream", usecase: "use_case", priority: "priority", due: "due" };
const quote = (v) => (/[\s,:"]/.test(v) ? `"${v}"` : v);

// The line a filter reads as: one word per field that has choices, then is:closed or is:all-open-and-closed as the mode says.
export function lineOf(filter, nameOf = (f, v) => v) {
  const out = [];
  const add = (key, list, show) => { if (list.length) out.push(`${key}:${list.map((v) => quote(show(v))).join(",")}`); };
  add("type", filter.kinds, (v) => v);
  add("status", filter.status, (v) => v);
  add("due", filter.due, (v) => v);
  add("priority", filter.priority, (v) => (v === NONE ? "none" : v));
  add("owner", filter.owner, (v) => (v === NONE ? "none" : v));
  add("workstream", filter.workstream, (v) => (v === NONE ? "none" : v));
  add("usecase", filter.use_case, (v) => (v === NONE ? "none" : nameOf("use_case", v)));
  if (filter.mode === "closed") out.push("is:closed");
  else if (filter.mode === "all") out.push("is:open,closed");
  return out.join(" ");
}

// The chips a filter shows: [{field, value, label}] in the line's order. `field` is the filter's key, `value` what is stored.
export function chipsOf(filter, nameOf = (f, v) => v) {
  const out = [];
  const add = (field, list, label) => { for (const v of list) out.push({ field, value: v, label: label(v) }); };
  add("kinds", filter.kinds, (v) => `Type: ${WORDS.kinds[v] || v}`);
  add("status", filter.status, (v) => `Status: ${v}`);
  add("due", filter.due, (v) => `Due: ${WORDS.due[v] || v}`);
  add("priority", filter.priority, (v) => `Priority: ${v === NONE ? WORDS.none.priority : v}`);
  add("owner", filter.owner, (v) => `Owner: ${v === NONE ? WORDS.none.owner : v}`);
  add("workstream", filter.workstream, (v) => `Workstream: ${v === NONE ? WORDS.none.workstream : v}`);
  add("use_case", filter.use_case, (v) => `Use case: ${v === NONE ? WORDS.none.use_case : nameOf("use_case", v)}`);
  return out;
}

// A typed line read onto a filter. Returns { filter } with the choices the line names (every choice field is set from the line,
// so a word taken out of the line is taken off the list), or { problem } in plain words and nothing is to be saved.
// `known` lists use cases as [{id, names: [text it may be typed as]}] so a use case can be typed by its name or its id.
export function readLine(line, base, known = []) {
  const parsed = parseQuery(line, schemaOf());
  const next = { ...base, kinds: [], status: [], due: [], priority: [], owner: [], workstream: [], use_case: [] };
  let open = false, closed = false;
  for (const t of parsed.tokens) {
    if (t.error) return { problem: `"${t.raw}" is not a word the filter line knows. Try type:, status:, owner:, workstream:, usecase:, priority:, due: or is:.` };
    if (t.kind === "state") {
      if (t.negate) return { problem: `A minus sign is not used in this list's filter. Name what you want, for example is:open.` };
      for (const s of t.states) {
        if (s === "open") open = true; else if (s === "closed") closed = true;
        else return { problem: `"is:${s}" is not a choice this list has. Use is:open or is:closed.` };
      }
      continue;
    }
    if (t.kind !== "field" || t.negate || !FIELD[t.field]) {
      return { problem: `"${t.raw}" is not a choice this list has. Use type:, status:, owner:, workstream:, usecase:, priority:, due: or is:open.` };
    }
    const key = FIELD[t.field];
    for (const raw of t.values) {
      const v = low(raw);
      let got = null;
      if (key === "kinds") got = KINDS.find((k) => squash(k) === squash(v) || squash(WORDS.kinds[k]) === squash(v));
      else if (key === "status") got = STATUSES.find((s) => low(s) === v);
      else if (key === "priority") got = v === "none" ? NONE : PRIORITIES.find((p) => low(p) === v);
      else if (key === "due") got = DUE_WORD[squash(v)];
      else if (v === "none") got = NONE;
      else if (key === "use_case") { const u = known.find((k) => k.id === raw || k.names.some((n) => low(n) === v)); got = u ? u.id : null; }
      else got = raw;
      if (!got) return { problem: `"${raw}" is not a value ${t.field} can take here. Check the spelling, or use the choices under Choose from lists.` };
      if (!next[key].includes(got)) next[key].push(got);
    }
  }
  next.mode = open && closed ? "all" : closed ? "closed" : "open";
  return { filter: next };
}
