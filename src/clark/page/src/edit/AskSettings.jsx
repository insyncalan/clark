// Settings: asking (#47). The on/off switch and the folders asking may read, for the open project. Edit parts only: a published
// file has no Settings. The switch is askState.js, kept by the server for this computer; the folders are saved by the server too (the
// page asks the server to open the folder window and shows what the server answers, in its words).
import { useEffect, useState } from "preact/hooks";
import { project } from "../stores/report.js";
import { askOn, askStatus, askSaved, loadAsk, setAsk, ASK_OFF_LINE, ASK_CHECKING_LINE, ASK_UNAVAILABLE_LINE } from "./askState.js";
import { askFoldersRead, askFoldersChange, askFoldersChoose, words } from "./publishApi.js";

const NOT_READY = "Choosing folders isn't ready on this computer yet. Asking uses only this project's data until it is.";

export function AskSettings() {
  const on = askOn.value;
  const status = askStatus.value;
  const saved = askSaved.value;
  const code = project.value;
  const [folders, setFolders] = useState(null);          // null: not read yet; "unavailable"; or the list
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);                  // {kind: "error" | "note", text}

  useEffect(() => { loadAsk(true); }, []);      // asked again each time Settings opens, so the page never shows a stale choice

  async function flip() {
    setBusy(true);
    setMsg(null);
    const r = await setAsk(!on);
    setBusy(false);
    if (!r.ok) setMsg({ kind: "error", text: r.message });
    else if (r.message) setMsg({ kind: "note", text: r.message });
  }

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

  async function change(action, path) {
    setBusy(true);
    setMsg(null);
    const r = action === "choose" ? await askFoldersChoose(code) : await askFoldersChange(code, action, path);
    setBusy(false);
    const b = r.body;
    if (r.status === 200 && b && b.ok === true && Array.isArray(b.folders)) {
      setFolders(b.folders);
      if (b.message) setMsg({ kind: "note", text: b.message });
      return;
    }
    setMsg({ kind: "error", text: failure(r) });
  }

  const list = Array.isArray(folders) ? folders : [];
  return (
    <section class="frame setting" id="ask-settings">
      <h2>Asking</h2>
      <p class="muted">Claude is started on this computer for you.</p>
      <p id="ask-state">{status === "loading" ? ASK_CHECKING_LINE : status === "unavailable" ? ASK_UNAVAILABLE_LINE : on ? "Asking is on. Your question and the passages it needs go to Claude, which Anthropic runs." : ASK_OFF_LINE}</p>
      {status === "ready" && !saved ? <p class="muted" id="ask-unsaved">This computer's saved data can't keep this choice yet, so asking stays off. Restart clark to bring the saved data up to date.</p> : null}
      <div class="row">
        <button type="button" class="btn" data-ask-switch aria-pressed={on ? "true" : "false"} disabled={busy || status !== "ready"} onClick={flip}>{on ? "Turn off asking" : "Turn on asking"}</button>
      </div>
      <h3>Folders asking may read</h3>
      <p class="muted">Asking may read the files in these folders, as well as this project's own data. It only reads: it never changes a file. Parts of the files in these folders can be sent to Claude, which Anthropic runs, when they help answer a question.</p>
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
      <div class="pub-msg" role={msg && msg.kind === "error" ? "alert" : "status"} aria-live="polite">{msg && msg.text ? <p class={msg.kind}>{msg.text}</p> : null}</div>
    </section>
  );
}
