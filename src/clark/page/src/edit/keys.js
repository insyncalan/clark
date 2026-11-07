// The keys V and E: on the Dashboard and the Gantt page they switch to View and Edit, the same as the two buttons in Toggle.jsx. The listener is
// installed once, at boot (boot.jsx calls installModeKeys), not by the switch, so it is there whichever bar draws the switch.
// A plain key only: with a modifier, a held key or an input method composing, and anywhere focus is in a field, the editor, a
// menu, a dialog or the open peek, the key belongs to that and is left alone. A screen reader's own V and E in browse mode never
// reach the page, so they are not taken either.
import { view, data, mode, fromFile, peek } from "../stores/report.js";
import { singleKeys } from "../stores/keyPrefs.js";

const FIELD = /^(INPUT|TEXTAREA|SELECT)$/;
// The pages that have View and Edit with the plain keys: the Dashboard and the Gantt page (#928).
const MODE_PAGES = ["dashboard", "gantt"];
const OWN = '[role=textbox],[role=combobox],[role=listbox],[role=menu],[role=dialog],[role=alertdialog],dialog';

// Whether focus (or the target of the key) is somewhere that uses letters itself.
function busy(el) {
  return !!el && el.nodeType === 1 && (el.isContentEditable || FIELD.test(el.tagName) || !!el.closest(OWN));
}

/** Handle one keydown: switch the mode when it is a plain V or E on the Dashboard. Returns whether it did. */
export function modeKey(e) {
  if (!singleKeys.value) return false;                                  // #193: the switch in Settings › Personal
  const k = e.key && e.key.toLowerCase();
  if ((k !== "v" && k !== "e") || e.metaKey || e.ctrlKey || e.altKey || e.shiftKey || e.repeat || e.isComposing || e.defaultPrevented) return false;
  if (fromFile.value || !data.value || !MODE_PAGES.includes(view.value) || peek.value) return false;
  if (busy(document.activeElement) || busy(e.target)) return false;
  if (document.querySelector("dialog[open],[role=dialog],[role=alertdialog],[role=menu]")) return false;     // one is open, wherever focus is
  const next = k === "e" ? "edit" : "view";
  if (mode.value === next) return false;
  e.preventDefault();
  mode.value = next;
  return true;
}

/** Listen for V and E from the moment the page starts (boot.jsx), not when a component mounts: the switch is drawn in the top bar or in the
 *  report bar, and a key pressed before either exists, or while one is replaced by the other, must still be heard. modeKey itself
 *  decides whether the page is on the Dashboard with a report open. */
export function installModeKeys() {
  document.addEventListener("keydown", modeKey);
}
