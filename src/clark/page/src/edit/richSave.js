// The seam between the rich fields and the store (#66). A rich field gets an editor in Edit only when it is listed in RICH_WRITES:
// field name -> (id, html) => the change request that writes it. The list is EMPTY on purpose. A use case's standing and a needs or
// tracker section's body each have a write kind in changes.py (#164, #273; cleaned by sanitise.clean_html and checked by the stored
// section's type); the project's headline has none yet. A field is switched on with one line here when its editor lands, for example
//   body: (id, html) => ({ kind: "report_sections", op: "update", id, changes: { body: html } }),
// Everything else is already in place: the save goes through change() like every other edit, so it is one step with an Undo toast,
// a failure says its plain words, and the page redraws from the reply and reads the project again (stores/changes.js), so a
// section keeps its body: a reply never carries one.
import { change } from "../stores/changes.js";

export const RICH_WRITES = {};

export const richOn = (field) => typeof RICH_WRITES[field] === "function";

// Save a rich field's HTML. Resolves to the reply, or null when it failed (the toast has said why).
export function saveRich(field, id, html, done = "Saved.") {
  if (!richOn(field)) return Promise.resolve(null);
  return change(RICH_WRITES[field](id, html), done);
}
