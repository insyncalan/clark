// Who you are (#180, #440): the name, alias, email, phone number and organisation typed in Settings › Profile, kept by clark on this
// computer (api.js). Edit's parts only. Nothing here is read from the computer, the browser or the Claude sign-in: a fresh store has neither.
import { signal } from "@preact/signals";
import { getProfile, saveProfile, PROFILE_FIELDS } from "../api.js";

export { PROFILE_FIELDS };
export const BLANK = Object.fromEntries(PROFILE_FIELDS.map((f) => [f, ""]));
export const profile = signal({ ...BLANK });
export const wantName = signal(false);                  // "Add your name in Settings": the name box takes the focus when Settings has drawn
let reading = null;                                     // the read in flight, or the one that landed (shared by whoever asks)
let known = false;                                      // true once a read has landed: before that, profile.value is a blank, not what clark has

/** Read what was saved, once (the menu and Settings both ask; the first one reads and the others wait on the same read). Resolves true when
 *  what clark has is known, false when the read failed (it is tried again the next time something asks). */
export function loadProfile() {
  if (!reading) {
    reading = (async () => {
      const got = await getProfile();
      if (got) { if (!applied) profile.value = got; known = true; return true; }
      reading = null;
      return false;
    })();
  }
  return reading;
}

/** Wait until what clark has is known (a read that is slow is waited for; one that failed is tried once more). */
export async function profileKnown() {
  return known || (await loadProfile()) || (await loadProfile());
}

let sent = 0, applied = 0;                              // saves sent so far; the newest save whose answer the menu has been given

/** Save the five values ({name, alias, email, phone, org}). Resolves {ok: true, ...} (the menu shows them at once) or {ok: false, message} (nothing changed on screen or on disk).
 *  Answers can arrive late and out of order, so the answer also says `newest`: true only when no save was sent after this one. The menu
 *  is given a saved answer unless a newer saved answer has already been given (the older one must not put the menu back). */
export async function setProfile(values) {
  const n = ++sent;
  const r = await saveProfile(values);
  if (r.ok && n > applied) { applied = n; profile.value = Object.fromEntries(PROFILE_FIELDS.map((f) => [f, r[f]])); }
  return { ...r, newest: n === sent };
}
