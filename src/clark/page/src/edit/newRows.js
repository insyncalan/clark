// Adding a work item or a milestone from a button on the page (#458): one step with one Undo. The data is read again after it, so the page
// and the peek show what clark saved. Resolves to the reply (its `ref` is the new id), or to null when it failed (the toast says why).
// Edit only: stores/changes.js and api.js are not in a published file, and neither is this.
import { project, reread } from "../stores/report.js";
import { enqueue, say } from "../stores/changes.js";
import { sendNewRow } from "../api.js";

// `done(ref)` is what the toast says (with Undo, since the step can be undone).
export function addRow(kind, values, done) {
  const code = project.value;
  return enqueue(async () => {
    const r = await sendNewRow(code, kind, values);
    if (!r.ok) { say("problem", r.message); return null; }
    await reread(code);
    say("done", done(r.reply.ref), r.reply.apply_id, code);
    return r.reply;
  });
}
