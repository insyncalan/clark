// The page's only way to list, preview and restore backups: GET /api/backups, POST /api/backups/preview and POST /api/backups/restore
// (#111). No other file names these routes, so the published page (view.jsx) has no way to ask for them. The page sends a backup's
// name from the list the server gave and, for a restore, the step Preview saw; it never sends a path.
import { token } from "../stores/report.js";

// {status, body}: never a throw, whatever the network or the server did. A status of 0 is "no answer".
async function call(method, path, body) {
  try {
    const headers = { "X-Clark-Token": token() };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    const r = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body), cache: "no-store" });
    return { status: r.status, body: await r.json().catch(() => null) };
  } catch (e) {
    return { status: 0, body: null };
  }
}

export const listBackups = () => call("GET", "/api/backups");
export const previewBackup = (name) => call("POST", "/api/backups/preview", { name });
export const restoreBackup = (name, lastStep) => call("POST", "/api/backups/restore", { name, last_step: lastStep });
