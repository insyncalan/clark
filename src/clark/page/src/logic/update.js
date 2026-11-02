// Settings › clark version and updates: plain functions, no DOM and no Preact, so a test can run them alone. The server (updater.py,
// updates.py, update_install.py) decides everything; this file turns its answers into the words a person reads. A code it knows has
// its sentence here (WORDS; tests/test_update_page.py keeps them equal to the server's), the refusals that come with their own plain
// sentence are shown as they are (SERVER_SAYS), and anything else gets GENERIC.

export const WORDS = {
  bad_request: "That could not be read. Reload the page and try again.",
  busy: "An update is being installed. One moment.",
  none_found: "There is no update in your Downloads folder. Download it from the clark releases page, or choose the file.",
  review_again: "Review the update again, then install it.",
  arm_again: "Choose Undo update again: the second click must come within 5 seconds of the first.",
  dialog: "The window to choose a file could not be opened. Try again; if it keeps happening, restart clark.",
  updating: "An update is being installed, so nothing was changed. Wait a minute, then reload the page.",
  no_updates: "Updates can't be shown right now. Restart clark the usual way and try again.",
};
// The refusals whose sentence comes from the server (each names a version, a system or a reason in words it checked itself).
export const SERVER_SAYS = ["name", "source", "system", "unreadable", "damaged", "incomplete", "unsafe", "older", "same", "min_from",
  "newer_data", "installed", "noversion", "folder", "git", "norecord", "link", "readonly", "toodeep", "blocked", "space", "backup", "staging", "first_check",
  "helper", "no_update", "undone", "data_changed", "backup_damaged", "data_gone", "data_restore"];
export const GENERIC = "That didn't work, and nothing was changed. Try again, or restart clark.";
export const NOT_ANSWERING = "Nothing is answering. Check that the window clark runs in is still open, then reload the page.";
export const STALE = "This page is out of date because clark was restarted. Reload the page and try again.";
export const LOADING = "Looking for updates.";
export const TITLE = "clark version and updates";
export const INTRO = "Your projects, settings and published reports are kept when clark is updated.";
// The labels of the rows and the hints under them, in the words of the prototype's card.
export const ROWS = { installed: "Installed", update: "Update", file: "Install from a file", last: "Last update" };
export const UP_TO_DATE = "Up to date";   // the server says this, with a full stop, when nothing newer is in Downloads (updater.UP_TO_DATE; a test keeps them equal); the row has no full stop, as the prototype draws it
export const HINT_NONE = "Download the new clark from the release page, then choose the zip below";
export const HINT_FILE = "The zip attached to the release, named like clark-X.Y.Z-mac.zip (or -windows or -linux), not the source code zip";
export const hintReady = (version) => `clark ${version} is ready to install`;
export const CANCELLED = "No file was chosen, so nothing was changed.";
export const COPIED = "The release notes are copied.";
export const NOT_COPIED = "The release notes couldn't be copied. Select them and copy them yourself.";
export const SLOW = "The new version is taking a while to start. Close every clark window, then open clark again.";
export const DISARMED = "Undo update was not confirmed in time, so nothing was changed.";
export const LABELS = { choose: "Choose zip…", install: "Install", installAgain: "Install again", cancel: "Cancel", copy: "Copy",
  files: "Show the files", undo: "Undo update", undoConfirm: "Undo update", appOnly: "Put back the app and settings only", tryAgain: "Try again" };

// {status, body} → one sentence. Status 0 is no answer; 403 is a page from before clark was restarted.
export function answerWords(status, body) {
  if (status === 0) return NOT_ANSWERING;
  if (status === 403) return STALE;
  const code = body && typeof body.code === "string" ? body.code : "";
  if (Object.prototype.hasOwnProperty.call(WORDS, code)) return WORDS[code];
  if (SERVER_SAYS.includes(code) && typeof body.message === "string" && body.message.trim() && body.message.length <= 600) return body.message;
  return GENERIC;
}

const text = (v, n = 600) => (typeof v === "string" ? v.slice(0, n) : "");

// The review as the panel draws it: the heading, the notes (or the line that there are none), the checksum line, the changed-by-hand
// line, the three file lists with their counts, and the line that the person's things are kept.
export function reviewView(r) {
  const list = (x) => ({ label: text(x && x.label, 80), names: Array.isArray(x && x.names) ? x.names.slice(0, 2000).map((n) => text(n, 300)) : [] });
  return {
    heading: text(r.heading, 200),
    notes: text(r.notes_text, 20000),
    hasNotes: typeof r.notes === "string" && r.notes.trim() !== "",
    checksum: text(r.checksum_text, 200),
    byHand: r.by_hand ? text(r.by_hand, 300) : "",
    lists: [list(r.replaced), list(r.added), list(r.removed)],
    kept: text(r.kept, 300),
  };
}

// The status block: one of "blocked", "update" (a button "Review X.Y.Z", with its version) or "line" ("Up to date").
export function statusView(s) {
  return {
    installed: text(s.installed, 200),
    blocked: s.blocked ? text(s.blocked, 600) : "",
    review: s.available && typeof s.available.label === "string" ? text(s.available.label, 40) : "",
    version: s.available && typeof s.available.version === "string" ? text(s.available.version, 40) : "",
    line: s.line ? text(s.line, 200) : "",
    last: s.last && typeof s.last.line === "string" ? text(s.last.line, 200) : "",
    notice: s.notice ? text(s.notice, 600) : "",
  };
}

// After an install or undo the server stops and the new version starts with a new token. `who` gives a promise of "old", "new" or
// "down" (updateApi.whoAnswers); `sleep` waits a number of ms. Resolves "reload" as soon as the new run answers, or "slow".
export async function waitForRestart(who, sleep, tries = 120) {
  for (let i = 0; i < tries; i += 1) {
    if ((await who()) === "new") return "reload";
    await sleep(1000);
  }
  return "slow";
}
