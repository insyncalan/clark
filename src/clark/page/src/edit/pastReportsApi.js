// The page's only way to the published reports: GET /api/publications and GET /api/past-report (#443). Nothing here names a file or
// a folder: the server makes a kept copy's name from the project's code and the publication's number, and sends no path.
import { token } from "../stores/report.js";

// {status, body}: never a throw, whatever the network or the server did. A status of 0 is "no answer".
async function call(path) {
  try {
    const r = await fetch(path, { headers: { "X-Clark-Token": token() }, cache: "no-store" });
    return { status: r.status, body: await r.json().catch(() => null) };
  } catch (e) {
    return { status: 0, body: null };
  }
}

// Show archived (#345) asks for the archived ones too, marked.
export const listPublications = (project, archived = false) => call(`/api/publications?project=${encodeURIComponent(project)}${archived ? "&archived=1" : ""}`);
// Archive and Restore (#345): the project and the publication's number, nothing else. No Undo goes with either.
async function mark(action, project, number) {
  try {
    const r = await fetch(`/api/publications/${action}`, {
      method: "POST", headers: { "X-Clark-Token": token(), "Content-Type": "application/json" },
      body: JSON.stringify({ project, number }), cache: "no-store",
    });
    return { status: r.status, body: await r.json().catch(() => null) };
  } catch (e) {
    return { status: 0, body: null };
  }
}
export const archivePublication = (project, number) => mark("archive", project, number);
export const restorePublication = (project, number) => mark("restore", project, number);
export const readyPast = (project, number) => call(`/api/past-report?project=${encodeURIComponent(project)}&number=${encodeURIComponent(number)}`);
