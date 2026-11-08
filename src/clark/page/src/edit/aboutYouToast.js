// The toast for a saved name or email in Settings › Profile › About you, with Undo (#429). The name and email are kept in clark's
// settings, not in the change history, so this Undo is the page saving the old value again through the same route as any save
// (stores/profile.js setProfile). It is offered only when the save changed something, and only while the boxes still hold what was
// saved: a person who has typed again since is never put back.
import { say, dismiss, toast } from "../stores/changes.js";
import { setProfile } from "../stores/profile.js";

let mine = null;                        // { saved, before, restore }: the save the toast on screen speaks for
let latest = { name: "", email: "", alias: "" };   // what the boxes hold now

// Says it as a toast of About you's own (`own`): the profile menu's region draws these in View too (Settings opens in View, #429), with the
// same 20 second timeout and Close as every toast (changes.js say, ToastCard.jsx). `local` is the Undo it carries, if any.
function sayOwn(kind, text, local = null) {
  say(kind, text);
  toast.value = { ...toast.value, local, own: true };
}

/** Settings (or its Personal tab) is left: a toast of About you's own goes with it, and no Undo is kept for a save made here. */
export function leave() {
  mine = null;
  latest = { name: "", email: "", alias: "" };
  if (toast.value && toast.value.own) dismiss();
}

/** The boxes now hold `typed`. Once they differ from what was saved, that toast has nothing left to say or undo, so it goes. */
export function noteTyped(typed) {
  latest = typed;
  if (!mine || (typed.name === mine.saved.name && typed.email === mine.saved.email && (typed.alias || "") === mine.saved.alias)) return;
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

// The Alias (item 613) is spoken of only when it is the person's own (typed in its box). An Alias still filled in from the name changes
// with the name and goes back with it on Undo, without words of its own.
const aliasSaid = (r) => `Alias ${said(r.alias)}.`;
const aliasBack = (b) => (b.alias === "" ? "Alias is blank again." : `Alias is back to ${b.alias}.`);
const joined = (first, second) => [first, second].filter(Boolean).join(" ");

/** A save was answered {ok: true, name, email, alias, before}: say what was saved when it changed something. `restore({name, email, alias})`
 *  puts values in the boxes; `ownAlias` is true when the Alias box holds what the person typed. */
export function announce(r, restore, ownAlias = false) {
  const b = r.before;
  if (!b) return;
  const before = { ...b, alias: b.alias || "" }, after = { name: r.name, email: r.email, alias: r.alias || "" };
  const name = after.name !== before.name, email = after.email !== before.email, alias = ownAlias && after.alias !== before.alias;
  if (!name && !email && !alias) return;
  const entry = { saved: after, before };
  entry.take = async () => {
    if (mine !== entry || latest.name !== entry.saved.name || latest.email !== entry.saved.email || (latest.alias || "") !== entry.saved.alias) return;     // typed again since: leave it
    mine = null;
    const back = await setProfile(before.name, before.email, before.alias);
    if (back.ok) {
      restore({ name: back.name, email: back.email, alias: back.alias });
      sayOwn("done", joined(name || email ? backWords(before, name, email) : "", alias ? aliasBack(before) : ""));
    } else sayOwn("problem", back.message);
  };
  mine = entry;
  sayOwn("done", joined(name || email ? words(after, name, email) : "", alias ? aliasSaid(after) : ""), entry.take);
}
