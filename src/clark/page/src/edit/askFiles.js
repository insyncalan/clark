// #1292 S14: files and pictures for the next question. The rules only (no page here): at most 5 files of 10 MB each, the kinds taken, the
// plain sentence for each refusal, the size as KB or MB, and the bin. The files are used for this one question and are not kept in the project.
export const FILE_MAX = 5;
export const FILE_BYTES = 10 * 1024 * 1024;

const TEXT = /\.(txt|md|csv)$/i, PICTURE = /\.(png|jpe?g)$/i, DOCUMENT = /\.(pdf|docx|xlsx)$/i;

export const ATTACH_LABEL = "Add a file";
export const FILES_LABEL = "Files for the next question";
export const SCREEN_LINE = "Screened for passwords and keys, then sent with your next question to Claude.";
export const THIS_QUESTION_LINE = "Files you add are used for this question only and are not kept in the project.";
export const DROP_LINE = "Drop a file or picture to add it to your next question";
export const REMOVE_FILE = (name) => `Remove ${name}`;
export const TOO_MANY = `${FILE_MAX} files at most for one question. Remove one first.`;
export const NOT_THIS_KIND = (name) => `${name} cannot be used. Add text, Markdown, CSV, PDF, Word, Excel, PNG or JPEG files.`;
export const TOO_BIG = (name) => `${name} is over ${FILE_BYTES / 1048576} MB. Add a smaller one.`;
export const EMPTY_FILE = (name) => `${name} is empty. Add one with something in it.`;

export function sizeText(n) {
  return n < 1048576 ? Math.max(1, Math.round(n / 1024)) + " KB" : (n / 1048576).toFixed(1) + " MB";
}

export function kindOf(name) {
  return TEXT.test(name) ? "text" : PICTURE.test(name) ? "picture" : DOCUMENT.test(name) ? "document" : "";
}

let nextId = 1;

/** `current` is what already waits, `incoming` the files just chosen (anything with name and size). Returns the new list and one plain
 *  sentence for each file (or, for the limit, once) that was not taken; a refused file never stops the ones after it. */
export function addFiles(current, incoming) {
  const files = [...current], notes = [];
  for (const f of incoming) {
    if (files.length >= FILE_MAX) { if (!notes.includes(TOO_MANY)) notes.push(TOO_MANY); continue; }
    const kind = kindOf(f.name);
    if (!kind) { notes.push(NOT_THIS_KIND(f.name)); continue; }
    if (f.size > FILE_BYTES) { notes.push(TOO_BIG(f.name)); continue; }
    if (f.size < 1) { notes.push(EMPTY_FILE(f.name)); continue; }
    nextId = Math.max(nextId, ...files.map((x) => x.id + 1));
    files.push({ id: nextId++, name: f.name, size: f.size, kind, file: f });
  }
  return { files, notes };
}

export function removeFile(files, id) {
  return files.filter((f) => f.id !== id);
}

/** What is sent with the question: each file's name and its bytes in base64. The server screens and reads them; nothing is kept. */
export async function encodeFiles(files) {
  const out = [];
  for (const f of files) {
    const bytes = new Uint8Array(await f.file.arrayBuffer());
    let raw = "";
    for (let i = 0; i < bytes.length; i += 0x8000) raw += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    out.push({ name: f.name, data: btoa(raw) });
  }
  return out;
}
