// Work items list: the filter LINE for the Edit part (row 1113). The same words the Work items page's filter line reads
// (logic/filterQueryParse.js does the reading), turned into the saved filter's own choices and back. Pure: no DOM, no store.
//   type:risk,issue   status:Open   owner:"Pat Demo"   workstream:x   usecase:UC1   priority:High   due:overdue   is:open  is:closed
// A word this list cannot use (a field it has no choice for, a minus sign, has: or no:, free text) is named back, never guessed.
import { parseQuery, schemaOf } from "../logic/filterQueryParse.js";
import { CLIENT_FIELDS, CLIENT_IS } from "../logic/filterLine.js";
import { KINDS, STATUSES, DUE, PRIORITIES, NONE, WORDS, PRESENT } from "./workItemsList.js";

const low = (s) => String(s == null ? "" : s).toLowerCase();
const squash = (s) => low(s).replace(/[^a-z0-9]/g, "");
const DUE_WORD = { overdue: "overdue", soon: "soon", "next7days": "soon", "in7days": "soon", none: "none", nodate: "none", later: "later" };
const FIELD = { type: "kinds", status: "status", owner: "owner", workstream: "workstream", usecase: "use_case", priority: "priority", due: "due", milestone: "milestone" };
const WORD = Object.fromEntries(Object.entries(FIELD).map(([w, k]) => [k, w]));      // the filter's key back to the word typed
// The fields and states a client's file can answer: the section is read by the client, so it takes no more than that.
const schema = () => { const s = schemaOf(); return { fields: s.fields.filter((f) => CLIENT_FIELDS.includes(f.key)), states: s.states.filter((x) => CLIENT_IS.includes(x)) }; };
// The filter line has no way to write a quote mark inside a value (the parser takes every quote as a bracket and drops it), so a
// value with one is written without it; readLine gives the saved value back when the line names it, so nothing is lost.
const bare = (s) => String(s == null ? "" : s).replace(/"/g, "");
const quote = (v) => { const b = bare(v); return /[\s,:]/.test(b) ? `"${b}"` : b; };

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
  add("milestone", filter.milestone || [], (v) => (v === NONE ? "none" : v));
  for (const k of Object.keys(filter.not || {})) {
    const list = filter.not[k];
    if (list.length) out.push(`-${WORD[k]}:${list.map((v) => quote(k === "priority" || k === "owner" || k === "workstream" || k === "milestone" ? (v === NONE ? "none" : v) : k === "use_case" ? (v === NONE ? "none" : nameOf("use_case", v)) : v)).join(",")}`);
  }
  for (const g of filter.has || []) out.push(`has:${g.join(",")}`);
  for (const g of filter.no || []) out.push(`no:${g.join(",")}`);
  for (const w of filter.text || []) out.push(/[\s"]/.test(w) ? `"${bare(w)}"` : bare(w));
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
  const parsed = parseQuery(line, schema());
  const next = { ...base, kinds: [], status: [], due: [], priority: [], owner: [], workstream: [], use_case: [], milestone: [],
    not: Object.fromEntries(Object.keys(base.not || {}).map((k) => [k, []])), has: [], no: [], text: [] };
  let open = false, closed = false, notOpen = false, notClosed = false;
  for (const t of parsed.tokens) {
    if (t.error) return { problem: `"${t.raw}" is not a word the filter line knows. Try type:, status:, owner:, workstream:, usecase:, priority:, due: or is:.` };
    if (t.kind === "text") { const w = (base.text || []).find((x) => bare(x) === t.text) || t.text; if (!next.text.includes(w)) next.text.push(w); continue; }
    if (t.kind === "presence") {
      const keys = t.fields.filter((k) => PRESENT.includes(k));
      if (keys.length !== t.fields.length) return { problem: `"${t.raw}" is not a choice this list has. Use type:, status:, owner:, workstream:, usecase:, priority:, due: or is:open.` };
      (t.present ? next.has : next.no).push(PRESENT.filter((k) => keys.includes(k)));
      continue;
    }
    if (t.kind === "state") {
      if (t.negate) {
        const one = t.states.length === 1 ? t.states[0] : "";
        if (one === "open") notOpen = true; else if (one === "closed") notClosed = true;
        else if (one === "overdue") { if (!next.not.due.includes("overdue")) next.not.due.push("overdue"); }
        else return { problem: `"${t.raw}" is not a choice this list has. Use type:, status:, owner:, workstream:, usecase:, priority:, due: or is:open.` };
        continue;
      }
      for (const s of t.states) {
        if (s === "open") open = true; else if (s === "closed") closed = true;
        else if (s === "overdue" && t.states.length === 1) { if (!next.due.includes("overdue")) next.due.push("overdue"); }
        else return { problem: `"is:${s}" is not a choice this list has. Use is:open or is:closed.` };
      }
      continue;
    }
    if (t.kind !== "field" || !FIELD[t.field]) {
      return { problem: `"${t.raw}" is not a choice this list has. Use type:, status:, owner:, workstream:, usecase:, priority:, due: or is:open.` };
    }
    const key = FIELD[t.field], into = t.negate ? next.not : next;
    for (const raw of t.values) {
      const v = low(raw);
      let got = null;
      if (key === "kinds") got = KINDS.find((k) => squash(k) === squash(v) || squash(WORDS.kinds[k]) === squash(v));
      else if (key === "status") got = STATUSES.find((s) => low(s) === v);
      else if (key === "priority") got = v === "none" ? NONE : PRIORITIES.find((p) => low(p) === v);
      else if (key === "due") got = DUE_WORD[squash(v)];
      else if (v === "none") got = NONE;
      else if (raw === "@me") got = null;
      else if (key === "use_case") {
        const saved = (t.negate ? (base.not || {}).use_case : base.use_case) || [];
        const hits = known.filter((k) => k.id === raw || k.names.some((n) => low(bare(n)) === v));
        const byId = hits.filter((k) => k.id === raw);
        const ids = [...new Set((byId.length ? byId : hits).map((k) => k.id))];
        if (ids.length > 1 && !ids.every((i) => saved.includes(i))) return { problem: `"${raw}" is not a value ${t.field} can take here. Check the spelling, or use the choices under Choose from lists.` };
        if (ids.length) { for (const i of ids) if (!into[key].includes(i)) into[key].push(i); continue; }
        got = saved.includes(raw) ? raw : null;      // a use case that is gone stays on the list as it was saved, and matches nothing
      } else got = ((t.negate ? (base.not || {})[key] : base[key]) || []).find((x) => bare(x) === raw) || raw;
      if (!got) return { problem: `"${raw}" is not a value ${t.field} can take here. Check the spelling, or use the choices under Choose from lists.` };
      if (!into[key].includes(got)) into[key].push(got);
    }
  }
  if (notOpen && notClosed) return { problem: `"-is:open -is:closed" is not a choice this list has. Use type:, status:, owner:, workstream:, usecase:, priority:, due: or is:open.` };
  const wantOpen = open || notClosed, wantClosed = closed || notOpen;
  next.mode = wantOpen && wantClosed ? "all" : wantClosed ? "closed" : "open";
  return { filter: next };
}
