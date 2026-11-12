import { fromFile } from "../stores/report.js";

// Item 454 and row 824: Import from Excel and Export to Excel (edit parts; a published file has neither). Row 1084: they sit on the filter line, before the view icons.
export function ImportExport({ tools, line }) {
  if (fromFile.value) return null;
  const imp = tools.ImportBtn ? <tools.ImportBtn /> : null, exp = tools.ExportBtn ? <tools.ExportBtn /> : null;
  return line ? <span class="fio">{imp}{exp}</span> : <>{imp}{exp}</>;
}
