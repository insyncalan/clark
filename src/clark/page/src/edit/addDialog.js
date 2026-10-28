// The way in to the Add a section box (#96). #101's gutter "+" and the section menu's "Add a section below…" call
// `openAddSection(after, opener)`; anything else may dispatch the same event: a cancelable CustomEvent on the document that bubbles (the box listens on the document and calls preventDefault() to claim it). Nothing here draws or sends.
// `after` is the id of the section the new one goes below (null: at the end); `opener` is the element that had focus, so Esc and
// Cancel can give it back. The box (AddDialog.jsx) is mounted in Edit only, so in View the event does nothing.
export const ADD_SECTION_EVENT = "clark:add-section";

export function openAddSection(after, opener) {
  const e = new CustomEvent(ADD_SECTION_EVENT, { detail: { after: after === undefined ? null : after, opener: opener || document.activeElement || null }, cancelable: true, bubbles: true });
  document.dispatchEvent(e);
  return e;
}
