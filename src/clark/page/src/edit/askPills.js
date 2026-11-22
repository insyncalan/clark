// Row 1332: the suggestions above the ask box, as one pure function. Help open beats everything; then the subject the last question named; then the
// page that is open; then the general list. The items of the last answer (rows 3 and 11) put what can be done about them in front of that list. What the project holds (state) only puts one of that subject's own questions first. At most PILLS_MAX.
import * as W from "./askWords.js";

const ORDER = ["overdue", "red", "noOwner"];

/** view: the open page; turns: the chat so far; help: is Help open; state: { overdue, red, noOwner } counts (optional). Returns the words, never mutates its input. */
export function pills(view, turns, help, state) {
  if (help) return W.PILLS_HELP.slice(0, W.PILLS_MAX);
  const list = Array.isArray(turns) ? turns : [];
  const acts = actionsFor(lastItems(list)).map((a) => a.label);
  const asked = [...list].reverse().find((t) => t && t.role === "user" && typeof t.text === "string");
  const said = asked ? asked.text.toLowerCase().replace(/[-_\s]+/g, " ") : "";
  // A whole word (or its plural), with the space inside a two-word name optional: "use-case", "usecase" and "use case" all match.
  const named = (word) => new RegExp("(^|[^a-z])" + word.replace(/ /g, " ?") + "s?([^a-z]|$)").test(said);
  const hit = W.PILLS_WORDS.find(([word]) => named(word));
  const subject = hit ? hit[1] : W.PILLS_PAGE[view];
  const set = W.PILLS_BY_SUBJECT[subject] || W.SUGGESTIONS;
  return [...new Set([...acts, ...inOrder(set, W.PILLS_STATE[subject], state)])].slice(0, W.PILLS_MAX);
}

/** The question a clicked suggestion sends. The shown words never change; the two that act on named items send them with the ids in brackets. */
export function asking(label, turns) {
  const list = Array.isArray(turns) ? turns : [];
  const hit = actionsFor(lastItems(list)).find((a) => a.label === label);
  return hit ? hit.ask : label;
}

// The items of the last answer: the newest assistant turn that is an answer (a note is not), its items that have an id and only the known words.
// Items are not kept with a chat in History (DRAFT): a chat opened from History has none, so it shows no action suggestions.
function lastItems(list) {
  const answer = [...list].reverse().find((t) => t && t.role === "assistant" && !t.kind);
  const items = answer && Array.isArray(answer.items) ? answer.items : [];
  return items.filter((i) => i && typeof i.id === "string" && i.id).map((i) => ({ id: i.id, state: Array.isArray(i.state) ? i.state : [] }));
}

// What can be done about those items, each built from the items it is true of: the due date of the overdue ones, the urgency of the overdue ones that
// are not red yet. Why late is asked only when one is overdue; who owns, and the report, whenever the answer named an item.
function actionsFor(items) {
  if (!items.length) return [];
  const has = (i, w) => i.state.includes(w);
  const ids = (rows) => rows.map((i) => i.id).join(", ");
  const late = items.filter((i) => has(i, "overdue"));
  const soft = late.filter((i) => !has(i, "red"));
  return [
    late.length ? { label: W.PILLS_ITEM_DUE, ask: `${W.PILLS_ITEM_DUE} (${ids(late)})` } : null,
    soft.length ? { label: W.PILLS_ITEM_URGENCY, ask: `${W.PILLS_ITEM_URGENCY} (${ids(soft)})` } : null,
    late.length ? { label: W.PILLS_ITEM_LATE, ask: W.PILLS_ITEM_LATE } : null,
    { label: W.PILLS_ITEM_OWNERS, ask: W.PILLS_ITEM_OWNERS },
    { label: W.PILLS_ITEM_REPORT, ask: W.PILLS_ITEM_REPORT },
  ].filter(Boolean);
}

// The questions the state asks for go first, the larger count first (a tie: overdue, red, no owner); the rest keep their order.
function inOrder(set, wanted, state) {
  if (!wanted || !state) return set.slice();
  const first = ORDER.filter((k) => wanted[k] && state[k] > 0 && set.includes(wanted[k]))
    .sort((a, b) => state[b] - state[a] || ORDER.indexOf(a) - ORDER.indexOf(b)).map((k) => wanted[k]);
  return [...new Set([...first, ...set])];
}
