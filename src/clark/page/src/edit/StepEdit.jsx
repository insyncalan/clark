// A next step on the Use cases summary, changed in place in Edit (the prototype's views.js): the owner and the step's words are each text
// you click and type over. Enter or leaving the text saves it as ONE change with its own Undo (the same change the Owner picker and the
// work item make: stores/changes.js changeCell); Esc puts the old text back; a refusal is said in the toast and the old text stays.
// Plain text only, shown with textContent, never as markup. Where the browser has no plain-text-only editing it is a text input instead.
import { useLayoutEffect, useRef } from "preact/hooks";
import { changeCell, say } from "../stores/changes.js";
import { todayIso } from "../workItems.js";
import { changeFor, tableOf } from "./itemEdit.js";
import { plainTextEditing } from "./Title.jsx";

const read = (el) => (plainTextEditing ? el.textContent : el.value);
const show = (el, text) => { if (plainTextEditing) el.textContent = text; else el.value = text; };

function Text({ row, field, value, label, cls }) {
  const ref = useRef(null), now = useRef(value), cancelled = useRef(false);
  now.current = value;
  useLayoutEffect(() => { const el = ref.current; if (el && read(el) !== value && document.activeElement !== el) show(el, value); }, [value]);
  useLayoutEffect(() => { show(ref.current, value); }, []);                    // mounts with the saved text

  const commit = () => {
    const el = ref.current;
    if (cancelled.current) { cancelled.current = false; return; }
    const text = read(el).replace(/\s+/g, " ").trim();
    if (text === now.current) { show(el, now.current); return; }
    const made = changeFor(row, field, text, todayIso());
    if (!made) { show(el, now.current); return; }
    if (made.error) { show(el, now.current); say("problem", made.error); return; }
    changeCell(tableOf(row), row.id, made.changes, { text: made.words, back: made.back }).then((reply) => { if (!reply) show(el, now.current); });
  };
  const onKeyDown = (e) => {
    if (e.isComposing) return;
    if (e.key === "Enter") { e.preventDefault(); ref.current.blur(); }
    else if (e.key === "Escape") { e.preventDefault(); cancelled.current = true; show(ref.current, now.current); ref.current.blur(); }
  };
  const common = { ref, class: `stepin ${cls}`, "data-step-field": field, "aria-label": label, onBlur: commit, onKeyDown, spellcheck: false };
  return plainTextEditing
    ? <span {...common} contenteditable="plaintext-only" role="textbox" tabindex="0" />
    : <input {...common} type="text" size={Math.max(4, Math.min(60, value.length))} />;
}

/** The step's owner and words as text to change; the caller draws the id and the due date after them. */
export function StepEdit({ r }) {
  const who = String(r.owner || "").trim();
  return <><b><Text row={r} field="owner" value={who || "No owner"} label={`Owner of ${r.id}`} cls="stepin-o" />:</b>{" "}<Text row={r} field="title" value={r.title} label={`Next step ${r.id}`} cls="stepin-t" /></>;
}
