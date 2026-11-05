// Applying a Sneak peek reading (#42b): every change shown, as one step through the existing change for that kind (#68, #136, #164), place "peek".
// Returns true when the changes were made. A refusal says why in the route's plain words and changes nothing. After a change the
// data is read again (so the peek shows what clark saved), the changed fields flash, and the toast offers Undo.
import { say, enqueue, refresh, flash } from "../stores/changes.js";
import { project, rows, data } from "../stores/report.js";
import { sendPeekChange } from "../api.js";

const TABLE = { action: "actions", decision: "decisions" };           // every other kind of work item is a RAID item

// A milestone and a use case are read from the project's own data; a work item from the list's rows.
const TABLES = { milestone: "milestones", use_case: "use_cases" };
const find = (id, kind) => (TABLES[kind] ? ((data.value || {})[TABLES[kind]] || []).find((r) => r.id === id) : rows.value.find((r) => r.id === id));

export function applyReading(id, reading, kind = "item") {
  const code = project.value;
  const row = find(id, kind);
  const found = reading && Array.isArray(reading.changes) ? reading.changes : [];
  if (!row || !found.length) { say("problem", "There was nothing to change, so nothing was changed. Type what you want to change and try again."); return Promise.resolve(false); }
  const changes = {};
  for (const c of found) changes[c.field] = c.to;
  return enqueue(async () => {
    await refresh();                                  // the item may have changed since the words were read (a stale confirm)
    const now = find(id, kind);
    if (!now || found.some((c) => (now[c.field] ?? null) !== (c.from ?? null))) { say("problem", "This item changed while you were reading, so nothing was changed. Type your change again to see the new details, then apply."); return false; }
    const r = await sendPeekChange(code, TABLES[kind] || TABLE[row.kind] || "raid", id, changes);
    if (!r.ok) { say("problem", r.message); return false; }
    await refresh();
    flash(found.map((c) => ({ ref: id, field: c.field })));
    if (r.reply.undoable && r.reply.apply_id) say("done", `${id} changed.`, r.reply.apply_id);
    else if (r.reply.apply_id === null && found.some((c) => c.field === "status" && c.to === "Made")) say("done", `${id} changed. A decision that is made can't be undone from here. To change it, record a new decision that replaces it.`);
    else say("note", "Nothing needed changing.");
    return true;
  });
}
