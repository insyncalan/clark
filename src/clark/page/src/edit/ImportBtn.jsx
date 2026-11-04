// The Import icon beside Add on Work items (item 454, the prototype's Import from Excel at views.js): it opens the same two-step box as
// Settings > Data > Import workbook (ImportWorkbook.jsx), one icon with a tooltip. Edit parts only: a published file has no server to ask (FR-70).
import { Icon } from "../components/Icon.jsx";
import { data, project, reread } from "../stores/report.js";
import { openBox } from "./boxes.js";

export function ImportBtn() {
  return (
    <button type="button" class="bib" id="impBtn" aria-label="Import from Excel" title="Import from Excel" data-tip="Import from Excel" disabled={!data.value}
      onClick={(e) => openBox("import", { opener: e.currentTarget, project: project.value, projectName: data.value.project.name, onDone: () => reread(project.value) })}>
      <Icon name="ul" />
    </button>
  );
}
