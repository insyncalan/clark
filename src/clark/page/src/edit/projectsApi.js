// The Projects table's reads and its Archive and Restore (Settings › Projects). It uses routes that already exist: GET /api/projects
// (live, or archived with ?archived=1), GET /api/data for one project, and POST /api/change with kind projects (op archive or
// restore), whose Undo is the ordinary one (stores/changes.js). No other file names these calls, so the published page has none.
import { token } from "../stores/report.js";
import { plainChange } from "../stores/report.js";

async function get(path) {
  try {
    const r = await fetch(path, { headers: { "X-Clark-Token": token() }, cache: "no-store" });
    const body = await r.json().catch(() => null);
    return r.ok && body && body.ok === true ? body : null;
  } catch (e) {
    return null;
  }
}

// [{code, name}] or null when the list could not be read.
export async function listProjects(archived) {
  const b = await get(archived ? "/api/projects?archived=1" : "/api/projects");
  return b && Array.isArray(b.projects) ? b.projects : null;
}

// One project's data, or null.
export async function readProject(code) {
  const b = await get(`/api/data?project=${encodeURIComponent(code)}`);
  return b && b.data && typeof b.data === "object" ? b.data : null;
}

// {ok: true, applyId} or {ok: false, message}: never a throw. `op` is "archive" or "restore".
export async function sendProjectArchive(code, op) {
  try {
    const r = await fetch("/api/change", {
      method: "POST", headers: { "X-Clark-Token": token(), "Content-Type": "application/json" },
      body: JSON.stringify({ project: code, kind: "projects", op, id: code }), cache: "no-store",
    });
    const reply = await r.json().catch(() => null);
    if (r.ok && reply && reply.ok === true) return { ok: true, applyId: reply.apply_id || null };
    const said = reply && typeof reply.message === "string" && reply.message.length <= 240 && (r.status === 400 || r.status === 409) ? reply.message : "";
    return { ok: false, message: said || plainChange(r.ok ? 500 : r.status, reply) };
  } catch (e) {
    return { ok: false, message: plainChange(0) };
  }
}
