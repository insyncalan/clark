// Settings › Published reports (#443): the words and the row view. Plain functions, no DOM and no Preact, so a test can run them
// alone. The server (past_reports.py) decides what a row holds and what Open may do; this file only turns its answers into the
// words a person reads. The page never shows text from a reply that it does not know: a refusal of a code it knows is shown as
// the server wrote it (plain sentences already, pinned by tests/test_past_reports_card.py), anything else gets a fallback.
//
// The words follow the prototype (system/prototype/views.js, "Published reports"): the same title, columns and "Not kept". One
// sentence differs on purpose: the owner's ruling (#348) is that every publication is kept and the list shows the latest 10, where
// the prototype said the last 10 copies were kept.

export const TITLE = "Published reports";
export const INTRO = "Every copy of this project's report that clark has published, newest first. Open an older one here, so you never need to look through folders.";
export const COLUMNS = ["No.", "Week ending", "Date", "Where it went", "Files", "Who", ""];
export const LATEST = "Latest", EARLIER = "Earlier reports", SAVED = "Where it is saved", LOCAL_FOLDER = "Local folder", CLIENT_FOLDER = "Client folder";
export const NO_LOCAL = "No local folder yet.", NO_CLIENT = "No client folder yet.";
export const CHANGE_IN_SETTINGS = "Change in Settings";
export const SAVED_NOTE = "The list comes from clark's own record of what it published, not from the folder, so other files in the folder are never shown.";
export const EARLIER_NONE = "No earlier reports.";
export const NOT_RECORDED = "Not recorded";
export const NONE = "Nothing published yet. Each publish is listed here with its number.";
export const LOADING = "Looking for the published reports.";
export const NOT_KEPT = "Not kept";
export const timesLine = (zone) => `Times are shown in your own time zone: ${zone}.`;
export const LABELS = { open: "Open", tryAgain: "Try again", archive: "Archive", restore: "Restore", showArchived: "Show archived" };
export const ARCHIVED_TAG = "Archived";
export const ALL_ARCHIVED = "Every publication is archived. Show archived brings them back.";
export const archivedToast = (n) => `Publication ${n} archived. Restore it from Show archived.`;
export const restoredToast = (n) => `Publication ${n} restored. Archive it again if you want it out of the list.`;
export const LIST_FAILED = "The published reports could not be read. Reload the page and try again.";
export const OPEN_FAILED = "That report could not be opened. Try again; if it keeps happening, restart clark.";
export const BLOCKED = "The report could not be opened. Allow pop-ups for this page, then try again.";
export const NOT_ANSWERING = "Nothing is answering. Check that the window clark runs in is still open, then reload the page.";
export const STALE = "This page is out of date because clark was restarted. Reload the page and try again.";

// The codes of the server's own refusals to Open, whose sentences name the publication and so come from the server.
export const SERVER_SAYS = ["not_kept", "copy_changed", "no_publication", "project_not_found"];

const sentence = (body) => (body && typeof body.message === "string" && body.message.trim() && body.message.length <= 600 ? body.message : "");

// {status, body} of the list → one sentence.
export function listWords(status, body) {
  if (status === 0) return NOT_ANSWERING;
  if (status === 403) return STALE;
  return LIST_FAILED;
}

// {status, body} of Open → one sentence.
export function openWords(status, body) {
  if (status === 0) return NOT_ANSWERING;
  if (status === 403) return STALE;
  const code = body && typeof body.code === "string" ? body.code : "";
  if (SERVER_SAYS.includes(code) && sentence(body)) return sentence(body);
  return OPEN_FAILED;
}

// {status, body} of Archive or Restore → one sentence. A refusal the server worded (400 or 409, a short plain sentence) is shown as written.
export function markWords(status, body) {
  if (status === 0) return NOT_ANSWERING;
  if (status === 403) return STALE;
  if ((status === 400 || status === 409) && sentence(body) && body.message.length <= 200 && !/[\u0000-\u001f]/.test(body.message)) return body.message;
  return LIST_FAILED;
}

// Under the table: how many are shown of how many, when the list is cut.
export const cutLine = (total, shown) => (total > shown ? `Showing the latest ${shown} of ${total}. The older ones are kept.` : "");

const dmy = (iso) => (/^\d{4}-\d\d-\d\d$/.test(iso) ? iso.slice(8) + "-" + iso.slice(5, 7) + "-" + iso.slice(0, 4) : "");

// The server's times are UTC ("DD-MM-YYYY HH:MM"). `localWhen` gives the same shape in the person's own zone (`zone` is a seam for the tests;
// the browser's own zone when it is left out); a text that is not a time is returned as it came.
export function localWhen(when, zone) {
  const m = /^(\d\d)-(\d\d)-(\d{4}) (\d\d):(\d\d)$/.exec(String(when));
  if (!m) return String(when);
  const at = new Date(Date.UTC(+m[3], +m[2] - 1, +m[1], +m[4], +m[5]));
  if (Number.isNaN(at.getTime())) return String(when);
  try {
    const f = new Intl.DateTimeFormat("en-GB", { timeZone: zone || undefined, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
    const g = {};
    for (const p of f.formatToParts(at)) g[p.type] = p.value;
    return `${g.day}-${g.month}-${g.year} ${g.hour}:${g.minute}`;
  } catch (e) { return String(when); }
}

// The name of the person's zone, in words ("Gulf Standard Time"); the zone's own id when the browser has no name for it.
export function zoneName(zone) {
  try {
    const part = new Intl.DateTimeFormat("en-GB", { timeZone: zone || undefined, timeZoneName: "long" }).formatToParts().find((p) => p.type === "timeZoneName");
    if (part && part.value) return part.value;
  } catch (e) { /* falls through */ }
  return zone || "your computer's time zone";
}

// A number's rows as one line: a page and its Word copy share the number, the time and the folders (the server lists each file as a row).
export function groups(pubs, zone) {
  const by = new Map();
  for (const p of pubs) {
    const g = by.get(p.number) || { number: p.number, page: false, word: false, kept: false, archived: false, client: false, whenUtc: "", week: "", who: "" };
    const first = !by.has(p.number);
    if (p.word === true) g.word = true; else g.page = true;
    g.kept = g.kept || p.kept === true;
    g.archived = g.archived || p.archived === true;
    g.client = g.client || /to client/.test(String(p.where));
    if (first || (p.word !== true && !g.pageSeen)) { g.whenUtc = p.when; g.who = p.who; }
    if (p.word !== true) g.pageSeen = true;
    if (!g.week && /^\d{4}-\d\d-\d\d$/.test(String(p.week))) g.week = p.week;
    by.set(p.number, g);
  }
  return [...by.values()].map((g) => ({
    number: g.number, kept: g.kept, archived: g.archived, who: g.who || NOT_RECORDED,
    when: localWhen(g.whenUtc, zone), week: dmy(g.week), files: [g.page ? "Page" : "", g.word ? "Word" : ""].filter(Boolean).join(", "),
    folders: g.client ? [LOCAL_FOLDER, CLIENT_FOLDER] : [LOCAL_FOLDER],
  }));
}

export const wentRow = (g) => g.folders.join(", ");
export const wentLatest = (g) => "Went to the " + g.folders.join(" and the ");
export const publishedBadge = (g) => { const [d, t] = g.when.split(" "); return t ? `Published ${d} at ${t}` : `Published ${g.when}`; };
export const latestHead = (g) => `Publication ${g.number}` + (g.week ? ` \u00b7 Week ending ${g.week}` : "");

// Whether a reply is a list the card can draw.
export const isList = (b) => !!b && b.ok === true && Array.isArray(b.publications) && Number.isInteger(b.total);
