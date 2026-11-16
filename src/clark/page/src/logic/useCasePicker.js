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

// Row 1230: the add-a-milestone picker is the same machine with other fields. `fields` is [{key, label, more?, get(row), sort?(value)}], `hay(row)` the row's
// words the search looks in, `addWord` the button's word when none is picked. The use-case picker below is one call of this.
export function makePicker({ fields, hay, addWord }) {
  const field = (k) => fields.find((f) => f.key === k);
  const emptyState = () => ({ q: "", filters: {}, picked: [] });

  /** Search: every word typed must be in the name, the reference, the id or the status (any case). */
  function matchesQuery(r, q) {
    const h = hay(r).map((x) => text(x).toLowerCase()).join("\n");
    return text(q).toLowerCase().split(/\s+/).filter(Boolean).every((w) => h.includes(w));
  }

  /** One filter: "is" keeps rows whose value is any of the chosen; "not" keeps the others. No values chosen = no filter. */
  function matchesFilter(r, key, f) {
    const f0 = field(key);
    if (!f0 || !f || !Array.isArray(f.values) || !f.values.length) return true;
    const hit = f.values.map(text).includes(text(f0.get(r)));
    return f.mode === "not" ? !hit : hit;
  }

  const visible = (rows, s) => rows.filter((r) => matchesQuery(r, s.q) && Object.keys(s.filters).every((k) => matchesFilter(r, k, s.filters[k])));

  /** The values a field's list offers, each with how many of ALL rows hold it (blank values are not offered), sorted for people. */
  function optionsOf(rows, key) {
    const f0 = field(key), n = new Map();
    for (const r of rows) { const v = text(f0.get(r)); if (v !== "") n.set(v, (n.get(v) || 0) + 1); }
    return [...n].map(([value, count]) => ({ value, count })).sort((a, b) => (f0.sort ? (f0.sort(a.value) < f0.sort(b.value) ? -1 : f0.sort(a.value) > f0.sort(b.value) ? 1 : 0) : isNaN(a.value - b.value) ? a.value.localeCompare(b.value) : a.value - b.value));
  }

  function setMode(s, key, mode) {
    const cur = s.filters[key] || { values: [] };
    return { ...s, filters: { ...s.filters, [key]: { mode: mode === "not" ? "not" : "is", values: cur.values } } };
  }
  function toggleValue(s, key, value) {
    const cur = s.filters[key] || { mode: "is", values: [] }, v = text(value);
    const values = cur.values.includes(v) ? cur.values.filter((x) => x !== v) : [...cur.values, v];
    return { ...s, filters: { ...s.filters, [key]: { mode: cur.mode, values } } };
  }
  /** Select all: every value the field offers. Clear: none (and the filter goes). */
  const selectAllValues = (s, key, rows) => ({ ...s, filters: { ...s.filters, [key]: { mode: (s.filters[key] || {}).mode || "is", values: optionsOf(rows, key).map((o) => o.value) } } });
  function clearField(s, key) { const filters = { ...s.filters }; delete filters[key]; return { ...s, filters }; }
  const activeCount = (s) => Object.values(s.filters).filter((f) => f.values.length).length;

  /** Picking: Select all / Clear act on the rows shown now; a row already picked stays picked when a filter hides it. */
  const toggleRow = (s, id) => ({ ...s, picked: s.picked.includes(id) ? s.picked.filter((x) => x !== id) : [...s.picked, id] });
  const pickAllShown = (s, rows) => ({ ...s, picked: [...new Set([...s.picked, ...visible(rows, s).map((r) => r.id)])] });
  const clearPicked = (s) => ({ ...s, picked: [] });
  /** Only ids that are still rows count (a use case archived meanwhile is dropped). */
  const pickedIds = (s, rows) => { const ids = new Set(rows.map((r) => r.id)); return s.picked.filter((id) => ids.has(id)); };

  const counts = (rows, s) => ({ shown: visible(rows, s).length, total: rows.length, picked: pickedIds(s, rows).length });
  const resultWords = (c) => UNRULED_RESULT(c.shown, c.total);
  const addWords = (c) => (c.picked ? UNRULED_ADD(c.picked) : addWord);

  /** The header tick (row 1230): all shown picked takes the shown ones off the pick, otherwise it picks every one shown. A row picked but hidden by a filter stays picked. */
  const allShownPicked = (rows, s) => { const v = visible(rows, s); return v.length > 0 && v.every((r) => s.picked.includes(r.id)); };
  const someShownPicked = (rows, s) => visible(rows, s).some((r) => s.picked.includes(r.id));
  const toggleAllShown = (s, rows) => (allShownPicked(rows, s) ? { ...s, picked: s.picked.filter((id) => !visible(rows, s).some((r) => r.id === id)) } : pickAllShown(s, rows));
  return { fields, emptyState, matchesQuery, matchesFilter, visible, optionsOf, setMode, toggleValue, selectAllValues, clearField, activeCount, toggleRow, pickAllShown, clearPicked, pickedIds, counts, resultWords, addWords, allShownPicked, someShownPicked, toggleAllShown };
}

const uc = makePicker({ fields: FIELDS, hay: (r) => [r.name, r.ref, r.id, r.status], addWord: UNRULED_ADD(0) });
export const { emptyState, matchesQuery, matchesFilter, visible, optionsOf, setMode, toggleValue, selectAllValues, clearField, activeCount, toggleRow, pickAllShown, clearPicked, pickedIds, counts, resultWords, addWords } = uc;
export const UC_PICKER = uc;
