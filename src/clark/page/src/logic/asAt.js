// The words of the Dashboard "as at" a day (#349), as plain functions with no DOM: the Settings picker (edit/AsAtPick.jsx) and the
// banner over the rebuilt Dashboard (components/AsAtBanner.jsx). The banner's sentence is the #125 design note's (the prototype's
// past.js): it is never what anyone was sent, so it says "rebuilt from the change history" every time.
export const LABEL = "Dashboard as at a day";
export const HINT = "See the Dashboard as it stood at the end of a day, rebuilt from the change history. Read only; it was not published in this form.";
export const SHOW = "Show";
export const READING = "Rebuilding the Dashboard…";
export const NO_DAY = "Type a day as DD-MM-YYYY.";
export const BACK = "Back to now";
export const SMALL = "Read only · this was not published in this form";
// The server's own sentences the page may show, by code (as_at.py MESSAGES); any other answer gets the general words below.
export const SERVER_SAYS = ["bad_date", "future", "not_yet", "project_not_found"];
export const GENERAL = "The Dashboard could not be rebuilt for that day. Try again; if it keeps happening, restart clark.";
export const NO_ANSWER = "There was no answer. Check that clark is still running, then try again.";

export const shown = (iso) => (/^\d{4}-\d\d-\d\d$/.test(iso || "") ? iso.slice(8) + "-" + iso.slice(5, 7) + "-" + iso.slice(0, 4) : String(iso || ""));
export const say = (iso) => `You are looking at the dashboard as at ${shown(iso)}, rebuilt from the change history.`;

/** The plain words for an answer that was not the data. */
export function failWords(status, body) {
  if (!status) return NO_ANSWER;
  if (body && SERVER_SAYS.includes(body.code) && typeof body.message === "string" && body.message) return body.message;
  return GENERAL;
}

/** True when the answer is the rebuilt data for `code` and `day`. */
export function isData(body, code, day) {
  return !!(body && body.ok === true && body.as_at === day && body.data && body.data.project && body.data.project.code === code);
}
