// Settings › Data and Settings › Projects' forms (item 444): the words, and the plain rules for what the page sends and shows. No DOM and no
// Preact, so a test can run them alone. The words are the prototype's (system/prototype/views.js, io.js), with the build's own where the
// prototype names its browser database. Nothing here is sent: the server checks every request again.

// Why Export and Import workbook are grey with no project open (issue 682; wording approved).
export const IMPORT_NEEDS_PROJECT = "Add a project first.";

export const DATA = {
  title: "Data",
  export: "Export workbook",
  import: "Import workbook",
  note: "The workbook has a sheet each for actions, risks and issues, decisions, milestones and use cases.",
};

export const IMPORT = {
  pickTitle: "Import from Excel",
  pickBody: "Sheets called Actions, Risks & Issues, Decisions, Milestones and Use cases can be imported. You choose which after you pick a file (a History sheet from an export is left alone). A row whose ID exists updates it; a row without an ID adds a new one. You see the changes before anything is saved. If a row breaks a rule, nothing is imported and you are told which rows.",
  sheetsTitle: "What to import",
  sheetsBody: "Tick the sheets to import. Anything you leave unticked is not read and not changed.",
  selectAll: "Select all",
  clear: "Clear",
  continue: "Continue",
  tickOne: "Tick at least one sheet.",
  changesToCheck: "Changes to check",
  accept: "Accept",
  reject: "Reject",
  acceptAll: "Accept all",
  rejectAll: "Reject all",
  acceptNote: "Accept archives it. It is not deleted.",
  newNote: "gets the next free ID",
  choose: "Choose a file",
  template: "Get the template",
  templateSaved: "Your browser has saved the template",     // then its name: a workbook with the right sheets and columns and no rows
  templateFailed: "The template could not be made. Reload the page. If it happens again, restart clark.",
  checkTitle: "Check the import",
  checking: "Reading the workbook.",
  cancel: "Cancel",
  close: "Close",
  none: "Nothing in this workbook differs from what clark has, so there is nothing to import.",
  already: "That workbook was already imported as it is, so there is nothing to import. Save it again after editing it, or export a fresh one.",
  unrecorded: "There is no record of exporting this workbook from clark, so clark cannot say what you changed in it. Check it is the right file; every difference is listed and nothing is accepted that archives a row.",
  anyway: "Import anyway",
  undo: "Undo this import",
  undone: "Put back as it was before the import.",
  readFailed: "That file could not be read as a spreadsheet.",
  tooBig: "That file is more than 25 MB, more than clark will open. A clark export is far smaller. Check it is the right file.",
  notAnswering: "There was no answer. Check that the window clark runs in is still open, then try again.",
  stale: "This page is out of date because clark was restarted after you opened it. Reload the page and try again.",
  fallback: "That could not be done. Reload the page. If it happens again, restart clark.",
};

// "Actions (12 rows)", "Decisions (1 row)", "Risks & Issues (0 rows)", "Actions (more than 2,000 rows)": a sheet's name and how many rows it holds.
export const SHEET_ROWS_SHOWN = 2000;       // excel_import.MAX_ROWS: list_sheets gives one past it to any sheet the check would refuse, so such a sheet is named, never given a wrong number
export const sheetWord = (s) => `${s.name} (${s.rows > SHEET_ROWS_SHOWN ? "more than 2,000 rows" : `${s.rows} ${s.rows === 1 ? "row" : "rows"}`})`;

// The columns the import reads, per sheet, as the prototype lists them in the first box (tests/test_settings_data_page.py checks them
// against the export's own layout in excel.py, leaving out the ones that are worked out or never read back).
export const COLUMNS_INTRO = "Columns, in any order (only the name or title is needed):";
export const IMPORT_COLUMNS = [
  ["Actions", ["ID", "Description", "Workstream", "Owner", "Priority", "Due", "Status", "Raised", "Latest update", "Client-visible", "Client wording", "Milestone", "Use case", "Labels"]],
  ["Risks & Issues", ["ID", "Description", "Type", "Workstream", "Owner", "Response action", "Due", "Impact", "Likelihood", "Status", "Raised", "Client-visible", "Client wording", "Milestone", "Use case", "Labels"]],
  ["Decisions", ["ID", "Decision", "Status", "Made by", "Needed by", "Date", "Reasoning", "Options", "Revisit", "Replaces", "Client-visible", "Client wording", "Use case", "Labels"]],
  ["Milestones", ["ID", "Milestone", "Description", "Workstream", "Agreed", "Forecast", "Status", "Order", "% complete", "Owner", "State", "State reason", "Movement", "Achieved on", "Client-visible", "Client wording", "Internal note"]],
  ["Use cases", ["ID", "Use case", "Shown as", "Status", "Commitment", "Headline", "Where it stands", "Order", "Client-visible"]],
];

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
export const archivedOpenWords = (name, next) => `${name} archived. ${next} is open now. Show archived brings it back.`;

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

// The refusal of a whole file (the prototype's, io.js): one row that breaks a rule and nothing is imported.
export const refusedHead = (k) => `Nothing was imported, because ${k} ${k === 1 ? "row breaks a rule" : "rows break a rule"}:`;
export const refusedFoot = (k) => `Fix ${k === 1 ? "it" : "them"} in the workbook and import again. Nothing was changed.`;

// The counts row of the check: [number, word] pairs, as the prototype's (new, updated, refused, not in the workbook). A count of 0 for the
// last two is left out. The prototype's "skipped (no name)" and "left alone (archived)" are not counted by the server, so they are not here.
export function countsRow(r) {
  const c = (r && r.counts) || {};
  const row = [[c.new || 0, "new"], [c.changed || 0, "updated"]];
  if (r && r.refused && r.refused.length) row.push([r.refused.length, "refused"]);
  if (c.removed) row.push([c.removed, "not in the workbook"]);
  return row;
}

// The per-sheet line: "Work items: 1 new, 2 updated · Milestones: ... · Use cases: ..." (actions, risks and decisions are the Work items).
export function sheetLine(r) {
  const of = (tables, kind) => ((r && r.items) || []).filter((i) => tables.includes(i.table) && i.kind === kind).length;
  const part = (name, tables) => `${name}: ${of(tables, "new")} new, ${of(tables, "changed")} updated`;
  return [part("Work items", ["actions", "raid", "decisions"]), part("Milestones", ["milestones"]), part("Use cases", ["use_cases"])].join(" · ");
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
