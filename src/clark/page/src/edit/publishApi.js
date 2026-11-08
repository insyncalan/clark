// The page's only way to publish: POST /api/publish, POST /api/client-folder and GET /api/publication (#43). No other file names
// these routes, so the published page (view.jsx) has no way to publish and no mention of them. Nothing here names a folder or a
// file: the client folder is the one saved in Settings, which the server reads itself.
import { token, plain } from "../stores/report.js";
import { style } from "../stores/style.js";
import { forgetCheck } from "./askCheck.js";

// {status, body}: never a throw, whatever the network or the server did. A status of 0 is "no answer".
export async function call(method, path, body) {
  try {
    const headers = { "X-Clark-Token": token() };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    const r = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body), cache: "no-store" });
    return { status: r.status, body: await r.json().catch(() => null) };
  } catch (e) {
    return { status: 0, body: null };
  }
}

// The report is published, and previewed, in the section style chosen in Settings › Personal: it goes with the request and the file carries it.
export const publishRequest = (body) => call("POST", "/api/publish", { ...body, section_style: style.value });
export const localUndoRequest = (project, applyId) => call("POST", "/api/client-folder", { project, action: "undo_local", apply_id: applyId });
export const folderRequest = (project, action, value) => call("POST", "/api/client-folder", action === "paste" ? { project, action, value } : { project, action });
export const previewRequest = (project) => call("POST", "/api/preview", { project, section_style: style.value });
export const latestRequest = (project) => call("GET", `/api/publication?project=${encodeURIComponent(project)}`);

// The words for a reply. The publish routes write plain words themselves (to_client.py and publish_flow.py: a test pins that none
// has a technical word), so the message of an answer in their shape (a stable `code` and a `message`, with a status they use) is
// shown as it is. Anything else (no answer, a refusal by the server's token check, a fault) gets the page's own words.
const KNOWN = [200, 400, 404, 409];
export function words(r, what) {
  const b = r.body;
  if (KNOWN.includes(r.status) && b && typeof b.code === "string" && /^[a-z_]+$/.test(b.code) && typeof b.message === "string" && b.message) return b.message;
  if (r.status === 0 || r.status === 403) return plain(r.status, b);
  if (r.status === 503) return `Could not ${what} just now. Wait a moment and try again.`;
  return `Something went wrong while this was working. ${what === "publish" ? "Some of the report may have been saved: check the folders before you publish again." : "Nothing was changed."} If it happens again, restart clark.`;
}

// The workbook (#147): {status, body, blob, name}. A download is a file, so the answer is read as a file when it is one and as
// words when it is not. Never a throw. `name` is the one the server gave; the page does not make up its own.
export async function exportRequest(project) {
  try {
    const r = await fetch(`/api/export?project=${encodeURIComponent(project)}`, { headers: { "X-Clark-Token": token() }, cache: "no-store" });
    if (r.status === 200) {
      const given = /filename="([^"]+)"/.exec(r.headers.get("Content-Disposition") || "");
      let warning = "";
      try { warning = decodeURIComponent(r.headers.get("X-Export-Warning") || ""); } catch (e) { warning = ""; }
      return { status: 200, body: null, blob: await r.blob(), name: given ? given[1] : "", warning };
    }
    return { status: r.status, body: await r.json().catch(() => null), blob: null, name: "" };
  } catch (e) {
    return { status: 0, body: null, blob: null, name: "" };
  }
}
// The import template (item 454): GET /api/export?template=1, an export's workbook with no rows. It asks about no project and the server reads
// nothing for it; `name` is the one the server gave. Never a throw.
export async function templateRequest() {
  try {
    const r = await fetch("/api/export?template=1", { headers: { "X-Clark-Token": token() }, cache: "no-store" });
    if (r.status === 200) {
      const given = /filename="([^"]+)"/.exec(r.headers.get("Content-Disposition") || "");
      return { status: 200, body: null, blob: await r.blob(), name: given ? given[1] : "" };
    }
    return { status: r.status, body: await r.json().catch(() => null), blob: null, name: "" };
  } catch (e) {
    return { status: 0, body: null, blob: null, name: "" };
  }
}
// Saves a file the page was given: a download anchor on a blob, which saves a file and does not navigate (only router.js touches
// history or the address). Returns the name the browser is asked to save it under.
export function saveBlob(blob, name) {
  const url = URL.createObjectURL(blob), a = document.createElement("a");
  a.href = url; a.download = name; a.hidden = true;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
  return a.download;
}
// The folders asking may read (#47): GET /api/ask-folders?project= and POST /api/ask-folders {project, action: "add" | "remove",
// path}; "choose" opens the system's folder window on the server (no path from the page). The server checks a folder and saves it; a server without this route answers 404, which the page says in plain words.
// Settings › AI (#54): whether Claude is connected and the model asking uses. Words and true or false only: clark holds no key or password.
export const aiConnectRead = () => call("GET", "/api/providers");
// Row 858: each of these changes what the ask panel's connection check would answer, so the kept answer is dropped (before and after).
const changing = async (method, path, body) => { forgetCheck(); try { return await call(method, path, body); } finally { forgetCheck(); } };
export const aiConnectSend = (provider) => changing("POST", "/api/providers/connect", { provider });
export const aiDisconnectSend = (provider) => changing("POST", "/api/providers/disconnect", { provider });
export const aiModelSend = (model, accept) => changing("POST", "/api/providers/model", accept ? { model, accept: true } : { model });
export const askFoldersRead = (project) => call("GET", `/api/ask-folders?project=${encodeURIComponent(project)}`);
export const askFoldersChoose = (project) => call("POST", "/api/ask-folders", { project, action: "choose" });
export const askFoldersChange = (project, action, path) => call("POST", "/api/ask-folders", { project, action, path });

// Asking's on/off switch for this computer (#47), kept in the database. GET /api/ask-enabled answers {ok, ask_enabled, saved}; POST
// takes {enabled: true | false}. The server checks the value and keeps it (with history and Undo); the page shows what it answered.
export const askEnabledRead = () => call("GET", "/api/ask-enabled");
export const askEnabledChange = (enabled) => changing("POST", "/api/ask-enabled", { enabled });
