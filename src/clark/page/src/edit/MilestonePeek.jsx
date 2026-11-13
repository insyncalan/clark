// Row 828 (the spec's M4 and M5): the milestone peek's fields, editable in place. Each is one change with one Undo (changeMilestone) and
// the data is read again after it. Text: click or Enter starts, Enter or leaving the box saves, Esc leaves it as it was. A date opens the
// Work items' date picker; the state is a row of buttons; Visible to client is the eye (the page's own report_hidden step). Rows and
// words are the build's own (Help: The milestone peek); the toasts use the Work items cell's sentences ("Owner of ABC-M-001 changed to ...").
// Row 1078 (the owner's rulings): the work item peek's format. The name is the title (MilestoneTitle, drawn in the h2 by Peek.jsx); under
// it the shared header line (Peek.jsx MsHead: the state, the owner and the progress, here with their controls) and the state buttons; then
// the rows Description, Agreed date, Forecast date, Achieved on (a Done milestone's alone), Workstream, Visible to client and Client
// wording, plain rows (never the four property cells). Description and Client wording are on the one rich editor (item 1005).
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
import { usecasesOfMilestone } from "../logic/ucRow.js";
import { RichField } from "./RichField.jsx";
import { richOrPlain } from "../logic/richOrPlain.js";
import { richWords } from "../logic/richWords.js";
import { MsHead, MsState, MsSep } from "../components/Peek.jsx";
import { PICKABLE, ALL_STATES, shownState, stateChange, textChange, progressChange } from "./msPeek.js";

const DASH = "—";
const Row = ({ name, k, children }) => <div class="pk-row" data-ms-row={k}><dt>{name}</dt><dd>{children}</dd></div>;

// Send one change and read the data again. A refusal is said in a toast (nothing changed); resolves to true when it was saved.
async function save(m, changes, words) {
  const res = await changeMilestone({ id: m.id, changes, place: "peek" }, words);
  if (!res.ok) { say("problem", res.message); return false; }
  await reread(project.value);
  return true;
}
const said = (m, field, now, text) => (now == null || now === "" ? `${field} of ${m.id} cleared.` : `${field} of ${m.id} changed to ${text === undefined ? now : text}.`);

// A text value you click to change (the name in the title, the owner in the header line): one line, Enter saves.
function Text({ m, field, label, value, required = false, max = 200 }) {
  const [open, setOpen] = useState(false), [text, setText] = useState("");
  const box = useRef(null), settled = useRef(false), shown = useRef(null);
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
    else if (e.key === "Enter" && !e.isComposing) { e.preventDefault(); commit(e.currentTarget.value); }
  };
  if (!open) {
    return (
      <button type="button" class="pk-latest-text pk-ms-text" data-ms-field={field} ref={shown} aria-label={`${label} of ${m.id}: ${value || DASH}. Change`}
        onClick={() => { settled.current = false; setText(value || ""); setOpen(true); }}>{value || DASH}</button>
    );
  }
  return <input type="text" class="pk-latest-in pk-ms-in" data-ms-in={field} aria-label={label} maxLength={max} value={text} ref={box} autocomplete="off" spellcheck={false}
    onInput={(e) => setText(e.currentTarget.value)} onKeyDown={key} onBlur={(e) => { if (!settled.current) commit(e.currentTarget.value); }} />;
}

// Item 1005: the description is on the one rich editor (RichField): the text drawn is cleanHtml of what is stored (the editor's HTML, or the plain
// text an older clark stored), Cmd or Ctrl with Enter saves, Esc leaves it as it was. One change with one Undo; it stays open if clark refuses.
// Row 1078 (ruled): the client wording is on the same editor, the same way.
const asHtml = (value) => { try { return richOrPlain(value || ""); } catch (e) { return "<p>" + String(value || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") + "</p>"; } };
function Description({ m }) {
  const put = (value) => save(m, { description: value }, richWords(value).trim() ? `Description of ${m.id} changed.` : `Description of ${m.id} cleared.`);
  return <RichField field="description" id={m.id} value={asHtml(m.description)} label="Description" empty={DASH} save={put} />;
}
function ClientWording({ m }) {
  const put = (value) => save(m, { client_message: value }, richWords(value).trim() ? `Client wording of ${m.id} changed.` : `Client wording of ${m.id} cleared.`);
  return <RichField field="client_message" id={m.id} value={asHtml(m.client_message)} label="Client wording" empty={DASH} save={put} />;
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
    <span class="pk-ms-states" role="group" aria-label={`State of ${m.id}`} data-ms-states>
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

// The title: the milestone's name, changed in place (Peek.jsx draws it in the h2 when the milestone is editable).
export function MilestoneTitle({ m }) {
  return <Text m={m} field="name" label="Name" value={m.name} required />;
}

export function MilestoneEdit({ m }) {
  const owner = ownerOf(m.owner).text;
  return (
    <>
      <MsHead>
        <MsState m={m} dated={false} /><MsSep />
        <span class="pk-ms-owner" data-ms-head="owner"><Text m={m} field="owner" label="Owner" value={owner === DASH ? "" : owner} /></span><MsSep />
        <span class="pk-ms-progress" data-ms-head="progress"><Progress m={m} /></span>
      </MsHead>
      <States m={m} />
      <dl class="pk-fields" data-ms-edit>
        <Row name="Description" k="description"><Description m={m} /></Row>
        <Row name="Agreed date" k="baseline">{showDate(m.baseline_date)}</Row>
        <Row name="Forecast date" k="forecast"><DateField m={m} field="forecast_date" label="Forecast date" /></Row>
        {m.status === "Done" ? <Row name="Achieved on" k="actual"><DateField m={m} field="actual_date" label="Achieved on" /></Row> : null}
        <Row name="Workstream" k="workstream"><Workstream m={m} /></Row>
        <Row name="Use cases" k="use_cases"><span data-ms-ucs>{usecasesOfMilestone(data.value, m.id).map((u) => `${u.ref ? u.ref + " " : ""}${u.title}`).join(", ") || "—"}</span></Row>      {/* row 1107: the use cases linked straight to it and those reaching it through their actions, risks, issues and decisions (the editor only; a use case is linked or unlinked on its own page) */}
        <Row name="Visible to client" k="visible"><Visible m={m} /></Row>
        <Row name="Client wording" k="client_message"><ClientWording m={m} /></Row>
      </dl>
    </>
  );
}
