// Excel file layout (row 951): what the exported workbook holds, in words. Read-only: it reads no project and sends nothing. Edit only.
import { Dialog } from "./Dialog.jsx";
import * as D from "../logic/dataCard.js";

export function ExcelLayout({ opener, onClose }) {
  return (
    <Dialog id="excel-layout-box" opener={opener} title={D.LAYOUT.title} onClose={onClose} first="#excel-layout-close"
      foot={<button type="button" class="btn pri" id="excel-layout-close" onClick={onClose}>{D.LAYOUT.close}</button>}>
      <p id="excel-layout-client">{D.LAYOUT.client}</p>
      <dl class="xl-sheets">
        {[D.LAYOUT.cover, D.LAYOUT.gantt, D.LAYOUT.history].map(([name, text]) => <div key={name}><dt><strong>{name}</strong></dt><dd>{text}</dd></div>)}
      </dl>
    </Dialog>
  );
}
