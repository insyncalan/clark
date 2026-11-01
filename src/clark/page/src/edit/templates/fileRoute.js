// The Files and links templates' one request of their own (#96): POST /api/section-file {project, section}. clark opens the system's
// file window, copies the chosen file into the client folder's "Report files" folder and adds it to the section, in one step with
// one Undo (the copy stays in the folder: Undo takes it off the section). Edit only; never in a published file. The route's
// refusals are plain words with the next step (src/clark/section_files.py), shown as they are when the reply has their shape.
import { token, project, reread, plain } from "../../stores/report.js";
import { say } from "../../stores/changes.js";

const KNOWN = [200, 400, 404, 409];

// The words for a reply that did not add a file.
export function fileWords(status, body) {
  if (KNOWN.includes(status) && body && typeof body.code === "string" && /^[a-z_]+$/.test(body.code)
      && typeof body.message === "string" && body.message && body.message.length <= 400) return body.message;
  if (status === 0 || status === 403) return plain(status, body);
  if (status === 503) return "The file could not be added just now, and nothing was changed. Wait a moment and try again.";
  return "Something went wrong, and no file was added. Try again. If it happens again, restart clark.";
}

// Ask for a file for section `id`. Resolves to "added", "cancelled" or "refused" (the toast says what happened).
export async function chooseFile(id) {
  const code = project.value;
  let status = 0, body = null;
  try {
    const r = await fetch("/api/section-file", {
      method: "POST", cache: "no-store",
      headers: { "X-Clark-Token": token(), "Content-Type": "application/json" },
      body: JSON.stringify({ project: code, section: id }),
    });
    status = r.status;
    body = await r.json().catch(() => null);
  } catch (e) { status = 0; }
  if (status === 200 && body && body.ok === true) {
    if (body.cancelled) return "cancelled";
    await reread(code);
    say("done", typeof body.message === "string" && body.message ? body.message : "File added.", body.apply_id || null, code);
    return "added";
  }
  say("problem", fileWords(status, body));
  return "refused";
}
