// The 'Needs from you' section in Edit (#121): the same table a reader sees, with each row editable in place. Add a row, edit one,
// leave one out of the published page (or include it again), or remove it. Each is ONE change with one Undo: the whole list is sent
// as the section's body in a single update (the same route as every other section change), after the page has checked the row in
// plain words. The page keeps no copy of its own: it draws what clark saved (stores/changes.js reads the project again after a save).
import { useEffect, useRef, useState } from "preact/hooks";
import { data } from "../stores/report.js";
import { change } from "../stores/changes.js";
import { showDate } from "../workItems.js";
import { needsToday } from "../components/Needs.jsx";
import { rowsOf, dueOf, kindWord, problem, made, bodyOf, withAdded, withReplaced, withFlipped, withoutRow, KINDS, MAX_ROWS, WHAT_MAX, FROM_MAX, WORDS } from "../logic/needs.js";

const DASH = "—";
const NEW = -1;                                           // the row being added, not yet in the list

const blank = () => ({ what: "", kind: "decision", from: "", by: "" });
const draftOf = (r) => ({ what: r.what, kind: r.kind, from: r.from, by: r.by ? showDate(r.by) : "" });

// The one request: the section's body replaced by the new list.
const save = (id, rows, done) => change({ op: "update", id, changes: { body: bodyOf(rows) }, place: "cell" }, done);

function focusLater(section, selector) {
  setTimeout(() => {
    const el = document.querySelector(`.sec[data-id="${CSS.escape(section)}"] ${selector}`);
    if (el) el.focus();
  }, 0);
}

function RowForm({ id, draft, setDraft, error, busy, onSave, onCancel, label }) {
  const first = useRef(null);
  useEffect(() => { if (first.current) first.current.focus(); }, []);
  const set = (k) => (e) => { const v = e.currentTarget.value; setDraft((d) => ({ ...d, [k]: v })); };      // from the latest draft, so two quick edits never undo each other
  return (
    <tr class="n-form" data-row-form onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onCancel(); } else if (e.key === "Enter" && !e.isComposing && e.target.tagName === "INPUT") { e.preventDefault(); onSave(); } }}>
      <td class="n-what">
        <label class="n-f"><span class="sr">{WORDS.kind}</span>
          <select data-f="kind" value={draft.kind} onChange={set("kind")}>{KINDS.map(([k, w]) => <option key={k} value={k}>{w}</option>)}</select>
        </label>
        <label class="n-f"><span class="sr">{WORDS.what}</span>
          <input ref={first} data-f="what" type="text" autocomplete="off" maxLength={WHAT_MAX * 2} placeholder={WORDS.what} value={draft.what} onInput={set("what")} />
        </label>
        {error ? <p class="n-err" role="alert">{error}</p> : null}
      </td>
      <td class="n-from">
        <label class="n-f"><span class="sr">{WORDS.from}</span>
          <input data-f="from" type="text" autocomplete="off" maxLength={FROM_MAX * 2} placeholder={WORDS.from} value={draft.from} onInput={set("from")} />
        </label>
      </td>
      <td class="n-by">
        <label class="n-f"><span class="sr">{WORDS.by}</span>
          <input data-f="by" type="text" inputmode="numeric" autocomplete="off" placeholder={WORDS.datePlaceholder} value={draft.by} onInput={set("by")} />
        </label>
        <span class="n-acts">
          <button type="button" class="btn sm" data-save disabled={busy} onClick={onSave} aria-label={label}>{id === NEW ? WORDS.add : WORDS.save}</button>
          <button type="button" class="btn sm" data-cancel onClick={onCancel}>{WORDS.cancel}</button>
        </span>
      </td>
    </tr>
  );
}

export function NeedsEdit({ section }) {
  data.value;                                             // read, so a change to the sections draws again
  const rows = rowsOf(section, false);
  const [at, setAt] = useState(null);                     // null, NEW, or the index of the row being edited
  const [draft, setDraft] = useState(blank());
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const today = needsToday();
  const sid = section.id;

  const open = (i) => { setAt(i); setDraft(i === NEW ? blank() : draftOf(rows[i])); setError(""); };
  const close = (back) => { setAt(null); setError(""); if (back) focusLater(sid, back); };
  const run = async (next, done, back) => {
    if (!next || busy) return false;
    setBusy(true);
    const reply = await save(sid, next, done);
    setBusy(false);
    if (reply) { setAt(null); setError(""); if (back) focusLater(sid, back); }
    return !!reply;
  };

  const onSave = () => {
    const said = problem(draft);
    if (said) { setError(said); return; }
    const row = made(draft, at === NEW ? 0 : rows[at].hidden);
    if (at === NEW) run(withAdded(rows, row), WORDS.added, "[data-add-row]");
    else run(withReplaced(rows, at, row), WORDS.saved, `[data-row="${at}"] [data-edit]`);
  };

  return (
    <div class="sec-needs needs-edit" data-needs data-edit-only>
      {rows.length === 0 && at !== NEW ? <p class="quiet" data-needs-none>{WORDS.none}</p> : null}
      {rows.length || at === NEW ? (
        <table class="needs">
          <thead>
            <tr><th scope="col" class="n-what">{WORDS.what}</th><th scope="col" class="n-from">{WORDS.from}</th><th scope="col" class="n-by">{WORDS.by}</th></tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              if (at === i) return <RowForm key={i} id={i} draft={draft} setDraft={setDraft} error={error} busy={busy} onSave={onSave} onCancel={() => close(`[data-row="${i}"] [data-edit]`)} label={`${WORDS.save}: ${r.what}`} />;
              const due = dueOf(r, today);
              return (
                <tr key={i} class={r.hidden ? "n-left" : undefined} data-row={i}>
                  <td class="n-what"><span class="tag n-kind">{kindWord(r.kind)}</span> <span class="n-text">{r.what}</span>{r.hidden ? <> <span class="tag hid">{WORDS.left}</span></> : null}</td>
                  <td class="n-from">{r.from || DASH}</td>
                  <td class="n-by num">
                    <span class="n-date">{r.by ? due.text : <span class="muted">{DASH}</span>}{due.overdue ? <> <span class="pill r n-over">{WORDS.overdue}</span></> : null}</span>
                    <span class="n-acts">
                      <button type="button" class="btn sm" data-edit disabled={busy || at !== null} aria-label={`${WORDS.edit}: ${r.what}`} onClick={() => open(i)}>{WORDS.edit}</button>
                      <button type="button" class="btn sm" data-flip disabled={busy || at !== null} aria-label={`${r.hidden ? WORDS.show : WORDS.hide}: ${r.what}`}
                        onClick={() => run(withFlipped(rows, i), r.hidden ? WORDS.shown : WORDS.hidden, `[data-row="${i}"] [data-flip]`)}>{r.hidden ? WORDS.show : WORDS.hide}</button>
                      <button type="button" class="btn sm" data-remove disabled={busy || at !== null} aria-label={`${WORDS.remove}: ${r.what}`}
                        onClick={() => run(withoutRow(rows, i), WORDS.removed, "[data-add-row]")}>{WORDS.remove}</button>
                    </span>
                  </td>
                </tr>
              );
            })}
            {at === NEW ? <RowForm key="new" id={NEW} draft={draft} setDraft={setDraft} error={error} busy={busy} onSave={onSave} onCancel={() => close("[data-add-row]")} label={WORDS.addRow} /> : null}
          </tbody>
        </table>
      ) : null}
      <p class="n-add">
        <button type="button" class="btn sm" data-add-row disabled={busy || at !== null || rows.length >= MAX_ROWS} onClick={() => open(NEW)}>{WORDS.addRow}</button>
        {rows.length >= MAX_ROWS ? <span class="muted"> {WORDS.full}</span> : null}
      </p>
    </div>
  );
}
