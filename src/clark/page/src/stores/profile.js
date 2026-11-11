// Who you are (#180): the name and email typed in Settings › Profile › About you, kept by clark on this computer (api.js). Edit's
// parts only. Nothing here is read from the computer, the browser or the Claude sign-in: a fresh store has neither.
import { signal } from "@preact/signals";
import { getProfile, saveProfile } from "../api.js";
import { plainChange, wantName } from "./report.js";
export { wantName };

export const profile = signal({ name: "", email: "", alias: "" });      // alias: the Alias (item 613), "" when none was saved
export const profileRead = signal(false);               // clark has answered a read: only then is an empty name known to be empty (the welcome, #174)
export const welcomeHeld = signal(false);               // the browser tests' copy holds the welcome back unless a test asks for it (testhook.js)
let asked = false;
let loaded = false;                                     // clark has said what it holds (a read or a save was answered): only then is a save compared with "before"
{ let first = true; profile.subscribe(() => { if (first) first = false; else loaded = true; }); }

/** Read what was saved, once (the menu and Settings both ask; the first one reads). */
export async function loadProfile() {
  if (asked) return;
  asked = true;
  const got = await getProfile();
  if (got) { profile.value = got; profileRead.value = true; } else asked = false;       // a failed read is tried again the next time something asks
}

let sent = 0, applied = 0;                              // saves sent so far; the newest save whose answer the menu has been given

/** Save both values (one left undefined is clark's own: read first when clark has not yet said what it holds, #420). Resolves {ok: true, ...} (the menu shows them at once) or {ok: false, message} (nothing changed on screen or on disk).
 *  `before` is what clark held when the save was sent ({name, email}), or null when that could not be read: an answer to compare with (#429).
 *  Answers can arrive late and out of order, so the answer also says `newest`: true only when no save was sent after this one. The menu
 *  is given a saved answer unless a newer saved answer has already been given (the older one must not put the menu back). */
export async function setProfile(name, email, alias) {     // with no alias given (undefined), the saved Alias is kept
  const n = ++sent;
  const before = loaded ? profile.value : null;      // not read yet (Settings opened a moment ago): without an answer there is no "before", and the save never waits for a read
  if (name === undefined || email === undefined) {      // a box left alone before clark's first answer (#420): its saved value is read, never guessed as empty
    const held = loaded ? profile.value : await getProfile();
    if (!held) return { ok: false, message: plainChange(0), newest: n === sent, before };
    if (name === undefined) name = held.name;
    if (email === undefined) email = held.email;
  }
  const r = await saveProfile(name, email, alias);
  if (r.ok && n > applied) { applied = n; profile.value = { name: r.name, email: r.email, alias: r.alias }; }
  return { ...r, newest: n === sent, before };
}
