// Row 828 (the spec's M4 and M5): the milestone peek's fields, editable in place. Each is one change with one Undo (changeMilestone) and
// the data is read again after it. Text: click or Enter starts, Enter or leaving the box saves, Esc leaves it as it was (a description
// takes Enter for a new line and Ctrl or Cmd with Enter to save). A date opens the Work items' date picker; the state is a row of
// buttons; Visible to client is the eye (the page's own report_hidden step). Rows and words are the build's own (Help: The milestone
// peek); the toasts use the Work items cell's sentences ("Owner of ABC-M-001 changed to ...").
import { useLayoutEffect, useRef, useState } from "preact/hooks";
import { data, project, reread } from "../stores/report.js";
import { changeMilestone, say } from "../stores/changes.js";
import { DuePick } from "./cells/DuePick.jsx";
import { MenuPick } from "./cells/MenuPick.jsx";
import { fieldIcon } from "../menuIcons.js";
import { quickDates } from "./itemEdit.js";
import { showDate, todayIso, ownerOf } from "../workItems.js";
import { leftOutIds } from "../logic/picker.js";
import { setMsHidden } from "./actions.js";
import { useGrow } from "./useGrow.js";
import { RichField } from "./RichField.jsx";
import { richOrPlain } from "../logic/richOrPlain.js";
import { richWords } from "../logic/richWords.js";
import { PICKABLE, ALL_STATES, shownState, stateChange, textChange, progressChange } from "./msPeek.js";

const DASH = "—";
const Row = ({ name, k, children }) => <div class="pk-row" data-row={k}><dt>{name}</dt><dd>{children}</dd></div>;

// Send one change and read the data again. A refusal is said in a toast (nothing changed); resolves to true when it was saved.
async function save(m, changes, words) {
  const res = await changeMilestone({ id: m.id, changes, place: "peek" }, words);
  if (!res.ok) { say("problem", res.message); return false; }
  await reread(project.value);
  return true;
}
const said = (m, field, now, text) => (now == null || now === "" ? `${field} of ${m.id} cleared.` : `${field} of ${m.id} changed to ${text === undefined ? now : text}.`);

// A text value you click to change. `lines`: a description (several lines; Ctrl or Cmd with Enter saves).
function Text({ m, field, label, value, lines = false, required = false, max = 200 }) {
  const [open, setOpen] = useState(false), [text, setText] = useState("");
  const box = useRef(null), settled = useRef(false), shown = useRef(null);
  useGrow(box, open && lines ? text : null);
  useLayoutEffect(() => { if (open && box.current) { box.current.focus(); const n = box.current.value.length; box.current.setSelectionRange(n, n); } }, [open]);
  const stop = () => { settled.current = true; setOpen(false); setTimeout(() => { if (shown.current) shown.current.focus(); }, 0); };
  const commit = async (typed) => {
    const c = textChange(field, value, typed, { required });
    if (!c) return stop();
    settled.current = true;
    const ok = await save(m, c, said(m, label, c[field]));
    if (ok) stop(); else { settled.current = false; if (box.current) box.current.focus(); }
    return undefined;
  };
  const key = (e) => {
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); stop(); }
    else if (e.key === "Enter" && !e.isComposing && (!lines || e.metaKey || e.ctrlKey)) { e.preventDefault(); commit(e.currentTarget.value); }
  };
  if (!open) {
    return (
      <button type="button" class="pk-latest-text pk-ms-text" data-ms-field={field} ref={shown} aria-label={`${label} of ${m.id}: ${value || DASH}. Change`}
        onClick={() => { settled.current = false; setText(value || ""); setOpen(true); }}>{value || DASH}</button>
    );
  }
  return lines
    ? <textarea class="pk-latest-in grow" data-ms-in={field} aria-label={label} rows={3} maxLength={max} value={text} ref={box}
        onInput={(e) => setText(e.currentTarget.value)} onKeyDown={key} onBlur={(e) => { if (!settled.current) commit(e.currentTarget.value); }} />
    : <input type="text" class="pk-latest-in pk-ms-in" data-ms-in={field} aria-label={label} maxLength={max} value={text} ref={box} autocomplete="off" spellcheck={false}
        onInput={(e) => setText(e.currentTarget.value)} onKeyDown={key} onBlur={(e) => { if (!settled.current) commit(e.currentTarget.value); }} />;
}

// Item 1005: the description is on the one rich editor (RichField): the text drawn is cleanHtml of what is stored (the editor's HTML, or the plain
// text an older clark stored), Cmd or Ctrl with Enter saves, Esc leaves it as it was. One change with one Undo; it stays open if clark refuses.
function Description({ m }) {
  const html = (() => { try { return richOrPlain(m.description || ""); } catch (e) { return "<p>" + String(m.description || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") + "</p>"; } })();
  const put = (value) => save(m, { description: value }, richWords(value).trim() ? `Description of ${m.id} changed.` : `Description of ${m.id} cleared.`);
  return <RichField field="description" id={m.id} value={html} label="Description" empty={DASH} save={put} />;
}

// A date you pick: the Work items' date picker, with no new words (its panel is named by the field and the id).
function DateField({ m, field, label }) {
  const [open, setOpen] = useState(false);
  const button = useRef(null);
  const value = m[field] || "";
  const today = todayIso();
  const close = (back) => { setOpen(false); if (back && button.current) button.current.focus(); };
  const pick = async (day) => {
    close(true);
    const iso = day || null;
    if (iso === (value || null)) return;
    await save(m, { [field]: iso }, said(m, label, iso, iso ? showDate(iso) : ""));
  };
  const quick = quickDates(today).concat(value ? [["No date", ""]] : []);
  return (
    <>
      <button type="button" class="cell-pick pk-ms-date" ref={button} data-ms-field={field} aria-haspopup="dialog" aria-expanded={open ? "true" : "false"}
        aria-label={`${label} of ${m.id}: ${value ? showDate(value) : DASH}. Change`} onClick={() => setOpen(!open)}
        onKeyDown={(e) => { if (e.key === "Escape" && open) { e.preventDefault(); e.stopPropagation(); close(true); } }}>{value ? showDate(value) : DASH}</button>
      {open ? <DuePick row={{ id: m.id, kind: "action", due_date: value || null }} anchor={button} today={today} label={`${label} of ${m.id}`} quick={quick} onPick={pick} onClose={close} /> : null}
    </>
  );
}

function Progress({ m }) {
  const was = m.percent_complete == null ? null : m.percent_complete;
  const [typed, setTyped] = useState(null);                 // null: showing the saved number
  const [again, setAgain] = useState(0);                     // a new key after each try, so a number that was not taken is drawn as it was saved
  const shown = typed === null ? (was == null ? "" : String(was)) : typed;
  const commit = async (v) => {
    setTyped(null);
    setAgain((n) => n + 1);
    const c = progressChange(was, v);
    if (c) await save(m, c, said(m, "Progress", c.percent_complete, `${c.percent_complete}%`));
  };
  return (
    <span class="pk-ms-progress">
      <input type="range" min="0" max="100" step="1" value={shown === "" ? 0 : Number(shown)} aria-label={`Progress of ${m.id}`} data-ms-range
        onInput={(e) => setTyped(e.currentTarget.value)} onChange={(e) => commit(e.currentTarget.value)} />
      <input type="text" inputMode="numeric" class="pk-ms-num" key={again} value={shown} maxLength={3} placeholder={DASH} aria-label={`Progress of ${m.id}, a number from 0 to 100`} data-ms-num
        onInput={(e) => setTyped(e.currentTarget.value)} onBlur={(e) => commit(e.currentTarget.value)}
        onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); commit(e.currentTarget.value); } else if (e.key === "Escape") { e.stopPropagation(); setTyped(null); } }} />
    </span>
  );
}

function States({ m }) {
  const today = todayIso(), now = shownState(m, today);
  const pick = (s) => {
    const c = stateChange(m, s, today);
    return save(m, c, `State of ${m.id} changed to ${c.state || shownState({ ...m, ...c }, today)}.`);
  };
  return (
    <span class="pk-ms-states" role="group" aria-label={`State of ${m.id}`}>
      {ALL_STATES.map((s) => (
        <button type="button" key={s} class="pk-ms-state" data-ms-state={s} aria-pressed={now === s ? "true" : "false"} disabled={!PICKABLE.includes(s)}
          onClick={() => pick(s)}>{s}</button>
      ))}
    </span>
  );
}

function Workstream({ m }) {
  const [open, setOpen] = useState(false);
  const button = useRef(null);
  const names = ((data.value && data.value.workstreams) || []).filter((w) => !w.archived && w.status !== "Closed").map((w) => w.name).filter(Boolean);
  const value = m.workstream || "";
  const options = value && !names.includes(value) ? [value, ...names] : names;
  const choices = options.map((w) => ({ value: w, text: w, ...fieldIcon("workstream") })).concat([{ value: "", text: "No workstream", ...fieldIcon("workstream", true) }]);
  const close = (back) => { setOpen(false); if (back && button.current) button.current.focus(); };
  const pick = (v) => {
    close(true);
    const c = textChange("workstream", value, v);
    if (c) save(m, c, said(m, "Workstream", c.workstream));
  };
  return (
    <>
      <button type="button" class="pk-pick" ref={button} data-ms-field="workstream" aria-haspopup="menu" aria-expanded={open ? "true" : "false"}
        aria-label={`Workstream of ${m.id}: ${value || DASH}. Change`} onClick={() => setOpen(!open)}>{value || DASH}</button>
      {open ? <MenuPick anchor={button} label={`Workstream of ${m.id}`} current={value} choices={choices} onPick={pick} onClose={close} /> : null}
    </>
  );
}

function Visible({ m }) {
  const internal = !m.client_visible && m.client_visible !== undefined;
  const left = leftOutIds(data.value).includes(m.id);
  const on = !internal && !left;
  return (
    <button type="button" class="pk-ms-eye" data-ms-visible aria-pressed={on ? "true" : "false"} disabled={internal}
      aria-label={`Visible to client: ${m.name}`} onClick={() => setMsHidden(m.id, on, m.name).then(() => reread(project.value))}>{on ? "Yes" : "No"}</button>
  );
}

export function MilestoneEdit({ m }) {
  return (
    <dl class="pk-fields" data-ms-edit>
      <Row name="Name" k="name"><Text m={m} field="name" label="Name" value={m.name} required /></Row>
      <Row name="Owner" k="owner"><Text m={m} field="owner" label="Owner" value={ownerOf(m.owner).text === DASH ? "" : ownerOf(m.owner).text} /></Row>
      <Row name="Agreed date" k="baseline">{showDate(m.baseline_date)}</Row>
      <Row name="Forecast date" k="forecast"><DateField m={m} field="forecast_date" label="Forecast date" /></Row>
      {m.status === "Done" ? <Row name="Achieved on" k="actual"><DateField m={m} field="actual_date" label="Achieved on" /></Row> : null}
      <Row name="State" k="state"><States m={m} /></Row>
      <Row name="Progress" k="progress"><Progress m={m} /></Row>
      <Row name="Description" k="description"><Description m={m} /></Row>
      <Row name="Workstream" k="workstream"><Workstream m={m} /></Row>
      <Row name="Visible to client" k="visible"><Visible m={m} /></Row>
      <Row name="Client wording" k="client_message"><Text m={m} field="client_message" label="Client wording" value={m.client_message || ""} lines max={500} /></Row>
    </dl>
  );
}
