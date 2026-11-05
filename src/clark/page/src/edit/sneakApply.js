// Applying a Sneak peek reading (#42b): every change shown, as one step through the work-item change (#68), place "peek".
// Returns true when the changes were made. A refusal says why in the route's plain words and changes nothing. After a change the
// data is read again (so the peek shows what clark saved), the changed fields flash, and the toast offers Undo.
import { say, enqueue, refresh, flash } from "../stores/changes.js";
import { project, rows, data } from "../stores/report.js";
import { sendPeekChange } from "../api.js";

const TABLE = { action: "actions", decision: "decisions" };           // every other kind of work item is a RAID item

// The row an id names now: a work item, else a milestone or a use case (the reading says which table it was read from, #728).
function rowOf(id, table) {
  if (table === "milestones" || table === "use_cases") return ((data.value && data.value[table]) || []).find((r) => r.id === id);
  return rows.value.find((r) => r.id === id);
}

export function applyReading(id, reading) {
  const code = project.value;
  const own = reading && (reading.table === "milestones" || reading.table === "use_cases") ? reading.table : "";
  const row = rowOf(id, own);
  const found = reading && Array.isArray(reading.changes) ? reading.changes : [];
  if (!row || !found.length) { say("problem", "There was nothing to change, so nothing was changed. Type what you want to change and try again."); return Promise.resolve(false); }
  const changes = {};
  for (const c of found) changes[c.field] = c.to;
  return enqueue(async () => {
    await refresh();                                  // the item may have changed since the words were read (a stale confirm)
    const now = rowOf(id, own);
    if (!now || found.some((c) => (now[c.field] ?? null) !== (c.from ?? null))) { say("problem", "This item changed while you were reading, so nothing was changed. Type your change again to see the new details, then apply."); return false; }
    const r = await sendPeekChange(code, own || TABLE[row.kind] || "raid", id, changes);
    if (!r.ok) { say("problem", r.message); return false; }
    await refresh();
    flash(found.map((c) => ({ ref: id, field: c.field })));
    if (r.reply.undoable && r.reply.apply_id) say("done", `${id} changed.`, r.reply.apply_id);
    else if (r.reply.apply_id === null && found.some((c) => c.field === "status" && c.to === "Made")) say("done", `${id} changed. A decision that is made can't be undone from here. To change it, record a new decision that replaces it.`);
    else say("note", "Nothing needed changing.");
    return true;
  });
}
