// The Projects table's reads and its Archive and Restore (Settings › Projects). It uses routes that already exist: GET /api/projects
// (live, or archived with ?archived=1), GET /api/data for one project, and the project archive change (sendProjectArchive, in api.js, the only file that names the change route), whose Undo is the ordinary one (stores/changes.js). No other file names these calls, so the published page has none.
import { token } from "../stores/report.js";
import { sendProjectArchive } from "../api.js";

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

export { sendProjectArchive };
