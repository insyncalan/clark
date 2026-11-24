// The Files and links templates' one request of their own (#96): POST /api/section-file {project, section}. clark opens the system's
// file window, copies the chosen file into the client folder's "Report files" folder and adds it to the section, in one step with
// one Undo (the copy stays in the folder: Undo takes it off the section). Edit only; never in a published file. The route's
// refusals are plain words with the next step (src/clark/section_files.py), shown as they are when the reply has their shape.
import { token, project, reread, plain } from "../../stores/report.js";
import { zoneFetch } from "../../api.js";
import { say } from "../../stores/changes.js";
import { openInNewTab } from "../../router.js";
import { fileReader } from "../../templates/DocLinks.jsx";
import { DROP_ONE, DROP_TOO_BIG, DROP_UNREAD, DROP_MAX_BYTES } from "../../logic/docLinksWords.js";

const KNOWN = [200, 400, 404, 409];      // the drop route answers 400 for too_big and a drop it could not read, in the same shape

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
    const r = await zoneFetch("/api/section-file", {
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

// Row 1275: a file dropped on the Documents and links area. `drop` is the browser's DataTransfer. Refused whole, with nothing sent,
// when it holds more than one file or a folder, or one over 25 MB; otherwise one POST of the raw bytes (the same token header as every
// write; the project, the section and the URL-encoded name in headers) to /api/section-file-drop, and the same toast and Undo as the file
// window's. Resolves to "added" or "refused".
export async function dropFile(id, drop) {
  const code = project.value;
  const list = Array.from((drop && drop.files) || []);
  const items = Array.from((drop && drop.items) || []);
  const folder = items.some((i) => { const e = typeof i.webkitGetAsEntry === "function" ? i.webkitGetAsEntry() : null; return !!e && e.isDirectory; });
  if (list.length !== 1 || items.length > 1 || folder) { say("problem", DROP_ONE); return "refused"; }
  const file = list[0];
  if (file.size > DROP_MAX_BYTES) { say("problem", DROP_TOO_BIG); return "refused"; }
  let bytes;
  try { bytes = await file.arrayBuffer(); } catch (e) { say("problem", DROP_UNREAD); return "refused"; }
  let status = 0, body = null;
  try {
    const r = await zoneFetch("/api/section-file-drop", {
      method: "POST", cache: "no-store",
      headers: { "X-Clark-Token": token(), "Content-Type": "application/octet-stream", "X-Clark-Project": code, "X-Clark-Section": id,
                 "X-Clark-File-Name": encodeURIComponent(file.name) },
      body: bytes,
    });
    status = r.status;
    body = await r.json().catch(() => null);
  } catch (e) { status = 0; }
  if (status === 200 && body && body.ok === true) {
    await reread(code);
    say("done", typeof body.message === "string" && body.message ? body.message : "File added.", body.apply_id || null, code);
    return "added";
  }
  say("problem", fileWords(status, body));
  return "refused";
}

// Row 1221: the editor View's Open and Download on a file row (templates/DocLinks.jsx): GET /api/section-file?project=&name=[&download=1]
// with the token (a new tab cannot send it, so the bytes are read here and handed to the browser as a blob). Open: a new tab; Download:
// the browser's own save. A refusal says plain()'s words for its status, as every other read does.
async function readFile(name, download) {
  // The blob for the file, or null when it was refused (the toast says why).
  const blobUrl = async () => {
    try {
      const r = await zoneFetch(`/api/section-file?project=${encodeURIComponent(project.value)}&name=${encodeURIComponent(name)}${download ? "&download=1" : ""}`,
        { headers: { "X-Clark-Token": token() }, cache: "no-store" });
      if (!r.ok) {
        const body = await r.json().catch(() => null);
        say("problem", plain(r.status, body));
        return null;
      }
      const url = URL.createObjectURL(await r.blob());
      setTimeout(() => URL.revokeObjectURL(url), 60000);
      return url;
    } catch (e) {
      say("problem", plain(0));
      return null;
    }
  };
  if (!download) { await openInNewTab(blobUrl); return; }   // the router opens and points the tab: only it sets an address
  const url = await blobUrl();
  if (!url) return;
  const a = document.createElement("a");
  a.href = url; a.download = name;
  document.body.appendChild(a); a.click(); a.remove();
}
fileReader.read = readFile;
