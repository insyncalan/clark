// Table (#96), store type "table": its view part. A small typed table drawn with a header row, an optional caption and the rows
// that hold text, all as text nodes. isEmpty: no header text and no row with text.
// The Edit part is edit/templates/Table.jsx; the content rules are section_kinds/table.py.
import { source, tidyTable, tableEmpty } from "./notes.js";

export const READY = true;
export const isEmpty = (section) => tableEmpty(tidyTable(source(section)));

export function View({ section }) {
  const t = tidyTable(source(section));
  return (
    <div class="tpl-table-wrap">
      <table class="tpl-table">
        {t.caption ? <caption>{t.caption}</caption> : null}
        <thead><tr>{t.cols.map((c, i) => <th scope="col" key={i}>{c}</th>)}</tr></thead>
        <tbody>{t.rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}>{c}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}
