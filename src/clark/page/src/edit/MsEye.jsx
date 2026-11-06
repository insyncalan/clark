// The eye on one milestone row (Edit only): leave the milestone out of the published page, or put it back. A real button whose
// name changes with the state ("Leave out of..." / "Include in..."), so it has no aria-pressed (a screen reader would hear the
// state twice). The state is the data's `report_hidden` ids (clark's own, read again after every change and every Undo), so the
// page never keeps a copy of its own.
import { Icon } from "../components/Icon.jsx";
import { setMsHidden } from "./actions.js";
import { blink } from "../stores/motion.js";

export function MsEye({ id, name, left, internal }) {
  // An Internal-only milestone is never on the published page, so there is nothing to leave out: the eye is drawn as already out.
  if (internal) {
    return (
      <button type="button" class="ib ms-eye is-left" data-ms-eye={id} data-ms-internal data-edit-only disabled aria-label={`Internal only, never on the published page: ${name}`}
        title="Internal only, never on the published page">
        <Icon name="eyeoff" />
      </button>
    );
  }
  const verb = left ? "Include in the published page" : "Leave out of the published page";
  return (
    <button type="button" class={`ib ms-eye${left ? " is-left" : ""}`} data-ms-eye={id} data-edit-only aria-label={`${verb}: ${name}`}
      title={verb} onClick={(e) => { setMsHidden(id, !left, name).then(blink(e)); }}>
      <Icon name={left ? "eyeoff" : "eye"} />
    </button>
  );
}
