// The page's only way to ask about and install updates: GET /api/update and POST /api/update/review, /install, /arm-undo and /undo.
// No other file names these routes, so the published page (view.jsx) has no way to ask for them. The page never sends a path or a
// file name: it says "downloads" or "file" (the server opens the system's own dialog), then names only the review or the arm the
// server handed out.
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

export const updateStatus = () => call("GET", "/api/update");
export const reviewUpdate = (from, reinstall) => call("POST", "/api/update/review", { from, reinstall: !!reinstall });
export const installUpdate = (reviewId) => call("POST", "/api/update/install", { review_id: reviewId });
export const armUndo = () => call("POST", "/api/update/arm-undo", {});
export const undoUpdate = (armId, appOnly) => call("POST", "/api/update/undo", { arm_id: armId, app_only: !!appOnly });

// Which server answers now: "old" (this page's server, still running), "new" (another run of clark: this page's token is out of
// date, so the update or undo has restarted it) or "down" (nothing answers). Never a throw.
export async function whoAnswers() {
  const r = await updateStatus();
  if (r.status === 0) return "down";
  return r.status === 403 ? "new" : "old";
}
