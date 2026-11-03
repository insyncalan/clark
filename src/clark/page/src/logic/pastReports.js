// Settings › Published reports (#443): the words and the row view. Plain functions, no DOM and no Preact, so a test can run them
// alone. The server (past_reports.py) decides what a row holds and what Open may do; this file only turns its answers into the
// words a person reads. The page never shows text from a reply that it does not know: a refusal of a code it knows is shown as
// the server wrote it (plain sentences already, pinned by tests/test_past_reports_card.py), anything else gets a fallback.
//
// The words follow the prototype (system/prototype/views.js, "Published reports"): the same title, columns and "Not kept". One
// sentence differs on purpose: the owner's ruling (#348) is that every publication is kept and the list shows the latest 10, where
// the prototype said the last 10 copies were kept.

export const TITLE = "Published reports";
export const INTRO = "Every time you publish, the report gets the next number for this project and a copy of the page is kept. Open shows the copy as it was published. Every copy is kept; this list shows the latest 10.";
export const COLUMNS = ["#", "Date and time", "Where", "Who", ""];
export const NONE = "Nothing published yet. Each publish is listed here with its number.";
export const LOADING = "Looking for the published reports.";
export const NOT_KEPT = "Not kept";
export const TIMES = "Times are shown as UTC.";
export const LABELS = { open: "Open", tryAgain: "Try again" };
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

// Under the table: how many are shown of how many, when the list is cut.
export const cutLine = (total, shown) => (total > shown ? `Showing the latest ${shown} of ${total}. The older ones are kept.` : "");

// A list row as it is drawn.
export const rowView = (p) => ({ number: p.number, when: p.when, where: p.where, who: p.who, kept: p.kept === true });

// Whether a reply is a list the card can draw.
export const isList = (b) => !!b && b.ok === true && Array.isArray(b.publications) && Number.isInteger(b.total);
