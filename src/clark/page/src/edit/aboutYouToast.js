// The toast for a saved name or email in Settings › Personal › About you, with Undo (#429). The name and email are kept in clark's
// settings, not in the change history, so this Undo is the page saving the old value again through the same route as any save
// (stores/profile.js setProfile). It is offered only when the save changed something, and only while the boxes still hold what was
// saved: a person who has typed again since is never put back.
import { say, dismiss, toast } from "../stores/changes.js";
import { setProfile } from "../stores/profile.js";

let mine = null;                        // { saved, before, restore }: the save the toast on screen speaks for
let latest = { name: "", email: "" };   // what the boxes hold now

// Says it as a toast of About you's own (`own`): the profile menu's region draws these in View too (Settings opens in View, #429), with the
// same 20 second timeout and Close as every toast (changes.js say, ToastCard.jsx). `local` is the Undo it carries, if any.
function sayOwn(kind, text, local = null) {
  say(kind, text);
  toast.value = { ...toast.value, local, own: true };
}

/** Settings (or its Personal tab) is left: a toast of About you's own goes with it, and no Undo is kept for a save made here. */
export function leave() {
  mine = null;
  latest = { name: "", email: "" };
  if (toast.value && toast.value.own) dismiss();
}

/** The boxes now hold `typed`. Once they differ from what was saved, that toast has nothing left to say or undo, so it goes. */
export function noteTyped(typed) {
  latest = typed;
  if (!mine || (typed.name === mine.saved.name && typed.email === mine.saved.email)) return;
  if (toast.value && toast.value.local === mine.take) dismiss();
  mine = null;
}

const said = (value) => (value === "" ? "cleared" : "saved");

/** The words for what a save did: "Name saved.", "Name cleared.", "Name and email saved.", "Name saved. Email cleared." (#429). */
function words(r, name, email) {
  if (name && email) return said(r.name) === said(r.email) ? `Name and email ${said(r.name)}.` : `Name ${said(r.name)}. Email ${said(r.email)}.`;
  return name ? `Name ${said(r.name)}.` : `Email ${said(r.email)}.`;
}

/** The words after Undo: "Name is back to Sam.", "Name is blank again.", "Email is back to ...", "Name and email are back as they were." */
function backWords(b, name, email) {
  if (name && email) return "Name and email are back as they were.";
  return name ? (b.name === "" ? "Name is blank again." : `Name is back to ${b.name}.`) : (b.email === "" ? "Email is blank again." : `Email is back to ${b.email}.`);
}

/** A save was answered {ok: true, name, email, before}: say what was saved when it changed something. `restore({name, email})` puts values in the boxes. */
export function announce(r, restore) {
  const b = r.before;
  if (!b) return;
  const name = r.name !== b.name, email = r.email !== b.email;
  if (!name && !email) return;
  const entry = { saved: { name: r.name, email: r.email }, before: b };
  entry.take = async () => {
    if (mine !== entry || latest.name !== entry.saved.name || latest.email !== entry.saved.email) return;     // typed again since: leave it
    mine = null;
    const back = await setProfile(b.name, b.email);
    if (back.ok) { restore({ name: back.name, email: back.email }); sayOwn("done", backWords(b, name, email)); }
    else sayOwn("problem", back.message);
  };
  mine = entry;
  sayOwn("done", words(r, name, email), entry.take);
}
