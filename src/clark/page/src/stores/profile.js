// Who you are (#180): the name and email typed in Settings › Personal › About you, kept by clark on this computer (api.js). Edit's
// parts only. Nothing here is read from the computer, the browser or the Claude sign-in: a fresh store has neither.
import { signal } from "@preact/signals";
import { getProfile, saveProfile } from "../api.js";

export const profile = signal({ name: "", email: "" });
export const wantName = signal(false);                  // "Add your name in Settings": the name box takes the focus when Settings has drawn
let asked = false;
let loaded = false;                                     // clark has said what it holds (a read or a save was answered): only then is a save compared with "before"
{ let first = true; profile.subscribe(() => { if (first) first = false; else loaded = true; }); }

/** Read what was saved, once (the menu and Settings both ask; the first one reads). */
export async function loadProfile() {
  if (asked) return;
  asked = true;
  const got = await getProfile();
  if (got) profile.value = got; else asked = false;       // a failed read is tried again the next time something asks
}

let sent = 0, applied = 0;                              // saves sent so far; the newest save whose answer the menu has been given

/** Save both values. Resolves {ok: true, ...} (the menu shows them at once) or {ok: false, message} (nothing changed on screen or on disk).
 *  `before` is what clark held when the save was sent ({name, email}), or null when that could not be read: an answer to compare with (#429).
 *  Answers can arrive late and out of order, so the answer also says `newest`: true only when no save was sent after this one. The menu
 *  is given a saved answer unless a newer saved answer has already been given (the older one must not put the menu back). */
export async function setProfile(name, email) {
  const n = ++sent;
  const before = loaded ? profile.value : await getProfile();      // not read yet (Settings opened a moment ago): ask clark, and without an answer there is no "before"
  const r = await saveProfile(name, email);
  if (r.ok && n > applied) { applied = n; profile.value = { name: r.name, email: r.email }; }
  return { ...r, newest: n === sent, before };
}
