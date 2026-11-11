// Changes made on the page (#65): one request at a time, in the order they were made, and the toast that says what happened.
// A change is sent as it is; the page never edits its own copy. It redraws from the sections the reply carries, so what is on
// the page is what clark saved. A failed change draws nothing and the toast says why, in plain words (api.js).
import { signal } from "@preact/signals";
import { data, project, reread, plainChange } from "./report.js";
import { busy, beforeReload, stayed, trouble } from "./leave.js";
import { sendChange, sendUndo, sendUndoMany, sendItemChange, sendRecordChange, sendCellChange, sendMilestoneChange, sendMilestoneRestore, sendBulk, readData, sendRestore } from "../api.js";
import { isProject } from "../router.js";
import { flashed } from "./wordsState.js";
import { assignNewPerson } from "../edit/peopleApi.js";
import { diffIds, markChanged } from "./changed.js";
import { undoRequest as wordUndoRequest, words as wordWords } from "../edit/wordApi.js";

// null, or { id, kind: "done" | "note" | "problem", text, undo: the step's id or null, code: the project the step was made in }
import { toastClock } from "./toastClock.js";
import { FIELDS as GANTT_FIELDS } from "../gantt/ganttTab.js";
export const toast = signal(null);
// Row 1075: a message goes after 5 seconds (stores/toastClock.js), unless the pointer is over it or focus is in it; Cmd or Ctrl+Z still undoes the step after that (below).
let shown = 0;
export const toastTimer = toastClock(() => { if (toast.value && toast.value.id === shown) toast.value = null; });
const clock = toastTimer;
// Counts the undos that worked, so the Movement block (edit/Movement.jsx) reads its milestones again after one.
export const undone = signal(0);

let counter = 0, tail = Promise.resolve();
const wordSteps = new Set();             // the steps a Word import made (#48): their Undo goes by the Word route, which undoes only those
const focusSteps = new Map();            // row 865: step -> a selector; after its Undo the focus goes there if the page dropped it
const itemSteps = new Map();             // the steps that changed a work item (#80 cells, #68 board moves), to what their Undo says ("" for "Undone."): their undo reply has no items, so the data is read again

// #197: the steps the toast offered Undo for, newest last, so Cmd or Ctrl+Z (undoKey.js) undoes the last one even after the toast
// has gone. Kept in memory only; a step leaves it once it is undone (by the key or the toast's button).
const undoable = [];
// The list is not saved: after a reload it is empty, so the key says so plainly and points to Activity, which keeps every change.
export const NOTHING_TO_UNDO = "Nothing to undo since this page was opened. Older changes are in Activity.";
const MAX_KEPT = 50;

export function say(kind, text, undo = null, code = project.value, focusUndo = false) {
  if (undo) {
    const at = undoable.findIndex((s) => s.step === undo);
    if (at >= 0) undoable.splice(at, 1);
    undoable.push({ step: undo, code });
    if (undoable.length > MAX_KEPT) { undoable.shift(); }
  }
  if (kind === "problem") trouble.n++;
  const id = ++counter;
  toast.value = { id, kind, text, undo, code, focusUndo };
  if (kind !== "problem") { shown = id; clock.start(); } else clock.stop();
}

// A different project is a page load (report.js), which would take the message with its Undo away: the one message on show goes with the
// person, once, in sessionStorage (cleared when it is read; never kept longer), and is said again, with the same Undo and project, in the page that loads.
const CARRIED = "clark-toast-carried";
function carry() {
  try {
    const t = toast.value;
    if (t && !t.local && (t.kind === "done" || t.kind === "note") && typeof t.text === "string") {
      window.sessionStorage.setItem(CARRIED, JSON.stringify({ kind: t.kind, text: t.text.slice(0, 400), undo: t.undo, code: t.code }));
    }
  } catch (e) { /* storage unavailable: the message stays behind */ }
}
function takeCarried() {
  try {
    const raw = window.sessionStorage.getItem(CARRIED);
    if (raw === null) return;
    window.sessionStorage.removeItem(CARRIED);
    const c = JSON.parse(raw);
    if (c && (c.kind === "done" || c.kind === "note") && typeof c.text === "string" && c.text && c.text.length <= 400
      && (c.undo === null || Number.isInteger(c.undo)) && isProject(c.code)) say(c.kind, c.text, c.undo, c.code);
  } catch (e) { /* nothing usable was kept */ }
}
busy.push(() => tail);                    // report.js waits for what is still being saved before it loads another project
beforeReload.push(carry);
stayed.push((late) => { if (late) say("problem", plainChange(0)); });      // a save still not answered: the page stays and says so; a failed one has said why already
takeCarried();

export function dismiss() {
  clock.stop();
  toast.value = null;
}

// Draw what the reply carries: the sections, and (#45) the tiles or the project's health and reason when it has them. It is drawn only
// while the page is still on the project the change was made in (`code`): Back or Forward may have moved it to another project while
// the change was on its way, and that project's page must not take this reply's sections, tiles or health. A reply
// never carries a section's body (changes.py SHOWN), so each section keeps what the page already has of it: the reply's fields
// win, the rest stay (#188). readAgain then brings the body as clark stored it.
function redraw(code, reply) {
  if (project.value !== code || !data.value) return;
  const next = { ...data.value };
  if (Array.isArray(reply.sections)) {
    const was = new Map((next.report_sections || []).map((sec) => [sec.id, sec]));
    next.report_sections = reply.sections.map((sec) => ({ ...was.get(sec.id), ...sec }));
  }
  if (Array.isArray(reply.tiles)) next.glance_tiles = reply.tiles;
  if (reply.project && typeof reply.project === "object") next.project = { ...next.project, health: reply.project.health, health_reason: reply.project.health_reason, ...(reply.project.week_ending !== undefined ? { week_ending: reply.project.week_ending } : {}), ...(reply.project.review_after_days !== undefined ? { review_after_days: reply.project.review_after_days } : {}), ...(reply.project.brand !== undefined ? { brand: reply.project.brand } : {}), ...Object.fromEntries(Object.values(GANTT_FIELDS).filter((k) => reply.project[k] !== undefined).map((k) => [k, reply.project[k]])) };
  data.value = next;
}

// After a change or an undo the page reads the project again (#188), so a section's body is the one clark stored, not the one the
// page had: a body saved or undone elsewhere must never be written over by the next save. Resolves to false, with a plain line,
// when it could not be read; true when it was, or when the person has opened another project meanwhile (nothing is wrong then).
async function readAgain(code, what) {
  if (await reread(code) || project.value !== code) return true;
  say("problem", `${what}, but the page could not be refreshed. Reload the page to see it.`);
  return false;
}

// What the page holds now that a step can change: the sections, the work items and the milestones, each with its id.
function held() {
  const d = data.value;
  return d ? [...(d.report_sections || []), ...(d.actions || []), ...(d.raid || []), ...(d.decisions || []), ...(d.milestones || [])] : [];
}

// Runs a step and marks what it changed (the rows whose data differs afterwards), so a person sees what the step, or its Undo, did.
// Only when the page is still on the project the step began in.
async function marking(task) {
  const code = project.value, before = held();
  const out = await task();
  if (project.value === code && data.value) markChanged(diffIds(before, held()));
  return out;
}

// Runs `task` after every earlier one has finished, whether it worked or not.
export function enqueue(task) {
  const run = tail.then(() => marking(task));
  tail = run.catch(() => {});
  return run;
}

// Make one change. Resolves to the reply, or to null when it failed (and the toast says why). `done` is what the toast says
// when it worked; with a step to undo it carries Undo. A change that altered nothing (no step) says nothing.
// `named` (row 865): { focus: a selector } makes the Undo say "Undone: <the toast's words>" and puts focus back on that control.
export function change(req, done, named = null) {
  const code = project.value;
  return enqueue(async () => {
    const r = await sendChange(code, req);
    if (!r.ok) { say("problem", r.message); return null; }
    redraw(code, r.reply);
    if (!(await readAgain(code, "The change was saved"))) return r.reply;
    if (r.reply.apply_id && named) { itemSteps.set(r.reply.apply_id, `Undone: ${done}`); if (named.focus) focusSteps.set(r.reply.apply_id, named.focus); }
    if (r.reply.apply_id) say("done", done, r.reply.apply_id, code);
    return r.reply;
  });
}

// Move one work item on the board (#68): the work items are read again (reread, report.js) after it and after its undo, so
// the page shows what clark saved. `done` is the toast's words; an Undo goes with it only when the reply says the step can be put
// back (a decision made is not). A refusal is a note: nothing was changed and there is nothing to undo.
export function changeItem(req, done) {
  const code = project.value;
  return enqueue(async () => {
    const r = await sendItemChange(code, req);
    if (!r.ok) { say("note", r.message); return null; }
    await reread(code);
    const step = r.reply.undoable === false ? null : r.reply.apply_id;
    if (step) itemSteps.set(step, "");
    say("done", done, step, code);
    return r.reply;
  });
}

// Archive an item or add a copy of it (#97), from the right-click menu: one step with Undo (`req` is the change, `done.text` what the
// toast says and `done.back` what it says after the Undo, "" for "Undone."). The work items are read again, as after a board move.
// A refusal is a note: nothing was changed.
export function changeRecord(req, done) {
  const code = project.value;
  return enqueue(async () => {
    const r = await sendRecordChange(code, req);
    if (!r.ok) { say("note", r.message); return null; }
    await reread(code);
    const w = typeof done === "function" ? done(r.reply) : done;     // #442: words that need the reply (a copy's new id)
    itemSteps.set(r.reply.apply_id, w.back || "");
    if (w.focus) focusSteps.set(r.reply.apply_id, w.focus);
    say("done", w.text, r.reply.apply_id, code, !!w.focusUndo);      // focusUndo: the toast puts the focus on its Undo as it is drawn
    return r.reply;
  });
}

// Add one work item (gap list B-8: the Add menu on Work items). `req` is {kind: actions | raid | decisions, op: "new", values, place}
// as edit/addItem.js builds it. The work items are read again so the new row is drawn as clark saved it; the toast says "<ID> added"
// with Undo, and that Undo says "<ID> removed." A refusal says why, and nothing was added. `more` is a sentence added to the toast
// (what was filled in for the person). Resolves to the reply, or null.
export function newItem(req, more = "") {
  const code = project.value;
  return enqueue(async () => {
    const r = await sendItemChange(code, req);
    if (!r.ok) { say("problem", r.message); return null; }
    const ref = String(r.reply.ref || r.reply.item.id);
    if (!(await readAgain(code, `${ref} was added`))) return r.reply;
    const step = r.reply.apply_id || null;
    if (step) itemSteps.set(step, `${ref} removed.`);
    say("done", `${ref} added.${more ? " " + more : ""}`, step, code);
    return r.reply;
  });
}

// Restore one archived work item (B-5): the work items are read again after it and after its undo. A refusal is a note.
export function restoreItem(table, id) {
  const code = project.value;
  return enqueue(async () => {
    const r = await sendRestore(code, table, id);
    if (!r.ok) { say("note", r.message); return null; }
    const step = r.reply.apply_id || null;
    if (step) itemSteps.set(step, "");
    if (!(await reread(code)) && project.value === code) { say("problem", `${id} was restored, but the page could not be refreshed. Reload the page to see it.`, step, code); return r.reply; }
    say("done", `${id} restored.`, step, code);
    return r.reply;
  });
}

// Undo one step, by the id the change's reply gave, in the project the step was made in (`code`; the open one if not given). If some rows were left as they are, the toast
// says which, in the words clark gives (they name the section and why); otherwise it says what went back (a work item's cell, #80)
// or that it is undone.
export function undo(applyId, code = project.value) {
  const at = undoable.findIndex((s) => s.step === applyId);
  if (at >= 0) undoable.splice(at, 1);
  return enqueue(async () => {
    const word = wordSteps.has(applyId);
    const r = word ? await sendWordUndo(code, applyId) : await sendUndo(code, applyId);
    if (!r.ok) { say("problem", r.message, applyId, code); return null; }
    redraw(code, r.reply);
    undone.value++;
    const back = word ? (typeof r.reply.message === "string" && r.reply.message) || "Undone." : itemSteps.get(applyId);
    itemSteps.delete(applyId);
    const focus = focusSteps.get(applyId);
    focusSteps.delete(applyId);
    wordSteps.delete(applyId);
    // Read again after every undo: an item's cell, or a section's body, comes back from the database. Not read again because the
    // person has opened another project meanwhile: nothing is wrong, so nothing is said about it.
    if (!(await readAgain(code, "The change was undone"))) return r.reply;
    if (Array.isArray(r.reply.reversed)) flash(r.reply.reversed.map((e) => ({ ref: e.ref, field: e.field })));   // the peek (#42) flashes what went back
    const skipped = Array.isArray(r.reply.skipped) && r.reply.skipped.length > 0;
    say("done", skipped && typeof r.reply.words === "string" && r.reply.words ? r.reply.words : back || "Undone.", null, code);
    if (focus) setTimeout(() => {         // row 865: where the person was, unless they have already moved on
      const now = document.activeElement, el = document.querySelector(focus);
      if (el && (!now || now === document.body || !now.isConnected)) el.focus({ preventScroll: true });
    }, 60);
    return r.reply;
  });
}

// A Word import's one step (#48): `send(code)` makes the request (the page has already shown what was read, and the person chose what
// to add). Resolves to {ok: true} (the toast says what was added, in the server's words, with Undo) or {ok: false, status, message}
// (nothing is said here: the import box shows the refusal where the person is). The work items are read again, so the page shows
// what clark saved.
export function changeWord(send, failed) {
  const code = project.value;
  return enqueue(async () => {
    const r = await send(code);
    const b = r.body;
    if (!(r.status === 200 && b && b.ok === true && Number.isInteger(b.apply_id) && typeof b.message === "string")) return { ok: false, status: r.status, message: wordWords(r, failed) };
    wordSteps.add(b.apply_id);
    const fresh = (await reread(code)) || project.value !== code;
    say("done", fresh ? b.message : `${b.message} The page could not be refreshed. Reload the page to see them.`, b.apply_id, code);
    return { ok: true };
  });
}

async function sendWordUndo(code, applyId) {
  const r = await wordUndoRequest(code, applyId);
  if (r.status === 200 && r.body && r.body.ok === true) return { ok: true, reply: r.body };
  return { ok: false, message: wordWords(r, "That could not be undone just now. Nothing was changed. Reload the page and try again.") };
}

// #80: change fields of one work item, in one step. `table` is actions, raid or decisions; `changes` the fields to set. The page
// draws the item as clark saved it (the reply's item), never its own guess. `done.text` is what the toast says; it carries Undo
// when the step can be undone, and `done.back` is what the toast says after that Undo. A decision that is made has none (the reply says so): with `done.always` the toast still says what
// happened. Otherwise a change that altered nothing says nothing. `done.place` is where the page says it was made (the history says
// "in the peek", "with a draft"; "cell" when not given). `done.refused(message)`, when given, hears a refusal in place of the toast, so
// a box that is still open can show it beside what was typed.
export function changeCell(table, id, changes, done) {
  const code = project.value;
  return enqueue(async () => {
    const r = await sendCellChange(code, table, id, changes, done.place || "cell");
    if (!r.ok) { if (typeof done.refused === "function") { trouble.n++; done.refused(r.message); } else say("problem", r.message); return null; }      // a refusal the box shows is still a problem for saved() (#944)
    const item = r.reply.item;
    const d = data.value;
    if (d && project.value === code && Array.isArray(d[table])) {
      data.value = { ...d, [table]: d[table].map((row) => (row.id === item.id ? { ...row, ...item } : row)) };
    }
    const step = r.reply.undoable === true && r.reply.apply_id ? r.reply.apply_id : null;
    if (step) { itemSteps.set(step, done.back || ""); say("done", done.text, step, code); }
    else if (done.always) say("done", done.text, null, code);                   // a decision that is made: it changed, and has no Undo
    return r.reply;
  });
}

// Row 986: Assign to a person who is not on the list yet, in one step with one Undo (the person and the owner go back together).
// Resolves to {ok: true} or {ok: false, message, code, person}: a refusal is shown by the picker that is still open, beside what was typed.
export function changeNewPerson(table, id, c, place) {
  const code = project.value;
  return enqueue(async () => {
    const r = await assignNewPerson(table, id, c.changes, c.new_person, place || "cell");
    if (!r.ok) return r;
    const item = r.reply.item;
    const d = data.value;
    if (d && project.value === code && Array.isArray(d[table])) data.value = { ...d, [table]: d[table].map((row) => (row.id === item.id ? { ...row, ...item } : row)) };
    const step = r.reply.undoable === true && r.reply.apply_id ? r.reply.apply_id : null;
    if (step) { itemSteps.set(step, c.back || ""); say("done", c.words, step, code); }
    else say("done", c.words, null, code);
    return { ok: true };
  });
}

// Item 210: a risk's or issue's impact or likelihood from its Priority cell. The update op doesn't take those two (clark works the
// priority out from them), so the change goes as a bulk change of this one item, from the cell: one step and one Undo, the value
// checked by clark, the history "in the table". The data is read again, so the cell shows the priority clark worked out, and
// the toast says it.
export function changeRating(table, id, changes, done) {
  const code = project.value;
  return enqueue(async () => {
    const r = await sendBulk(code, { kind: table, op: "bulk", ids: [id], changes, place: "cell" });
    if (!r.ok) { say("problem", r.message); return null; }
    await reread(code);
    const row = project.value === code && data.value && Array.isArray(data.value[table]) ? data.value[table].find((x) => x.id === id) : null;
    const text = row && row.priority ? `${done.text} Its priority is now ${row.priority}.` : done.text;
    const step = r.reply.undoable === true && r.reply.apply_id ? r.reply.apply_id : null;
    if (step) { itemSteps.set(step, done.back || ""); say("done", text, step, code); }
    else say("note", r.reply.words, null, code);
    return r.reply;
  });
}

// Reads the project's data again and puts it on the page (the work items and the peek read it). A failed read leaves the page as it is.
export async function refresh() {
  const d = await readData(project.value);
  if (d) data.value = d;
}

// Marks fields as changed for a moment: [{ref, field}]. The peek flashes the rows that show them.
export function flash(list) {
  const mine = list.filter((e) => e && typeof e.ref === "string" && typeof e.field === "string");
  if (!mine.length) return;
  const token = {};
  flashed.value = { token, list: mine };
  setTimeout(() => { if (flashed.value && flashed.value.token === token) flashed.value = null; }, 1600);
}

// A change to one milestone from the Movement block (#136): one step, one Undo. Resolves to {ok: true, reply} or {ok: false, message};
// a refusal says nothing here (the block shows it where the person is), a success says `done` with Undo.
export function changeMilestone(req, done) {
  const code = project.value;
  return enqueue(async () => {
    const r = await sendMilestoneChange(code, req);
    if (r.ok && r.reply.apply_id) say("done", typeof done === "function" ? done(r.reply) : done, r.reply.apply_id, code);   // #603: `done` may work out its words from the reply
    return r;
  });
}

// #196: one change to several work items, in one step with one Undo. The work items are read again after it (and after its Undo),
// so the page shows what clark saved. Resolves to {ok: true, reply} or {ok: false, code, message, leftOut, count}; a refusal is said
// in the toast unless it is clark asking before more than 25 (`code` "confirm": the caller asks, then sends again with confirm).
// `back` is what the toast says after its Undo. Nothing changed (they already had it): the toast says so, with no Undo.
export function changeBulk(req, back) {
  const code = project.value;
  return enqueue(async () => {
    const r = await sendBulk(code, req);
    if (!r.ok) {
      if (r.code !== "confirm") say("note", r.leftOut.length > 1 && r.code === "none_can" ? `${r.message} ${r.leftOut.slice(0, 3).map((e) => `${e.id}: ${e.why}`).join(" ")}` : r.message);
      return r;
    }
    await reread(code);
    const step = r.reply.undoable === true && r.reply.apply_id ? r.reply.apply_id : null;
    if (step) itemSteps.set(step, typeof back === "function" ? back(r.reply) : back || "");     // #199: `back` may work out its words from the reply
    say(step ? "done" : "note", r.reply.words, step, code);
    return r;
  });
}

// #197: Cmd or Ctrl+Z. Undoes the newest step of the open project that the toast offered Undo for (the same as its button); with none,
// it says NOTHING_TO_UNDO. Resolves to the undo's reply, or null.
export function undoLast(code = project.value) {
  for (let i = undoable.length - 1; i >= 0; i--) {
    if (undoable[i].code === code) {
      const { step } = undoable[i];
      if (toast.value && toast.value.undo === step) dismiss();
      return undo(step, code);
    }
  }
  say("note", NOTHING_TO_UNDO);
  return Promise.resolve(null);
}

// The Activity tab's Undo N (#232). `preview` reads what would be undone and what left, and changes nothing: {ok, reply} or
// {ok: false, message}. Without it one new change undoes them all: the page reads the project again, the toast says what went back
// and carries Undo (which takes the whole batch back), and the Movement block reads its milestones again.
export function undoSeveral(steps, { preview = false, confirm = false } = {}) {
  const code = project.value;
  if (preview) return sendUndoMany(code, steps, { preview: true });
  return enqueue(async () => {
    const r = await sendUndoMany(code, steps, { confirm });
    if (!r.ok) { if (r.confirm) trouble.n++; else say("problem", r.message); return r; }      // clark asking first is no save either: saved() sees it (#944)
    redraw(code, r.reply);
    undone.value++;
    for (const s of steps) { const at = undoable.findIndex((u) => u.step === s); if (at >= 0) undoable.splice(at, 1); }
    if (await readAgain(code, "The changes were undone")) {
      const words = typeof r.reply.words === "string" && r.reply.words ? r.reply.words : "Undone.";
      say("done", words, r.reply.apply_id || null, code);
    }
    return r;
  });
}

// Restore one archived milestone (C-M4): one step, one Undo; the project's data is read again after it, so the Plan and the count
// are the database's. Resolves to the reply, or to null when it was refused (the toast says why).
export function restoreMilestone(id, name) {
  const code = project.value;
  return enqueue(async () => {
    const r = await sendMilestoneRestore(code, id);
    if (!r.ok) { say("note", r.message); return null; }
    if (!(await reread(code)) && project.value === code) { say("problem", `${name} was restored, but the page could not be refreshed. Reload the page to see it.`, r.reply.apply_id || null, code); return r.reply; }
    say("done", `${name} restored.`, r.reply.apply_id || null, code);
    return r.reply;
  });
}
