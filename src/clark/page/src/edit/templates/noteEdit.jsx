// The shared parts of the typed notes' Edit parts (#96 G5: Callout, Quote, Contacts, Table): one saved write and one text field.
// Edit only (this folder is never in a published file). A field keeps its own draft and saves when it is left (or on Enter in a
// one-line field); Esc puts the saved words back. Every save is one change(): one step, one Undo, place "report".
import { useEffect, useRef, useState } from "preact/hooks";
import { change } from "../../stores/changes.js";
import { RichField } from "../RichField.jsx";

// Write a section's content (an object) as its body. Resolves to the reply, or null when it failed (the toast says why).
export function saveContent(section, value, done) {
  return change({ op: "update", id: section.id, changes: { body: JSON.stringify(value) }, place: "report" }, done);
}

// One saved write for a template whose content is one object (Callout, Quote). A save is built from the latest words, not the last
// drawn ones: two quick saves (one after another before the first lands) both keep their words. A refused save puts the drawn words back.
export function useSaver(section, saved, done) {
  const key = JSON.stringify(saved);
  const now = useRef(saved), drawn = useRef(saved), flying = useRef(0);
  drawn.current = saved;
  useEffect(() => { if (!flying.current) now.current = drawn.current; }, [key]);
  return (patch) => {
    now.current = { ...now.current, ...patch };
    flying.current += 1;
    const sent = saveContent(section, { v: 1, ...now.current }, done);
    Promise.resolve(sent).then((reply) => { flying.current -= 1; if (reply === null || !flying.current) now.current = drawn.current; });
    return sent;
  };
}

// The words of a card or a note: the one editor with its / menu (RichField). `value` is the HTML to open, `save(html)` writes it
// (one change: one step, one Undo) and resolves to the reply, or null when the save failed (the field then stays open).
export function RichWords({ kind, id, value, label, save }) {
  return <RichField field={kind} id={id} value={value} label={label} empty="Click to write." save={save} />;
}

// A plain text field (one line). `value` is what is saved; `onCommit(text)` is told the new words only when they differ.
export function Field({ value, onCommit, label, max, cls = "" }) {
  const [draft, setDraft] = useState(value);
  const focused = useRef(false), cancelled = useRef(false), latest = useRef(value);
  latest.current = value;
  useEffect(() => { if (!focused.current) setDraft(value); }, [value]);
  const done = (el) => {
    focused.current = false;
    if (cancelled.current) { cancelled.current = false; setDraft(value); return; }
    const text = el.value.trim();
    setDraft(text);
    if (text === value) return;
    // A refused save (the reply is null; the message says why and what to do) puts the saved words back, so the refused text isn't left on screen.
    const sent = onCommit(text);
    if (sent && typeof sent.then === "function") sent.then((reply) => { if (reply === null && !focused.current) setDraft(latest.current); });
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
    else if (e.key === "Enter") { e.preventDefault(); e.currentTarget.blur(); }
  };
  return <input {...common} type="text" onKeyDown={keys} />;
}
