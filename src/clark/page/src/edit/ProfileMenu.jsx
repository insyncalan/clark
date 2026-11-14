// The profile circle and its menu (#77, #147), Edit parts only: what the page can do. Publish opens the dialog (#43). Preview opens
// the page as it would be published in a new tab, and Export downloads the project's workbook; both ask the server (publishApi.js)
// and neither publishes or saves a file. Export to Word and Import from Word (#48) open their own boxes (Word.jsx); Import from Word is not in this menu (row 1063). Settings is a page opened from this menu (row 976: no top-bar tab), Help is the Help page. The tooltip lists the entries that carry a short
// word (`tip`), so it follows the entries; Help has none, as its "?" key is its own way in. The accessible name is just "Your menu".
// Appearance (Light, Dark, System) is in the menu (#179); the top line is the name and email from Settings › Personal (#180).
import { useEffect } from "preact/hooks";
import { Menu } from "../components/Menu.jsx";
import { data, tabs, show, project, mode, view, status } from "../stores/report.js";
import { openInNewTab } from "../router.js";
import { openHelp, openContext } from "../help/helpStore.js";
import { openPublish, lastLine } from "./Publish.jsx";
import { BarToast } from "./BarToast.jsx";
import { latest } from "./publishState.js";
import { note, say, closeNote, noteTimer } from "./menuNote.js";
import { holdOn } from "../stores/toastClock.js";
import { previewRequest, exportRequest, words } from "./publishApi.js";
import { showPublished } from "./PublishedReports.jsx";
import { appearance, setAppearance, MODES } from "../stores/appearance.js";
import { profile, loadProfile, wantName } from "../stores/profile.js";
import { openExport } from "./wordState.js";
import { toast } from "../stores/changes.js";
import { ToastCard, ToastBar, startHeld, keepFocus } from "./ToastCard.jsx";
import { actionIcon } from "../menuIcons.js";
import { Welcome } from "./Welcome.jsx";

export const MENU_NAME = "Your menu";
const LOOK_WORDS = { light: "Light", dark: "Dark", system: "System" };
export const menuTip = (items) => `${MENU_NAME}: ${items.filter((i) => i.tip).map((i) => i.tip).join(", ")}`;

// What Preview, Export or Publish did, in words (menuNote.js). The change toast is for Edit only, and this menu is in View too.
export { note };

// The note itself. There is one live region on the page: in Edit it is the change toast's (Toast.jsx shows this note in it, so
// the two never sit on top of each other), and in View, where there is no change toast, the menu has its own, which also draws About you's own toasts (aboutYouToast.js).
export function MenuNote() {
  const n = note.value;
  return n ? (
    <div class={`toast ${n.kind}`} key={n.id} data-kind={n.kind} role={n.kind === "problem" ? "alert" : undefined} ref={startHeld(noteTimer)} {...holdOn(noteTimer)}>
      <span class="toast-text">{n.text}</span>
      <button type="button" class="toast-btn" data-dismiss aria-label="Dismiss this message" onClick={() => { keepFocus(); closeNote(); }}>Close</button>
      <ToastBar kind={n.kind} />
    </div>
  ) : null;
}

const isAnswer = (r) => r.body && typeof r.body.message === "string" && typeof r.body.code === "string";

// The new tab is opened first and pointed at the page by the router (openInNewTab), which is the one place that sets an address.
export async function preview() {
  let r = null;
  const opened = await openInNewTab(async () => {
    r = await previewRequest(project.value);
    return r.status === 200 && r.body && typeof r.body.url === "string" ? r.body.url : null;
  });
  if (opened) { say("note", r.body.message); return; }
  say("problem", r && r.status === 200 ? "The preview could not be opened. Allow pop-ups for this page, then try again." : words(r, "preview"));
}

const exporting = new Set();                         // one export at a time for a project: a second click on it while one runs does nothing (#181)

export async function exportExcel() {
  const code = project.value;
  if (exporting.has(code)) return;
  exporting.add(code);
  let r;
  try { r = await exportRequest(code); } finally { exporting.delete(code); }
  if (r.status !== 200 || !r.blob) {
    say("problem", isAnswer(r) && [400, 404, 409].includes(r.status) ? r.body.message : words(r, "export"));
    return;
  }
  // A download anchor on a blob: this saves a file, it does not navigate (only router.js touches history or the address).
  const url = URL.createObjectURL(r.blob), a = document.createElement("a");
  a.href = url; a.download = r.name || `${project.value}.xlsx`; a.hidden = true;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
  say("done", `Your browser has saved “${a.download}”.${r.warning ? " " + r.warning : ""}`);
}

export function ProfileMenu() {
  useEffect(() => { loadProfile(); }, []);
  // Row 786: with no project open the circle is still there, with the entries that need no project (Settings, Appearance, Help); Publish and the rest wait for the report, or Publish would open without the project's client folder
  const open = !!data.value;
  if (!open && status.value !== "none") return null;      // while the report loads (or failed) there is still no circle, as before
  const items = open ? [{ id: "publish", name: "Publish…", tip: "Publish", icon: actionIcon("publish") }, { id: "preview", name: "Preview the page in a new tab", tip: "Preview", icon: actionIcon("preview") },
    { id: "export", name: "Export to Excel", tip: "Export", icon: actionIcon("exportExcel") }, { id: "word-export", name: "Export to Word", icon: actionIcon("exportWord") }] : [];
  if (open && tabs.value.includes("published")) items.push({ id: "published", name: "Published reports", icon: actionIcon("published") });
  if (tabs.value.includes("settings")) items.push({ id: "settings", name: "Settings", icon: actionIcon("settings") });      // row 1092: after Published reports, before the Appearance group, always (no short word, so the tooltip is as it was)
  items.push({ id: "help", name: "Help", icon: actionIcon("help") });
  // Who you are (#180), the top line: the name in bold with the email under it, or only the name; with neither, a link that opens
  // Settings › Profile and puts the cursor in the name box. Only what was typed in Settings: clark never makes up an email.
  const me = profile.value;
  const named = !!(me.name || me.email);
  const tip = menuTip(items);
  const last = lastLine(latest.value);
  // The last-published note is hidden from the bar in a narrow window, so the menu says it too; a separator sets the settings apart.
  // Appearance (#179; its group is called Appearance in the menu and in Settings): the same three choices as Settings › Personal, in the same order, below the separator that divides the actions
  // (Publish, Preview, Export) from the settings entries; the one in use is marked. One signal feeds both places.
  const look = [{ id: "look-lab", lab: "Appearance" }, ...MODES.map((m) => ({ id: `look-${m}`, name: LOOK_WORDS[m], icon: actionIcon("look" + m[0].toUpperCase() + m.slice(1)), checked: appearance.value === m }))];
  const actions = items.filter((i) => ["publish", "preview", "export", "word-export", "published", "settings"].includes(i.id)), rest = items.filter((i) => !actions.includes(i));
  const who = named ? { id: "who", head: { name: me.name || me.email, line: me.name ? me.email : "", title: [me.name, me.email].filter(Boolean).join("\n") } }
    : { id: "who", name: "Add your name in Settings", link: true, icon: actionIcon("profile") };
  // item 1177: the report bar's state chip is gone; its words (Editing while in Edit, Draft while nothing is published) are here, beside the published note
  const state = mode.value === "edit" ? "Editing · each change saves on its own" : last ? "" : open ? "Draft · not published yet" : "";
  const shown = [who, ...(last ? [{ id: "note", lab: last }] : []), ...(state ? [{ id: "state", lab: state }] : []), ...actions, { id: "sep", sep: true }, ...look, ...(rest.length ? [{ id: "sep", sep: true }] : []), ...rest];   // a separator sets the settings entries apart from the look group
  const pick = (id) => {
    if (id === "publish") openPublish();
    else if (id === "preview") preview();
    else if (id === "export") exportExcel();
    else if (id === "published") showPublished();
    else if (id === "word-export") openExport();
    else if (id === "who") { wantName.value = true; show("settings"); }
    else if (id.startsWith("look-")) setAppearance(id.slice(5));
    else if (id === "settings") show("settings");
    else if (id === "help") { const b = document.getElementById("profile-btn"); if (b) b.focus(); if (!openContext()) openHelp(); }       // row 896: the same peek as the ? key, with the open page's articles; the full Help is its foot link
  };
  return (
    <>
      <Menu id="profile-btn" btnCls="me" icon="user" label="" chevron={false} ariaLabel={MENU_NAME} tip={tip} menuId="profile-menu" menuLabel={MENU_NAME} items={shown} onPick={pick} />
      {open ? <Welcome /> : null}{/* #174: the first-run name prompt, asked once (Welcome.jsx) */}
      {mode.value !== "edit" && view.value === "dashboard" ? <div class="toasts" role="status" aria-live="polite">{toast.value && toast.value.own ? <ToastCard t={toast.value} /> : <BarToast />}<MenuNote /></div> : null}      {/* the Dashboard in View: About you's own toast, with Undo, too (item 429), and one made in View (item 439) */}
    </>
  );
}
