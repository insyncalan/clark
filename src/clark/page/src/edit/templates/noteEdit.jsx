// The shared parts of the typed notes' Edit parts (#96 G5: Callout, Quote, Contacts, Table): one saved write and one text field.
// Edit only (this folder is never in a published file). A field keeps its own draft and saves when it is left (or on Enter in a
// one-line field); Esc puts the saved words back. Every save is one change(): one step, one Undo, place "report".
import { useEffect, useRef, useState } from "preact/hooks";
import { change } from "../../stores/changes.js";

// Write a section's content (an object) as its body. Resolves to the reply, or null when it failed (the toast says why).
export function saveContent(section, value, done) {
  return change({ op: "update", id: section.id, changes: { body: JSON.stringify(value) }, place: "report" }, done);
}

// A plain text field (one line, or several in a text area). `value` is what is saved; `onCommit(text)` is told the new words only when they differ.
export function Field({ value, onCommit, label, multiline = false, max, cls = "" }) {
  const [draft, setDraft] = useState(value);
  const focused = useRef(false), cancelled = useRef(false);
  useEffect(() => { if (!focused.current) setDraft(value); }, [value]);
  const done = (el) => {
    focused.current = false;
    if (cancelled.current) { cancelled.current = false; setDraft(value); return; }
    const text = el.value.trim();
    setDraft(text);
    if (text !== value) onCommit(text);
  };
  const common = {
    class: `tpl-field ${cls}`, value: draft, "aria-label": label, maxLength: max, spellcheck: true,
    onFocus: () => { focused.current = true; },
    onInput: (e) => setDraft(e.currentTarget.value),
    onBlur: (e) => done(e.currentTarget),
  };
  const keys = (e) => {
    if (e.isComposing) return;
    if (e.key === "Escape") { e.preventDefault(); cancelled.current = true; e.currentTarget.blur(); }
    else if (e.key === "Enter" && !multiline) { e.preventDefault(); e.currentTarget.blur(); }
  };
  return multiline ? <textarea {...common} rows={3} onKeyDown={keys} /> : <input {...common} type="text" onKeyDown={keys} />;
}
