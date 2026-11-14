// Settings: the client folder (#43). A folder on this computer that OneDrive syncs to the client's SharePoint, chosen with the
// system's own folder window (the server opens it) and saved as the project's setting. Since item 647 the page may also send a
// pasted folder path (action "paste"): the server checks it exactly as a chosen one (it must be inside OneDrive) and refuses a
// pasted link by its form, never opening it, so the page decides nothing. Undo can put the old one back. Row 852: the Local folder is
// chosen the same way (actions choose_local and clear_local), saved once, and said in the toast with its Undo.
// Edit parts only.
import { useState } from "preact/hooks";
import { data, project } from "../stores/report.js";
import { savedFolder, savedLocal, folderName } from "./publishState.js";
import { folderRequest, localUndoRequest, words } from "./publishApi.js";
import { say, toast } from "../stores/changes.js";

const PASTE_MAX = 2000;            // the server refuses anything longer (publish_flow.MAX_PASTE)

async function undoLocal(code, applyId) {
  const r = await localUndoRequest(code, applyId);
  if (r.status === 200 && r.body && r.body.ok === true) {
    const d = data.value;
    if (project.value === code && d) data.value = { ...d, project: { ...d.project, publish_local: r.body.folder || null } };
    say("done", "Undone.");
  } else say("problem", words(r, "save the local folder"));
}

// One change of the Local folder (choose_local or clear_local): the project's setting is updated and the toast says it with its Undo. Returns the refusal's words, or "".
async function changeLocal(action) {
  const r = await folderRequest(project.value, action);
  const b = r.body;
  if (r.status === 200 && b && b.ok === true) {
    if (b.changed) {
      const d = data.value;
      data.value = { ...d, project: { ...d.project, publish_local: b.folder || null } };
      say("done", b.message);
      if (b.apply_id) toast.value = { ...toast.value, local: () => undoLocal(project.value, b.apply_id) };   // the toast's own Undo (aboutYouToast.js): this setting has its own route
    }
    return "";
  }
  return words(r, "save the local folder");
}

// The Local folder control, shared by the Publishing card and the Essentials card (row 1115): the folder's name, Choose folder and Clear.
// Its ids and data hooks start with "ess-" so the page never holds one twice. It keeps its own busy flag and refusal line.
export function LocalFolderPick() {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const local = savedLocal();
  async function run(action) {
    setBusy(true);
    setMsg(null);
    const bad = await changeLocal(action);
    setBusy(false);
    if (bad) setMsg(bad);
  }
  const hook = (n) => ({ [`data-ess-${n}`]: "" });
  return (
    <div class="ess-folder">
      <p class="folder-now" id="ess-local-folder-now">{local ? <b>{folderName(local)}</b> : <span class="muted">No local folder yet.</span>}</p>
      <div class="row">
        <button type="button" class="btn" id="ess-local-folder" {...hook("choose-local")} onClick={() => run("choose_local")} disabled={busy}>Choose folder</button>
        {local ? <button type="button" class="btn quiet" {...hook("clear-local")} onClick={() => run("clear_local")} disabled={busy}>Clear</button> : null}
      </div>
      <div role="alert" aria-live="polite">{msg ? <p class="error">{msg}</p> : null}</div>
    </div>
  );
}

export function ClientFolder() {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);                  // {kind: "error" | "note", text}
  const [pasted, setPasted] = useState("");
  const saved = savedFolder(), local = savedLocal();

  async function run(action, value) {
    setBusy(true);
    setMsg(null);
    const r = await folderRequest(project.value, action, value);
    setBusy(false);
    const b = r.body;
    if (r.status === 200 && b && b.ok === true) {
      if (action === "paste") setPasted("");
      if (b.changed) {
        const d = data.value;
        data.value = { ...d, project: { ...d.project, publish_client: b.folder || null } };
        setMsg({ kind: "note", text: b.warning || b.message || "" });
      } else if (action === "paste" && b.message) {
        setMsg({ kind: "note", text: b.message });
      }
      return;
    }
    setMsg({ kind: "error", text: words(r, "save the client folder") });
  }

  async function runLocal(action) {
    setBusy(true);
    setMsg(null);
    const bad = await changeLocal(action);
    setBusy(false);
    if (bad) setMsg({ kind: "error", text: bad });
  }

  function usePasted(e) {
    e.preventDefault();
    if (pasted.trim() && !busy) run("paste", pasted);
  }

  return (
    <section class="frame setting" id="publishing">
      <h2 id="client-folder-h" tabIndex={-1}>Publishing</h2>
      <p class="muted">Where Publish saves the report. Local is always used; the client folder only when you tick To client.</p>
      <div class="setting-part" id="local-folder">
        <h3>Local folder</h3>
        <p class="muted">Always saved. Publish's save window opens in this folder; with none chosen, it opens where you last saved this report.</p>
        <p class="folder-now" id="local-folder-now">{local ? <b>{folderName(local)}</b> : <span class="muted">No local folder yet.</span>}</p>
        <div class="row">
          <button type="button" class="btn" data-choose-local onClick={() => runLocal("choose_local")} disabled={busy}>Choose folder</button>
          {local ? <button type="button" class="btn quiet" data-clear-local onClick={() => runLocal("clear_local")} disabled={busy}>Clear</button> : null}
        </div>
      </div>
      <div class="setting-part" id="client-folder">
        <h3>Client folder</h3>
        <p class="muted">This must be a folder OneDrive syncs to the client's SharePoint. Publish copies the finished page into it when you tick To client; OneDrive then uploads it.</p>
        <p class="folder-now" id="client-folder-now">{saved ? <b>{folderName(saved)}</b> : <span class="muted">No client folder yet.</span>}</p>
        <div class="row">
          <button type="button" class="btn" data-choose-folder onClick={() => run("choose")} disabled={busy}>Choose folder</button>
          {saved ? <button type="button" class="btn quiet" data-clear-folder onClick={() => run("clear")} disabled={busy}>Clear</button> : null}
        </div>
        <form class="folder-paste" data-paste-folder onSubmit={usePasted}>
          <label for="client-folder-paste">or paste the folder's path</label>
          <div class="row">
            <input type="text" id="client-folder-paste" autocomplete="off" spellcheck={false} maxLength={PASTE_MAX} value={pasted}
                   aria-describedby="client-folder-paste-hint" onInput={(e) => setPasted(e.currentTarget.value)} disabled={busy} />
            <button type="submit" class="btn" data-use-pasted disabled={busy || !pasted.trim()}>Use</button>
          </div>
          <p class="muted" id="client-folder-paste-hint">A folder on this computer.</p>
        </form>
        <div class="pub-msg" role={msg && msg.kind === "error" ? "alert" : "status"} aria-live="polite">{msg && msg.text ? <p class={msg.kind}>{msg.text}</p> : null}</div>
      </div>
    </section>
  );
}
