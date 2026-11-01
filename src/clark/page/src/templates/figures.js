// The Key figures templates' shared pure part (#96, store types figures4 and figures3): no DOM, no Preact, no clock (today is passed
// in). Reads a section's stored body (the served page) or the figures the published file carries (section.figures), and works the live
// figures out from the rows the file would keep (logic/publishable.js), with the same values, words and colours as
// section_kinds/_figures.py, which works them out at publish time (a test runs both over the same rows). Counts come from the
// At a glance tiles (glanceTiles.js tiles), so a figure here is the number a tile shows.
import { tiles, TILE_TITLES } from "../glanceTiles.js";
import { rowsOf, isOpen, dayNumber, showDate, plural, colourOf } from "../workItems.js";
import { keptRows, rulesFor } from "../logic/publishable.js";
import { dateWords } from "./safe.js";

export const PLACES = { figures4: 4, figures3: 3 };
export const METRICS = [["overdue", TILE_TITLES.overdue], ["risks", TILE_TITLES.risks], ["decisions", TILE_TITLES.decisions]];
export const LIMITS = { label: 60, value: 30, detail: 80 };
const KIND_OF = { overdue: "actions", risks: "raid", decisions: "decisions" };
const RANK = { g: 1, a: 2, r: 3 };
const text = (v) => (typeof v === "string" ? v : typeof v === "number" ? String(v) : "");

// The stored slots of a section (an array no longer than its places): a body that is empty or does not read gives none.
export function slotsOf(section, places) {
  let v = null;
  try { v = typeof section.body === "string" && section.body ? JSON.parse(section.body) : null; } catch (e) { v = null; }
  const list = v && typeof v === "object" && Array.isArray(v.figures) ? v.figures.slice(0, places) : [];
  return list.map((s) => (s && s.mode === "live" && METRICS.some(([k]) => k === s.metric)
    ? { mode: "live", metric: s.metric }
    : { mode: "typed", label: text(s && s.label), value: text(s && s.value), detail: text(s && s.detail), asof: text(s && s.asof) }));
}

// The body to save for these slots: trailing empty ones dropped; none left is no content ("").
export function bodyOf(slots) {
  const empty = (s) => s.mode === "typed" && !s.label && !s.value && !s.detail && !s.asof;
  const list = slots.slice();
  while (list.length && empty(list[list.length - 1])) list.pop();
  return list.length ? JSON.stringify({ v: 1, figures: list }) : "";
}

// The live figures by metric, from the rows the file would keep: { overdue, risks, decisions } each { label, value, detail, rag }.
// A metric with no row of its kind to count is absent (a hidden section, or none at all).
export function liveFigures(d, today) {
  if (!d || dayNumber(today) === null) return {};
  const rules = rulesFor({ code: d.project && d.project.code, hidden: (d.report_hidden || []).map((h) => (h && h.item_id) || h),
    labelRules: d.label_rules || [], labels: d.labels || {}, sections: d.report_sections || [] });
  const kept = Object.fromEntries(Object.values(KIND_OF).map((k) => [k, keptRows(d, k, rules)]));
  const rows = rowsOf({ ...kept, use_cases: d.use_cases || [], milestones: d.milestones || [] });
  const by = Object.fromEntries(tiles(rows, today).map((t) => [t.key, t]));
  const out = {};
  const open = rows.filter((r) => isOpen(r));
  if (kept.actions.length) {
    const n = open.filter((r) => r.kind === "action").length;
    out.overdue = { label: TILE_TITLES.overdue, value: by.overdue.value, detail: n ? `of ${plural(n, "open action")}` : "No open actions", rag: by.overdue.value ? "r" : "g" };
  }
  if (kept.raid.length) {
    const live = open.filter((r) => r.kind !== "action" && r.kind !== "decision");
    const worst = live.reduce((w, r) => { const l = colourOf(r.priority).class; return (RANK[l] || 0) > (RANK[w] || 0) ? l : w; }, "");
    out.risks = { label: TILE_TITLES.risks, value: by.risks.value, rag: worst || "g",
      detail: !live.length ? "None open" : live.length === 1 ? "of 1 open risk or issue" : `of ${live.length} open risks and issues` };
  }
  if (kept.decisions.length) {
    const pending = rows.filter((r) => r.kind === "decision" && r.status === "Pending");
    const dated = pending.map((r) => r.needed_by).filter((x) => dayNumber(x) !== null).sort();
    out.decisions = { label: TILE_TITLES.decisions, value: by.decisions.value, rag: pending.length ? "a" : "g",
      detail: !pending.length ? "None waiting" : dated.length ? `Oldest needed by ${showDate(dated[0])}` : "No date needed by" };
  }
  return out;
}

// The figures to draw for a section, in order: { label, value, detail, rag (g a r n), asof (DD-MM-YYYY or "") }. The published file
// carries them already worked out (section.figures); the served page works them out from the stored body and the live rows. A typed
// figure with no label or no number, and a live one with nothing to count, is not drawn.
export function figuresOf(section, d, today, places) {
  if (Array.isArray(section.figures)) {
    return section.figures.slice(0, places).map((f) => ({ label: text(f && f.label), value: text(f && f.value), detail: text(f && f.detail),
      rag: ["g", "a", "r"].includes(f && f.rag) ? f.rag : "n", asof: dateWords(text(f && f.asof)) })).filter((f) => f.label && f.value);
  }
  const slots = slotsOf(section, places);
  const live = slots.some((s) => s.mode === "live") ? liveFigures(d, today) : {};
  const out = [];
  for (const s of slots) {
    if (s.mode === "live") { const f = live[s.metric]; if (f) out.push({ ...f, value: text(f.value), asof: "" }); }
    else if (s.label && s.value) out.push({ label: s.label, value: s.value, detail: s.detail, rag: "n", asof: dateWords(s.asof) });
  }
  return out;
}
