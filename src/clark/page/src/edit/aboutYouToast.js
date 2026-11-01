// The toast for a saved name or email in Settings › Personal › About you, with Undo (#429). The name and email are kept in clark's
// settings, not in the change history, so this Undo is the page saving the old value again through the same route as any save
// (stores/profile.js setProfile). It is offered only when the save changed something, and only while the boxes still hold what was
// saved: a person who has typed again since is never put back.
import { say, toast } from "../stores/changes.js";
import { setProfile } from "../stores/profile.js";

let mine = null;                        // { saved, before, restore }: the save the toast on screen speaks for
let latest = { name: "", email: "" };   // what the boxes hold now

/** The boxes now hold `typed`. Once they differ from what was saved, that toast has no Undo. */
export function noteTyped(typed) {
  latest = typed;
  if (!mine || (typed.name === mine.saved.name && typed.email === mine.saved.email)) return;
  const t = toast.value;
  if (t && t.local === mine.take) toast.value = { ...t, local: null };
  mine = null;
}

/** A save was answered {ok: true, name, email, before}: say what was saved when it changed something. `restore({name, email})` puts values in the boxes. */
export function announce(r, restore) {
  const b = r.before;
  if (!b) return;
  const name = r.name !== b.name, email = r.email !== b.email;
  if (!name && !email) return;
  say("done", name && email ? "Name and email saved." : name ? "Name saved." : "Email saved.");
  const entry = { saved: { name: r.name, email: r.email }, before: b };
  entry.take = async () => {
    if (mine !== entry || latest.name !== entry.saved.name || latest.email !== entry.saved.email) return;     // typed again since: leave it
    mine = null;
    const back = await setProfile(b.name, b.email);
    if (back.ok) { restore({ name: back.name, email: back.email }); say("done", "Undone."); }
    else say("problem", back.message);
  };
  mine = entry;
  toast.value = { ...toast.value, local: entry.take };
}
