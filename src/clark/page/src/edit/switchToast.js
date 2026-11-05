// The toast for a Settings switch (Asking, Single-key shortcuts), with Undo (row 849): it says the new state in the switch's own words
// and carries a local Undo that puts the switch back and says that state. The choices are kept by clark or the browser, not in the
// change log, so Undo is the page setting the old value again through the same route as the switch. Leaving the card takes it away.
import { say, dismiss, toast } from "../stores/changes.js";

let mine = null;                       // the Undo function of the toast on screen, if it is one of these

function sayOwn(kind, text, local = null) {
  say(kind, text);
  toast.value = { ...toast.value, local, own: true };
  mine = local;
}

/** A switch was changed: say `text` with an Undo that calls `back()`; `back` resolves to {ok, message}, and `backText` is what is said after it. */
export function announceSwitch(text, back, backText) {
  const take = async () => {
    const r = await back();
    if (r && r.ok === false) sayOwn("problem", r.message);
    else sayOwn("done", backText);
  };
  sayOwn("done", text, take);
}

/** The card with the switch is left: its toast goes with it. */
export function leaveSwitch() {
  if (mine && toast.value && toast.value.local === mine) dismiss();
  mine = null;
}
