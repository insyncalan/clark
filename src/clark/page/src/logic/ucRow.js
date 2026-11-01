// What a use case's row on the Dashboard needs in Edit for its next steps and its links (#485). Plain functions, no DOM and no store,
// so the row and the tests read them alone. Nothing here saves: the row sends each result through the one change path.
import { isOpen, dueField, showDate, pillOf } from "../workItems.js";

/** "Owner: what it is" as the box takes it: the words before the first colon (2 to 40 characters) are the owner, the rest the step.
 * With no owner the whole text is the step and the owner is left to clark ("TBC"). Nothing typed, or only an owner, gives null. */
export function splitStep(text) {
  const t = String(text == null ? "" : text).trim();
  if (!t) return null;
  const m = /^\s*([^:]{2,40}):\s*(.+)$/.exec(t);
  const owner = m ? m[1].trim() : "", title = (m ? m[2] : t).trim();
  return title ? { owner, title } : null;
}

/** A day as YYYY-MM-DD, `n` days after `iso` (a real calendar day; the local clock is never read here). */
export function addDays(iso, n) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso));
  if (!m) return "";
  const t = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3] + n));
  return `${String(t.getUTCFullYear()).padStart(4, "0")}-${String(t.getUTCMonth() + 1).padStart(2, "0")}-${String(t.getUTCDate()).padStart(2, "0")}`;
}

/** The values of a new next step: its words, its owner when one was typed, the day a week from `today`, and the use case it names. */
export function stepValues(parts, ucId, today) {
  const v = { description: parts.title, use_case: ucId };
  if (parts.owner) v.owner = parts.owner;
  const due = addDays(today, 7);
  if (due) v.due_date = due;
  return v;
}

/** The kinds the link box can narrow to, in the order it lists them: [[key, words, rowKind]]. */
export const KINDS = [["A", "Actions", "action"], ["R", "Risks", "risk"], ["I", "Issues", "issue"], ["D", "Decisions", "decision"]];

/** The open work items that are not yet linked to the use case `ucId`: [{id, title, kind, meta, pill, search}]. `all` is workItems.rowsOf(d);
 * `d` is the project's data (it holds the use_case link of each action, risk and decision). `meta` is the line under the title:
 * "ABC-A-001 · Sam · 12-11-2026 · now in use case 1.2"; `pill` is the item's status as the Work items list shows it. */
export function linkable(d, all, ucId, today) {
  const link = {};
  for (const r of [...((d && d.actions) || []), ...((d && d.raid) || []), ...((d && d.decisions) || [])]) if (r.use_case) link[r.id] = r.use_case;
  const refs = Object.fromEntries(((d && d.use_cases) || []).map((u) => [u.id, u.ref || u.id]));
  return all.filter((r) => isOpen(r) && link[r.id] !== ucId).map((r) => {
    const due = dueField(r), other = link[r.id] && refs[link[r.id]] ? ` · now in use case ${refs[link[r.id]]}` : "";
    const meta = `${r.id} · ${String(r.owner || "").trim() || "No owner"}${due ? ` · ${showDate(due)}` : ""}${other}`;
    return { id: r.id, title: r.title, kind: r.kind, meta, pill: pillOf(r, today), search: [r.id, r.title, r.owner, r.workstream, refs[link[r.id]]].filter(Boolean).join(" ").toLowerCase() };
  });
}

/** The rows the box shows: the kind chosen ("" is all) and the words typed (every word must be in the row's text). */
export function narrow(items, kind, query) {
  const want = (KINDS.find(([k]) => k === kind) || [])[2];
  const terms = String(query || "").toLowerCase().split(/\s+/).filter(Boolean);
  return items.filter((r) => (!want || r.kind === want) && terms.every((t) => r.search.includes(t)));
}

/** "3 work items linked to use case 1.1." */
export const linkedWords = (n, name) => `${n} work item${n === 1 ? "" : "s"} linked to use case ${name}.`;
