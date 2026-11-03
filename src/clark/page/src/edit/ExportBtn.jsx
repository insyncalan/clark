// The Export icon beside Add on Work items (B-4): the same workbook download as the profile menu's Export to Excel
// (GET /api/export through exportExcel), one icon with a tooltip. Edit parts only: a published file has no server to ask (FR-70).
// The Import icon beside it (#454 point 2, the prototype's #impBtn "Import from Excel"): it opens the same Import from Excel box as
// Settings › Data's Import workbook (ImportWorkbook.jsx, drawn by Boxes.jsx), so the two never differ.
import { Icon } from "../components/Icon.jsx";
import { exportExcel } from "./ProfileMenu.jsx";
import { openBox } from "./boxes.js";
import { data, project, reread } from "../stores/report.js";
import { IMPORT } from "../logic/dataCard.js";

export function ExportBtn() {
  return (
    <button type="button" class="bib" id="expBtn" aria-label="Export to Excel" title="Export to Excel" data-tip="Export to Excel" onClick={() => exportExcel()}>
      <Icon name="dl" />
    </button>
  );
}

export function ImportBtn() {
  const word = IMPORT.pickTitle;
  return (
    <button type="button" class="bib" id="impBtn" aria-label={word} title={word} data-tip={word} disabled={!data.value}
      onClick={(e) => openBox("import", { opener: e.currentTarget, project: project.value, projectName: data.value.project.name, onDone: () => reread(project.value) })}>
      <Icon name="ul" />
    </button>
  );
}
