// Milestones Movement (#136; BRD FR-50 to FR-53), the owner's block under the Milestones list. Edit only: it is one of the `tools`
// (edit/index.js), so the published page, which is given none, has none of it. It reads GET /api/movement (the server's cut-down view,
// movement_view.py: no internal note), draws the sentence, one row per open milestone (worst first), the chosen milestone's card
// with What changed, and the four choices: Hold, Move the agreed date (who agreed it, the reason and the source are asked for, and
// the confirm says what will happen), Add a recovery action and Escalate to steering (#458: a linked action, a steering decision;
// each opens in the peek). Below them is the owner's Internal note (#458), saved when the box is left. Each choice is one change
// with one Undo (stores/changes.js). Words: edit/movementWords.js.
import { signal } from "@preact/signals";
import { useEffect, useRef } from "preact/hooks";
import { project, mode, data, reread, openPeek } from "../stores/report.js";
import { changeMilestone, say, undone } from "../stores/changes.js";
import { dayNumber, showDate, todayIso } from "../workItems.js";
import { addDays } from "../logic/milestones.js";
import { readMovement } from "./movementApi.js";
import { addRow } from "./newRows.js";
import * as W from "./movementWords.js";

const phase = signal("loading");        // loading | ready | failed
const view = signal(null);              // the last view that was read
const picked = signal("");              // the chosen milestone's id ("" for the first row)
const form = signal(null);              // null, or { to, who, reason, source, errors: [], busy } for the open Move form
const adding = signal(false);           // a recovery action or a steering decision is being added: the two buttons wait

let seq = 0;
async function load() {
  const code = project.value;
  const mine = ++seq;
  if (!view.value) phase.value = "loading";
  const r = await readMovement(code);
  if (mine !== seq) return;
  if (r.ok) { view.value = r.view; phase.value = "ready"; } else { view.value = null; phase.value = "failed"; }
}

const PILL = { green: "g", amber: "a", red: "r", blue: "b", grey: "n" };

// Where a date sits on a row's track, 0 to 100, from the row's own dates and today; null when the date is missing.
function trackAt(r, today) {
  const days = [r.original, r.agreed, r.forecast, r.expected, today].map(dayNumber).filter((n) => n !== null);
  if (!days.length) return () => null;
  const lo = Math.min(...days) - 3, hi = Math.max(...days) + 3;
  return (iso) => { const n = dayNumber(iso); return n === null ? null : ((n - lo) / (hi - lo)) * 100; };
}

function Track({ r }) {
  const today = todayIso(), at = trackAt(r, today);
  const a = at(r.agreed), o = at(r.original), f = at(r.forecast), x = at(r.expected), t = at(today);
  const style = (n) => ({ left: `${n}%` });
  return (
    <span class="mvm-track" aria-hidden="true">
      <i class="mvm-line"></i>
      {a !== null && x !== null && x > a ? <i class="mvm-late" style={{ left: `${a}%`, width: `${x - a}%` }}></i> : null}
      {o !== null && r.rebaselined ? <i class="mvm-orig" style={style(o)}></i> : null}
      {a !== null ? <i class="mvm-agreed" style={style(a)}></i> : null}
      {f !== null ? <i class="mvm-fc" style={style(f)}></i> : null}
      {t !== null ? <i class="mvm-today" style={style(t)}></i> : null}
    </span>
  );
}

function Row({ r, on, onPick, onKey }) {
  return (
    <button type="button" class={`mvm-row${on ? " on" : ""}`} data-id={r.id} aria-pressed={on ? "true" : "false"} onClick={() => onPick(r.id)} onKeyDown={onKey}>
      <span class="mvm-name">{r.name}</span>
      <span class={`pill ${PILL[r.colour] || "n"}`}>{r.state}</span>
      <span class="mvm-dates num">{W.LABELS.agreed} {showDate(r.agreed)}{r.slip > 0 && r.forecast ? `, forecast ${showDate(r.forecast)}` : ""}</span>
      <Track r={r} />
      <span class="mvm-var">{r.variance}</span>
      <span class="mvm-moved muted">{r.moved_label}</span>
    </button>
  );
}

function Entry({ en }) {
  return (
    <li class={`mvm-en${en.undone ? " undone" : ""}`}>
      <span class="mv-en-text">{en.text}</span>
      {en.tag ? <span class="tag">{en.tag}</span> : null}
      <span class="mv-en-by muted num">{[en.by ? `by ${en.by}` : "", en.at_text || ""].filter(Boolean).join(", ")}</span>
      {en.why ? <span class="mv-en-why">{en.why}</span> : null}
      {en.decision ? <span class="mv-en-dec muted">Decision {en.decision}</span> : null}
    </li>
  );
}

// The Move form's checks, in the words of milestone_rows.rebaseline_request (the server checks them again).
function problems(r, f) {
  const out = [], today = todayIso();
  const m = /^(\d{2})-(\d{2})-(\d{4})$/.exec(f.to.trim()), iso = m ? `${m[3]}-${m[2]}-${m[1]}` : /^\d{4}-\d\d-\d\d$/.test(f.to.trim()) ? f.to.trim() : "";
  const n = dayNumber(iso);
  if (n === null) out.push(W.DATE_UNREADABLE);
  else if (iso === r.agreed) out.push(W.fill(W.SAME_DATE, showDate(r.agreed)));
  else if (iso < r.agreed) out.push(W.fill(W.EARLIER_DATE, showDate(r.agreed)));
  else if (iso < today) out.push(W.fill(W.PAST_DATE, showDate(today)));
  if (!f.who.trim()) out.push(W.WHO_MISSING);
  if (!f.reason.trim()) out.push(W.REASON_MISSING);
  if (!f.source.trim()) out.push(W.SOURCE_MISSING);
  return { out, iso };
}

const toIso = (text) => { const m = /^(\d{2})-(\d{2})-(\d{4})$/.exec(text.trim()); return m ? `${m[3]}-${m[2]}-${m[1]}` : text.trim(); };

function focusRow(id) {
  setTimeout(() => { const el = document.querySelector(`.mvm-row[data-id="${id}"]`); if (el) el.focus(); }, 0);
}

async function hold(r) {
  const res = await changeMilestone({ id: r.id, changes: { movement: "hold" } }, W.TOAST_HOLD);
  if (!res.ok) { say("problem", res.message || W.CHOICE_FAILED); return; }
  await reread(project.value);            // the Hold's dated line is in the internal note: the box shows it
  await load();
  focusRow(r.id);
}

const lower = (name) => name.charAt(0).toLowerCase() + name.slice(1);
const milestoneRow = (id) => ((data.value && data.value.milestones) || []).find((m) => m.id === id);

// The line a new recovery action or steering decision starts with (the prototype's): how far behind the agreed date the milestone is.
// None when the milestone has no agreed date to be behind.
function explain(r) {
  if (typeof r.slip !== "number") return "";
  return r.slip > 0 ? W.fill(W.BEHIND_LINE, r.name, `${r.slip} ${r.slip === 1 ? "day" : "days"}`) : W.fill(W.NOT_BEHIND_LINE, r.name);
}

// The workstream a recovery action goes in: the milestone's own while it is open, else the first open one. An action can only go in
// an open workstream (the store refuses a closed or archived one); null when there is none.
function openWorkstream(m) {
  const open = ((data.value && data.value.workstreams) || []).filter((w) => w.name && w.status !== "Closed" && !w.archived);
  const own = m && m.workstream ? open.find((w) => w.name === m.workstream) : null;
  return own ? own.name : open.length ? open[0].name : null;
}

// Add a recovery action (#458): a High priority action due in 7 days, in the milestone's workstream and linked to it. It opens in the peek.
async function recover(r) {
  if (adding.value) return;
  adding.value = true;
  try {
    const ws = openWorkstream(milestoneRow(r.id));
    if (!ws) { say("problem", W.NO_WORKSTREAM); return; }
    const values = { description: W.fill(W.RECOVER_TITLE, lower(r.name)), priority: "High", due_date: addDays(todayIso(), 7), milestone: r.id, workstream: ws };
    const line = explain(r).slice(0, 200);
    if (line) values.latest_update = line;
    const reply = await addRow("actions", values, (id) => W.fill(W.TOAST_ACTION, id, r.name));
    if (reply && reply.ref) openPeek(reply.ref, "item");
  } finally { adding.value = false; }
}

// Escalate to steering (#458): a Pending decision needed in 7 days. A decision is not tied to a milestone, so its words name it. It opens in the peek.
async function escalate(r) {
  if (adding.value) return;
  adding.value = true;
  try {
    const values = { decision: W.fill(W.ESCALATE_TITLE, lower(r.name)), needed_by: addDays(todayIso(), 7) };
    const line = explain(r).slice(0, 200);
    if (line) values.reasoning = line;
    const reply = await addRow("decisions", values, (id) => W.fill(W.TOAST_DECISION, id, r.name));
    if (reply && reply.ref) openPeek(reply.ref, "item");
  } finally { adding.value = false; }
}

async function move(r) {
  const f = form.value;
  const { out, iso } = problems(r, f);
  if (out.length) { form.value = { ...f, errors: out }; return; }
  form.value = { ...f, errors: [], busy: true };
  const res = await changeMilestone({ id: r.id, changes: { baseline_date: iso },
    rebaseline: { agreed_with: f.who.trim(), reason: f.reason.trim(), source: f.source.trim() } }, W.fill(W.TOAST_MOVED, r.name, showDate(iso)));
  if (!res.ok) { form.value = { ...form.value, errors: [res.message], busy: false }; return; }
  form.value = null;
  await load();
  focusRow(r.id);
}

function MoveForm({ r }) {
  const f = form.value;
  const set = (k) => (e) => { form.value = { ...form.value, [k]: e.currentTarget.value, errors: [] }; };
  const cancel = () => { form.value = null; setTimeout(() => { const b = document.getElementById("mv-move"); if (b) b.focus(); }, 0); };
  const iso = toIso(f.to), ready = dayNumber(iso) !== null;
  const confirm = W.fill(W.CONFIRM, r.name, showDate(r.agreed), ready ? showDate(iso) : f.to.trim() || "…", r.original_text);
  useEffect(() => { const el = document.getElementById("mv-to"); if (el) el.focus(); }, []);
  return (
    <form class="mvm-form" aria-labelledby="mv-form-h" onSubmit={(e) => { e.preventDefault(); if (!f.busy) move(r); }}
      onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); cancel(); } }}>
      <h4 id="mv-form-h">{W.MOVE_LABEL}</h4>
      <label class="mvm-f" for="mv-to"><span>{W.FIELDS.to}</span><input id="mv-to" type="text" inputmode="numeric" autocomplete="off" value={f.to} onInput={set("to")} /></label>
      <label class="mvm-f" for="mv-who"><span>{W.FIELDS.who}</span><input id="mv-who" type="text" autocomplete="off" value={f.who} onInput={set("who")} /></label>
      <label class="mvm-f" for="mv-reason"><span>{W.FIELDS.reason}</span><input id="mv-reason" type="text" autocomplete="off" value={f.reason} onInput={set("reason")} /></label>
      <label class="mvm-f" for="mv-source"><span>{W.FIELDS.source}</span><input id="mv-source" type="text" autocomplete="off" value={f.source} onInput={set("source")} /></label>
      <p class="mvm-confirm" id="mvm-confirm">{confirm}</p>
      <div class="mvm-problems" role="alert">{f.errors.map((e) => <p key={e}>{e}</p>)}</div>
      <div class="mvm-actions">
        <button type="submit" class="again" id="mv-go" disabled={f.busy} aria-describedby="mvm-confirm">{W.MOVE_LABEL}</button>
        <button type="button" class="btn" id="mv-keep" onClick={cancel}>{W.KEEP_LABEL}</button>
      </div>
    </form>
  );
}

// The owner's Internal note (#458): saved when the box is left, never published. It is read from the project's own data (the Movement
// read leaves it out), and the data is read again after the save and after an Undo, so the box shows what clark holds.
function Note({ r }) {
  const m = milestoneRow(r.id), saved = (m && m.internal_note) || "", box = useRef(null);
  useEffect(() => { if (box.current) box.current.value = saved; }, [r.id, saved]);
  const save = async (e) => {
    const text = e.currentTarget.value.trim();
    if (text === saved.trim()) return;
    const res = await changeMilestone({ id: r.id, changes: { internal_note: text } }, W.TOAST_NOTE);
    if (!res.ok) { say("problem", res.message || W.NOTE_FAILED); return; }
    await reread(project.value);
  };
  return (
    <>
      <h4>{W.NOTE_HEADING}</h4>
      <textarea ref={box} class="field mvm-note" id="mvNote" rows="4" maxlength="2000" placeholder={W.NOTE_PLACEHOLDER} aria-describedby="mvNote-help" onBlur={save}></textarea>
      <p class="muted mvm-help" id="mvNote-help">{W.NOTE_HELP}</p>
    </>
  );
}

function Card({ r }) {
  const open = form.value && form.value.id === r.id;
  const can = r.can_move;
  const start = () => { form.value = { id: r.id, to: showDate(r.expected || ""), who: "", reason: "", source: "", errors: [], busy: false }; };
  return (
    <div class="mvm-card" aria-labelledby="mv-card-h">
      <h3 id="mv-card-h">{r.name}</h3>
      <ul class="mvm-chips plain">
        <li><span class="muted">{W.LABELS.original}</span> <b class="num">{r.original_text}</b></li>
        <li><span class="muted">{W.LABELS.agreed}</span> <b class="num">{showDate(r.agreed)}</b></li>
        <li><span class="muted">{W.LABELS.forecast}</span> <b class="num">{showDate(r.forecast)}</b></li>
        <li><b>{r.moves_text}</b></li>
        <li><span class="muted">{W.LABELS.progress}</span> <b class="num">{r.percent === null || r.percent === undefined ? "—" : `${r.percent}%`}</b></li>
        <li><span class="muted">{W.LABELS.owner}</span> <b>{r.owner || "—"}</b></li>
      </ul>
      <h4>{W.WHAT_CHANGED}</h4>
      {r.entries.length ? <ul class="mvm-list plain">{r.entries.map((en) => <Entry key={`${en.step}-${en.event_id}`} en={en} />)}</ul> : (r.notice ? null : <p class="muted">{W.NOTHING_CHANGED}</p>)}
      {r.notice ? <p class="muted">{r.notice}</p> : null}
      <h4>{W.DECIDE}</h4>
      <p class="muted mvm-help">{W.DECIDE_HELP}</p>
      <div class="mvm-actions">
        <button type="button" class="btn" id="mv-hold" onClick={() => hold(r)}>{W.HOLD_LABEL}</button>
        <button type="button" class="btn" id="mv-move" disabled={!can || open} aria-describedby={can ? undefined : "mv-why"} onClick={start}>{W.MOVE_LABEL}</button>
        <button type="button" class="btn" id="mv-recover" disabled={adding.value} onClick={() => recover(r)}>{W.RECOVER_LABEL}</button>
        <button type="button" class="btn" id="mv-escalate" disabled={adding.value} onClick={() => escalate(r)}>{W.ESCALATE_LABEL}</button>
      </div>
      {!can ? <p class="muted" id="mv-why">{W.NOT_SLIPPED}</p> : null}
      {open ? <MoveForm r={r} /> : null}
      <Note r={r} />
    </div>
  );
}

export function Movement() {
  const code = project.value, again = undone.value, editing = mode.value === "edit";
  useEffect(() => { form.value = null; picked.value = ""; if (editing) load(); }, [code, editing]);
  useEffect(() => { if (again && editing) load(); }, [again]);
  if (!editing) return null;
  const v = view.value;
  let body;
  if (phase.value === "loading" && !v) body = <p class="muted" role="status">{W.LOADING}</p>;
  else if (phase.value === "failed" || !v) {
    body = (
      <div role="alert">
        <p>{W.READ_FAILS}</p>
        <button type="button" class="again" onClick={load}>{W.TRY_AGAIN}</button>
      </div>
    );
  } else {
    const on = v.rows.find((r) => r.id === picked.value) || v.rows[0];
    const keys = (e) => {
      if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
      const all = [...document.querySelectorAll(".mvm-row")], i = all.indexOf(e.currentTarget), next = all[i + (e.key === "ArrowDown" ? 1 : -1)];
      if (next) { e.preventDefault(); next.focus(); }
    };
    body = (
      <>
        <p class="mvm-sentence" role="status">{v.sentence}</p>
        {v.worst ? <p class="mvm-worst">{v.worst}</p> : null}
        {v.rows.length ? <div class="mvm-rows" role="group" aria-label="Open milestones">{v.rows.map((r) => <Row key={r.id} r={r} on={on && on.id === r.id} onPick={(id) => { form.value = null; picked.value = id; }} onKey={keys} />)}</div> : null}
        {on ? <Card key={on.id} r={on} /> : null}
      </>
    );
  }
  return (
    <section class="mvm" id="movement" data-edit-only aria-labelledby="mv-h">
      <div class="mvm-top"><h2 id="mv-h">{W.HEADING}</h2><span class="tag">{W.TAG_INTERNAL}</span></div>
      <p class="muted">{W.HELP_LINE}</p>
      {body}
    </section>
  );
}
