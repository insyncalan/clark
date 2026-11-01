// The 'Progress tracker' section in Edit (#189): the same bar, groups and lines a reader sees, each editable in place. Add, change,
// move or remove a line; add, rename, move or remove a group; pick a status from the fixed list; set the overall health and note; switch
// the extra columns on. Each is ONE change with one Undo: the whole tracker is sent as the section's body in a single update (the same
// route as every other section change), after the page has checked the line in plain words. A refusal from clark comes back as a plain
// toast (stores/report.js) and the form stays open. The page keeps no copy of its own: it draws what clark saved.
import { useEffect, useRef, useState } from "preact/hooks";
import { data } from "../stores/report.js";
import { change } from "../stores/changes.js";
import { Overall, GroupFull, GroupHalf, columnsOf, fitOf } from "../components/Tracker.jsx";
import {
  trackerOf, totals, pct, problem, totalProblem, made, draftOf, blankLine, nameProblem, noteProblem, bodyOf, STATUSES, HEALTH, COLUMNS, NAME_MAX, TEXT_MAX, NO_MAX, NOTE_MAX, WORDS,
  withLineAdded, withLineReplaced, withoutLine, withLineMoved, withGroupAdded, withGroupRenamed, withoutGroup, withGroupMoved, withOverall, withColumn, MAX_GROUPS, MAX_LINES,
} from "../logic/tracker.js";

const NEW = -1;                                           // the line being added, not yet in the list

// The one request: the section's body replaced by the new tracker.
const save = (id, tracker, done) => change({ op: "update", id, changes: { body: bodyOf(tracker) }, place: "cell" }, done);

function focusLater(section, selector) {
  setTimeout(() => {
    const el = document.querySelector(`.sec[data-id="${CSS.escape(section)}"] ${selector}`);
    if (el) el.focus();
  }, 0);
}

const FIELDS = [["no", "no", WORDS.no, "text"], ["text", "text", WORDS.what, "text"], ["start", "start", WORDS.start, "date"], ["end", "end", WORDS.end, "date"],
  ["weight", "weight", WORDS.weight, "pct"], ["planned", "planned", WORDS.planned, "pct"], ["achieved", "achieved", WORDS.achieved, "pct"]];

function LineForm({ at, draft, setDraft, error, busy, onSave, onCancel, counts }) {
  const first = useRef(null);
  useEffect(() => { if (first.current) first.current.focus(); }, []);
  const set = (k) => (e) => { const v = e.currentTarget.value; setDraft((d) => ({ ...d, [k]: v })); };      // from the latest draft, so two quick edits never undo each other
  return (
    <div class="t-form" data-line-form onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onCancel(); } else if (e.key === "Enter" && !e.isComposing && e.target.tagName === "INPUT") { e.preventDefault(); onSave(); } }}>
      <div class="t-grid">
        {FIELDS.map(([k, f, label, kind], n) => (
          <label key={k} class={`t-f t-f-${k}`}><span class="t-fl">{label}</span>
            <input ref={n === 1 ? first : null} data-f={f} type="text" autocomplete="off" inputmode={kind === "text" ? undefined : "decimal"}
              maxLength={k === "text" ? TEXT_MAX * 2 : k === "no" ? NO_MAX * 2 : 12} placeholder={kind === "date" ? WORDS.datePlaceholder : kind === "pct" ? WORDS.percentPlaceholder : undefined}
              value={draft[k]} onInput={set(k)} />
          </label>
        ))}
        <label class="t-f t-f-status"><span class="t-fl">{WORDS.status}</span>
          <select data-f="status" value={draft.status} onChange={set("status")}>{STATUSES.map(([k, w]) => <option key={k} value={k}>{w}</option>)}</select>
        </label>
        {counts.map(([k, w]) => (
          <label key={k} class="t-f t-f-count"><span class="t-fl">{w}</span>
            <input data-f={k} type="text" inputmode="numeric" autocomplete="off" maxLength={5} value={draft[k]} onInput={set(k)} />
          </label>
        ))}
      </div>
      {error ? <p class="t-err" role="alert" data-line-error>{error}</p> : null}
      <span class="t-acts">
        <button type="button" class="btn sm" data-save disabled={busy} onClick={onSave}>{at === NEW ? WORDS.add : WORDS.save}</button>
        <button type="button" class="btn sm" data-cancel onClick={onCancel}>{WORDS.cancel}</button>
      </span>
    </div>
  );
}

export function TrackerEdit({ section, slot }) {
  data.value;                                             // read, so a change to the sections draws again
  const tracker = trackerOf(section, false);
  const t = totals(tracker);
  const fit = fitOf(slot);
  const [at, setAt] = useState(null);                     // null, or { g, i } with i the line's index, or NEW
  const [draft, setDraft] = useState(blankLine());
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [naming, setNaming] = useState(null);             // null, NEW (a new group) or the index of the group being renamed
  const [name, setName] = useState("");
  const [nameError, setNameError] = useState("");
  const [noteError, setNoteError] = useState("");
  const sid = section.id;
  const counts = columnsOf(tracker);
  const locked = busy || at !== null || naming !== null;

  // `close`: the save is the open form's own, so that form closes. Any other save leaves an open form and what was typed in it as they are.
  const run = async (next, done, back, close = false) => {
    if (!next || busy) return false;
    setBusy(true);
    const reply = await save(sid, next, done);
    setBusy(false);
    if (reply) { if (close) { setAt(null); setNaming(null); setError(""); setNameError(""); } if (back) focusLater(sid, back); }
    return !!reply;
  };
  const openLine = (g, i) => { setAt({ g, i }); setDraft(i === NEW ? blankLine() : draftOf(tracker.groups[g].lines[i])); setError(""); };
  const closeLine = (back) => { setAt(null); setError(""); if (back) focusLater(sid, back); };
  const onSave = () => {
    const said = problem(draft);
    if (said) { setError(said); return; }
    const line = made(draft);
    const next = at.i === NEW ? withLineAdded(tracker, at.g, line) : withLineReplaced(tracker, at.g, at.i, line);
    const over = next && totalProblem(next);
    if (over) { setError(over); return; }
    if (at.i === NEW) run(next, WORDS.added, `[data-group="${at.g}"] [data-add-line]`, true);
    else run(next, WORDS.saved, `[data-group="${at.g}"] [data-line="${at.i}"] [data-edit]`, true);
  };
  const openName = (g) => { setNaming(g); setName(g === NEW ? "" : tracker.groups[g].name); setNameError(""); };
  const onName = () => {
    const said = nameProblem(name);
    if (said) { setNameError(said); return; }
    if (naming === NEW) run(withGroupAdded(tracker, name.trim()), WORDS.groupAdded, "[data-add-group]", true);
    else run(withGroupRenamed(tracker, naming, name.trim()), WORDS.saved, `[data-group="${naming}"] [data-rename]`, true);
  };
  const onNote = (e) => {
    const note = e.currentTarget.value.trim();
    const said = noteProblem(note);
    setNoteError(said);
    if (!said && note !== tracker.overall.note) run(withOverall(tracker, { note }), WORDS.saved);
  };

  const lineTools = (g) => (l, i) => {
    const group = tracker.groups[g];
    const label = (w) => `${w}: ${l.text}`;
    const cell = (
      <span class="t-acts">
        <button type="button" class="btn sm" data-edit disabled={locked} aria-label={label(WORDS.edit)} onClick={() => openLine(g, i)}>{WORDS.edit}</button>
        <button type="button" class="btn sm" data-up disabled={locked || i === 0} aria-label={label(WORDS.up)} onClick={() => run(withLineMoved(tracker, g, i, -1), WORDS.moved, `[data-group="${g}"] [data-line="${Math.max(0, i - 1)}"] [data-up]`)}>↑</button>
        <button type="button" class="btn sm" data-down disabled={locked || i === group.lines.length - 1} aria-label={label(WORDS.down)} onClick={() => run(withLineMoved(tracker, g, i, 1), WORDS.moved, `[data-group="${g}"] [data-line="${i + 1}"] [data-down]`)}>↓</button>
        <button type="button" class="btn sm" data-remove disabled={locked} aria-label={label(WORDS.remove)} onClick={() => run(withoutLine(tracker, g, i), WORDS.removed, `[data-group="${g}"] [data-add-line]`)}>{WORDS.remove}</button>
      </span>
    );
    return fit === "full" ? <td class="t-tools" data-line={i}>{cell}</td> : <span class="t-tools-wrap" data-line={i}>{cell}</span>;
  };
  // A line's row is marked data-line by its tools cell; the row's form replaces it while it is being edited.
  const formAt = (g) => (i) => {
    if (!at || at.g !== g || at.i !== i) return null;
    const form = <LineForm at={i} draft={draft} setDraft={setDraft} error={error} busy={busy} onSave={onSave} onCancel={() => closeLine(`[data-group="${g}"] [data-line="${i}"] [data-edit]`)} counts={counts} />;
    return fit === "full" ? <tr key={`f${i}`} class="t-form-row"><td colSpan={9 + counts.length}>{form}</td></tr> : <li key={`f${i}`} class="t-form-row">{form}</li>;
  };
  const footOf = (g) => {
    if (at && at.g === g && at.i === NEW) {
      const form = <LineForm at={NEW} draft={draft} setDraft={setDraft} error={error} busy={busy} onSave={onSave} onCancel={() => closeLine(`[data-group="${g}"] [data-add-line]`)} counts={counts} />;
      return fit === "full" ? <tr key="new" class="t-form-row"><td colSpan={9 + counts.length}>{form}</td></tr> : <li key="new" class="t-form-row">{form}</li>;
    }
    return null;
  };

  const lineCount = t.lines;
  return (
    <div class={`sec-tracker tracker-edit tr-${fit}`} data-tracker data-edit-only data-fit={fit}>
      <Overall overall={t.overall} />
      <div class="t-overall-edit" data-overall-edit>
        <label class="t-f"><span class="t-fl">{WORDS.health}</span>
          <select data-f="health" disabled={busy} value={tracker.overall.health} onChange={(e) => run(withOverall(tracker, { health: e.currentTarget.value }), WORDS.saved)}>
            <option value="">{WORDS.noHealth}</option>
            {HEALTH.map(([k, w]) => <option key={k} value={k}>{w}</option>)}
          </select>
        </label>
        <label class="t-f t-f-note"><span class="t-fl">{WORDS.note}</span>
          <input data-f="note" type="text" autocomplete="off" maxLength={NOTE_MAX * 2} disabled={busy} defaultValue={tracker.overall.note} key={tracker.overall.note} onBlur={onNote}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.isComposing) { e.preventDefault(); e.currentTarget.blur(); } }} />
        </label>
        {!lineCount ? ["actual", "planned"].map((k) => (
          <label key={k} class="t-f"><span class="t-fl">{k === "actual" ? WORDS.actual : WORDS.planned}</span>
            <OverallNumber field={k} tracker={tracker} busy={busy} run={run} />
          </label>
        )) : null}
        <fieldset class="t-cols"><legend class="t-fl">{WORDS.columns}</legend>
          {COLUMNS.map(([k, w]) => (
            <label key={k} class="t-check"><input type="checkbox" data-col={k} disabled={busy} checked={tracker.columns[k]} onChange={(e) => run(withColumn(tracker, k, e.currentTarget.checked), WORDS.saved)} /> {w}</label>
          ))}
        </fieldset>
      </div>
      {noteError ? <p class="t-err" role="alert">{noteError}</p> : null}
      {t.groups.length === 0 && naming !== NEW ? <p class="quiet" data-tracker-none>{WORDS.none}</p> : null}
      {t.groups.map((g, gi) => (
        <div key={gi} class="t-group" data-group={gi}>
          <div class="t-gtools">
            {naming === gi ? (
              <span class="t-name-form" onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); setNaming(null); setNameError(""); focusLater(sid, `[data-group="${gi}"] [data-rename]`); } else if (e.key === "Enter" && !e.isComposing) { e.preventDefault(); onName(); } }}>
                <label class="t-f"><span class="t-fl">{WORDS.group}</span><input data-f="group" type="text" autoFocus autocomplete="off" maxLength={NAME_MAX * 2} value={name} onInput={(e) => setName(e.currentTarget.value)} /></label>
                <button type="button" class="btn sm" data-save-name disabled={busy} onClick={onName}>{WORDS.save}</button>
                <button type="button" class="btn sm" data-cancel-name onClick={() => { setNaming(null); setNameError(""); }}>{WORDS.cancel}</button>
                {nameError ? <p class="t-err" role="alert" data-name-error>{nameError}</p> : null}
              </span>
            ) : (
              <span class="t-acts">
                <button type="button" class="btn sm" data-rename disabled={locked} aria-label={`${WORDS.rename}: ${g.name}`} onClick={() => openName(gi)}>{WORDS.rename}</button>
                <button type="button" class="btn sm" data-gup disabled={locked || gi === 0} aria-label={`${WORDS.up}: ${g.name}`} onClick={() => run(withGroupMoved(tracker, gi, -1), WORDS.moved)}>↑</button>
                <button type="button" class="btn sm" data-gdown disabled={locked || gi === t.groups.length - 1} aria-label={`${WORDS.down}: ${g.name}`} onClick={() => run(withGroupMoved(tracker, gi, 1), WORDS.moved)}>↓</button>
                <button type="button" class="btn sm" data-remove-group disabled={locked} aria-label={`${WORDS.removeGroup}: ${g.name}`} onClick={() => run(withoutGroup(tracker, gi), WORDS.groupRemoved, "[data-add-group]")}>{WORDS.removeGroup}</button>
              </span>
            )}
          </div>
          {fit === "full"
            ? <GroupFull group={g} columns={counts} extraHead={<th scope="col" class="t-tools"><span class="sr">{WORDS.edit}</span></th>} extraCell={lineTools(gi)} below={formAt(gi)} foot={footOf(gi)} />
            : <GroupHalf group={g} extraCell={lineTools(gi)} below={formAt(gi)} foot={footOf(gi)} />}
          <p class="t-add">
            <button type="button" class="btn sm" data-add-line disabled={locked || lineCount >= MAX_LINES} onClick={() => openLine(gi, NEW)}>{WORDS.addLine}</button>
            {lineCount >= MAX_LINES ? <span class="muted"> {WORDS.fullLines}</span> : null}
          </p>
        </div>
      ))}
      {t.weightsNote ? <p class="quiet tr-weights" data-tr-weights>{t.weightsNote}</p> : null}
      {naming === NEW ? (
        <div class="t-gtools t-new-group" onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); setNaming(null); setNameError(""); focusLater(sid, "[data-add-group]"); } else if (e.key === "Enter" && !e.isComposing) { e.preventDefault(); onName(); } }}>
          <label class="t-f"><span class="t-fl">{WORDS.group}</span><input data-f="group" type="text" autoFocus autocomplete="off" maxLength={NAME_MAX * 2} value={name} onInput={(e) => setName(e.currentTarget.value)} /></label>
          <button type="button" class="btn sm" data-save-name disabled={busy} onClick={onName}>{WORDS.add}</button>
          <button type="button" class="btn sm" data-cancel-name onClick={() => { setNaming(null); setNameError(""); }}>{WORDS.cancel}</button>
          {nameError ? <p class="t-err" role="alert" data-name-error>{nameError}</p> : null}
        </div>
      ) : null}
      <p class="t-add">
        <button type="button" class="btn sm" data-add-group disabled={locked || t.groups.length >= MAX_GROUPS} onClick={() => openName(NEW)}>{WORDS.addGroup}</button>
        {t.groups.length >= MAX_GROUPS ? <span class="muted"> {WORDS.fullGroups}</span> : null}
      </p>
    </div>
  );
}

// The overall's own Actual or Planned, typed only while there are no lines ("just the bar"): saved when the field is left.
function OverallNumber({ field, tracker, busy, run }) {
  const [error, setError] = useState("");
  const shown = tracker.overall[field] === null ? "" : String(tracker.overall[field] / 10);
  const onBlur = (e) => {
    const text = e.currentTarget.value.trim();
    if (text === shown) return;
    const n = text === "" ? null : pctOf(text);
    if (n === undefined) { setError(WORDS.problems.percent); return; }
    setError("");
    run(withOverall(tracker, { [field]: n }), WORDS.saved);
  };
  return (
    <>
      <input data-f={field} type="text" inputmode="decimal" autocomplete="off" maxLength={6} placeholder={WORDS.percentPlaceholder} disabled={busy} defaultValue={shown} key={shown} onBlur={onBlur}
        onKeyDown={(e) => { if (e.key === "Enter" && !e.isComposing) { e.preventDefault(); e.currentTarget.blur(); } }} />
      {error ? <span class="t-err" role="alert">{error}</span> : null}
    </>
  );
}

const pctOf = (text) => { const n = pct(text); return n === null ? undefined : n; };
