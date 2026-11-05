// The Help peek's pure rules (#645 steps 3 to 5): which screen "?" means, and the one shape the panel draws whatever contextText(page)
// hands back. No page, no signals: bundled alone in the quick tests.

/** The screen "?" means: a LIVE_SCREENS name; the Dashboard is "dashboard+edit" while you edit. */
export function screenOf(view, mode) {
  return view === "dashboard" && mode === "edit" ? "dashboard+edit" : view;
}

/** What the panel draws: { title, lines, cards: [{ name, line }], full }, or null when there is nothing to draw (no title, no line and no card).
 *  `t` is what contextText(page) returns: a title, its sentences (`sentences` or `lines`), optional `cards` lines (a string, or { name, line }),
 *  and `full`, the place in the full Help the foot link opens. Everything is text: a value that is not a string is read as one, never as markup. */
export function shapeContext(t) {
  if (!t || typeof t !== "object" || !t.title) return null;
  const text = (x) => String(x == null ? "" : x).trim();
  const list = (a) => (Array.isArray(a) ? a : a ? [a] : []);
  const lines = list(t.sentences || t.lines).map(text).filter(Boolean);
  const cards = list(t.cards).map((c) => (c && typeof c === "object" ? { name: text(c.name || c.title), line: text(c.line || c.text) } : { name: "", line: text(c) })).filter((c) => c.line || c.name);
  if (!lines.length && !cards.length) return null;
  return { title: text(t.title), lines, cards, full: text(t.full) };
}
