// The Publish dialog's state: the same steps as to_client.dialog_step, which the tests pin. Local is always on. To client is
// unticked every time the dialog opens (never remembered, not even in localStorage) and cannot be ticked until a client folder is
// saved. A taken name in the client folder is asked about before anything is written. Nothing here names a folder or a file.
import { signal } from "@preact/signals";
import { data, project } from "../stores/report.js";
import { publishRequest, previewRequest, latestRequest, words } from "./publishApi.js";
import { openInNewTab } from "../router.js";
import { printUrl } from "../logic/printView.js";

export const NO_FOLDER = "No client folder yet. Set it in Settings.";
export const dialog = signal(null);      // null (closed) or the state below
export const latest = signal(null);      // {at: YYYY-MM-DD, to_client} for the report bar, or null

// What the PDF tick adds to the answer (#438): the browser's own print box opens on the published page in a new tab, and the person chooses Save as PDF there.
export const PRINT_OPENED = "Your browser’s print box opens in a new tab; choose Save as PDF. In the print box, untick Headers and footers, so the PDF carries no web address.";
export const PRINT_NOT_OPENED = "The PDF did not open. Allow pop-ups for this page, then choose Preview the page in a new tab in the profile menu and print it.";

export const savedFolder = () => {
  const d = data.value;
  return (d && d.project && typeof d.project.publish_client === "string" && d.project.publish_client) || null;
};
export const folderName = (path) => (path ? String(path).replace(/[\\/]+$/, "").split(/[\\/]/).pop() || String(path) : "");

const fresh = (saved) => ({ saved, ticked: false, pdf: false, phase: "choose", clash: null, choice: "number", newName: "", confirmed: false, message: null });
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
export function tickPdf(on) {      // the PDF tick: never remembered either; it needs nothing on the computer but a browser
  const s = dialog.value;
  if (s && ["choose", "error", "done"].includes(s.phase)) set({ pdf: !!on });
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
  let r = null, printed = false;
  if (s.pdf) {      // the new tab is opened now, while the click still counts, and pointed at the page when it is published
    printed = await openInNewTab(async () => {
      r = await publishRequest(body);
      if (!(r.status === 200 && r.body && r.body.ok === true)) return null;
      const p = await previewRequest(project.value);
      return p.status === 200 && p.body && typeof p.body.url === "string" ? printUrl(p.body.url) : null;
    });
  } else r = await publishRequest(body);
  const b = r.body;
  if (r.status === 200 && b && b.ok === false && b.clash === true) {
    set({ phase: "clash", clash: { name: b.name, numbered: b.numbered, canOverwrite: b.can_overwrite !== false, note: b.note, title: words(r, "publish") }, choice: "number", confirmed: false, newName: "", message: null });
    return;
  }
  const said = words(r, "publish");
  if (r.status === 200 && b && b.ok === true) {
    const text = s.pdf ? `${said} ${printed ? PRINT_OPENED : PRINT_NOT_OPENED}` : said;
    set({ phase: "done", clash: null, message: { kind: s.pdf && !printed ? "info" : "success", text } });
    refreshLatest();
    return;
  }
  const cancelled = r.status === 200 && b && (b.code === "cancelled" || b.code === "cancel");
  set({ phase: "error", clash: null, message: { kind: cancelled ? "info" : "error", text: said } });
  if (b && b.local_saved === true) refreshLatest();       // Local was saved and logged although the copy was not
}
