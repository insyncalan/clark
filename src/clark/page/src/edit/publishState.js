// The Publish dialog's state (#43): the same steps as to_client.dialog_step, which the tests pin. Local is always on. To client is
// unticked every time the dialog opens (never remembered, not even in localStorage) and cannot be ticked until a client folder is
// saved. A taken name in the client folder is asked about before anything is written. Nothing here names a folder or a file.
import { signal } from "@preact/signals";
import { data, project } from "../stores/report.js";
import { publishRequest, latestRequest, words } from "./publishApi.js";
import { say } from "../stores/changes.js";

export const NO_FOLDER = "No client folder yet. Set it in Settings.";
export const dialog = signal(null);      // null (closed) or the state below
export const latest = signal(null);      // {at: YYYY-MM-DD, to_client} for the report bar, or null
export const next = signal(0);           // the number the next publication will have (#437), or 0 until the server has said
export const closeAfter = { ms: 1200 };  // how long the finished dialog stays before it closes itself; the test build changes it (testhook.js)
let closing = 0;                         // counts finished dialogs, so a timer from an earlier one never closes a later dialog

export const savedFolder = () => {
  const d = data.value;
  return (d && d.project && typeof d.project.publish_client === "string" && d.project.publish_client) || null;
};
export const folderName = (path) => (path ? String(path).replace(/[\\/]+$/, "").split(/[\\/]/).pop() || String(path) : "");

const fresh = (saved) => ({ saved, ticked: false, phase: "choose", clash: null, choice: "number", newName: "", confirmed: false, message: null, number: 0 });
const set = (patch) => { if (dialog.value) dialog.value = { ...dialog.value, ...patch }; };

export async function refreshLatest() {
  const code = project.value;
  if (!code) { latest.value = null; next.value = 0; return; }
  const r = await latestRequest(code);
  const ok = r.status === 200 && r.body && r.body.ok === true;
  latest.value = ok && r.body.latest ? r.body.latest : null;
  next.value = ok && Number.isInteger(r.body.next) && r.body.next >= 1 ? r.body.next : 0;
}

export function open() { dialog.value = fresh(savedFolder()); refreshLatest(); }       // asks again: a Word copy may have taken the number

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
export const pick = (choice) => { if (dialog.value && dialog.value.phase === "clash") set({ choice, confirmed: false }); };
export const rename = (text) => set({ newName: String(text) });
export const confirmOverwrite = (on) => { const s = dialog.value; if (s && s.phase === "clash" && s.choice === "overwrite") set({ confirmed: !!on }); };

// Whether the clash question has an answer that can be sent: a Rename needs text, an Overwrite needs its own confirmation.
export const ready = (s) => s.phase !== "clash" || (s.choice === "rename" ? s.newName.trim() !== "" : s.choice !== "overwrite" || s.confirmed);

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
export function cancel() {
  const s = dialog.value;
  if (s && s.phase !== "working") close();
}

export async function go() {
  const s = dialog.value;
  if (!s || s.phase === "working" || !ready(s)) return;
  if (s.phase === "done") return close();
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
    // #437: the button shows a tick and "Published (Publication N)", the words go to the toast, and the dialog closes by itself.
    // A publication is no step, so the toast has no Undo (history.py: the files are already where they were put).
    set({ phase: "done", clash: null, message: null, number: Number.isInteger(b.publication) ? b.publication : 0 });
    say("done", said);
    refreshLatest();
    const mine = ++closing;
    setTimeout(() => { const now = dialog.value; if (mine === closing && now && now.phase === "done") close(); }, closeAfter.ms);
    return;
  }
  const cancelled = r.status === 200 && b && (b.code === "cancelled" || b.code === "cancel");
  set({ phase: "error", clash: null, message: { kind: cancelled ? "info" : "error", text: said } });
  if (b && b.local_saved === true) refreshLatest();       // Local was saved and logged although the copy was not
}
