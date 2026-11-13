// Cmd or Ctrl+Z (#197): in Edit, on the Dashboard, Work items and Milestones (and the Use cases page, row 1079), it undoes the last change, the same step as the
// toast's Undo (stores/changes.js, undoLast). With nothing to undo it says so. Focus in a box, a rich-text field (which keeps its own
// undo), a dialog or a menu leaves the key to that; with Shift (redo) or Alt, or a held key, it is not taken either.
import { view, data, mode, fromFile } from "../stores/report.js";
import { undoLast, toast, dismiss } from "../stores/changes.js";
import { note, closeNote } from "./menuNote.js";

const FIELD = /^(INPUT|TEXTAREA|SELECT)$/;
const OWN = "[role=textbox],[role=combobox],[role=listbox],[role=menu],[role=dialog],[role=alertdialog],dialog";
const OPEN = "dialog[open],[role=dialog],[role=alertdialog],[role=menu],[role=listbox]";
const PAGES = ["dashboard", "gantt", "work", "milestones", "usecases"];     // row 1079: the use case page too, where two changes in a row leave only the last toast

function busy(el) {
  return !!el && el.nodeType === 1 && (el.isContentEditable || FIELD.test(el.tagName) || !!el.closest(OWN));
}

/** Whether a keydown is the undo key that clark should take here. Pure apart from reading the page's state. */
export function isUndoKey(e) {
  if (!e || (e.key !== "z" && e.key !== "Z" && e.code !== "KeyZ")) return false;
  if (!(e.metaKey || e.ctrlKey) || e.shiftKey || e.altKey || e.repeat || e.isComposing || e.defaultPrevented) return false;
  if (fromFile.value || !data.value || (mode.value !== "edit" && (view.value === "dashboard" || view.value === "gantt")) || !PAGES.includes(view.value)) return false;
  if (busy(document.activeElement) || busy(e.target)) return false;
  return !document.querySelector(OPEN);
}

/** Handle one keydown: undo the last change when it is the undo key here. Returns whether it did. */
export function undoKey(e) {
  if (!isUndoKey(e)) return false;
  e.preventDefault();
  undoLast();
  return true;
}

/** Esc (no other key held) puts away the message at the foot, when nothing else has the key: no box, dialog, menu or field is open. */
export function isDismissKey(e) {
  if (!e || e.key !== "Escape" || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.isComposing || e.defaultPrevented) return false;
  if (!toast.value && !note.value) return false;
  if (busy(document.activeElement) || busy(e.target)) return false;
  return !document.querySelector(OPEN);
}

export function dismissKey(e) {
  if (!isDismissKey(e)) return false;
  e.preventDefault();
  if (toast.value) dismiss(); else closeNote();
  return true;
}
