// Settings › Safety: the backup list, Preview and Restore (#111). Plain functions, no DOM and no Preact, so a test can run them alone.
// The server (safety.py) decides everything; this file only turns its answers into the words a person reads. The page never shows a
// reply's text that it does not know: a code it knows has its sentence here (WORDS; tests/test_safety_logic.py keeps them equal to
// safety.py's), the refusals of the backup and database code are plain sentences already and are shown as they are, and anything
// else gets GENERIC.

export const WORDS = {
  busy: "Something is being saved. Wait a moment and try again.",
  changed: "Your data changed after you looked. Look at the backup again.",
  in_use: "Another window or program has clark's data open. Close it there and try again.",
  bad_request: "Choose a backup from the list and try again.",
  folder: "The backups folder can't be read. Check that it is a folder and that you can open it, then try again.",
  reopen: "The backup was put back, but clark could not open it again. Close clark and start it again.",
  no_backups: "Backups can't be shown right now. Restart clark the usual way and try again.",
};
// The refusals whose sentence comes from the server because it names the backup (a name that passed the server's own check).
export const SERVER_SAYS = ["no_backup", "damaged", "newer", "other_database", "migrate_failed", "unfinished", "file_problem", "refused"];
export const GENERIC = "That didn't work, and nothing was changed. Try again, or restart clark.";
export const NOT_ANSWERING = "Nothing is answering. Check that the window clark runs in is still open, then reload the page.";
export const STALE = "This page is out of date because clark was restarted. Reload the page and try again.";
export const LOADING = "Looking for your backups.";
export const NONE_SHOWN = "There are no backups to show yet.";
export const TITLE = "Backups";
export const INTRO = "A copy of your data is kept each day, and before an undo or an import. Choose one to look at, or to put back.";
export const LABELS = { preview: "Preview", restore: "Restore", putBack: "Put it back", cancel: "Cancel", close: "Close", tryAgain: "Try again" };

// {status, body} → one sentence. Status 0 is no answer; 403 is a page from before clark was restarted.
export function answerWords(status, body) {
  if (status === 0) return NOT_ANSWERING;
  if (status === 403) return STALE;
  const code = body && typeof body.code === "string" ? body.code : "";
  if (Object.prototype.hasOwnProperty.call(WORDS, code)) return WORDS[code];
  if (SERVER_SAYS.includes(code) && typeof body.message === "string" && body.message.trim() && body.message.length <= 600) return body.message;
  return GENERIC;
}

// A list row as it is drawn: the date and time, the kind in words, and the size.
export const rowView = (b) => ({ name: b.name, when: b.when, kind: b.kind_label, size: b.size_text });

export const plural = (n, one, many) => `${n} ${n === 1 ? one : many || one + "s"}`;
export const holds = (c) => `${plural(c.projects, "project")}, ${plural(c.work_items, "work item")} and ${plural(c.milestones, "milestone")}`;

// What Preview says. Nothing here changes anything.
export function previewLines(p) {
  const lines = [`This backup is from ${p.when}. It holds ${holds(p.copy)}.`];
  if (p.now) lines.push(`You have ${holds(p.now)} now.`);
  if (p.older && p.older_note) lines.push(p.older_note);
  if (!p.same_database) lines.push("This is a backup of a different database, so it can't be put back over yours.");
  return lines;
}
export const canRestore = (p) => !!p && p.same_database !== false;
export const confirmLine = (p) => `Put back the backup from ${p.when}? What you have now is kept first.`;

// The sentence shown once after a restore: kept in sessionStorage across the reload (never anywhere longer), in try/catch because
// storage can be unavailable. Nothing but the sentence is kept.
const KEY = "clark-safety-done";
export function rememberDone(text, store) {
  try { (store || window.sessionStorage).setItem(KEY, String(text).slice(0, 300)); return true; } catch (e) { return false; }
}
export function takeDone(store) {
  try {
    const s = store || window.sessionStorage;
    const v = s.getItem(KEY);
    if (v !== null) s.removeItem(KEY);
    return v || "";
  } catch (e) { return ""; }
}
