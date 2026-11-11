// What the profile menu's actions did (Preview, Export, Publish), in words, until it is closed (or 5 seconds, which a pointer over it or focus in it holds). The change toast is
// for Edit only and these actions are in View too, so they speak here; ProfileMenu.jsx draws it (and Toast.jsx, in Edit). The note
// never carries an Undo: what these actions did is not a step in the change history.
import { signal } from "@preact/signals";
import { toastClock } from "../stores/toastClock.js";

export const note = signal(null);
let noteId = 0;
export const noteTimer = toastClock(() => { if (note.value && note.value.id === noteId) note.value = null; });
export function say(kind, text) {
  const id = ++noteId;
  note.value = { id, kind, text };
  if (kind !== "problem") noteTimer.start(); else noteTimer.stop();
}
export const closeNote = () => { noteTimer.stop(); note.value = null; };
