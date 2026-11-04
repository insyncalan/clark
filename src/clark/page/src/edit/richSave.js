// The seam between the rich fields and the store (#66). A rich field gets an editor in Edit only when it is listed in RICH_WRITES:
// field name -> (id, html) => the change request that writes it. A text section's body (Summary, This week, Next week; #220) is
// listed: its write kind is in changes.py (a text body goes through sanitise.clean_html on the server), and sendChange (api.js)
// picks the route. A use case's standing has a write kind of its own (#164) and brings its own save. The project's headline has no
// write kind yet; when it does, it is switched on with one line here.
// Everything else is already in place: the save goes through change() like every other edit, so it is one step with an Undo toast,
// a failure says its plain words, and the page redraws from the reply and reads the project again (stores/changes.js), so a
// section keeps its body: a reply never carries one.
import { change } from "../stores/changes.js";

export const RICH_WRITES = {
  body: (id, html) => ({ kind: "report_sections", op: "update", id, changes: { body: html } }),
};

export const richOn = (field) => typeof RICH_WRITES[field] === "function";

// Save a rich field's HTML. Resolves to the reply, or null when it failed (the toast has said why).
export function saveRich(field, id, html, done = "Saved.") {
  if (!richOn(field)) return Promise.resolve(null);
  return change(RICH_WRITES[field](id, html), done);
}
