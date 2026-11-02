// Settings › Data (prototype parity A-S11): Export to Excel, the same export as the profile menu's "Export to Excel" (one function,
// exportExcel, so the two never differ). Edit parts only: a published file has no Settings. The card has no Import button yet: the
// server has no route that reads a workbook back in, and a button that does nothing would only mislead. Reset demo data is left out.
import { exportExcel } from "./ProfileMenu.jsx";
import { data } from "../stores/report.js";

export function Data() {
  return (
    <section class="frame setting" id="data-card" aria-labelledby="data-card-h">
      <h2 id="data-card-h">Data</h2>
      <p class="muted">Export saves this project's actions, risks and issues, decisions and milestones as an Excel workbook, so you can look at them or keep a copy. Your browser saves the file; nothing is sent or published.</p>
      <div class="row">
        <button type="button" class="btn" id="export-workbook" data-export-workbook disabled={!data.value} onClick={() => exportExcel()}>Export to Excel</button>
      </div>
    </section>
  );
}
