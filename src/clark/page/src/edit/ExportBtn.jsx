// The Export icon beside Add on Work items (B-4): the same workbook download as the profile menu's Export to Excel
// (GET /api/export through exportExcel), one icon with a tooltip. Edit parts only: a published file has no server to ask (FR-70).
import { Icon } from "../components/Icon.jsx";
import { exportExcel } from "./ProfileMenu.jsx";

export function ExportBtn() {
  return (
    <button type="button" class="bib" id="expBtn" aria-label="Export to Excel" title="Export to Excel" data-tip="Export to Excel" onClick={() => exportExcel()}>
      <Icon name="dl" />
    </button>
  );
}
