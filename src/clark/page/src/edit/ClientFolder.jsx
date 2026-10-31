// Settings: the client folder (#43). A folder on this computer that OneDrive syncs to the client's SharePoint, chosen with the
// system's own folder window (the server opens it) and saved as the project's setting. The page never types a path or sends one:
// the server chooses, checks and saves, and Undo can put the old one back. Edit parts only.
import { useState } from "preact/hooks";
import { data, project } from "../stores/report.js";
import { savedFolder, folderName } from "./publishState.js";
import { folderRequest, words } from "./publishApi.js";

export function ClientFolder() {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);                  // {kind: "error" | "note", text}
  const saved = savedFolder();

  async function run(action) {
    setBusy(true);
    setMsg(null);
    const r = await folderRequest(project.value, action);
    setBusy(false);
    const b = r.body;
    if (r.status === 200 && b && b.ok === true) {
      if (b.changed) {
        const d = data.value;
        data.value = { ...d, project: { ...d.project, publish_client: b.folder || null } };
        setMsg({ kind: "note", text: b.warning || b.message || "" });
      }
      return;
    }
    setMsg({ kind: "error", text: words(r, "save the client folder") });
  }

  return (
    <section class="frame setting" id="client-folder">
      <h2 id="client-folder-h" tabIndex={-1}>Client folder</h2>
      <p class="muted">This must be a folder OneDrive syncs to the client's SharePoint. Publish copies the finished page into it when you tick To client; OneDrive then uploads it.</p>
      <p class="folder-now" id="client-folder-now">{saved ? <b>{folderName(saved)}</b> : <span class="muted">No client folder yet.</span>}</p>
      <div class="row">
        <button type="button" class="btn" data-choose-folder onClick={() => run("choose")} disabled={busy}>Choose folder</button>
        {saved ? <button type="button" class="btn quiet" data-clear-folder onClick={() => run("clear")} disabled={busy}>Clear</button> : null}
      </div>
      <div class="pub-msg" role={msg && msg.kind === "error" ? "alert" : "status"} aria-live="polite">{msg && msg.text ? <p class={msg.kind}>{msg.text}</p> : null}</div>
    </section>
  );
}
