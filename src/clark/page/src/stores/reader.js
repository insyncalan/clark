// What the reader of a published file keeps for themselves (issue 713), in their own browser only: the name in their profile and the
// Light / Dark / System choice. Both live in localStorage and nowhere else: never in the file, the data block, an address or a
// workbook. Every read and write is inside try/catch, because storage can be blocked (a private window, a policy) or full; then
// the page works and simply forgets. A published file only: the editor keeps its own look and profile.
import { signal } from "@preact/signals";

export const NAME_KEY = "clark.reader.name";
export const LOOK_KEY = "clark.reader.look";
export const LOOKS = ["light", "dark", "system"];
const NAME_MAX = 80;

const read = (k) => { try { return window.localStorage.getItem(k); } catch (e) { return null; } };
const write = (k, v) => { try { if (v === null) window.localStorage.removeItem(k); else window.localStorage.setItem(k, v); } catch (e) { /* not kept */ } };

/** The name as it is kept: trimmed, spaces squeezed, cut to a sane length; "" when there is none. */
export const cleanName = (s) => String(s == null ? "" : s).replace(/\s+/g, " ").trim().slice(0, NAME_MAX);

/** Up to two letters: the first letter of the first and of the last word of the name ("Ada Lovelace" gives "AL"; "(Bob) Smith" gives "BS");
 *  "" for no name. A mark that is not a letter is skipped, and upper-casing that widens a letter ("ß" gives "SS") is cut back to two. */
export function initialsOf(name) {
  const first = (w) => Array.from(w).find((c) => /\p{L}/u.test(c)) || "";
  const words = cleanName(name).split(" ").map(first).filter(Boolean);
  const pick = words.length > 1 ? [words[0], words[words.length - 1]] : words;
  return Array.from(pick.join("").toUpperCase()).slice(0, 2).join("");
}

export const readerName = signal(cleanName(read(NAME_KEY)));
export function setReaderName(name) {
  const n = cleanName(name);
  readerName.value = n;
  write(NAME_KEY, n || null);
}
export const removeReader = () => setReaderName("");

const stored = () => { const v = read(LOOK_KEY); return LOOKS.includes(v) ? v : "system"; };
export const look = signal(stored());

let forPrint = false;                      // while the browser prints the page is always light
let started = false;                       // only a published file starts it: the editor's own look is never touched here
function paint() {
  if (!started) return;
  try {
    const root = document.documentElement;
    const v = forPrint ? "light" : look.value;
    if (v === "dark") root.dataset.theme = "dark";
    else if (v === "system") root.dataset.theme = "auto";     // brand/tokens.css answers "auto" with the computer's own colour scheme
    else delete root.dataset.theme;
  } catch (e) { /* no document */ }
}

/** Light, Dark or System: applied at once and remembered in this browser. Anything else is ignored. */
export function setLook(v) {
  if (!LOOKS.includes(v)) return;
  look.value = v;
  write(LOOK_KEY, v);
  paint();
}

/** The remembered choice is applied when the file starts. */
export function startLook() { started = true; paint(); }

/** stores/print.js: light while printing, and back afterwards. */
export function lightForPrint(on) { forPrint = !!on; paint(); }
