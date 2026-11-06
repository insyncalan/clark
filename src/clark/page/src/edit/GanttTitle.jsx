// The Gantt page's own title (#928), edited in place in the banner (Edit only): click, type, Enter or click away saves, Esc puts the old one back.
// It is the same plain-text field as a section's title (Title.jsx), so the banner looks exactly as the Dashboard's. Saving an empty title goes back
// to the project's name. `onSave(text)` is the page's; it draws nothing but the field.
import { useLayoutEffect, useRef } from "preact/hooks";
import { plainBox, read, show } from "./Title.jsx";
import { titleProblem } from "./actions.js";
import { say } from "../stores/changes.js";

export function GanttTitle({ text, label, onSave }) {
  const ref = useRef(null), now = useRef(text), cancelled = useRef(false);
  now.current = text;
  useLayoutEffect(() => { if (ref.current && read(ref.current) !== text && document.activeElement !== ref.current) show(ref.current, text); }, [text]);
  useLayoutEffect(() => { show(ref.current, text); }, []);
  const commit = () => {
    const el = ref.current;
    if (cancelled.current) { cancelled.current = false; return; }
    const next = read(el).replace(/\s+/g, " ").trim();
    if (next === now.current) { show(el, now.current); return; }
    const problem = next ? titleProblem(next) : "";
    if (problem) { show(el, now.current); say("problem", problem); return; }
    onSave(next);
  };
  const onKeyDown = (e) => {
    if (e.isComposing) return;
    if (e.key === "Enter") { e.preventDefault(); ref.current.blur(); }
    else if (e.key === "Escape") { e.preventDefault(); cancelled.current = true; show(ref.current, now.current); ref.current.blur(); }
  };
  return plainBox({ ref, class: "gp-title", "data-g-title": "", "aria-label": label, onBlur: commit, onKeyDown, spellcheck: false });
}
