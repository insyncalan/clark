// Settings › Data (prototype parity A-S11, item 444): Export workbook and Import workbook. Edit parts only: a published file has no
// Settings. Export is the same export as the profile menu's "Export to Excel" (one function, exportExcel, so the two never differ).
// Import opens the two-step box (ImportWorkbook.jsx) and changes the project in ONE step. The box is drawn at the page's top level (boxes.js).
import { exportExcel } from "./ProfileMenu.jsx";
import { data, project, reread } from "../stores/report.js";
import { templateRequest, saveBlob } from "./publishApi.js";
import { say } from "./menuNote.js";
import { Icon } from "../components/Icon.jsx";
import { openBox } from "./boxes.js";
import { openExport, openImport } from "./wordState.js";   // row 831: the same two boxes as the profile menu
import * as L from "../logic/dataCard.js";

// Line 9 of row 1299: the empty template as a button on the card (the import box keeps its own). The template asks about no project.
async function downloadTemplate() {
  const r = await templateRequest();
  if (r.status !== 200 || !r.blob) { say("problem", L.IMPORT.templateFailed); return; }
  say("done", `${L.IMPORT.templateSaved}, “${saveBlob(r.blob, r.name || "import template.xlsx")}”.`);
}

export function Data() {
  const imported = () => reread(project.value);                         // the project's own page reads what the step changed

  return (
    <section class="frame setting" id="data-card" aria-labelledby="data-card-h">
      <h2 id="data-card-h" tabIndex={-1}>{L.DATA.title}</h2>
      <div class="row">
        <div>
          <button type="button" class="btn gb" id="export-workbook" data-export-workbook disabled={!data.value} aria-describedby={data.value ? undefined : "export-why"} onClick={() => exportExcel()}><Icon name="dl" />{L.DATA.export}</button>
          {data.value ? null : <p class="muted dc-note" id="export-why">{L.IMPORT_NEEDS_PROJECT}</p>}
        </div>
        <div>
          <button type="button" class="btn gb" id="import-workbook" data-import-workbook disabled={!data.value} aria-describedby={data.value ? undefined : "import-why"}
            onClick={(e) => openBox("import", { opener: e.currentTarget, project: project.value, projectName: data.value.project.name, onDone: imported })}><Icon name="ul" />{L.DATA.import}</button>
          {data.value ? null : <p class="muted dc-note" id="import-why">{L.IMPORT_NEEDS_PROJECT}</p>}
        </div>
        <div>
          <button type="button" class="btn gb" id="excel-layout" data-excel-layout onClick={(e) => openBox("layout", { opener: e.currentTarget })}><Icon name="doc" />{L.DATA.layout}</button>
        </div>
        <div>
          <button type="button" class="btn gb" id="word-export" data-word-export disabled={!data.value} aria-describedby={data.value ? undefined : "word-export-why"} onClick={(e) => openExport(e.currentTarget)}><Icon name="dl" />{L.DATA.wordExport}</button>
          {data.value ? null : <p class="muted dc-note" id="word-export-why">{L.IMPORT_NEEDS_PROJECT}</p>}
        </div>
        <div>
          <button type="button" class="btn gb" id="word-import" data-word-import disabled={!data.value} aria-describedby={data.value ? undefined : "word-import-why"} onClick={(e) => openImport(e.currentTarget)}><Icon name="ul" />{L.DATA.wordImport}</button>
          {data.value ? null : <p class="muted dc-note" id="word-import-why">{L.IMPORT_NEEDS_PROJECT}</p>}
        </div>
        <div>
          <button type="button" class="btn gb" id="data-template" data-data-template onClick={downloadTemplate}><Icon name="dl" />{L.DATA.template}</button>
        </div>
      </div>
      <p class="muted dc-note">{L.DATA.note}</p>
    </section>
  );
}
