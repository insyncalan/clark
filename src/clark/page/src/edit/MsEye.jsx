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
      title={verb} onClick={(e) => { blink(e); setMsHidden(id, !left, name); }}>
      <Icon name={left ? "eyeoff" : "eye"} />
    </button>
  );
}

// Pressing the eye on the Dashboard takes the row off the page, so the button that had focus goes with it. Focus is planned before the press
// (the next row's eye, else the previous row's, else the section's handle, else its title) and given once the row is gone.
export function keepFocus(e, dash) {
  const eye = dash && e.target.closest && e.target.closest("button[data-ms-eye]");
  if (!eye || eye.disabled) return;
  const box = eye.closest(".msv"), art = box && box.closest("article");
  const eyes = box ? [...box.querySelectorAll(".msl-row button[data-ms-eye]:not([disabled])")] : [], at = eyes.indexOf(eye);
  const near = eyes[at + 1] || eyes[at - 1], next = near ? near.dataset.msEye : null, gone = eye.dataset.msEye;
  let tries = 0;
  const give = () => {
    const row = document.querySelector(`.msl-row[data-ms="${CSS.escape(gone)}"]`);
    if (row && row.contains(eye) && ++tries < 60) { requestAnimationFrame(give); return; }
    if (row && row.contains(eye)) return;      // the press was refused or is slow: the row is still here, and the eye keeps focus
    const a = document.activeElement;
    if (a && a !== document.body && a !== eye && eye.isConnected) return;      // the person moved on meanwhile
    const to = (next && document.querySelector(`.msl-row[data-ms="${CSS.escape(next)}"] button[data-ms-eye]`)) || (art && (art.querySelector(".handle") || art.querySelector(".sec-title")));
    if (to) to.focus();
  };
  requestAnimationFrame(give);
}
