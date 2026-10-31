// THE HOOK FOR #96 (Add a section dialog). The "+" under a section's grip and the menu's "Add a template below…" both call
// askToAdd(afterId): it announces the request as a "clark:add-section" event on the document, with { after, opener } (after: the section the new
// one goes below, null for the end; opener: the button that was pressed, so focus can go back to it). The event is cancelable and
// bubbles. The #96 build listens for it, opens its dialog and calls preventDefault() to say it has taken
// the request. Until then nothing has, so the old behaviour stands in: a plain text section is added below (with its Undo), as it was
// before the control moved to the gutter, but below the whole row, so a pair is never split. Remove the fallback when #96's dialog is on main, and check the gutter's labels ("Add a template below…") against the dialog's title then.
import { addBelowRow } from "./actions.js";

export const ADD_EVENT = "clark:add-section";

export function askToAdd(after, opener) {
  const e = new CustomEvent(ADD_EVENT, { detail: { after: after || null, opener: opener || null }, cancelable: true, bubbles: true });
  document.dispatchEvent(e);
  if (!e.defaultPrevented) addBelowRow(after || null, "report");
}
