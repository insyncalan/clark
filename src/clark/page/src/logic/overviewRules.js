// Settings > Projects overview (row 1299 slice 2): the three needs-attention rules, the problem phrases and the chip counts. Plain functions, no DOM and no
// Preact, so a test can run them alone. The rules are the mock-up's (FINAL-settings-A7, function `projects`): (1) no client folder; (2) the last backup is
// more than 1 day old; (3) asking is on and no folder is added to read. The words are here so the page and its tests read the same sentences.

export const TITLE = "Projects overview";
export const INTRO = "Every project at a glance. Click a value to open that setting for the project. Grey is the default, amber is something to fix.";
export const COLUMNS = ["Project", "Asking", "Brand", "Read folders", "Review days", "Client folder", "Last backup"];
export const LOADING = "Looking for your projects.";
export const FAILED = "The projects could not be read. Choose Try again. If it happens again, restart clark.";
export const NONE = "No projects yet.";
export const NO_FOLDERS = "none";
export const TRY_AGAIN = "Try again";

const whole = (v) => (typeof v === "number" && Number.isInteger(v) && v >= 0 ? v : null);

/** The rows of GET /api/projects-overview ({asking, last_backup: {days}, projects: [{code, name, brand, review_days, client_folder, read_folders}]}) as the page keeps them
 * (the rules read these names). Asking and the newest backup are the computer's one value each, copied into every row. A value the read cannot give is null (not known):
 * it shows "not known" and never raises a problem. */
export function rowsOf(body) {
  const asking = typeof body.asking === "boolean" ? body.asking : null;
  const days = body.last_backup && typeof body.last_backup === "object" ? whole(body.last_backup.days) : null;
  return (Array.isArray(body.projects) ? body.projects : []).map((r) => ({
    code: String(r.code), name: typeof r.name === "string" && r.name ? r.name : String(r.code), asking,
    brand: typeof r.brand === "string" ? r.brand : "", folders: whole(r.read_folders), reviewDays: reviewDays(r.review_days),
    clientFolder: typeof r.client_folder === "string" ? r.client_folder.trim() : null, lastBackupDays: days,
  }));
}

/** Review days as the store reads them (review_days_for): a whole number 1 to 365, else the default of 14. */
export function reviewDays(v) {
  return Number.isInteger(v) && v >= 1 && v <= 365 ? v : 14;
}

/** The problems of one row, in the mock-up's words, in the mock-up's order. Not known (null) is never a problem. */
export function problems(row) {
  const out = [];
  if (row.clientFolder === "") out.push(`${row.name} has no client folder`);
  if (row.lastBackupDays !== null && row.lastBackupDays > 1) out.push(`${row.name}: last backup ${row.lastBackupDays} days ago`);
  if (row.asking && row.folders === 0) out.push(`${row.name}: asking is on, no folders`);
  return out;
}

export const needsLook = (row) => problems(row).length > 0;

/** Every problem of every row, in row order. */
export const allProblems = (rows) => rows.flatMap(problems);

export const NOT_KNOWN = "not known";
export const backupWords = (days) => (days === null ? NOT_KNOWN : days === 0 ? "Today" : days === 1 ? "1 day ago" : `${days} days ago`);
export const askingWords = (on) => (on === null ? NOT_KNOWN : on ? "On" : "Off");
