// A section's title, edited in place as plain text (Edit only). It is saved when the field is left or on Enter; Esc puts the
// old title back. It is shown with textContent (or an input's value), never as HTML, so "<b>x</b>" stays those letters. Where the
// browser has no plain-text-only editing, the title is an ordinary text input instead.
import { useLayoutEffect, useRef } from "preact/hooks";
import { rename, titleProblem } from "./actions.js";
import { say } from "../stores/changes.js";

// Chrome and Safari have contenteditable="plaintext-only"; a browser without it keeps "inherit" as the value.
export const plainTextEditing = (() => {
  try {
    const el = document.createElement("div");
    el.contentEditable = "plaintext-only";
    return el.contentEditable === "plaintext-only";
  } catch (e) { return false; }
})();

const read = (el) => (plainTextEditing ? el.textContent : el.value);
const show = (el, text) => { if (plainTextEditing) el.textContent = text; else el.value = text; };

export function Title({ section }) {
  const ref = useRef(null), now = useRef(section.title), cancelled = useRef(false);
  now.current = section.title;
  useLayoutEffect(() => { if (ref.current && read(ref.current) !== section.title && document.activeElement !== ref.current) show(ref.current, section.title); }, [section.title]);
  useLayoutEffect(() => { show(ref.current, section.title); }, []);         // mounts with the saved title

  const commit = () => {
    const el = ref.current;
    if (cancelled.current) { cancelled.current = false; return; }
    const text = read(el).replace(/\s+/g, " ").trim();
    if (text === now.current) { show(el, now.current); return; }
    const problem = titleProblem(text);
    if (problem) { show(el, now.current); say("problem", problem); return; }
    rename(section.id, text).then((reply) => { if (!reply) show(el, now.current); });
  };
  const onKeyDown = (e) => {
    if (e.isComposing) return;
    if (e.key === "Enter") { e.preventDefault(); ref.current.blur(); }
    else if (e.key === "Escape") { e.preventDefault(); cancelled.current = true; show(ref.current, now.current); ref.current.blur(); }
  };
  const common = { ref, class: "sec-title", "data-edit-only": "", "data-title": "", "aria-label": "Section title", onBlur: commit, onKeyDown, spellcheck: false };
  return plainTextEditing
    ? <span {...common} contenteditable="plaintext-only" role="textbox" tabindex="0" />
    : <input {...common} type="text" />;
}
