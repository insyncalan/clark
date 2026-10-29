// Changes made on the page (#65): one request at a time, in the order they were made, and the toast that says what happened.
// A change is sent as it is; the page never edits its own copy. It redraws from the sections the reply carries, so what is on
// the page is what clark saved. A failed change draws nothing and the toast says why, in plain words (api.js).
import { signal } from "@preact/signals";
import { data, project } from "./report.js";
import { sendChange, sendUndo } from "../api.js";

// null, or { id, kind: "done" | "note" | "problem", text, undo: the step's id or null }
export const toast = signal(null);

let counter = 0, tail = Promise.resolve(), timer = 0;

export function say(kind, text, undo = null) {
  clearTimeout(timer);
  const id = ++counter;
  toast.value = { id, kind, text, undo };
  if (kind !== "problem") timer = setTimeout(() => { if (toast.value && toast.value.id === id) toast.value = null; }, 20000);
}

export function dismiss() {
  clearTimeout(timer);
  toast.value = null;
}

function redraw(sections) {
  data.value = { ...data.value, report_sections: sections };
}

// Runs `task` after every earlier one has finished, whether it worked or not.
function enqueue(task) {
  const run = tail.then(task);
  tail = run.catch(() => {});
  return run;
}

// Make one change. Resolves to the reply, or to null when it failed (and the toast says why). `done` is what the toast says
// when it worked; with a step to undo it carries Undo. A change that altered nothing (no step) says nothing.
export function change(req, done) {
  const code = project.value;
  return enqueue(async () => {
    const r = await sendChange(code, req);
    if (!r.ok) { say("problem", r.message); return null; }
    redraw(r.reply.sections);
    if (r.reply.apply_id) say("done", done, r.reply.apply_id);
    return r.reply;
  });
}

// Undo one step, by the id the change's reply gave. If some rows were left as they are, the toast says which, in the words
// clark gives (they name the section and why); otherwise it says it is undone.
export function undo(applyId) {
  const code = project.value;
  return enqueue(async () => {
    const r = await sendUndo(code, applyId);
    if (!r.ok) { say("problem", r.message); return null; }
    redraw(r.reply.sections);
    const skipped = Array.isArray(r.reply.skipped) && r.reply.skipped.length > 0;
    say("done", skipped && typeof r.reply.words === "string" && r.reply.words ? r.reply.words : "Undone.");
    return r.reply;
  });
}
