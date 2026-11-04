// Settings › Data (prototype parity A-S11, #444): Export workbook, Import workbook and Reset the demo data, as the prototype's card has
// them. Edit parts only: a published file has no Settings. Export is the same export as the profile menu's "Export to Excel" (one function,
// exportExcel, so the two never differ). Import opens the two-step box (ImportWorkbook.jsx) and changes the project in ONE step.
// Reset the demo data is on the card only when clark says its data is the demo data (POST /api/demo, op "state"), and asks first
// (Boxes.jsx). The boxes are drawn at the page's top level (boxes.js). `api` is a seam for the tests; the page passes none.
import { useEffect, useState } from "preact/hooks";
import { exportExcel } from "./ProfileMenu.jsx";
import { data, project, reread } from "../stores/report.js";
import { Icon } from "../components/Icon.jsx";
import { openBox } from "./boxes.js";
import { takeResetDone } from "./Boxes.jsx";
import { demoState } from "./dataApi.js";
import * as L from "../logic/dataCard.js";

export function Data({ api = { state: demoState } }) {
  const [demo, setDemo] = useState(false);
  const [done] = useState(takeResetDone);
  useEffect(() => { let live = true; api.state().then((r) => { if (live && r.ok && r.body.demo === true) setDemo(true); }); return () => { live = false; }; }, []);

  const open = (kind, props) => (e) => openBox(kind, { opener: e.currentTarget, ...props });
  const imported = () => reread(project.value);                         // the project's own page reads what the step changed

  return (
    <section class="frame setting" id="data-card" aria-labelledby="data-card-h">
      <h2 id="data-card-h">{L.DATA.title}</h2>
      <div class="row">
        <button type="button" class="btn gb" id="export-workbook" data-export-workbook disabled={!data.value} onClick={() => exportExcel()}><Icon name="dl" />{L.DATA.export}</button>
        <button type="button" class="btn gb" id="import-workbook" data-import-workbook disabled={!data.value}
          onClick={(e) => openBox("import", { opener: e.currentTarget, project: project.value, projectName: data.value.project.name, onDone: imported })}><Icon name="ul" />{L.DATA.import}</button>
        {demo ? <button type="button" class="btn danger" id="reset-demo" data-reset-demo onClick={open("reset")}>{L.DATA.reset}</button> : null}
      </div>
      <p class="muted dc-note">{L.DATA.note}</p>
      {done ? <p role="status" id="reset-done">{done}</p> : null}
    </section>
  );
}
