// The first-run setup page (row 836, step 5): plain functions, no DOM and no Preact, so a test can run them alone. The page only
// draws what the server's checks say: a list of {id, status, words}, the shape the spec gives GET /api/setup/checks. Each line's
// words come from the doctor (src/clark/doctor.py) and are shown as they are; nothing here repeats one of them. The status labels
// are the doctor's own (doctor.LABELS), so a line reads the same here and in the Terminal.

export const LABELS = { ready: "Ready:", fix: "To fix:", advice: "Worth knowing:", "not checked": "Not checked:" };   // doctor.py:38
// NEW words (not in the product yet; listed for approval in the row 836 report; NEW-WORDS.md items 8 and 10 for the first two).
export const TITLE = "Setting up clark";
export const CHECK_AGAIN = "Check again";
export const ALL_READY = "Everything is ready. Opening clark.";
export const CHOOSE_FOLDER = "Choose a folder…";
export const LOADING = "Checking this computer.";
export const REFUSED = "The checks could not be read. Check that the window clark runs in is still open, then choose Check again.";
export const FOLDER_FAILED = "That folder could not be chosen. Nothing was changed.";
export const FOLDER_NONE = "No folder was chosen, so nothing was changed.";

const MAX_WORDS = 600;

// The server's answer to the checks -> the lines to draw, or null when the answer is not the list (refused, or not understood).
export function linesFrom(r) {
  if (!r || r.status !== 200) return null;
  const list = Array.isArray(r.body) ? r.body : r.body && Array.isArray(r.body.checks) ? r.body.checks : null;
  if (!list) return null;
  const out = [];
  for (const c of list) {
    if (!c || typeof c.words !== "string" || c.words === "" || c.words.length > MAX_WORDS) return null;
    const status = Object.prototype.hasOwnProperty.call(LABELS, c.status) ? c.status : "not checked";
    out.push({ id: String(c.id == null ? out.length : c.id).slice(0, 60), status, label: LABELS[status], words: c.words });
  }
  return out;
}

// Only a line that is ready lets the person go on; advice does not stop them, a fix does. An empty list is not "all ready".
export const allReady = (lines) => lines.length > 0 && lines.every((l) => l.status === "ready" || l.status === "advice");
export const problems = (lines) => lines.filter((l) => l.status === "fix" || l.status === "not checked");

export const lineClass = (status) => (status === "fix" ? "error" : "");   // a line that needs fixing is drawn in the shell's error colour

// The folder chooser's answer -> {kind: "chosen" | "none" | "error", text}. The server checks the folder and says why it refused in a
// sentence of its own; that sentence is shown as it is when it is short plain text.
export function folderAnswer(r) {
  if (r && r.status === 200 && r.body && r.body.ok === true) return r.body.cancelled === true ? { kind: "none", text: FOLDER_NONE } : { kind: "chosen", text: "" };
  const m = r && r.body && typeof r.body.message === "string" && r.body.message.length > 0 && r.body.message.length <= MAX_WORDS ? r.body.message : FOLDER_FAILED;
  return { kind: "error", text: m };
}
