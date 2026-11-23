// The page's only way to publish: POST /api/publish, POST /api/client-folder and GET /api/publication (#43). No other file names
// these routes, so the published page (view.jsx) has no way to publish and no mention of them. Nothing here names a folder or a
// file: the client folder is the one saved in Settings, which the server reads itself.
import { token, plain } from "../stores/report.js";
import { zoneFetch } from "../api.js";
import { density, sectionWord } from "../stores/density.js";
import { forgetCheck } from "./askCheck.js";

// {status, body}: never a throw, whatever the network or the server did. A status of 0 is "no answer".
// `within` (row 1492): milliseconds after which the call is given up, so a hung server or a lost network ends in words (status 0) and not in a wait without end.
export async function call(method, path, body, within) {
  const stop = within ? new AbortController() : null;
  const timer = stop ? setTimeout(() => stop.abort(), within) : 0;
  try {
    const headers = { "X-Clark-Token": token() };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    const r = await zoneFetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body), cache: "no-store", signal: stop ? stop.signal : undefined });
    return { status: r.status, body: await r.json().catch(() => null) };
  } catch (e) {
    return { status: 0, body: null };
  } finally {
    if (timer) clearTimeout(timer);
  }
}

// The report is published, and previewed, in the Spacing chosen in Settings › Personal: it goes with the request and the file carries it.
export const publishRequest = (body) => call("POST", "/api/publish", { ...body, section_style: sectionWord(density.value) });
export const localUndoRequest = (project, applyId) => call("POST", "/api/client-folder", { project, action: "undo_local", apply_id: applyId });
export const folderRequest = (project, action, value) => call("POST", "/api/client-folder", action === "paste" ? { project, action, value } : { project, action });
export const previewRequest = (project) => call("POST", "/api/preview", { project, section_style: sectionWord(density.value) });
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

// The file name in a Content-Disposition header: filename* (the whole name, percent-encoded UTF-8) when there is one, else filename="...".
export function givenName(head) {
  const star = /filename\*=UTF-8''([^;\s]+)/i.exec(head || "");
  if (star) { try { return decodeURIComponent(star[1]); } catch (e) { /* fall through to the plain name */ } }
  const plain = /filename="([^"]+)"/.exec(head || "");
  return plain ? plain[1] : "";
}

// The workbook (#147): {status, body, blob, name}. A download is a file, so the answer is read as a file when it is one and as
// words when it is not. Never a throw. `name` is the one the server gave; the page does not make up its own.
export async function exportRequest(project) {
  try {
    const r = await zoneFetch(`/api/export?project=${encodeURIComponent(project)}`, { headers: { "X-Clark-Token": token() }, cache: "no-store" });
    if (r.status === 200) {
      const given = givenName(r.headers.get("Content-Disposition"));
      let warning = "";
      try { warning = decodeURIComponent(r.headers.get("X-Export-Warning") || ""); } catch (e) { warning = ""; }
      return { status: 200, body: null, blob: await r.blob(), name: given, warning };
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
    const r = await zoneFetch("/api/export?template=1", { headers: { "X-Clark-Token": token() }, cache: "no-store" });
    if (r.status === 200) {
      const given = givenName(r.headers.get("Content-Disposition"));
      return { status: 200, body: null, blob: await r.blob(), name: given };
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
const changing = async (method, path, body, within) => { forgetCheck(); try { return await call(method, path, body, within); } finally { forgetCheck(); } };
export const aiConnectSend = (provider) => changing("POST", "/api/providers/connect", { provider });
export const aiDisconnectSend = (provider) => changing("POST", "/api/providers/disconnect", { provider });
export const VERIFY_WAIT_MS = 35000;      // row 1492: the server's own deadline is 30 seconds; the page gives up 5 seconds after it
export const aiVerifySend = (provider) => changing("POST", "/api/providers/verify", { provider }, VERIFY_WAIT_MS);
export const aiCancelSend = (provider) => call("POST", "/api/providers/cancel", { provider });
export const aiProgressRead = () => call("GET", "/api/providers/progress");
export const aiTestSend = () => call("POST", "/api/providers/test", {});      // row 1294: Test the connection asks each model that is on one short question; nothing is kept
export const aiModelSend = (model, accept) => changing("POST", "/api/providers/model", accept ? { model, accept: true } : { model });
export const askFoldersRead = (project) => call("GET", `/api/ask-folders?project=${encodeURIComponent(project)}`);
export const askFoldersChoose = (project) => call("POST", "/api/ask-folders", { project, action: "choose" });
export const askFoldersChange = (project, action, path) => call("POST", "/api/ask-folders", { project, action, path });
// Row 1294: the folders for all projects (the All projects tab): the same, with scope "all" in place of a project.
export const askFoldersAllRead = (project) => call("GET", "/api/ask-folders?scope=all" + (project ? `&project=${encodeURIComponent(project)}` : ""));
export const askFoldersAllChoose = () => call("POST", "/api/ask-folders", { scope: "all", action: "choose" });
export const askFoldersAllChange = (action, path) => call("POST", "/api/ask-folders", { scope: "all", action, path });

// Usage in tokens (row 1294): GET answers {ok, title, asking, projects: [{code, name, questions, tokens}], all: {questions, tokens}, note}.
export const askUsageRead = () => call("GET", "/api/ask-usage");

// The standing instructions of asking (row 1294): GET answers {ok, all, project, saved, max}; POST takes {scope: "all" | "project", project?, text} or {scope, project?, undo}.
export const askInstructionsRead = (project) => call("GET", `/api/ask-instructions?project=${encodeURIComponent(project || "")}`);
export const askInstructionsChange = (body) => call("POST", "/api/ask-instructions", body);
// The slash commands of ask clark (row 1295): GET answers {ok, all, project, damaged, max, builtins}; POST takes {scope: "all" | "project", project?, action: "save" | "remove" | "reset", ...}.
export const askCommandsRead = (project) => call("GET", `/api/ask-commands?project=${encodeURIComponent(project || "")}`);
export const askCommandsChange = (body) => call("POST", "/api/ask-commands", body);
// Connectors set up on this computer (row 1306, slice C3). GET /api/ask-connectors?project= answers {ok, connectors: [{id, label, on, off_here}]}: only the ones found
// on this computer, `on` the choice for every project (off until turned on), `off_here` the project's own turn-off. POST {id, on} changes the first, {project, id, off_here}
// the second; both answer the same list. Words and true or false only: nothing about a connector is kept in a project's data and no key is held.
export const askConnectorsRead = (project) => call("GET", project ? `/api/ask-connectors?project=${encodeURIComponent(project)}` : "/api/ask-connectors");
export const askFilesRead = (project) => call("GET", project ? `/api/ask-files?project=${encodeURIComponent(project)}` : "/api/ask-files");
export const askFilesChange = (body) => call("POST", "/api/ask-files", body);
export const askConnectorsChange = (body) => call("POST", "/api/ask-connectors", body);
export const askNewRead = (project) => call("GET", project ? `/api/ask-new-projects?project=${encodeURIComponent(project)}` : "/api/ask-new-projects");
export const askNewChange = (body) => call("POST", "/api/ask-new-projects", body);

// Asking's on/off switch for this computer (#47), kept in the database. GET /api/ask-enabled answers {ok, ask_enabled, saved}; POST
// takes {enabled: true | false}. The server checks the value and keeps it (with history and Undo); the page shows what it answered.
export const askEnabledRead = () => call("GET", "/api/ask-enabled");
export const askEnabledChange = (enabled) => changing("POST", "/api/ask-enabled", { enabled });

// The theme for this computer (row 1269): GET /api/theme answers {ok, theme: "classic" | "cards", saved}; POST takes {theme}.
export const themeRead = () => call("GET", "/api/theme");
export const themeChange = (theme) => call("POST", "/api/theme", { theme });
