// The Publish dialog's state (#43): the same steps as to_client.dialog_step, which the tests pin. Local is always on. To client is
// unticked every time the dialog opens (never remembered, not even in localStorage) and cannot be ticked until a client folder is
// saved. A taken name in the client folder is asked about before anything is written. Nothing here names a folder or a file.
// Also a Word document (#48) is unticked every time as well: when it is ticked, the Word report is saved by the one Word path (wordApi.js exportWord,
// the same as Export to Word) once the web page is published, beside it, and in the client folder too when To client is ticked.
import { signal } from "@preact/signals";
import { data, project } from "../stores/report.js";
import { publishRequest, latestRequest, words } from "./publishApi.js";
import { exportWord } from "./wordApi.js";

export const NO_FOLDER = "No client folder yet. Set it in Settings.";
export const dialog = signal(null);      // null (closed) or the state below
export const latest = signal(null);      // {at: YYYY-MM-DD, to_client} for the report bar, or null

export const savedFolder = () => {
  const d = data.value;
  return (d && d.project && typeof d.project.publish_client === "string" && d.project.publish_client) || null;
};
export const folderName = (path) => (path ? String(path).replace(/[\\/]+$/, "").split(/[\\/]/).pop() || String(path) : "");

const fresh = (saved) => ({ saved, ticked: false, word: false, step: "publish", published: "", wclash: null, wchoice: "number", wconfirmed: false, phase: "choose", clash: null, choice: "number", newName: "", confirmed: false, message: null });
const set = (patch) => { if (dialog.value) dialog.value = { ...dialog.value, ...patch }; };

export async function refreshLatest() {
  const code = project.value;
  if (!code) { latest.value = null; return; }
  const r = await latestRequest(code);
  latest.value = r.status === 200 && r.body && r.body.ok === true && r.body.latest ? r.body.latest : null;
}

export function open() { dialog.value = fresh(savedFolder()); }

export function close() {
  const el = document.getElementById("publish-dialog");
  if (el && el.open) el.close();
  dialog.value = null;
  const back = document.querySelector("[data-publish]");
  if (back) back.focus();
}

export function tick(on) {
  const s = dialog.value;
  if (s && s.saved && ["choose", "error", "done"].includes(s.phase)) set({ ticked: !!on });
}
export function tickWord(on) {
  const s = dialog.value;
  if (s && ["choose", "error", "done"].includes(s.phase)) set({ word: !!on });
}
export const wordPick = (choice) => { if (dialog.value && dialog.value.phase === "wordclash") set({ wchoice: choice, wconfirmed: false }); };
export const wordConfirm = (on) => { const s = dialog.value; if (s && s.phase === "wordclash" && s.wchoice === "overwrite") set({ wconfirmed: !!on }); };
export const pick = (choice) => { if (dialog.value && dialog.value.phase === "clash") set({ choice, confirmed: false }); };
export const rename = (text) => set({ newName: String(text) });
export const confirmOverwrite = (on) => { const s = dialog.value; if (s && s.phase === "clash" && s.choice === "overwrite") set({ confirmed: !!on }); };

// Whether the clash question has an answer that can be sent: a Rename needs text, an Overwrite needs its own confirmation.
export const ready = (s) => s.phase === "wordclash" ? s.wchoice !== "overwrite" || s.wconfirmed : s.phase !== "clash" || (s.choice === "rename" ? s.newName.trim() !== "" : s.choice !== "overwrite" || s.confirmed);

export function request(s, code) {
  const body = { project: code, to_client: !!(s.ticked && s.saved) };
  if (s.clash) {
    body.on_clash = s.choice;
    if (s.choice === "rename") body.new_name = s.newName.trim();
    if (s.choice === "overwrite" && s.confirmed) body.confirmed = true;
  }
  return body;
}

// Esc or Cancel: the clash question ends the dialog, as does any other state, except while it is working.
// The Word question is the exception: the web page is already published, so Cancel there leaves the Word report unsaved and says so.
export function cancel() {
  const s = dialog.value;
  if (s && s.phase === "wordclash") { set({ phase: "done", wclash: null, message: { kind: "info", text: `${s.published} The Word report was not saved.` } }); return; }
  if (s && s.phase !== "working") close();
}

// Save the Word report beside the web page that was just published (`said` is what publishing said), or answer the question about a
// taken name. Whatever happens, the box ends in "done" with both results in words: the web page is published either way.
async function sendWord(s, said) {
  set({ phase: "working", step: "word", published: said, message: null });
  const o = await exportWord(project.value, s.ticked && s.saved, s.phase === "wordclash" ? { on_clash: s.wchoice } : null);
  if (o.kind === "clash") { set({ phase: "wordclash", step: "publish", wclash: o, wchoice: "number", wconfirmed: false, message: null }); return; }
  if (o.kind === "saved") set({ phase: "done", step: "publish", wclash: null, message: { kind: "success", text: `${said} ${o.message}` } });
  else set({ phase: "done", step: "publish", wclash: null, message: { kind: "error", text: `${said} The Word report was not saved. ${o.message}` } });
}

export async function go() {
  const s = dialog.value;
  if (!s || s.phase === "working" || !ready(s)) return;
  if (s.phase === "done") return close();
  if (s.phase === "wordclash") return sendWord(s, s.published);
  const body = request(s, project.value);
  set({ phase: "working", message: null });
  const r = await publishRequest(body);
  const b = r.body;
  if (r.status === 200 && b && b.ok === false && b.clash === true) {
    set({ phase: "clash", clash: { name: b.name, numbered: b.numbered, canOverwrite: b.can_overwrite !== false, note: b.note, title: words(r, "publish") }, choice: "number", confirmed: false, newName: "", message: null });
    return;
  }
  const said = words(r, "publish");
  if (r.status === 200 && b && b.ok === true) {
    refreshLatest();
    if (s.word) return sendWord(s, said);
    set({ phase: "done", clash: null, message: { kind: "success", text: said } });
    return;
  }
  const cancelled = r.status === 200 && b && (b.code === "cancelled" || b.code === "cancel");
  set({ phase: "error", clash: null, message: { kind: cancelled ? "info" : "error", text: said } });
  if (b && b.local_saved === true) refreshLatest();       // Local was saved and logged although the copy was not
}
