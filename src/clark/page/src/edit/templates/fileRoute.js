// The Files and links templates' one request of their own (#96): POST /api/section-file {project, section}. clark opens the system's
// file window, copies the chosen file into the client folder's "Report files" folder and adds it to the section, in one step with
// one Undo (the copy stays in the folder: Undo takes it off the section). Edit only; never in a published file. The route's
// refusals are plain words with the next step (src/clark/section_files.py), shown as they are when the reply has their shape.
import { token, project, reread, plain } from "../../stores/report.js";
import { zoneFetch } from "../../api.js";
import { say } from "../../stores/changes.js";
import { openInNewTab } from "../../router.js";
import { fileReader } from "../../templates/DocLinks.jsx";
import { DROP_FOLDER, DROP_TOO_BIG, DROP_UNREAD, DROP_MAX_BYTES } from "../../logic/docLinksWords.js";

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
    problemLines(body).forEach((line) => say("problem", line));
    return "added";
  }
  const lines = problemLines(body);
  if (lines.length) lines.forEach((line) => say("problem", line));
  else say("problem", fileWords(status, body));
  return "refused";
}

// Row 1593: each file a batch refused has its OWN problem line, "{file name}: {reason}" (a separate message from the added toast).
// The lines are the server's words, taken as they are when they have the shape.
function problemLines(body) {
  return body && Array.isArray(body.problems) ? body.problems.filter((l) => typeof l === "string" && l && l.length <= 400).slice(0, 20) : [];
}

// The line for one refused file: the server's reply for it, led by the file's name unless it names it already.
const lineFor = (name, text) => (text.startsWith(`${name}: `) ? text : `${name}: ${text}`);

// Row 1275 and 1593: files dropped on the Documents and links area. `drop` is the browser's DataTransfer. A folder in the drop refuses
// the whole drop with nothing sent. One file: one POST of its raw bytes (the same token header as every write; the project, the section
// and the URL-encoded name in headers), the same toast and Undo as the file window's. Several files: each is checked on its own and sent
// in its own request (25 MB stays per file) with X-Clark-Hold, which copies it and adds nothing; then ONE commit request adds every held
// file in one step, so there is one toast and one Undo. A refused file has its own problem line. Resolves to "added" or "refused".
export async function dropFile(id, drop) {
  const list = Array.from((drop && drop.files) || []);
  const items = Array.from((drop && drop.items) || []);
  const folder = items.some((i) => { const e = typeof i.webkitGetAsEntry === "function" ? i.webkitGetAsEntry() : null; return !!e && e.isDirectory; });
  if (list.length === 0 && !folder) return "refused";          // an empty drop: nothing to add, nothing to say
  if (folder) { say("problem", DROP_FOLDER); return "refused"; }
  if (list.length === 1) return dropOne(id, list[0]);
  return dropMany(id, list);
}

// One request for the bytes of `file`: {status, body}, or {refusal} when it was refused before anything was sent.
async function sendBytes(id, file, hold) {
  const code = project.value;
  if (file.size > DROP_MAX_BYTES) return { refusal: DROP_TOO_BIG };
  let bytes;
  try { bytes = await file.arrayBuffer(); } catch (e) { return { refusal: DROP_UNREAD }; }
  let status = 0, body = null;
  try {
    const r = await zoneFetch("/api/section-file-drop", {
      method: "POST", cache: "no-store",
      headers: { "X-Clark-Token": token(), "Content-Type": "application/octet-stream", "X-Clark-Project": code, "X-Clark-Section": id,
                 "X-Clark-File-Name": encodeURIComponent(file.name), ...(hold ? { "X-Clark-Hold": "1" } : {}) },
      body: bytes,
    });
    status = r.status;
    body = await r.json().catch(() => null);
  } catch (e) { status = 0; }
  return { status, body };
}

async function dropOne(id, file) {
  const code = project.value;
  const sent = await sendBytes(id, file, false);
  if (sent.refusal) { say("problem", sent.refusal); return "refused"; }
  const { status, body } = sent;
  if (status === 200 && body && body.ok === true) {
    await reread(code);
    say("done", typeof body.message === "string" && body.message ? body.message : "File added.", body.apply_id || null, code);
    return "added";
  }
  say("problem", fileWords(status, body));
  return "refused";
}

async function dropMany(id, list) {
  const code = project.value;
  const held = [], lines = [];
  for (const file of list) {
    const sent = await sendBytes(id, file, true);
    if (sent.refusal) { lines.push(lineFor(file.name, sent.refusal)); continue; }
    const { status, body } = sent;
    if (status === 200 && body && body.ok === true && body.held && typeof body.held.name === "string") held.push(body.held.name);
    else lines.push(lineFor(file.name, fileWords(status, body)));
  }
  let status = 0, body = null;
  if (held.length) {
    try {
      const r = await zoneFetch("/api/section-file-drop", {
        method: "POST", cache: "no-store",
        headers: { "X-Clark-Token": token(), "Content-Type": "application/octet-stream", "X-Clark-Project": code, "X-Clark-Section": id,
                   "X-Clark-Commit": encodeURIComponent(JSON.stringify(held)) },
        body: new ArrayBuffer(0),
      });
      status = r.status;
      body = await r.json().catch(() => null);
    } catch (e) { status = 0; }
  }
  const added = status === 200 && body && body.ok === true;
  if (added) {
    await reread(code);
    lines.push(...problemLines(body));
    // There is ONE toast slot and a problem toast replaces what is on show, so a drop of good files plus a refused one says both in the ONE
    // toast that carries the Undo: what was added, then each refused file with its reason (row 1593; the single "problem" toast hid the Undo).
    const head = typeof body.message === "string" && body.message ? body.message : `${Array.isArray(body.added) && body.added.length ? body.added.length : held.length} files added.`;
    say("done", [head, ...lines].join(" "), body.apply_id || null, code);
  } else {
    if (held.length) {
      const more = problemLines(body);
      lines.push(...(more.length ? more : [fileWords(status, body)]));
    }
    if (lines.length) say("problem", lines.join(" "));      // nothing was added: all the refusals in the one toast (a toast per file would show only the last)
  }
  return added ? "added" : "refused";
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
