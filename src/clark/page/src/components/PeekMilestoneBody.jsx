// Item 1184: the milestone peek's Details rows on the shared frame (Description, Agreed date, Achieved on, Workstream, Use case, Client wording,
// then the Client visible line). The chip row (State, Owner, Progress, Forecast date) is drawn by Peek.jsx's MilestoneChips, which can use the
// exports here (saveMilestone, said, DateField). Each field is one change with one Undo (changeMilestone) and the data is read again after it.
// Decisions: the Use case row links with msadd and msremove on use_cases (a single choice: its old direct link is removed, the new one added);
// the Latest update box waits for its store ticket and is not drawn.
import { useRef, useState } from "preact/hooks";
import { data, project, reread } from "../stores/report.js";
import { change, changeMilestone, say } from "../stores/changes.js";
import { DuePick } from "../edit/cells/DuePick.jsx";
import { MenuPick } from "../edit/cells/MenuPick.jsx";
import { fieldIcon } from "../menuIcons.js";
import { quickDates } from "../edit/itemEdit.js";
import { showDate, todayIso } from "../workItems.js";
import { leftOutIds } from "../logic/picker.js";
import { setMsHidden } from "../edit/actions.js";
import { RichField } from "../edit/RichField.jsx";
import { richOrPlain } from "../logic/richOrPlain.js";
import { richWords } from "../logic/richWords.js";
import { Icon } from "./Icon.jsx";
import { PeekDetails } from "./PeekDetails.jsx";
import { textChange } from "../edit/msPeek.js";

const DASH = "—";
const Row = ({ name, k, off = false, children }) => <div class={off ? "pk-row off" : "pk-row"} data-ms-row={k} aria-disabled={off ? "true" : undefined}><dt>{name}</dt><dd>{children}</dd></div>;

// Send one change and read the data again. A refusal is said in a toast (nothing changed); resolves to true when it was saved.
export async function saveMilestone(m, changes, words) {
  const res = await changeMilestone({ id: m.id, changes, place: "peek" }, words);
  if (!res.ok) { say("problem", res.message); return false; }
  await reread(project.value);
  return true;
}
export const said = (m, field, now, text) => (now == null || now === "" ? `${field} of ${m.id} cleared.` : `${field} of ${m.id} changed to ${text === undefined ? now : text}.`);

// Item 1005: the description is on the one rich editor (RichField): the text drawn is cleanHtml of what is stored (the editor's HTML, or the plain
// text an older clark stored), Cmd or Ctrl with Enter saves, Esc leaves it as it was. One change with one Undo; it stays open if clark refuses.
// Row 1078 (ruled): the client wording is on the same editor, the same way.
const asHtml = (value) => { try { return richOrPlain(value || ""); } catch (e) { return "<p>" + String(value || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") + "</p>"; } };
function Description({ m }) {
  const put = (value) => saveMilestone(m, { description: value }, richWords(value).trim() ? `Description of ${m.id} changed.` : `Description of ${m.id} cleared.`);
  return <RichField field="description" id={m.id} value={asHtml(m.description)} label="Description" empty={DASH} save={put} />;
}
function ClientWording({ m }) {
  const put = (value) => saveMilestone(m, { client_message: value }, richWords(value).trim() ? `Client wording of ${m.id} changed.` : `Client wording of ${m.id} cleared.`);
  return <RichField field="client_message" id={m.id} value={asHtml(m.client_message)} label="Client wording" empty={DASH} save={put} />;
}


// A date you pick: the Work items' date picker, with no new words (its panel is named by the field and the id).
export function DateField({ m, field, label }) {
  const [open, setOpen] = useState(false);
  const button = useRef(null);
  const value = m[field] || "";
  const today = todayIso();
  const close = (back) => { setOpen(false); if (back && button.current) button.current.focus(); };
  const pick = async (day) => {
    close(true);
    const iso = day || null;
    if (iso === (value || null)) return;
    await saveMilestone(m, { [field]: iso }, said(m, label, iso, iso ? showDate(iso) : ""));
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
    if (c) saveMilestone(m, c, said(m, "Workstream", c.workstream));
  };
  return (
    <>
      <button type="button" class="pk-pick" ref={button} data-ms-field="workstream" aria-haspopup="menu" aria-expanded={open ? "true" : "false"}
        aria-label={`Workstream of ${m.id}: ${value || DASH}. Change`} onClick={() => setOpen(!open)}>{value || DASH}</button>
      {open ? <MenuPick anchor={button} label={`Workstream of ${m.id}`} current={value} choices={choices} onPick={pick} onClose={close} /> : null}
    </>
  );
}


// Item 1184: the use case a milestone is linked to straight (one choice). Options: none, then the project's live use cases.
const directLinks = (m) => (((data.value && data.value.uc_milestones) || []).filter((l) => l.milestone === m.id).map((l) => l.use_case));
const ucName = (u) => `${u.ref ? u.ref + " " : ""}${u.title}`;
function UseCase({ m }) {
  const [open, setOpen] = useState(false);
  const button = useRef(null);
  const ucs = ((data.value && data.value.use_cases) || []).filter((u) => !u.archived);
  const have = directLinks(m);
  const current = have.length ? have[0] : "";
  const shown = ucs.find((u) => u.id === current);
  const choices = [{ value: "", text: "No use case", ...fieldIcon("use_case", true) }].concat(ucs.map((u) => ({ value: u.id, text: ucName(u), ...fieldIcon("use_case") })));
  const close = (back) => { setOpen(false); if (back && button.current) button.current.focus(); };
  const pick = async (id) => {
    close(true);
    if (id === current) return;
    for (const old of have) {
      const o = ucs.find((u) => u.id === old);
      await change({ kind: "use_cases", op: "msremove", id: old, ids: [m.id], place: "peek" }, `Use case of ${m.id} cleared${o ? " (" + ucName(o) + ")" : ""}.`);
    }
    const u = ucs.find((x) => x.id === id);
    if (u) await change({ kind: "use_cases", op: "msadd", id, ids: [m.id], place: "peek" }, `Use case of ${m.id} changed to ${ucName(u)}.`);
    await reread(project.value);
  };
  return (
    <>
      <button type="button" class="pk-pick" ref={button} data-ms-field="use_case" aria-haspopup="menu" aria-expanded={open ? "true" : "false"}
        aria-label={`Use case of ${m.id}: ${shown ? ucName(shown) : "none"}. Change`} onClick={() => setOpen(!open)}>{shown ? ucName(shown) : "Select use case"}</button>
      {open ? <MenuPick anchor={button} label={`Use case of ${m.id}`} current={current} choices={choices} onPick={pick} onClose={close} /> : null}
    </>
  );
}

// The Client visible line for a milestone: the eye of the Milestones page (the page's report_hidden step). Disabled when the milestone is internal.
export function MsClientLine({ m }) {
  const internal = !m.client_visible && m.client_visible !== undefined;
  const on = !internal && !leftOutIds(data.value).includes(m.id);
  return (
    <button type="button" class={`pk-client${on ? " on" : ""}`} data-pk-client data-ms-visible aria-pressed={on ? "true" : "false"} disabled={internal}
      onClick={() => setMsHidden(m.id, on, m.name).then(() => reread(project.value))}>
      <Icon name={on ? "eye" : "eyeoff"} />{on ? "Client visible" : "Client not visible"}
    </button>
  );
}

// Client wording is greyed and not clickable while the milestone is not shown to the client.
function Wording({ m, on }) {
  if (on) return <ClientWording m={m} />;
  return <div class="rt-view" data-rich="client_message" aria-disabled="true">{m.client_message ? <div class="sec-body prose" dangerouslySetInnerHTML={{ __html: asHtml(m.client_message) }} /> : <p class="quiet">{DASH}</p>}</div>;
}

export function MilestoneBody({ m }) {
  const internal = !m.client_visible && m.client_visible !== undefined;
  const on = !internal && !leftOutIds(data.value).includes(m.id);
  return (
    <PeekDetails summary={[m.workstream]}>
      <dl class="pk-fields" data-ms-edit>
        <Row name="Description" k="description"><Description m={m} /></Row>
        <Row name="Agreed date" k="baseline">{showDate(m.baseline_date)}</Row>
        {m.status === "Done" ? <Row name="Achieved on" k="actual"><DateField m={m} field="actual_date" label="Achieved on" /></Row> : null}
        <Row name="Workstream" k="workstream"><Workstream m={m} /></Row>
        <Row name="Use case" k="use_cases"><UseCase m={m} /></Row>
        <Row name="Client wording" k="client_message" off={!on}><Wording m={m} on={on} /></Row>
        <div class="pk-row" data-pk-client-row><dd><MsClientLine m={m} /></dd></div>
      </dl>
    </PeekDetails>
  );
}
