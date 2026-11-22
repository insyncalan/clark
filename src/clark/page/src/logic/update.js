// Settings › Version and updates: plain functions, no DOM and no Preact, so a test can run them alone. The server (updater.py,
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
  no_latest: "Look for the newest version first, then download it.",
};
// The refusals whose sentence comes from the server (each names a version, a system or a reason in words it checked itself).
export const SERVER_SAYS = ["name", "source", "system", "unreadable", "damaged", "incomplete", "unsafe", "unsigned", "badsig", "nokey", "older", "same", "min_from",
  "newer_data", "installed", "noversion", "folder", "git", "norecord", "link", "readonly", "toodeep", "blocked", "space", "backup", "staging", "first_check",
  "helper", "unfinished", "no_update", "undone", "data_changed", "backup_damaged", "data_gone", "data_restore"];
export const GENERIC = "That didn't work, and nothing was changed. Try again, or restart clark.";
export const NOT_ANSWERING = "Nothing is answering. Check that the window clark runs in is still open, then reload the page.";
export const STALE = "This page is out of date because clark was restarted. Reload the page and try again.";
export const LOADING = "Looking for updates.";
export const TITLE = "Version and updates";
export const INTRO = "Install a newer version from a file you downloaded from the clark releases page. Your projects, settings and published reports are kept.";
export const CANCELLED = "No file was chosen, so nothing was changed.";
export const COPIED = "The release notes are copied.";
export const NOT_COPIED = "The release notes couldn't be copied. Select them and copy them yourself.";
export const SLOW = "The new version is taking a while to start. Close every clark window, then open clark again.";
export const DISARMED = "Undo update was not confirmed in time, so nothing was changed.";
// The card's labelled rows (the prototype's Installed / Update / Install from a file / Last update) and the hint lines under the Update
// and Install from a file rows. The file hint names only the update for this computer; it names neither the other download nor the
// file type (updates.py: a sentence a person reads holds no word for the file type).
export const ROWS = { installed: "Installed", update: "Update", file: "Use a file instead", last: "Last update",
  // Row 1327, the approved table (comment 7016158346, rows 2 to 8): the row titles "Last checked", "Use a file instead", "Updated to clark <X>"
  // (X from the server's record) and "The download failed its check"; "Not checked yet" before the first look.
  checked: "Last checked", notChecked: "Not checked yet" };
export const updatedTo = (v) => `Updated to clark ${v}`;
export const FAILED_TITLE = "The download failed its check";
// The sentence under that title; it is the one the server sends for a download that failed its check (updater.py FETCH_TOOBIG), shown as sent.
export const FAILED_TEXT = "It was not installed and nothing changed. Try the download again; if it happens again, use a file from the releases page.";
export const FILE_TEXT = "For a computer with no internet. Review a clark download you already have.";
export const REVIEW_LABEL = "Review";
export const QUIET = "clark looks quietly when it starts and when you choose Check now. It never installs by itself.";
export const KEPT = "Your projects, settings and published reports are kept.";
// The installed row's text (table row 4); `from` is the version the update replaced.
export const installedText = (from) => `clark restarted and kept everything. If something looks wrong you can go back to ${from}.`;
export const HINTS = {
  upToDate: "Download the new version from the clark releases page, then choose it below.",
  ready: (v) => `Version ${v} is ready to install.`,
};
// The newest version on the releases page (the server's "latest" and "fetch"; updater.py). The sentences that come from the server
// (offline, the failed check) are shown as it sends them. None says "signed", and none names a file type.
export const FETCH = {
  looking: "Looking for the newest version.",
  notesLabel: "What is new in this version",
  cancelled: "Download cancelled.",
  ready: (v) => `Version ${v} is ready to download.`,
  latest: (v, when, today) => `You have the latest version (${v}).${checkedAt(when, today) ? ` Last checked ${checkedAt(when, today).replace(/^Today/, "today")}.` : ""}`,
  downloading: (v) => `Downloading version ${v}`,
  downloadingHint: "From the clark releases page, straight into clark. You do not need to sign in.",
  checkingHint: "Checking the download is complete and every file matches its list.",
  willChange: (add, rep, rem) => `Will add ${add} file${add === 1 ? "" : "s"}, replace ${rep}, remove ${rem}. You can undo it afterwards.`,
  progress: (pct) => `${pct}%`,
  downloaded: (v) => `Version ${v} is downloaded and checked.`,      // WORDING FOR APPROVAL (1327 s2): the mock-up's "is downloaded and checked" line
  didNotFinish: "The check did not finish. Try again.",
};
export const FETCH_LABELS = { download: "Download", checkNow: "Check now", cancel: "Cancel", tryAgain: "Try again", downloadAgain: "Download again",
  install: "Install and restart", notNow: "Not now" };

// The newest-version block as the Update row draws it: {kind, ...}. kind is one of "looking", "avail", "latest", "offline",
// "downloading", "checking", "ready", "failed", or "none" when the server told nothing (an older server, or no updates here).
export function fetchView(s) {
  const f = s && s.fetch && typeof s.fetch === "object" ? s.fetch : null;
  const l = s && s.latest && typeof s.latest === "object" ? s.latest : null;
  const v = (x) => text(x, 40);
  if (f && f.state === "downloading") return { kind: "downloading", version: v(f.version), pct: Math.max(0, Math.min(100, Number.isInteger(f.pct) ? f.pct : 0)) };
  if (f && f.state === "checking") return { kind: "checking", version: v(f.version) };
  if (f && f.state === "ready" && f.review && typeof f.review_id === "string") {
    const n = (x) => (x && Array.isArray(x.names) ? x.names.length : 0);
    return { kind: "ready", version: v(f.version), id: f.review_id, add: n(f.review.added), replace: n(f.review.replaced), remove: n(f.review.removed) };
  }
  if (f && f.state === "failed") return { kind: "failed", message: text(f.message, 600) };
  if (!l) return { kind: "none" };
  const when = text(l.checked, 40);
  if (l.state === "avail") return { kind: "avail", version: v(l.version), date: text(l.date, 40), size: text(l.size, 40), notes: text(l.notes, 20001), when, note: text(l.note, 600) };
  if (l.state === "latest") return { kind: "latest", version: v(s.version), when };
  if (l.state === "offline" || l.state === "unavailable") return { kind: "offline", message: text(l.message, 600), when };
  return { kind: "looking" };
}

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

// The ready card's second line (table row 1): "Released <date> · <size>." The size the server did not know is left out with its "·"
// (never "unknown"); with no date there is no line.
export function releasedText(f) {
  return f && f.kind === "avail" && f.date ? `Released ${[f.date, f.size].filter(Boolean).join(" · ")}.` : "";
}

// The server's stamp "DD-MM-YYYY HH:MM" as words: "Today HH:MM" when the day is `today` ("DD-MM-YYYY"), the stamp as it is on another day,
// "" when it is not a stamp.
function checkedAt(when, today) {
  const m = /^(\d\d-\d\d-\d{4}) (\d\d:\d\d)$/.exec(typeof when === "string" ? when : "");
  if (!m) return "";
  return m[1] === today ? `Today ${m[2]}` : when;
}

// The Last checked row's text (table row 2): "Today 11:42. <QUIET>", or "18-11-2026 11:42. <QUIET>", or "Not checked yet." alone (never "Never").
export function checkedText(when, today) {
  const t = checkedAt(when, today);
  return t ? `${t}. ${QUIET}` : `${ROWS.notChecked}.`;
}

// Today as "DD-MM-YYYY" (the stamp's own spelling), from a Date.
export function dayText(d) {
  const t = (n) => String(n).padStart(2, "0");
  return `${t(d.getDate())}-${t(d.getMonth() + 1)}-${d.getFullYear()}`;
}

// The status block: one of "blocked", "update" (a button "Review X.Y.Z" and the version it names) or "line" ("Up to date."), and the
// last update without the words "Last update: " in front (the row's label says them).
export function statusView(s) {
  return {
    installed: text(s.installed, 200),
    blocked: s.blocked ? text(s.blocked, 600) : "",
    review: s.available && typeof s.available.label === "string" ? text(s.available.label, 40) : "",
    version: s.available && typeof s.available.version === "string" ? text(s.available.version, 40) : "",
    line: s.line ? text(s.line, 200) : "",
    last: s.last && typeof s.last.line === "string" ? text(s.last.line, 200).replace(/^Last update: /, "") : "",
    lastTo: s.last && typeof s.last.to === "string" ? text(s.last.to, 40) : "",
    lastFrom: s.last && typeof s.last.from === "string" ? text(s.last.from, 40) : "",
    notice: s.notice ? text(s.notice, 600) : "",
    fetch: fetchView(s),
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
