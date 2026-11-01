// "Make into": the request that turns a chosen passage into one new work item. No AI runs. Plain JS, no DOM.
// The request is the one the report's add-a-row change already takes (changes.py: actions, raid and decisions, op "new"); the text is the
// passage on one line, 200 characters at most (the store's limit for an item's title).
export const ITEM_TEXT_MAX = 200;

const KINDS = {
  action: { kind: "actions", values: (t) => ({ description: t }), done: "Action added." },
  risk: { kind: "raid", values: (t) => ({ type: "Risk", description: t }), done: "Risk added." },
  decision: { kind: "decisions", values: (t) => ({ decision: t }), done: "Decision added." },
};

// The passage as an item's title: one line, trimmed, cut with an ellipsis when it is longer than the store takes.
export function itemText(text) {
  const one = String(text || "").split(/\s+/).filter(Boolean).join(" ");
  return one.length > ITEM_TEXT_MAX ? one.slice(0, ITEM_TEXT_MAX - 1).trimEnd() + "…" : one;
}

// null when the kind is unknown or there is no text.
export function makeIntoRequest(id, text) {
  const k = Object.prototype.hasOwnProperty.call(KINDS, id) ? KINDS[id] : null;
  const t = itemText(text);
  if (!k || !t) return null;
  return { kind: k.kind, op: "new", values: k.values(t) };
}

export const makeIntoDone = (id) => (Object.prototype.hasOwnProperty.call(KINDS, id) ? KINDS[id].done : "");
