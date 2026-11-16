// Report headline (row 1261), store type "reportheadline": its Edit part. Slice 1 builds no editing: the section shows its View look and says
// so. The fields, the health menu and the toolbar come in a later slice (listed as questions on the ticket). View part: templates/ReportHeadline.jsx.
import { View } from "../../templates/ReportHeadline.jsx";

export function Edit({ section }) {
  return (
    <div class="tpl-edit tpl-edit-reportheadline" data-tpl="reportheadline">
      <View section={section} />
      <p class="quiet">Editing this section comes in the next step.</p>
    </div>
  );
}
