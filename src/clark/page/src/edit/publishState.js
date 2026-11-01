// The Publish dialog's state (#43): the same steps as to_client.dialog_step, which the tests pin. Local is always on. To client is
// unticked every time the dialog opens (never remembered, not even in localStorage) and cannot be ticked until a client folder is
// saved. A taken name in the client folder is asked about before anything is written. Nothing here names a folder or a file.
import { signal } from "@preact/signals";
import { data, project, show } from "../stores/report.js";
import { publishRequest, latestRequest, words } from "./publishApi.js";

// With no client folder, To client says where to set one; the second part is a link to the Publishing card (the prototype's
// "Set it in Settings, Publishing", io.js).
export const NO_FOLDER_LEAD = "No client folder yet. Set it in ", NO_FOLDER_LINK = "Settings, Publishing";
export const NO_FOLDER = NO_FOLDER_LEAD + NO_FOLDER_LINK + ".";
export const dialog = signal(null);      // null (closed) or the state below
export const latest = signal(null);      // {at: YYYY-MM-DD, to_client} for the report bar, or null

export const savedFolder = () => {
  const d = data.value;
  return (d && d.project && typeof d.project.publish_client === "string" && d.project.publish_client) || null;
};
export const folderName = (path) => (path ? String(path).replace(/[\\/]+$/, "").split(/[\\/]/).pop() || String(path) : "");

const fresh = (saved) => ({ saved, ticked: false, phase: "choose", clash: null, choice: "number", newName: "", confirmed: false, message: null });
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

// The link in To client: the box closes, Settings opens and the Publishing card is scrolled into view and takes the focus.
export function toPublishingCard() {
  const el = document.getElementById("publish-dialog");
  if (el && el.open) el.close();
  dialog.value = null;
  show("settings");
  let tries = 10;
  const find = () => {
    const card = document.getElementById("publishing");
    if (!card) { if (--tries > 0) setTimeout(find, 40); return; }
    const calm = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    card.setAttribute("tabindex", "-1");
    card.scrollIntoView({ block: "start", behavior: calm ? "auto" : "smooth" });
    card.focus({ preventScroll: true });
  };
  setTimeout(find, 40);                                                    // after the box's own focus-back and Settings' first draw
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
  if (r.status === 200 && b && b.ok === true) { set({ phase: "done", clash: null, message: { kind: "success", text: said } }); refreshLatest(); return; }
  const cancelled = r.status === 200 && b && (b.code === "cancelled" || b.code === "cancel");
  set({ phase: "error", clash: null, message: { kind: cancelled ? "info" : "error", text: said } });
  if (b && b.local_saved === true) refreshLatest();       // Local was saved and logged although the copy was not
}
