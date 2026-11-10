// The Published reports page (#443; a page of its own since row 1087, reached from the profile circle): the words and the row view. Plain functions, no DOM and no Preact, so a test can run them
// alone. The server (past_reports.py) decides what a row holds and what Open may do; this file only turns its answers into the
// words a person reads. The page never shows text from a reply that it does not know: a refusal of a code it knows is shown as
// the server wrote it (plain sentences already, pinned by tests/test_past_reports_card.py), anything else gets a fallback.
//
// The words follow the prototype (system/prototype/views.js, "Published reports"): the same title, columns and "Not kept". One
// sentence differs on purpose: the owner's ruling (#348) is that every publication is kept and the list shows the latest 10, where
// the prototype said the last 10 copies were kept.

export const TITLE = "Published reports";
export const INTRO = "Every copy of this project's report that clark has published, newest first. Open an older one here, so you never need to look through folders.";
export const COLUMNS = ["No.", "Week ending", "Published", "Went to", "Files", ""];
export const NONE = "Nothing published yet. Each publish is listed here with its number.";
export const LOADING = "Looking for the published reports.";
export const NOT_KEPT = "Not kept";
export const NOT_RECORDED = "Not recorded";
// Row 1087 (the mockup's words): the page's own lines. The times are the person's own, in their zone, and the zone is named.
export const PAGE = { latest: "Latest", earlier: "Earlier reports", saved: "Where it is saved", local: "Local folder", client: "Client folder", notChosen: "Not chosen yet",
  change: "Change in Settings", record: "The list comes from clark's own record of what it published, not from the folder, so other files in the folder are never shown." };
export const timesLine = (zone) => `Times are shown in your time zone${zone ? ", " + zone : ""}.`;
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

const DAY = /^\d{4}-\d\d-\d\d$/;
const dmy = (iso) => (typeof iso === "string" && DAY.test(iso) ? iso.slice(8) + "-" + iso.slice(5, 7) + "-" + iso.slice(0, 4) : NOT_RECORDED);
const STAMP = /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/;

/** `at` (UTC, YYYY-MM-DDTHH:MM:SSZ) as "DD-MM-YYYY at HH:MM" in the person's own zone (`zone`: a test's, else the browser's); "Not recorded" for anything else. */
export function whenIn(at, zone) {
  if (typeof at !== "string" || !STAMP.test(at)) return NOT_RECORDED;
  try {
    const parts = new Intl.DateTimeFormat("en-GB", { timeZone: zone || undefined, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(new Date(at));
    const g = (t) => (parts.find((x) => x.type === t) || {}).value;
    if (!g("year")) return NOT_RECORDED;
    return `${g("day")}-${g("month")}-${g("year")} at ${g("hour")}:${g("minute")}`;
  } catch (e) { return NOT_RECORDED; }
}

/** The person's zone by its name ("Gulf Standard Time"), or "" when the browser cannot say. */
export function zoneName(zone, at) {
  try {
    const p = new Intl.DateTimeFormat("en-GB", { timeZone: zone || undefined, timeZoneName: "long" }).formatToParts(at).find((x) => x.type === "timeZoneName");
    return p ? p.value : "";
  } catch (e) { return ""; }
}

// Where a publication went, in the page's words: the server says "Local", "Local and to client", with " · Word" for a Word copy; any other value is not a destination the page knows, so it says "Not recorded".
const wentTo = (where) => (typeof where === "string" && where.startsWith("Local and to client") ? "Local folder, Client folder" : typeof where === "string" && /^Local( |$)/.test(where) ? "Local folder" : NOT_RECORDED);
const filesOf = (p) => (p.word === true ? "Word" : p.pdf === true ? "Page, PDF" : "Page");

// A list row as it is drawn.
export const rowView = (p, zone) => ({ number: p.number, when: p.at ? whenIn(p.at, zone) : p.when, week: dmy(p.week), went: wentTo(p.where), files: filesOf(p), who: p.who, kept: p.kept === true, archived: p.archived === true });

// Whether a reply is a list the card can draw.
export const isList = (b) => !!b && b.ok === true && Array.isArray(b.publications) && Number.isInteger(b.total);
