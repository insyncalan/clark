// The Word screens' state (#48): the Export to Word box and the Import from Word box, and the one export path the Publish box's
// "Also a Word document" tick shares (exportWord). The server does the work and says what happened in plain words (word_route.py); nothing here
// names a folder or a file path. Like Publish, To client is unticked every time a box opens and cannot be ticked until a client
// folder is saved. Nothing is written until the person has chosen: an export asks before it replaces anything, and an import shows
// what it read and adds only the items that are ticked, when Add is pressed.
import { signal } from "@preact/signals";
import { project, mode } from "../stores/report.js";
import { changeWord } from "../stores/changes.js";
import { exportWord, checkRequest, applyRequest, readFile, words, tooBig, isWordName, notWord, WORD_FILE_MB } from "./wordApi.js";
import { savedFolder } from "./publishState.js";

export const READ_FAILED = "Something went wrong while the file was being read, and nothing was added. Choose the file again. If it happens again, restart clark.";
export const ADD_FAILED = "Something went wrong while the items were being added. Look at the lists to see whether any were added before you try again. If it happens again, restart clark.";

// ── The export ───────────────────────────────────────────────────────────────

export const exportBox = signal(null);        // null (closed) or {saved, ticked, phase: choose | working | clash | done | error, clash, choice, confirmed, message}
const freshExport = (saved) => ({ saved, ticked: false, phase: "choose", clash: null, choice: "number", confirmed: false, message: null });
const setExport = (patch) => { if (exportBox.value) exportBox.value = { ...exportBox.value, ...patch }; };

export const openExport = () => { exportBox.value = freshExport(savedFolder()); };
export function closeExport() {
  const el = document.getElementById("word-export-dialog");
  if (el && el.open) el.close();
  exportBox.value = null;
}
export function tickClient(on) {
  const s = exportBox.value;
  if (s && s.saved && ["choose", "error", "done"].includes(s.phase)) setExport({ ticked: !!on });
}
export const pickClash = (choice) => { if (exportBox.value && exportBox.value.phase === "clash") setExport({ choice, confirmed: false }); };
export const confirmReplace = (on) => { const s = exportBox.value; if (s && s.phase === "clash" && s.choice === "overwrite") setExport({ confirmed: !!on }); };
export const exportReady = (s) => s.phase !== "clash" || s.choice !== "overwrite" || s.confirmed;
export function cancelExport() {
  const s = exportBox.value;
  if (s && s.phase !== "working") closeExport();
}

export async function goExport() {
  const s = exportBox.value;
  if (!s || s.phase === "working" || !exportReady(s)) return;
  if (s.phase === "done") return closeExport();
  setExport({ phase: "working", message: null });
  const o = await exportWord(project.value, s.ticked && s.saved, s.phase === "clash" ? { on_clash: s.choice } : null);
  if (o.kind === "clash") setExport({ phase: "clash", clash: o, choice: "number", confirmed: false, message: null });
  else if (o.kind === "saved") setExport({ phase: "done", clash: null, message: { kind: "success", text: o.message } });
  else setExport({ phase: "error", clash: null, message: { kind: o.kind === "cancelled" ? "info" : "error", text: o.message } });
}

// ── The import ────────────────────────────────────────────────────────────────

// null (closed) or {phase: choose | reading | plan | adding, file: the chosen File or null, plan: null or what was read, ticks: the
// numbers ticked, message: null or {kind, text}}
export const importBox = signal(null);
const freshImport = () => ({ phase: "choose", file: null, plan: null, ticks: [], message: null });
const setImport = (patch) => { if (importBox.value) importBox.value = { ...importBox.value, ...patch }; };

export function openImport() {
  if (mode.value === "edit") importBox.value = freshImport();      // View never imports: nothing is added from there
}
export function closeImport() {
  const el = document.getElementById("word-import-dialog");
  if (el && el.open) el.close();
  importBox.value = null;
}
export function cancelImport() {
  const s = importBox.value;
  if (s && s.phase !== "reading" && s.phase !== "adding") closeImport();
}

// The person chose a file (or none): a file over the limit is refused here, before anything is read or sent.
export function chooseFile(file) {
  const s = importBox.value;
  if (!s || s.phase !== "choose") return;
  if (file && !isWordName(file.name)) setImport({ file: null, message: { kind: "error", text: notWord(file.name) } });
  else if (file && file.size > WORD_FILE_MB * 1024 * 1024) setImport({ file: null, message: { kind: "error", text: tooBig(file.name) } });
  else setImport({ file: file || null, message: null });
}

export async function goRead() {
  const s = importBox.value;
  if (!s || s.phase !== "choose" || !s.file) return;
  const file = s.file;
  setImport({ phase: "reading", message: null });
  const f = await readFile(file);
  if (!f.ok) { setImport({ phase: "choose", file: null, message: { kind: "error", text: f.message } }); return; }
  const r = await checkRequest(project.value, file.name, f.data);
  const b = r.body;
  if (r.status === 200 && b && b.ok === true && typeof b.plan === "string" && Array.isArray(b.items)) {
    const plan = { key: b.plan, file: String(b.file || file.name), items: b.items.map((i) => ({ n: i.n, text: String(i.text) })),
      problems: (b.problems || []).map(String), notes: (b.notes || []).map(String), already: Number.isInteger(b.already_added) ? b.already_added : 0 };
    setImport({ phase: "plan", plan, ticks: plan.items.map((i) => i.n), message: null });
    return;
  }
  setImport({ phase: "choose", file: null, message: { kind: "error", text: words(r, READ_FAILED) } });
}

export function tickItem(n, on) {
  const s = importBox.value;
  if (!s || s.phase !== "plan") return;
  const rest = s.ticks.filter((t) => t !== n);
  setImport({ ticks: on ? [...rest, n].sort((a, b) => a - b) : rest, message: null });
}
export function tickAllItems(on) {
  const s = importBox.value;
  if (s && s.phase === "plan") setImport({ ticks: on ? s.plan.items.map((i) => i.n) : [], message: null });
}

// The choice: add the ticked items, as one step. Only the Add button (or Enter while Add can be pressed) reaches this.
export async function goAdd() {
  const s = importBox.value;
  if (!s || s.phase !== "plan" || s.ticks.length === 0) return;
  const accept = s.ticks.length === s.plan.items.length ? "all" : s.ticks;
  setImport({ phase: "adding", message: null });
  const out = await changeWord((code) => applyRequest(code, s.plan.key, accept), ADD_FAILED);
  if (out.ok) { closeImport(); return; }
  // A plan that has expired is gone: the file has to be read again. Any other refusal leaves the list to change.
  if (out.status === 410) setImport({ phase: "choose", file: null, plan: null, ticks: [], message: { kind: "error", text: out.message } });
  else setImport({ phase: "plan", message: { kind: "error", text: out.message } });
}
