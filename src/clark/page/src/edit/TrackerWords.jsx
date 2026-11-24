// The words after the progress tracker's status chip, edited in place (#930, Edit only). They are the overall's note: the owner's own
// words when there are any, else the automatic words ("2 points behind plan."). Click the words and type. Full width allows one line,
// Half width three, and typing stops at the limit (the text is put back to what fitted, so nothing is cut after the fact); the note's
// own limit of 100 characters (logic/tracker.js NOTE_MAX) stops it too. Enter ends the edit, Escape puts the old words back. Words
// that are empty, or the same as the automatic words, are saved as no note (automatic again). A link puts the automatic words back.
// Each save is one change with one Undo (the caller's `onSave`). Plain text only: the field is "plaintext-only" and read as text.
import { useEffect, useRef } from "preact/hooks";
import { NOTE_MAX } from "../logic/tracker.js";
import { WORDS } from "../logic/trackerEdit.js";

export const LINES = { full: 1, half: 3 };
const chars = (s) => Array.from(s).length;

// How many lines the text takes as drawn now (the field is unclamped while it has focus).
const linesOf = (el) => {
  const lh = parseFloat(getComputedStyle(el).lineHeight) || 1;
  return Math.round(el.scrollHeight / lh);
};

export function TrackerWords({ note, auto, fit, busy, onSave }) {
  const box = useRef(null), last = useRef(""), old = useRef(""), skip = useRef(false);
  const shown = note || auto;
  const max = LINES[fit] || 1;
  // The field is not drawn by Preact's children (that would fight the typing): its text is set from here when what is saved changes.
  useEffect(() => { if (box.current && document.activeElement !== box.current) box.current.textContent = shown; }, [shown]);
  const onInput = () => {
    const el = box.current;
    const text = el.textContent;
    if (chars(text) > NOTE_MAX || linesOf(el) > max) {
      el.textContent = last.current;
      const r = document.createRange(); r.selectNodeContents(el); r.collapse(false);
      const s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
    } else last.current = text;
  };
  const onFocus = () => { last.current = old.current = box.current.textContent; skip.current = false; };
  const onBlur = () => {
    const el = box.current;
    if (skip.current) { el.textContent = old.current; return; }
    const v = el.textContent.trim();
    const next = !v || v === auto ? "" : v;
    el.textContent = next || auto;
    if (next !== note) onSave(next);
  };
  const onKeyDown = (e) => {
    if (e.key === "Enter" && !e.isComposing) { e.preventDefault(); box.current.blur(); }
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); skip.current = true; box.current.blur(); }
  };
  return (
    <>
      <span ref={box} class="tr-words tr-words-edit" data-tr-words data-f="note" contenteditable={busy ? "false" : "plaintext-only"} spellcheck="true" role="textbox" aria-multiline={max > 1 ? "true" : "false"}
        aria-label={max === 1 ? WORDS.wordsLabelOne : WORDS.wordsLabelThree} onInput={onInput} onFocus={onFocus} onBlur={onBlur} onKeyDown={onKeyDown} />
      <span class="tr-hint quiet" data-tr-hint>
        {note
          ? <>{WORDS.yourWords} <a href="#" role="button" data-tr-auto onClick={(e) => { e.preventDefault(); onSave(""); }}>{WORDS.useAuto}</a></>
          : WORDS.autoHint}
      </span>
    </>
  );
}
