// The Publish dialog's state: the same steps as to_client.dialog_step, which the tests pin. Local is always on. To client is
// unticked every time the dialog opens (never remembered, not even in localStorage) and cannot be ticked until a client folder is
// saved. A taken name in the client folder is asked about before anything is written. Nothing here names a folder or a file.
// Also a Word document (#48) is unticked every time as well: when it is ticked, the Word report is saved by the one Word path (wordApi.js exportWord,
// the same as Export to Word) once the web page is published, in the folder last used for the project, and in the client folder too when To client is ticked.
import { signal } from "@preact/signals";
import { data, project, openSettings } from "../stores/report.js";
import { publishRequest, latestRequest, words } from "./publishApi.js";
import { exportWord } from "./wordApi.js";
import { openInNewTab } from "../router.js";
import { printUrl } from "../logic/printView.js";
import { say } from "./menuNote.js";
import { placeholderItems, placeholderWarning } from "../logic/placeholders.js";

// With no client folder, To client says where to set one; the second part is a link to the Folder page (the prototype's
// "Set it in Settings, Publishing", io.js).
export const NO_FOLDER_LEAD = "No client folder yet. Set it in ", NO_FOLDER_LINK = "Settings, Publishing";
export const NO_FOLDER = NO_FOLDER_LEAD + NO_FOLDER_LINK + ".";
export const dialog = signal(null);      // null (closed) or the state below
export const latest = signal(null);      // {at: YYYY-MM-DD, to_client} for the report bar, or null
export const next = signal(0);           // the number the next publication will have (#437), or 0 until the server has said

// What the PDF tick adds to the answer (item 438): the browser's own print box opens on the page in a new tab, and the person chooses Save as PDF there.
// WORDING: owner to rule (both sentences)
export const PRINT_OPENED = "Your browser’s print box opens in a new tab; choose Save as PDF. In the print box, untick Headers and footers, so the PDF carries no web address.";
export const PRINT_NOT_OPENED = "The PDF did not open. Choose Preview the page in a new tab in the profile menu and print it.";

// WHERE THE PRINTED PAGE COMES FROM: this one function. It is the address the publish answer carries (print_url), kept from the exact
// bytes written to the Local file (item 465), so the PDF cannot differ from the published file. The number the reply gave goes on
// the address (&n=N) and the printed foot uses it first (stores/print.js).
export function printSource(answer, number) {
  return answer && typeof answer.print_url === "string" ? printUrl(answer.print_url, number) : null;
}
// #437: how long the finished dialog shows its tick before it closes by itself (the prototype's 1200 ms, io.js). The test build
// changes it through window.clarkPage.publishCloseMs (testhook.js); null keeps the dialog open until it is closed.
export const CLOSE_MS = 1200;
export const closeAfter = { ms: CLOSE_MS };
let finished = 0;                        // counts finished publishes, so a timer from an earlier dialog never closes a later one

// Item 449: the client-visible work items that still have the title Add gave them (logic/placeholders.js); the dialog warns.
export { placeholderItems, placeholderWarning };

export const savedFolder = () => {
  const d = data.value;
  return (d && d.project && typeof d.project.publish_client === "string" && d.project.publish_client) || null;
};
export const savedLocal = () => {
  const d = data.value;
  return (d && d.project && typeof d.project.publish_local === "string" && d.project.publish_local) || null;
};
export const folderName = (path) => (path ? String(path).replace(/[\\/]+$/, "").split(/[\\/]/).pop() || String(path) : "");

const fresh = (saved) => ({ saved, ticked: false, pdf: false, word: false, step: "publish", published: "", num: null, wclash: null, wchoice: "number", wconfirmed: false, prev: null, phase: "choose", clash: null, choice: "number", newName: "", confirmed: false, message: null });
const set = (patch) => { if (dialog.value) dialog.value = { ...dialog.value, ...patch }; };

export async function refreshLatest() {
  const code = project.value;
  if (!code) { latest.value = null; return; }
  const r = await latestRequest(code);
  latest.value = r.status === 200 && r.body && r.body.ok === true && r.body.latest ? r.body.latest : null;
  next.value = r.status === 200 && r.body && r.body.ok === true && Number.isInteger(r.body.next) && r.body.next >= 1 ? r.body.next : 0;
}

export function open() { dialog.value = fresh(savedFolder()); }

export function close() {
  const el = document.getElementById("publish-dialog");
  if (el && el.open) el.close();
  dialog.value = null;
  const back = document.querySelector("[data-publish]");
  if (back) back.focus();
}

// The link in To client: the box closes, Settings opens on the Folder page and its heading is scrolled into view and takes the focus.
export function toPublishingCard() {
  const el = document.getElementById("publish-dialog");
  if (el && el.open) el.close();
  dialog.value = null;
  openSettings("folder");
  let tries = 10;
  const find = () => {
    const card = document.getElementById("publishing");
    if (!card) { if (--tries > 0) setTimeout(find, 40); return; }
    card.setAttribute("tabindex", "-1");
    card.focus({ preventScroll: true });
  };
  setTimeout(find, 40);                                                    // after the box's own focus-back and Settings' first draw
}

export function tick(on) {
  const s = dialog.value;
  if (s && s.saved && ["choose", "error", "done"].includes(s.phase)) set({ ticked: !!on });
}
export function tickPdf(on) {      // the PDF tick: never remembered either; it needs nothing on the computer but a browser
  const s = dialog.value;
  if (s && ["choose", "error", "done"].includes(s.phase)) set({ pdf: !!on });
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
  const body = { project: code, to_client: !!(s.ticked && s.saved) };      // no "pdf" key: the browser makes the PDF
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
  if (s && s.phase === "wordclash") { set({ phase: "done", wclash: null, message: { kind: "info", text: `${s.published} The Word report was not saved, because you cancelled.` } }); return; }
  if (s && s.phase !== "working") close();
}

// The Word report's refusals say "Nothing was saved." (true in Export to Word); here the web page was saved, so that sentence is left out.
const afterPublish = (text) => String(text).replace(/\s*Nothing (was|has been) saved\.?/g, "").trim();

// Save the Word report, in the folder last used for the project, after the web page that was just published (`said` is what publishing said), or answer the question about a
// taken name. Whatever happens, the box ends in "done" with both results in words: the web page is published either way.
// The box ends in "done" with `message`. The same words go to the menu's note, which stays after the dialog has closed itself (item 437
// rows 27 and 57); it has no Undo, as in the prototype: a publication keeps its number and its files, so it is not a step that can be taken back.
// A finished box that is not an error closes itself after closeAfter.ms; an error stays up, and its note is a problem, which stays too.
function finish(message, extra = {}) {
  set({ phase: "done", clash: null, ...extra, message });
  say(message.kind === "error" ? "problem" : message.kind === "info" ? "note" : "done", message.text);
  const mine = ++finished;
  if (message.kind !== "error" && Number.isFinite(closeAfter.ms)) setTimeout(() => { const now = dialog.value; if (mine === finished && now && now.phase === "done") close(); }, Math.max(0, closeAfter.ms));
}

async function sendWord(s, said, num) {
  set({ phase: "working", step: "word", published: said, num, message: null });
  const o = await exportWord(project.value, s.ticked && s.saved, s.phase === "wordclash" ? { on_clash: s.wchoice } : null);
  if (o.kind === "clash") { set({ phase: "wordclash", step: "publish", wclash: o, wchoice: "number", wconfirmed: false, message: null }); return; }
  const ended = { step: "publish", wclash: null };
  if (o.kind === "saved") finish({ kind: "success", text: `${said} ${o.message}`, number: num }, ended);
  else if (o.kind === "cancelled") finish({ kind: "info", text: `${said} The Word report was not saved, because you cancelled.` }, ended);
  else finish({ kind: "error", text: `${said} The web page is published, but the Word report was not saved. ${afterPublish(o.message)}` }, ended);
}

export async function go() {
  const s = dialog.value;
  if (!s || s.phase === "working" || !ready(s)) return;
  if (s.phase === "done") return close();
  if (s.phase === "wordclash") return sendWord(s, s.published, s.num);
  const body = request(s, project.value);
  if (s.pdf) body.print = true;
  set({ phase: "working", message: null });
  let r = null, printed = false;
  if (s.pdf) {      // the new tab is opened now, while the click still counts, and pointed at the page once it is published
    printed = await openInNewTab(async () => {
      r = await publishRequest(body);
      if (!(r.status === 200 && r.body && r.body.ok === true)) return null;
      return printSource(r.body, Number.isInteger(r.body.publication) ? r.body.publication : 0);
    });
  } else r = await publishRequest(body);
  const b = r.body;
  if (r.status === 200 && b && b.ok === false && b.clash === true) {
    set({ phase: "clash", clash: { name: b.name, numbered: b.numbered, canOverwrite: b.can_overwrite !== false, note: b.note, title: words(r, "publish") }, choice: "number", confirmed: false, newName: "", message: null });
    return;
  }
  const said = words(r, "publish");
  // Item 353: the number the server gave this publication (item 120), so the success line can pick out "Published (Publication N)". A print box that did not open is an info line.
  if (r.status === 200 && b && b.ok === true) {
    const text = s.pdf ? `${said} ${printed ? PRINT_OPENED : PRINT_NOT_OPENED}` : said;
    const num = Number.isInteger(b.publication) && b.publication > 0 ? b.publication : null;
    refreshLatest();
    if (s.word) return sendWord(s, text, num);
    finish({ kind: s.pdf && !printed ? "info" : "success", text, number: num });
    return;
  }
  const cancelled = r.status === 200 && b && (b.code === "cancelled" || b.code === "cancel");
  set({ phase: "error", clash: null, message: { kind: cancelled ? "info" : "error", text: said } });
  if (b && b.local_saved === true) refreshLatest();       // Local was saved and logged although the copy was not
}
