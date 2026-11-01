// Table (#96), store type "table": its Edit part. Columns, rows and an optional caption, typed in place. A new table starts on the
// page with two columns and two blank rows; nothing is saved until it has some words. Each save is one change() (noteEdit.jsx
// saveContent): one step, one Undo. The view part is templates/Table.jsx.
import { useEffect, useRef, useState } from "preact/hooks";
import { source, tidyTable, LIMITS } from "../../templates/notes.js";
import { Field, saveContent } from "./noteEdit.jsx";

const START = { cols: ["", ""], rows: [["", ""], ["", ""]] };
const blank = (t) => !t.cols.some(Boolean) && !t.rows.some((r) => r.some(Boolean));

export function Edit({ section }) {
  // The saved rows drop blank ones (tidyTable), so the edit draft reads the stored table itself.
  const raw = source(section);
  const savedCols = Array.isArray(raw.cols) ? raw.cols.map((c) => (typeof c === "string" ? c : "")) : [];
  const savedRows = Array.isArray(raw.rows) ? raw.rows.filter(Array.isArray).map((r) => savedCols.map((_, i) => (typeof r[i] === "string" ? r[i] : ""))) : [];
  const saved = { cols: savedCols, rows: savedRows, caption: tidyTable(raw).caption };
  const key = JSON.stringify(saved);
  const start = savedCols.length ? saved : { ...START, caption: saved.caption };
  const [t, setT] = useState(start);
  const seen = useRef(key);          // take the saved table again only when it differs from the one the draft started from (a late first run must not wipe what is being typed)
  useEffect(() => { if (seen.current === key) return; seen.current = key; setT(savedCols.length ? saved : { ...START, caption: saved.caption }); }, [key]);
  const save = (next) => {
    setT(next);
    if (blank(next) && !next.caption && savedCols.length === 0) return null;      // nothing typed yet: nothing to save
    if (JSON.stringify(next) === key) return null;
    return saveContent(section, { v: 1, ...next }, "Table saved.");
  };
  const cell = (i, j, v) => save({ ...t, rows: t.rows.map((r, a) => (a === i ? r.map((c, b) => (b === j ? v : c)) : r)) });
  const head = (j, v) => save({ ...t, cols: t.cols.map((c, b) => (b === j ? v : c)) });
  return (
    <div class="tpl-edit tpl-edit-table" data-tpl="table">
      <div class="tpl-table-wrap">
        <table class="tpl-table tpl-table-edit">
          <thead><tr>
            {t.cols.map((c, j) => (
              <th scope="col" key={j}>
                <Field value={c} label={`Column ${j + 1} heading`} max={LIMITS.cell} onCommit={(v) => head(j, v)} />
                {t.cols.length > 1 ? <button type="button" class="btn sm quiet" aria-label={`Remove column ${j + 1}`}
                  onClick={() => save({ ...t, cols: t.cols.filter((_, b) => b !== j), rows: t.rows.map((r) => r.filter((_, b) => b !== j)) })}>Remove column</button> : null}
              </th>
            ))}
            <th class="tpl-sr">Row actions</th>
          </tr></thead>
          <tbody>
            {t.rows.map((r, i) => (
              <tr key={i}>
                {r.map((c, j) => <td key={j}><Field value={c} label={`Row ${i + 1} column ${j + 1}`} max={LIMITS.cell} onCommit={(v) => cell(i, j, v)} /></td>)}
                <td><button type="button" class="btn sm quiet" aria-label={`Remove row ${i + 1}`} onClick={() => save({ ...t, rows: t.rows.filter((_, a) => a !== i) })}>Remove row</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div class="tpl-actions">
        {t.cols.length < LIMITS.cols ? <button type="button" class="btn sm" onClick={() => save({ ...t, cols: [...t.cols, ""], rows: t.rows.map((r) => [...r, ""]) })}>Add a column</button> : null}
        {t.rows.length < LIMITS.rows ? <button type="button" class="btn sm" onClick={() => save({ ...t, rows: [...t.rows, t.cols.map(() => "")] })}>Add a row</button> : null}
      </div>
      <label class="tpl-lbl">Caption (optional)
        <Field value={t.caption} label="Table caption" max={LIMITS.caption} onCommit={(caption) => save({ ...t, caption })} />
      </label>
      {blank(t) ? <p class="quiet">Empty for now: type in a heading or a cell. It stays out of the published page until then.</p> : null}
    </div>
  );
}
