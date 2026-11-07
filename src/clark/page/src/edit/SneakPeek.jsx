// Sneak peek (#42b): change one item, milestone or use case in words. Type, read the from → to lines, press Enter (or Shift+Enter) to apply them as one
// step; the toast offers Undo. The reading is plain code on the server (POST /api/sneak/read): no model, and it writes nothing.
// Row 776: phrase chips (the typed words, in typed order) above the lines; Not now closes like Esc, Make the change applies like Enter.
// A reading that needs a confirm is never applied by Enter alone; the Make the change button counts as that OK (the chips and lines are on screen). Applying goes through the work-item change route (#68).
import { useState, useEffect, useRef } from "preact/hooks";
import { project } from "../stores/report.js";
import { wordsOpen } from "../stores/wordsState.js";
import { sneakRead } from "../api.js";
import { Icon } from "../components/Icon.jsx";
import { applyReading } from "./sneakApply.js";
import { PLACEHOLDER, LEAD } from "./sneakWords.js";

export function SneakButton() {
  return <button type="button" class="pkp-btn" data-sneak-open title="Change an item with words" aria-label="Change an item with words" aria-pressed={wordsOpen.value} onClick={() => { wordsOpen.value = !wordsOpen.value; }}><Icon name="sparkle" /></button>;
}

export function SneakPeek({ row, kind = "item" }) {
  const [words, setWords] = useState("");
  const [reading, setReading] = useState(null);       // null: nothing typed; {ok, reading | message}
  const [flash, setFlash] = useState(false);
  const [busy, setBusy] = useState(false);
  const box = useRef(null);
  useEffect(() => {                                   // focus goes into the box, and back to where it was when the box alone closes
    const before = document.activeElement;
    if (box.current) box.current.focus();
    return () => {
      if (wordsOpen.value) return;                    // the box is still wanted (another item): the new box takes focus
      const back = before && before !== document.body && before.isConnected ? before : (document.querySelector("[data-sneak-open]") || document.querySelector("#peek [data-pk-close]"));
      if (back && back.focus) back.focus();
    };
  }, []);
  useEffect(() => {                                   // read the words a moment after typing stops
    if (!words.trim()) { setReading(null); return undefined; }
    let live = true;
    const t = setTimeout(async () => { const r = await sneakRead(project.value, row.id, words); if (live) setReading(r); }, 200);
    return () => { live = false; clearTimeout(t); };
  }, [words, row.id]);
  const found = reading && reading.ok ? reading.reading : null;
  const apply = async (confirmed, keep) => {
    if (!found || busy) return;
    if (found.confirm && !confirmed) { setFlash(true); setTimeout(() => setFlash(false), 900); return; }     // the line flashes; nothing is applied
    setBusy(true);
    const done = await applyReading(row.id, found, kind);
    setBusy(false);
    if (done) { setWords(""); setReading(null); if (!keep) wordsOpen.value = false; }     // Enter closes the box; Shift+Enter keeps it for the next words
  };
  const chips = found ? chipsFor(found.changes, words) : [];
  const close = () => { setWords(""); setReading(null); wordsOpen.value = false; };      // Not now: the same as Esc (Peek.jsx), nothing changed
  const key = (e) => {
    if (e.key === "Enter" && !e.isComposing) {
      e.preventDefault();
      apply(e.metaKey || e.ctrlKey, e.shiftKey);
    }
  };
  return (
    <section class="wordsbox" data-sneak aria-label="Change an item with words">
      <div class="sn-head"><Icon name="sparkle" /><span>Change an item with words</span></div>
      <input ref={box} class="sn-in" type="text" value={words} maxLength={400} aria-label="What should change" placeholder={LEAD + (PLACEHOLDER[kind] || PLACEHOLDER.item)}
        onInput={(e) => { setReading(null); setWords(e.currentTarget.value); }} onKeyDown={key} />
      <div class="sn-out" role="status" aria-live="polite">
        {reading && !reading.ok ? <p class="sn-msg" data-sneak-message>{reading.message}</p> : null}
        {found ? <ul class="sn-chips" data-sneak-chips>{chips.map((t, i) => <li key={i} class="sn-chip">{t}</li>)}</ul> : null}
        {found ? (
          <ul class="sn-list">
            {found.changes.map((c) => (
              <li key={c.field} data-field={c.field}>
                <span class="sn-f">{c.label}</span>
                <span class="sn-from">{c.from_text}</span><span aria-hidden="true">{" → "}</span><span class="sn-to">{c.to_text}</span>
                {c.new_name ? <span class="tag">new name</span> : null}
              </li>
            ))}
          </ul>
        ) : null}
        {found && found.note ? <p class="muted">{found.note}</p> : null}
        {found ? (
          <div class="sn-acts">
            <button type="button" class="btn" data-sneak-not-now disabled={busy} onClick={close}>Not now</button>
            <button type="button" class="btn pri" data-sneak-make disabled={busy} onClick={() => apply(true, false)}>Make the change <span aria-hidden="true">⏎</span></button>
          </div>
        ) : null}
        {found && found.confirm ? (
          <p class={`sn-confirm${flash ? " flash" : ""}`} data-sneak-confirm>
            This change needs your OK. Press <button type="button" class="link" data-sneak-confirm-btn onClick={() => apply(true, false)}>Confirm and apply</button> to make it (or press Cmd+Enter, Ctrl+Enter on Windows), or change your words.
          </p>
        ) : null}
      </div>
      <p class="muted sn-foot">Enter applies the changes shown. Shift+Enter applies and keeps this box open. Esc closes it.</p>
    </section>
  );
}

// One chip per distinct phrase, in the order the words were typed. A line the reader gave no phrase for shows its own label and result.
function chipsFor(changes, words) {
  const at = (c) => { const i = c.phrase ? words.indexOf(c.phrase) : -1; return i < 0 ? Infinity : i; };
  const seen = new Set();
  return changes.map((c, n) => ({ n, at: at(c), text: c.phrase || `${c.label}: ${c.to_text}` }))
    .sort((a, b) => (a.at - b.at) || (a.n - b.n))
    .filter((c) => !seen.has(c.text) && seen.add(c.text)).map((c) => c.text);
}
