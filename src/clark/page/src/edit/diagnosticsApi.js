// The page's only way to the log settings: GET /api/diagnostics, POST /api/logging, POST /api/logging/open-folder. Nothing here
// sends text from the report or the page: the server reads and writes the log itself.
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

export const readDiagnostics = () => call("GET", "/api/diagnostics");
export const saveLevel = (level) => call("POST", "/api/logging", { level });
export const openLogFolder = () => call("POST", "/api/logging/open-folder", {});

export const LOAD_FAILED = "The log settings could not be read. Reload the page and try again.";
export const SAVE_FAILED = "The logging level could not be saved. Reload the page and try again.";
export const OPEN_FAILED = "The log folder could not be opened. Try again; if it keeps happening, restart clark.";

// The words for a reply the server wrote itself (a stable `code`, a plain `message`); anything else gets `fallback`.
export function said(r, fallback) {
  const b = r.body;
  return b && typeof b.code === "string" && /^[a-z_]+$/.test(b.code) && typeof b.message === "string" && b.message ? b.message : fallback;
}
