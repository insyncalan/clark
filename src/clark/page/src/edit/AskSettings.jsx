// Settings: asking (#47). The on/off switch and the folders asking may read, for the open project. Edit parts only: a published
// file has no Settings. The switch is askState.js, kept by the server for this computer; the folders are saved by the server too (the
// page asks the server to open the folder window and shows what the server answers, in its words).
import { useEffect, useRef, useState } from "preact/hooks";
import { project } from "../stores/report.js";
import { askOn, askStatus, askSaved, askProvider, loadAsk, setAsk, ASK_OFF_LINE, ASK_CHECKING_LINE, ASK_UNAVAILABLE_LINE } from "./askState.js";
import { named, ASK_NOTICE_LINE } from "./askWords.js";
import { AiSettings } from "./AiSettings.jsx";
import { announceSwitch, leaveSwitch } from "./switchToast.js";
import { askFoldersRead, askFoldersChange, askFoldersChoose, words } from "./publishApi.js";

const ASK_ON_TOAST = "ask clark is on";
const ASK_OFF_TOAST = "ask clark is off";
const NOT_READY = "Choosing folders isn't ready on this computer yet. Asking uses only this project's data until it is.";

// The asking switch's behaviour, shared by this card and the Essentials card (row 1115): `flip` turns asking on or off and says so in the toast
// with its Undo; the switch is disabled while the request runs, so focus is put back once it is not (row 849). The caller owns busy and the message line.
export function useAskFlip(on, busy, setBusy, setMsg) {
  const switchRef = useRef(null);
  const refocus = useRef(false);
  useEffect(() => {
    if (!busy && refocus.current) { refocus.current = false; if (switchRef.current) switchRef.current.focus(); }
  }, [busy]);
  async function flip() {
    const now = !on;
    setBusy(true);
    setMsg(null);
    refocus.current = true;
    const r = await setAsk(now);
    setBusy(false);
    if (!r.ok) setMsg({ kind: "error", text: r.message });
    else {
      if (r.message) setMsg({ kind: "note", text: r.message });
      announceSwitch(now ? ASK_ON_TOAST : ASK_OFF_TOAST, () => setAsk(!now), now ? ASK_OFF_TOAST : ASK_ON_TOAST);
    }
  }
  return { switchRef, flip };
}

export function AskSettings() {
  const on = askOn.value;
  const status = askStatus.value;
  const saved = askSaved.value;
  const code = project.value;
  const [folders, setFolders] = useState(null);          // null: not read yet; "unavailable"; or the list
  const [busy, setBusy] = useState(false);
  const [typing, setTyping] = useState(false);       // the server said no window can open here: a box to type the location into
  const [typed, setTyped] = useState("");
  const [msg, setMsg] = useState(null);                  // {kind: "error" | "note", text}

  const { switchRef, flip } = useAskFlip(on, busy, setBusy, setMsg);
  useEffect(() => { loadAsk(true); return leaveSwitch; }, []);      // asked again each time Settings opens, so the page never shows a stale choice

  useEffect(() => {
    let live = true;
    setFolders(null);
    askFoldersRead(code).then((r) => {
      if (!live) return;
      const b = r.body;
      setFolders(r.status === 200 && b && b.ok === true && Array.isArray(b.folders) ? b.folders : "unavailable");
    });
    return () => { live = false; };
  }, [code]);

  // The server's own words when it gave some (it never starts with the product's name); otherwise the page's, with a next step.
  function failure(r) {
    const b = r.body;
    if (r.status === 0 || r.status === 403 || (b && typeof b.code === "string")) return words(r, "save that folder");
    return "That folder could not be saved just now. Wait a moment and try again; if it keeps happening, close clark and start it again.";
  }

  // Choose folder and Remove are disabled while the request runs, which drops the focus: put it back once the list is drawn again.
  // After a Remove it goes to the Remove button that took its place, or to Choose folder when none is left.
  function refocusFolders(at) {
    setTimeout(() => {
      const root = document.getElementById("ask-settings");
      if (!root) return;
      const rm = root.querySelectorAll("[data-ask-remove]");
      const el = at >= 0 && rm.length ? rm[Math.min(at, rm.length - 1)] : root.querySelector("[data-ask-choose]");
      if (el) el.focus();
    }, 0);
  }

  async function change(action, path) {
    const at = action === "remove" && Array.isArray(folders) ? folders.indexOf(path) : -1;
    setBusy(true);
    setMsg(null);
    const r = action === "choose" ? await askFoldersChoose(code) : await askFoldersChange(code, action, path);
    setBusy(false);
    const b = r.body;
    if (action !== "add") refocusFolders(at);
    else setTimeout(() => { const i = document.getElementById("ask-folder-path"); if (i) i.focus(); }, 0);   // Add folder is disabled while the request runs: the focus goes to the box
    if (r.status === 200 && b && b.ok === true && Array.isArray(b.folders)) {
      setFolders(b.folders);
      if (b.message) setMsg({ kind: "note", text: b.message });
      return true;
    }
    if (b && b.code === "no_window") setTyping(true);
    setMsg({ kind: "error", text: failure(r) });
  }

  async function addTyped(e) {
    e.preventDefault();
    const path = typed.trim();
    if (!path) return;
    if (await change("add", path)) setTyped("");
  }

  const list = Array.isArray(folders) ? folders : [];
  return (
    <>
    <section class="frame setting" id="ask-settings">
      <h2 id="ask-settings-h" tabIndex={-1}>Asking</h2>
      <p class="muted">{named("Claude is started on this computer for you.", askProvider.value)}</p>
      <p class="muted" id="ask-notice">{named(ASK_NOTICE_LINE, askProvider.value)}</p>
      <p id="ask-state">{status === "loading" ? ASK_CHECKING_LINE : status === "unavailable" ? ASK_UNAVAILABLE_LINE : on ? "Asking is on." : ASK_OFF_LINE}</p>
      {status === "ready" && !saved ? <p class="muted" id="ask-unsaved">This computer's saved data can't keep this choice yet, so asking stays off. Restart clark to bring the saved data up to date.</p> : null}
      <div class="row">
        <button type="button" class="btn" ref={switchRef} data-ask-switch aria-pressed={on ? "true" : "false"} disabled={busy || status !== "ready"} onClick={flip}>{on ? "Turn off asking" : "Turn on asking"}</button>
      </div>
      <h3>Folders asking may read</h3>
      <p class="muted">{named("Asking may read the files in these folders, as well as this project's own data. It only reads: it never changes a file. Parts of the files in these folders can be sent to Claude, which Anthropic runs, when they help answer a question.", askProvider.value)}</p>
      {folders === "unavailable" ? <p class="muted" id="ask-folders-note">{NOT_READY}</p> : null}
      {folders !== "unavailable" && folders !== null && !list.length ? <p class="muted" id="ask-folders-none">No folders are set. Asking uses only this project's data.</p> : null}
      {list.length ? (
        <ul class="ask-folders" id="ask-folders">
          {list.map((p) => (
            <li key={p}><span class="folder-now">{p}</span> <button type="button" class="btn sm quiet" data-ask-remove={p} disabled={busy} onClick={() => change("remove", p)}>Remove</button></li>
          ))}
        </ul>
      ) : null}
      {Array.isArray(folders) ? (
        <div class="row">
          <button type="button" class="btn" data-ask-choose disabled={busy} onClick={() => change("choose")}>Choose folder</button>
        </div>
      ) : null}
      {typing && Array.isArray(folders) ? (
        <form class="row" id="ask-folder-form" onSubmit={addTyped}>
          <label for="ask-folder-path">Folder location</label>
          <input id="ask-folder-path" class="grow" type="text" autocomplete="off" spellcheck={false} value={typed} onInput={(e) => setTyped(e.currentTarget.value)} />
          <button type="submit" class="btn" data-ask-add disabled={busy || !typed.trim()}>Add folder</button>
        </form>
      ) : null}
      <div class="pub-msg" role={msg && msg.kind === "error" ? "alert" : "status"} aria-live="polite">{msg && msg.text ? <p class={msg.kind}>{msg.text}</p> : null}</div>
    </section>
    <AiSettings />
    </>
  );
}
