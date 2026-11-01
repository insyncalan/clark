// The "Not reviewed after (days)" setting (#160): the pure part, with no DOM, no clock and no fetch. One number for a project,
// 14 until it is changed. The Python side (src/clark/freshness.py check_days) says the same words, and a test pins that.
export const DEFAULT_REVIEW_DAYS = 14;
export const MAX_REVIEW_DAYS = 3650;
export const REVIEW_DAYS_WORDS = `Use a whole number of days from 1 to ${MAX_REVIEW_DAYS}. The setting stays as it was.`;

/** What was typed (or sent), checked: {ok: true, days} for a whole number from 1 to 3650, else {ok: false, message} in plain
 *  words. 0, a negative, a fraction, an empty box, a word and a true or false are all refused; the caller keeps the old number. */
export function parseReviewDays(value) {
  const text = typeof value === "number" || typeof value === "string" ? String(value).trim() : "";
  if (/^[0-9]{1,5}$/.test(text)) {
    const n = Number(text);
    if (n >= 1 && n <= MAX_REVIEW_DAYS) return { ok: true, days: n };
  }
  return { ok: false, message: REVIEW_DAYS_WORDS };
}

/** The number a project carries (its review_days), or the default when it has none or a bad one. */
export function daysOf(project) {
  const r = parseReviewDays(project && project.review_days);
  return r.ok ? r.days : DEFAULT_REVIEW_DAYS;
}
