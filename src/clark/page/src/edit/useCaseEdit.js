// What the use case summary's Edit controls ask of clark (A-D12): the name, the headline, the status and the "Where it stands"
// text of one use case, each one change with one Undo, through the same change route and Undo as every other edit
// (stores/changes.js, kind use_cases, clark/changes.py). The checks here only say the same thing first, in the server's words;
// the server checks again. Plain functions with no DOM.
import { change, say } from "../stores/changes.js";

export const NAME_LIMIT = 120;
export const HEADLINE_LIMIT = 300;
const HIDDEN = /[\p{Cc}\p{Cf}\p{Cs}\p{Co}\p{Zl}\p{Zp}]/u;

export const NAME_WORDS = `A use case needs a name of 1 to ${NAME_LIMIT} characters, with no line breaks or hidden characters.`;
export const HEADLINE_WORDS = `A headline can be at most ${HEADLINE_LIMIT} characters, with no line breaks or hidden characters.`;

/** A typed line as it is saved: runs of spaces and line breaks become one space, the ends are trimmed. */
export const tidy = (text) => String(text == null ? "" : text).replace(/\s+/g, " ").trim();

/** "" when `text` can be the name (field "title") or the headline, else the plain words to say. */
export function problem(field, text) {
  const limit = field === "title" ? NAME_LIMIT : HEADLINE_LIMIT;
  if (field === "title" && !text) return NAME_WORDS;
  if (Array.from(text).length > limit || HIDDEN.test(text)) return field === "title" ? NAME_WORDS : HEADLINE_WORDS;
  return "";
}

/** What a use case is called in a sentence: its name. */
export const called = (u) => u.title || u.ref || "this use case";

/** Save the name or headline. Resolves to the reply, or null (the toast has said why). Nothing is sent when it is unchanged. */
export function saveLine(u, field, raw) {
  const text = tidy(raw);
  if (text === (u[field] || "")) return Promise.resolve(null);
  const bad = problem(field, text);
  if (bad) { say("problem", bad); return Promise.resolve(null); }
  const words = field === "title" ? `Use case renamed to ${text}.` : text ? `Headline of ${called(u)} changed.` : `Headline of ${called(u)} cleared.`;
  return change({ kind: "use_cases", op: "update", id: u.id, changes: { [field]: text }, place: "cell" }, words);
}

export function saveStatus(u, status) {
  if (status === u.status) return Promise.resolve(null);
  return change({ kind: "use_cases", op: "update", id: u.id, changes: { status }, place: "menu" }, `Status of ${called(u)} changed to ${status}.`);
}

export function saveStanding(u, html) {
  return change({ kind: "use_cases", op: "update", id: u.id, changes: { standing: html }, place: "cell" }, `Where it stands for ${called(u)} saved.`);
}
