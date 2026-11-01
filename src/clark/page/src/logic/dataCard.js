// Settings › Data and Settings › Projects' forms (#444): the words, and the plain rules for what the page sends and shows. No DOM and no
// Preact, so a test can run them alone. The words are the prototype's (system/prototype/views.js, io.js), with the build's own where the
// prototype names its browser database. Nothing here is sent: the server checks every request again.

export const DATA = {
  title: "Data",
  export: "Export workbook",
  import: "Import workbook",
  reset: "Reset the demo data",
  note: "The workbook has a sheet each for actions, risks and issues, decisions, milestones and use cases. Export saves this project's as an Excel workbook; your browser saves the file and nothing is sent or published. Import shows what would change before anything is saved.",
};

export const RESET = {
  title: "Reset the demo data?",
  body: "Every change you made here is replaced by the starting demo data.",
  go: "Reset",
  done: "The demo data is back as it started.",
  failed: "The demo data could not be put back. Nothing was changed.",
};

export const IMPORT = {
  pickTitle: "Import from Excel",
  pickBody: "Sheets called Actions, Risks and issues (or RAID), Decisions, Milestones and Use cases are read. A row whose ID exists updates it; a row without an ID adds a new one. You see the changes before anything is saved.",
  choose: "Choose a file",
  checkTitle: "Check the import",
  checking: "Reading the workbook.",
  cancel: "Cancel",
  close: "Close",
  none: "Nothing in this workbook differs from what clark has, so there is nothing to import.",
  already: "That workbook was already imported as it is, so there is nothing to import. Save it again after editing it, or export a fresh one.",
  unrecorded: "clark has no record of exporting this workbook, so it cannot say what you changed in it. Check it is the right file; every difference is listed and nothing is ticked that archives a row.",
  anyway: "Import anyway",
  undo: "Undo this import",
  undone: "Put back as it was before the import.",
  readFailed: "That file could not be read as a spreadsheet.",
  tooBig: "That file is more than 25 MB, more than clark will open. A clark export is far smaller. Check it is the right file.",
  notAnswering: "clark did not answer. Check that the window clark runs in is still open, then try again.",
  stale: "This page is out of date: clark was restarted after you opened it. Reload the page and try again.",
  fallback: "That could not be done. Reload the page. If it happens again, restart clark.",
};

export const PROJECT = {
  newTitle: "New project",
  newNote: "You can import its work items, milestones and use cases from Excel afterwards.",
  editTitle: (name) => `Edit ${name}`,
  name: "Name",
  namePlace: "For example: Finance System Upgrade",
  code: "Short code",
  codePlace: "3 to 7 letters or digits",
  client: "Client",
  clientPlace: "Who the reports are for",
  workstreams: "Workstreams",
  workstreamsPlace: "Separated by commas",
  create: "Create project",
  save: "Save",
  cancel: "Cancel",
  created: (name) => `${name} created.`,
  saved: "Project saved.",
  codeTaken: "That code is already in use.",
  workstreamsNote: "A workstream you take out of the list is closed; its items keep it.",
};

export const ONLY_ONE = "This is your only project, so it can't be archived. Add another project first.";
export const archivedOpenWords = (name, next) => `${name} archived. clark has opened ${next}. Show archived brings it back.`;

// "Finance System Upgrade" -> "FSU": the first letters of the words, capitals, at most 4 (the prototype's suggestion).
export function suggestCode(name) {
  return String(name || "").split(/\s+/).map((w) => (w[0] || "")).join("").toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 4);
}

// The code as it is sent: capitals; the form's pattern is 3 to 7 letters or digits, starting with a letter.
export const CODE_RE = /^[A-Z][A-Z0-9]{2,6}$/;
export const cleanCode = (text) => String(text || "").trim().toUpperCase();

// "Build, Run , ,build" -> ["Build", "Run"]: split on commas, trimmed, empty ones and repeats (any case) left out.
export function splitWorkstreams(text) {
  const seen = new Set(), out = [];
  for (const part of String(text || "").split(",")) {
    const w = part.trim().replace(/\s+/g, " ");
    if (w && !seen.has(w.toLowerCase())) { seen.add(w.toLowerCase()); out.push(w); }
  }
  return out;
}

// What a project form sends. `mode` is "new" or "edit".
export function projectRequest(mode, f) {
  return { op: mode, code: cleanCode(f.code), name: String(f.name || "").trim(), client: String(f.client || "").trim(), workstreams: splitWorkstreams(f.workstreams) };
}

// Which project the page opens when the open one is archived: the first live project that is not it, or null when there is none
// (then the archive is refused in words, because a page with no project open has nothing to show).
export function nextAfterArchive(live, code) {
  const other = (live || []).find((r) => r.code !== code);
  return other ? other.code : null;
}

// The check's reply as the box shows it: the counts in a line, and the numbers each choice sends.
export function summaryLine(r) {
  const c = (r && r.counts) || {};
  const part = (n, w) => `${n} ${w}`;
  return [part(c.new || 0, "new"), part(c.changed || 0, "changed"), part(c.removed || 0, "no longer in the workbook"), part(r && r.unchanged || 0, "unchanged")].join(", ") + ".";
}

// The numbers ticked, in order. `ticked` is an object {n: true}. Items past the shown ones follow their own default.
export function acceptedNumbers(items, ticked) {
  return items.filter((i) => (Object.prototype.hasOwnProperty.call(ticked, i.n) ? ticked[i.n] : i.default) && !i.problem).map((i) => i.n);
}

// The starting ticks: what the server says Accept all takes (a new or changed row with no problem and no clash).
export function startTicks(items) {
  const t = {};
  for (const i of items) t[i.n] = !!i.default;
  return t;
}

export const KIND_WORD = { new: "New", changed: "Changed", removed: "Not in the workbook" };

// Base64 of bytes in pieces, so a large workbook does not overflow the call stack.
export function toBase64(bytes) {
  let s = "";
  const step = 0x8000;
  for (let i = 0; i < bytes.length; i += step) s += String.fromCharCode.apply(null, bytes.subarray(i, i + step));
  return btoa(s);
}

// The words for a reply that was not ok. The server's own sentence is shown only for the statuses it answers in plain words (400, 404,
// 409, 410, 503) and only when it is a sentence of a reasonable length; anything else is the fallback for the status.
export function replyWords(status, body) {
  const said = body && typeof body.message === "string" && body.message.length <= 800 ? body.message : "";
  if (status === 0) return IMPORT.notAnswering;
  if (status === 403) return IMPORT.stale;
  if (said && [400, 404, 409, 410, 503].includes(status)) return said;
  return IMPORT.fallback;
}
