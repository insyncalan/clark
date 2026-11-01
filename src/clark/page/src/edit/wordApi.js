// The page's only way to the Word routes (#48): POST /api/word-export and POST /api/word-import. No other file names them, so the
// published page (view.jsx) has no way to write a Word file or read one, and no mention of them. Nothing here names a folder or a
// file path: the report folder and the client folder are the ones clark already knows, and the Word file arrives as the bytes the
// person chose, sent as text in the request.
import { plain } from "../stores/report.js";
import { call } from "./publishApi.js";

export const WORD_FILE_MB = 25;        // the largest Word file clark reads (WORD_FILE_MB in server.py); a bigger one is refused here, before it is sent

// The refusal for a file over the limit, in the server's own words so the person reads the same thing from either place.
export const tooBig = (name) => `${name} is bigger than the ${WORD_FILE_MB} MB that clark can open. Save a smaller copy (for example without big pictures), then choose it again. Nothing was added.`;
// A file whose name does not end in .docx is refused here, before it is read or sent (the box's file picker only suggests Word files).
export const isWordName = (name) => /\.docx$/i.test(String(name || ""));
export const notWord = (name) => `${name} is not a Word file. Choose a Word file.`;
export const EMPTY = "That file is empty. Choose the Word file again.";
export const UNREADABLE = "That file could not be read by your browser. Choose the Word file again.";

export const importRequest = (body) => call("POST", "/api/word-import", body);

// The words for a reply. The Word routes write plain words themselves (word_route.py: a test pins that none has a technical word),
// so the message of an answer in their shape (a stable `code` and a `message`) is shown as it is. No answer, or a refusal by the
// server's token check, gets the page's own words; anything else gets the fallback, which says what is still true.
export function words(r, fallback) {
  const b = r.body;
  if (r.status === 0 || r.status === 403) return plain(r.status, b);
  if (b && typeof b.code === "string" && /^[a-z_]+$/.test(b.code) && typeof b.message === "string" && b.message && b.message.length <= 1500) return b.message;
  return fallback;
}

// The file as text for the request: {ok: true, data} (the bytes, as base64) or {ok: false, message}. A file over the limit is
// refused before it is read.
export function readFile(file) {
  if (!file) return Promise.resolve({ ok: false, message: "Choose a Word file first." });
  if (file.size > WORD_FILE_MB * 1024 * 1024) return Promise.resolve({ ok: false, message: tooBig(file.name) });
  if (file.size === 0) return Promise.resolve({ ok: false, message: EMPTY });
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onerror = () => resolve({ ok: false, message: UNREADABLE });
    reader.onload = () => {
      const text = typeof reader.result === "string" ? reader.result : "";
      const at = text.indexOf("base64,");
      resolve(at < 0 ? { ok: false, message: UNREADABLE } : { ok: true, data: text.slice(at + 7) });
    };
    reader.readAsDataURL(file);
  });
}

export const checkRequest = (project, name, data) => importRequest({ op: "check", project, name, data });
export const applyRequest = (project, plan, accept) => importRequest({ op: "apply", project, plan, accept });
export const undoRequest = (project, applyId) => importRequest({ op: "undo", project, apply_id: applyId });

export const EXPORT_FAILED = "Something went wrong while the Word report was being saved. Check the folder before you try again. If it happens again, restart clark.";

// Ask the server to save the report as a Word file. `clash` is null the first time, or {on_clash: "number" | "overwrite"} after the
// person answered the question about a name that is taken (a replace is confirmed by then). Resolves to one of
// {kind: "saved" | "cancelled" | "problem", message} or {kind: "clash", message, canReplace}.
export async function exportWord(code, toClient, clash) {
  const body = { project: code, to_client: !!toClient };
  if (clash) {
    body.on_clash = clash.on_clash;
    if (clash.on_clash === "overwrite") body.confirmed = true;
  }
  const r = await call("POST", "/api/word-export", body);
  const b = r.body;
  if (r.status === 200 && b && b.ok === true && typeof b.message === "string") return { kind: b.cancelled === true ? "cancelled" : "saved", message: b.message };
  if (r.status === 409 && b && b.code === "name_taken" && typeof b.message === "string") {
    return { kind: "clash", message: b.message, canReplace: b.can_replace === true && Array.isArray(b.choices) && b.choices.includes("overwrite") };
  }
  return { kind: "problem", message: words(r, EXPORT_FAILED) };
}
