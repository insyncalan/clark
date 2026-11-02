// What the profile menu's actions did (Preview, Export, Publish), in words, until it is closed (or 20 seconds). The change toast is
// for Edit only and these actions are in View too, so they speak here; ProfileMenu.jsx draws it (and Toast.jsx, in Edit).
import { signal } from "@preact/signals";

export const note = signal(null);
let noteTimer = 0, noteId = 0;
export function say(kind, text) {
  clearTimeout(noteTimer);
  const id = ++noteId;
  note.value = { id, kind, text };
  if (kind !== "problem") noteTimer = setTimeout(() => { if (note.value && note.value.id === id) note.value = null; }, 20000);
}
export const closeNote = () => { clearTimeout(noteTimer); note.value = null; };
