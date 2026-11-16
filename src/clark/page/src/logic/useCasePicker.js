// Row 1234: the add-a-use-case picker's logic. Plain functions, no DOM, no store, no imports, so a node test runs them alone.
// A row is the shape useCasesList.listOf gives ({id, ref, name, status, commitment, open, total}); `steps` (open steps) may be added by the caller.
// State: {q, filters: {fieldKey: {mode: "is" | "not", values: [..]}}, picked: [ids]}. Nothing here saves: the caller gets the ids.
// Words the owner has not ruled on yet (row 1234). One constant each so a ruling is one edit; the picker types none of them elsewhere.
export const UNRULED_OPEN_STEPS = "Open steps";
export const UNRULED_RESULT = (shown, total) => `Result: ${shown} of ${total} shown`;
export const UNRULED_ADD = (n) => (n ? `Add ${n}` : "Add selected"); // at 0 no number; "Add selected" is the old picker's word
export const FIELDS = [
  { key: "status", label: "Status", get: (r) => r.status },
  { key: "commitment", label: "Commitment", get: (r) => r.commitment },
  { key: "steps", label: UNRULED_OPEN_STEPS, more: true, get: (r) => r.steps },
  { key: "total", label: "Work items", more: true, get: (r) => r.total },
];
const text = (v) => (v === undefined || v === null ? "" : String(v));
const field = (k) => FIELDS.find((f) => f.key === k);

export const emptyState = () => ({ q: "", filters: {}, picked: [] });

/** Search: every word typed must be in the name, the reference, the id or the status (any case). */
export function matchesQuery(r, q) {
  const hay = [r.name, r.ref, r.id, r.status].map((x) => text(x).toLowerCase()).join("\n");
  return text(q).toLowerCase().split(/\s+/).filter(Boolean).every((w) => hay.includes(w));
}

/** One filter: "is" keeps rows whose value is any of the chosen; "not" keeps the others. No values chosen = no filter. */
export function matchesFilter(r, key, f) {
  const f0 = field(key);
  if (!f0 || !f || !Array.isArray(f.values) || !f.values.length) return true;
  const hit = f.values.map(text).includes(text(f0.get(r)));
  return f.mode === "not" ? !hit : hit;
}

export const visible = (rows, s) => rows.filter((r) => matchesQuery(r, s.q) && Object.keys(s.filters).every((k) => matchesFilter(r, k, s.filters[k])));

/** The values a field's list offers, each with how many of ALL rows hold it (blank values are not offered), sorted for people. */
export function optionsOf(rows, key) {
  const f0 = field(key), n = new Map();
  for (const r of rows) { const v = text(f0.get(r)); if (v !== "") n.set(v, (n.get(v) || 0) + 1); }
  return [...n].map(([value, count]) => ({ value, count })).sort((a, b) => (isNaN(a.value - b.value) ? a.value.localeCompare(b.value) : a.value - b.value));
}

export function setMode(s, key, mode) {
  const cur = s.filters[key] || { values: [] };
  return { ...s, filters: { ...s.filters, [key]: { mode: mode === "not" ? "not" : "is", values: cur.values } } };
}
export function toggleValue(s, key, value) {
  const cur = s.filters[key] || { mode: "is", values: [] }, v = text(value);
  const values = cur.values.includes(v) ? cur.values.filter((x) => x !== v) : [...cur.values, v];
  return { ...s, filters: { ...s.filters, [key]: { mode: cur.mode, values } } };
}
/** Select all: every value the field offers. Clear: none (and the filter goes). */
export const selectAllValues = (s, key, rows) => ({ ...s, filters: { ...s.filters, [key]: { mode: (s.filters[key] || {}).mode || "is", values: optionsOf(rows, key).map((o) => o.value) } } });
export function clearField(s, key) { const filters = { ...s.filters }; delete filters[key]; return { ...s, filters }; }
export const activeCount = (s) => Object.values(s.filters).filter((f) => f.values.length).length;

/** Picking: Select all / Clear act on the rows shown now; a row already picked stays picked when a filter hides it. */
export const toggleRow = (s, id) => ({ ...s, picked: s.picked.includes(id) ? s.picked.filter((x) => x !== id) : [...s.picked, id] });
export const pickAllShown = (s, rows) => ({ ...s, picked: [...new Set([...s.picked, ...visible(rows, s).map((r) => r.id)])] });
export const clearPicked = (s) => ({ ...s, picked: [] });
/** Only ids that are still rows count (a use case archived meanwhile is dropped). */
export const pickedIds = (s, rows) => { const ids = new Set(rows.map((r) => r.id)); return s.picked.filter((id) => ids.has(id)); };

export const counts = (rows, s) => ({ shown: visible(rows, s).length, total: rows.length, picked: pickedIds(s, rows).length });
export const resultWords = (c) => UNRULED_RESULT(c.shown, c.total);
export const addWords = (c) => UNRULED_ADD(c.picked);
