// A short line in the toast that is not a change (nothing to undo): "this section is already first".
import { say } from "../stores/changes.js";
export const note = (text) => say("note", text);
