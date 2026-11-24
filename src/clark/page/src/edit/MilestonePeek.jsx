// Row 828 (the spec's M4 and M5): the milestone peek's fields, editable in place. Each is one change with one Undo (changeMilestone) and
// the data is read again after it. Text: click or Enter starts, Enter or leaving the box saves, Esc leaves it as it was. A date opens the
// Work items' date picker; the state is a row of buttons; Visible to client is the eye (the page's own report_hidden step). Rows and
// words are the build's own (Help: The milestone peek); the toasts use the Work items cell's sentences ("Owner of ABC-M-001 changed to ...").
// Row 1078 (the owner's rulings): the work item peek's format. The name is the title (PeekMilestoneTitle in PeekHead.jsx, drawn in the h2 by Peek.jsx).
// Row 1184: under it the chip row (components/PeekMilestoneChips.jsx: State, Owner, Progress, Forecast date; their popovers are msChipPop below), the
// Latest update box (PeekMsLatest) above Details, then the rows Description, Agreed date (read only), Achieved on (an achieved milestone's alone),
// Workstream, Use case (one link, through the use cases' own msadd and msremove), Client wording (greyed while the milestone is not shown to the client)
// and the Client visible line. Description and Client wording are on the one rich editor (item 1005).
import { useRef, useState } from "preact/hooks";
import { data, project, reread } from "../stores/report.js";
import { changeMilestone, change, say } from "../stores/changes.js";
import { DuePick } from "./cells/DuePick.jsx";
import { OwnerPick } from "./cells/OwnerPick.jsx";
import { Pop } from "./cells/Pop.jsx";
import { MenuPick } from "./cells/MenuPick.jsx";
import { fieldIcon } from "../menuIcons.js";
import { quickDates } from "./itemEdit.js";
import { showDate, todayIso } from "../workItems.js";
import { leftOutIds } from "../logic/picker.js";
import { setMsHidden } from "./actions.js";
import { usecasesOfMilestone } from "../logic/ucRow.js";
import { RichField } from "./RichField.jsx";
import { richOrPlain } from "../logic/richOrPlain.js";
import { richWords } from "../logic/richWords.js";
import { STATE_LOOK, shownStateOf } from "../components/PeekMilestoneChips.jsx";
import { iconClass } from "../iconColours.js";
import { people } from "./itemEdit.js";
import { PeekDetails } from "../components/PeekDetails.jsx";
import { stampText } from "./peekLatest.js";
import { LatestBox } from "./PeekLatest.jsx";
import { Icon } from "../components/Icon.jsx";
import { PICKABLE, ALL_STATES, stateChange, textChange, progressChange } from "./msPeek.js";

const DASH = "—";
// Row icons as the Action peek's rows (PeekActionBody.jsx ARow).
const Row = ({ name, k, icon, children }) => <div class="pk-row" data-ms-row={k}><dt>{icon ? <span class={`pk-rowic ${iconClass("b")}`}><Icon name={icon} /></span> : null}{name}</dt><dd>{children}</dd></div>;

// Send one change and read the data again. A refusal is said in a toast (nothing changed); resolves to true when it was saved.
async function save(m, changes, words) {
  const res = await changeMilestone({ id: m.id, changes, place: "peek" }, words);
  if (!res.ok) { say("problem", res.message); return false; }
  await reread(project.value);
  return true;
}
const said = (m, field, now, text) => (now == null || now === "" ? `${field} of ${m.id} cleared.` : `${field} of ${m.id} changed to ${text === undefined ? now : text}.`);

// Item 1005: the description is on the one rich editor (RichField): the text drawn is cleanHtml of what is stored (the editor's HTML, or the plain
// text an older clark stored), Cmd or Ctrl with Enter saves, Esc leaves it as it was. One change with one Undo; it stays open if clark refuses.
// Row 1078 (ruled): the client wording is on the same editor, the same way.
const asHtml = (value) => { try { return richOrPlain(value || ""); } catch (e) { return "<p>" + String(value || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") + "</p>"; } };
function Description({ m }) {
  const put = (value) => save(m, { description: value }, richWords(value).trim() ? `Description of ${m.id} changed.` : `Description of ${m.id} cleared.`);
  return <RichField field="description" id={m.id} value={asHtml(m.description)} label="Description" empty="Add description" save={put} />;
}
// Client wording: on the editor while the milestone is shown to the client; greyed and not clickable while it is not (the Client visible line turns it on).
function ClientWording({ m, on }) {
  const put = (value) => save(m, { client_message: value }, richWords(value).trim() ? `Client wording of ${m.id} changed.` : `Client wording of ${m.id} cleared.`);
  if (!on) {
    return (
      <>
        <span class="pk-off" data-ms-wording-off aria-disabled="true" title="Turn on Client visible to edit">{richWords(m.client_message || "").trim() || "Add client wording"}</span>
        <span class="muted pk-hint" data-ms-wording-hint> not shown to the client</span>
      </>
    );
  }
  return <RichField field="client_message" id={m.id} value={asHtml(m.client_message)} label="Client wording" empty="Add client wording" save={put} />;
}

// Item 1185, row 1184: the milestone's Latest update, the work item peek's box (PeekLatest.jsx LatestBox) above Details, with its history. One change, one Undo.
export function PeekMsLatest({ m }) {
  const put = (value) => save(m, { latest_update: value }, richWords(value).trim() ? `Latest update of ${m.id} saved.` : `Latest update of ${m.id} cleared.`);
  const shown = m.client_visible !== false && m.client_visible !== 0 && !leftOutIds(data.value).includes(m.id);
  return <LatestBox id={m.id} now={m.latest_update ? String(m.latest_update) : ""} stamp={stampText(m.updated_at)} shown={shown} save={put} placeholder="What changed? Add the latest update…" />;
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

// Row 1184: the popovers of the chips. Each is `({ anchor, close }) => element`; a pick is one change with one Undo (save) and closes the popover.
function StatePop({ m, anchor, close }) {
  const today = todayIso(), now = shownStateOf(m);
  const pick = (s) => {
    close(true);
    const c = stateChange(m, s, today);
    save(m, c, `State of ${m.id} changed to ${c.state || shownStateOf({ ...m, ...c })}.`);
  };
  return (
    <Pop anchor={anchor} label={`State of ${m.id}`} cls="pk-ms-pop" onClose={close}>
      <div class="pk-ms-states" role="group" aria-label={`State of ${m.id}`} data-ms-states>
        {ALL_STATES.map((s) => (
          <button type="button" key={s} class="pk-ms-state" data-ms-state={s} aria-pressed={now === s ? "true" : "false"} disabled={!PICKABLE.includes(s)} onClick={() => pick(s)}>
            <span class={`pkc-ic ${iconClass(STATE_LOOK[s][1])}`}><Icon name={STATE_LOOK[s][0]} /></span>{s}
          </button>
        ))}
      </div>
    </Pop>
  );
}

function OwnerPop({ m, anchor, close }) {
  const was = m.owner == null ? "" : String(m.owner);
  const pick = (v) => {
    const value = String(v).trim().toUpperCase() === "TBC" ? "" : v;
    close(true);
    const c = textChange("owner", was, value);
    if (c) save(m, c, said(m, "Owner", c.owner));
    return "";
  };
  return <OwnerPick row={{ id: m.id, kind: "action", owner: was }} anchor={anchor} names={people(data.value)} onPick={pick} onClose={close} />;
}

const BLOCKS = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100];
function ProgressPop({ m, anchor, close }) {
  const was = m.percent_complete == null ? null : m.percent_complete;
  const [hover, setHover] = useState(0);
  const pick = (n) => {
    close(true);
    const c = progressChange(was, String(n));
    if (c) save(m, c, said(m, "Progress", c.percent_complete, `${c.percent_complete}%`));
  };
  const upto = hover || (was == null ? 0 : was);
  return (
    <Pop anchor={anchor} label={`Progress of ${m.id}`} cls="pk-ms-pop" onClose={close}>
      <div class="pk-ms-blocks" role="group" aria-label={`Progress of ${m.id}`} data-ms-blocks onMouseLeave={() => setHover(0)}>
        {BLOCKS.map((n, i) => (
          <button type="button" key={n} class={`pk-ms-block${upto >= n ? " on" : ""}${hover && hover >= n ? " pv" : ""}`} data-ms-block={n} style={`--p:${Math.round(38 + i * 62 / 9)}%`}
            title={`${n}%`} aria-label={`${n} percent`} aria-pressed={was != null && was >= n ? "true" : "false"} onMouseEnter={() => setHover(n)} onFocus={() => setHover(n)} onBlur={() => setHover(0)} onClick={() => pick(n)} />
        ))}
      </div>
    </Pop>
  );
}

function ForecastPop({ m, anchor, close }) {
  const value = m.forecast_date || "", today = todayIso();
  const pick = async (day) => {
    close(true);
    const iso = day || null;
    if (iso === (value || null)) return;
    await save(m, { forecast_date: iso }, said(m, "Forecast date", iso, iso ? showDate(iso) : ""));
  };
  const quick = quickDates(today).concat(value ? [["No date", ""]] : []);
  return <DuePick row={{ id: m.id, kind: "action", due_date: value || null }} anchor={anchor} today={today} label={`Forecast date of ${m.id}`} quick={quick} onPick={pick} onClose={close} />;
}

const POPS = { state: StatePop, owner: OwnerPop, progress: ProgressPop, forecast: ForecastPop };
/** The chip popover of one field, for tools.PeekMsChipPop. */
export const msChipPop = (m, field) => (POPS[field] ? ({ anchor, close }) => { const P = POPS[field]; return <P m={m} anchor={anchor} close={close} />; } : null);

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
        aria-label={`Workstream of ${m.id}: ${value || DASH}. Change`} onClick={() => setOpen(!open)}>{value || "Add workstream"}</button>
      {open ? <MenuPick anchor={button} label={`Workstream of ${m.id}`} current={value} choices={choices} onPick={pick} onClose={close} /> : null}
    </>
  );
}

// The first use case that reaches the milestone and the ones linked straight to it (row 1107). The picker adds or removes ONE link through the use cases' own
// msadd and msremove (no change of the store): a pick links the use case picked and unlinks the one shown, None unlinks every direct link.
const ucName = (u) => `${u.ref ? u.ref + " " : ""}${u.title}`;
function UseCase({ m }) {
  const [open, setOpen] = useState(false);
  const button = useRef(null);
  const d = data.value || {};
  const shownUc = usecasesOfMilestone(d, m.id)[0] || null;
  const direct = new Set((d.uc_milestones || []).filter((l) => l.milestone === m.id).map((l) => l.use_case));
  const choices = (d.use_cases || []).filter((u) => !u.archived || (shownUc && u.id === shownUc.id)).map((u) => ({ value: u.id, text: ucName(u), ...fieldIcon("use_case") }))
    .concat([{ value: "", text: "No use case", ...fieldIcon("use_case", true) }]);
  const close = (back) => { setOpen(false); if (back && button.current) button.current.focus(); };
  const link = (op, ucId, words) => change({ kind: "use_cases", op, id: ucId, ids: [m.id], place: "peek" }, words);
  const pick = async (value) => {
    close(true);
    if (!value) {
      for (const id of direct) await link("msremove", id, `Use case of ${m.id} cleared.`);
      return;
    }
    if (shownUc && shownUc.id === value) return;
    const text = (choices.find((c) => c.value === value) || {}).text || "";
    if (!direct.has(value)) await link("msadd", value, `${m.id}: use case changed to ${((d.use_cases || []).find((u) => u.id === value) || {}).ref || text}.`);
    if (shownUc && shownUc.id !== value && direct.has(shownUc.id)) await link("msremove", shownUc.id, `Use case of ${m.id} cleared.`);
    await reread(project.value);
  };
  return (
    <>
      <button type="button" class="pk-pick" ref={button} data-ms-field="use_case" data-ms-ucs aria-haspopup="menu" aria-expanded={open ? "true" : "false"}
        aria-label={`Use case of ${m.id}: ${shownUc ? ucName(shownUc) : DASH}. Change`} onClick={() => setOpen(!open)}>{shownUc ? ucName(shownUc) : "Select use case"}</button>
      {open ? <MenuPick anchor={button} label={`Use case of ${m.id}`} current={shownUc ? shownUc.id : ""} choices={choices} onPick={pick} onClose={close} /> : null}
    </>
  );
}

// The Client visible line, as the other peeks' (PeekProps.jsx ClientLine): the eye, "Client visible" or "Client not visible"; one click is the page's own report_hidden step.
const isOn = (m) => !(!m.client_visible && m.client_visible !== undefined) && !leftOutIds(data.value).includes(m.id);
function MsClientLine({ m }) {
  const internal = !m.client_visible && m.client_visible !== undefined, on = isOn(m);
  return (
    <button type="button" class={`pk-client${on ? " on" : ""}`} data-pk-client data-ms-visible aria-pressed={on ? "true" : "false"} disabled={internal}
      onClick={() => setMsHidden(m.id, on, m.name).then(() => reread(project.value))}>
      <Icon name={on ? "eye" : "eyeoff"} />{on ? "Client visible" : "Client not visible"}
    </button>
  );
}

export function MilestoneEdit({ m }) {
  const on = isOn(m), state = shownStateOf(m);
  return (
    <PeekDetails summary={[m.workstream, on ? "Client visible" : "Client not visible"]}>
      <dl class="pk-fields" data-ms-edit>
        <Row name="Description" k="description" icon="doc"><Description m={m} /></Row>
        <Row name="Agreed date" k="baseline" icon="cal">{showDate(m.baseline_date)}<span class="muted pk-hint" data-pk-ms-hint> read only</span></Row>
        {state === "Achieved" ? <Row name="Achieved on" k="actual" icon="cal"><DateField m={m} field="actual_date" label="Achieved on" /></Row> : null}
        <Row name="Workstream" k="workstream" icon="board"><Workstream m={m} /></Row>
        <Row name="Use case" k="use_cases" icon="flag"><UseCase m={m} /></Row>
        <Row name="Client wording" k="client_message" icon="doc"><ClientWording m={m} on={on} /></Row>
        <div class="pk-row" data-pk-client-row data-ms-row="visible"><dd><MsClientLine m={m} /></dd></div>
      </dl>
    </PeekDetails>
  );
}
