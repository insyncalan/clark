// Settings: the client folder (#43). A folder on this computer that OneDrive syncs to the client's SharePoint, chosen with the
// system's own folder window (the server opens it) and saved as the project's setting. Since item 647 the page may also send a
// pasted folder path (action "paste"): the server checks it exactly as a chosen one (it must be inside OneDrive) and refuses a
// pasted link by its form, never opening it, so the page decides nothing. Undo can put the old one back.
// Edit parts only.
import { useState } from "preact/hooks";
import { data, project } from "../stores/report.js";
import { savedFolder, folderName } from "./publishState.js";
import { folderRequest, words } from "./publishApi.js";

const PASTE_MAX = 2000;            // the server refuses anything longer (publish_flow.MAX_PASTE)

export function ClientFolder() {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);                  // {kind: "error" | "note", text}
  const [pasted, setPasted] = useState("");
  const saved = savedFolder();

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
        <p class="muted">Always saved. Publish opens the save window where you last saved this report, so you choose the local folder there each time.</p>
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
