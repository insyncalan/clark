// Row 1180: the ID tag and the project line under the peek's toolbar: the item's ID in a small outlined tag, then the project's name, said once.
// Read only, so a published file and the Dashboard in View draw it too.
import { data } from "../stores/report.js";

// The ID tag and the project line: <PeekIdLine id="HRB-R-007" />
export function PeekIdLine({ id }) {
  const d = data.value;
  const name = d && d.project && d.project.name;
  return (
    <div class="pkh-line" data-pk-idline>
      <span class="pkh-id num" data-pk-idtag data-pk-id>{id}</span>
      {name ? <span class="pkh-proj" data-pk-project>{name}</span> : null}
    </div>
  );
}
