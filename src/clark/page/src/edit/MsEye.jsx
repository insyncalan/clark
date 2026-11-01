// The eye on one milestone row (Edit only): leave the milestone out of the published page, or put it back. A real button; it is
// pressed while the milestone is left out. The state is the data's `hidden` ids (clark's own, read again after every change and
// every Undo), so the page never keeps a copy of its own.
import { Icon } from "../components/Icon.jsx";
import { setMsHidden } from "./actions.js";

export function MsEye({ id, name, left }) {
  const verb = left ? "Include in the published page" : "Leave out of the published page";
  return (
    <button type="button" class="ib ms-eye" data-ms-eye={id} data-edit-only aria-pressed={left ? "true" : "false"} aria-label={`${verb}: ${name}`}
      title={verb} onClick={() => setMsHidden(id, !left)}>
      <Icon name={left ? "eyeoff" : "eye"} />
    </button>
  );
}
