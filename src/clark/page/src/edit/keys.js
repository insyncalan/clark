// The keys V and E (#103): on the Dashboard they switch to View and Edit, the same as the two buttons (Toggle.jsx, which listens).
// A plain key only: with a modifier, a held key or an input method composing, and anywhere focus is in a field, the editor, a
// menu, a dialog or the open peek, the key belongs to that and is left alone. A screen reader's own V and E in browse mode never
// reach the page, so they are not taken either.
import { view, data, mode, fromFile, peek } from "../stores/report.js";

const FIELD = /^(INPUT|TEXTAREA|SELECT)$/;
const OWN = '[role=textbox],[role=combobox],[role=listbox],[role=menu],[role=dialog],[role=alertdialog],dialog';

// Whether focus (or the target of the key) is somewhere that uses letters itself.
function busy(el) {
  return !!el && el.nodeType === 1 && (el.isContentEditable || FIELD.test(el.tagName) || !!el.closest(OWN));
}

/** Handle one keydown: switch the mode when it is a plain V or E on the Dashboard. Returns whether it did. */
export function modeKey(e) {
  const k = e.key && e.key.toLowerCase();
  if ((k !== "v" && k !== "e") || e.metaKey || e.ctrlKey || e.altKey || e.shiftKey || e.repeat || e.isComposing || e.defaultPrevented) return false;
  if (fromFile.value || !data.value || view.value !== "dashboard" || peek.value) return false;
  if (busy(document.activeElement) || busy(e.target)) return false;
  if (document.querySelector("dialog[open],[role=dialog],[role=alertdialog],[role=menu]")) return false;     // one is open, wherever focus is
  const next = k === "e" ? "edit" : "view";
  if (mode.value === next) return false;
  e.preventDefault();
  mode.value = next;
  return true;
}
