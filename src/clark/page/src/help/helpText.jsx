// Help's small markup as page parts, never as HTML text (#82): **bold**, `code`, [[Mod+Enter]] keys, [words](#place) a link
// inside Help and [words](go:screen) a link to a screen. Whatever the text holds is drawn as text.
import { canGo, follow, goTo } from "./helpStore.js";

const KEY_NAMES = { Enter: "Enter", Esc: "Esc", Left: "←", Right: "→", Up: "↑", Down: "↓", Space: "Space", Tab: "Tab" };
const MAC = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent || "");
const TOKEN = /\[\[(.+?)\]\]|\*\*(.+?)\*\*|`([^`]+)`|\[([^\]]+)\]\((#|go:)([^)]+)\)/g;

const keys = (k) => k.split(/\+(?!$)/).map((p, i) => [i ? "+" : "", <kbd>{p === "Mod" ? (MAC ? "⌘" : "Ctrl") : KEY_NAMES[p] || p}</kbd>]);

/** The text as page parts. `mark` (optional) lets a search highlight plain stretches. */
export function Md({ text }) {
  const s = String(text == null ? "" : text), out = [];
  let last = 0, m;
  TOKEN.lastIndex = 0;
  while ((m = TOKEN.exec(s))) {
    if (m.index > last) out.push(s.slice(last, m.index));
    if (m[1] != null) out.push(keys(m[1]));
    else if (m[2] != null) out.push(<b>{m[2]}</b>);
    else if (m[3] != null) out.push(<code>{m[3]}</code>);
    else if (m[5] === "#") out.push(<a href="#" class="hp-a" data-hlink={m[6]} onClick={(e) => { e.preventDefault(); follow(m[6]); }}>{m[4]}</a>);
    else if (canGo(m[6])) out.push(<a href="#" class="hp-a hp-goa" data-hgo={m[6]} onClick={(e) => { e.preventDefault(); goTo(m[6]); }}>{m[4]}</a>);
    else out.push(m[4]);                                  // a screen that is not built yet: the words, not a link
    last = m.index + m[0].length;
  }
  if (last < s.length) out.push(s.slice(last));
  return <>{out}</>;
}
