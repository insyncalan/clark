// The peek (#42a): one work item's or milestone's fields beside the list. Read only on a Dashboard in View and in a published file: fields and
// the Source line (row 1077) and nothing else (no history, no words box, no /api/ text). `tools.Words`, `tools.PeekTabs` and
// `tools.PeekActivity` (Details and Activity, #42) are the editing part (every page but a Dashboard in View).
// The address holds which item is open (router.js, #63); Previous and Next replace that entry, Esc and Close go through
// closePeek(). The width is dragged from the left edge (keys too), double-click resets it.
// The arrow keys (#246, #289): Up and Down on one of its buttons step like Previous and Next, an arrow that moves the focus to
// another row or card moves the peek with it, and Esc puts the focus on the row of the item shown. Nothing else takes an arrow.
import { useCallback, useEffect, useLayoutEffect, useRef } from "preact/hooks";
import { signal } from "@preact/signals";
import { data, rows, peek, openPeek, closePeek, mode, fromFile, view } from "../stores/report.js";
import { isEditing } from "../logic/editing.js";
import { width, wide, setWidth, resetWidth, MIN, DEFAULT } from "../stores/peekState.js";
import { staleWords, notReviewed } from "../filters.js";
import { KIND_WORDS, dueCell, pillOf, ownerOf, showDate, todayIso, isOpen, colourOf } from "../workItems.js";
import { slideOut } from "../peek/exit.js";
import { closesPeek } from "../peek/outside.js";
import { itemIds, milestoneIds, around, placeIn } from "../peek/list.js";
import { holdScroll } from "../core/holdScroll.js";
import { Icon } from "./Icon.jsx";
import { classicTheme } from "./Contents.jsx";
import { wordsOpen, flashed, askFrom } from "../stores/wordsState.js";
import { singleKeys } from "../stores/keyPrefs.js";
import { statusTone, priorityTone, dateTone, iconClass } from "../iconColours.js";
import { stateOf, LOOK } from "../logic/milestones.js";
import { MsMark } from "./MsMark.jsx";
import { MsProgress } from "./MsList.jsx";
import { CleanProse } from "./CleanProse.jsx";
import { PeekToolbar } from "./PeekToolbar.jsx";
import { PeekIdLine } from "./PeekIdLine.jsx";
import { PeekChips, PeekChip } from "./PeekChips.jsx";
import { PeekDetails } from "./PeekDetails.jsx";
import { ActionChips } from "./PeekActionChips.jsx";
import { PeekActionBody } from "./PeekActionBody.jsx";
import { MilestoneChips } from "./PeekMilestoneChips.jsx";

// Up and Down while the peek is open (#246): the peek steps to the item before or after in the list it was opened from, the same list
// Previous and Next use. What it says after a step (a polite line only a screen reader hears) is kept here; `n` makes a repeat say it again.
const said = signal({ text: "", n: 0 });
const unsaved = signal(false);                          // row 1180: Close was pressed with an unsaved Latest update: the bar (Save and close, Discard, Keep editing) is shown
const say = (text) => { said.value = { text, n: said.value.n + 1 }; };

// Where the peek takes an arrow (#289): only Up and Down, only plain, only on one of its own buttons. A box, the width edge, a tab,
// a menu, a dialog, the words box, the activity list and the palette keep their arrows; so does the page's own scrolling, which is why a key aimed at nothing is left too.
// Row 1285: a decision's date chip names its date under the value, as the approved mock-up does ("needed by" while Pending, "made on" once Made, "was needed by" once Withdrawn); an overdue date keeps its own red "overdue N days".
const decisionDateWord = (row) => (!classicTheme() || row.kind !== "decision" ? "" : row.status === "Made" ? "made on" : row.status === "Withdrawn" ? "was needed by" : "needed by");
// Row 1285: whether the last thing the person did was a key press (a keyboard open keeps the ring on Close; a mouse open does not draw one).
let keyedLast = false;
if (typeof document !== "undefined") { document.addEventListener("keydown", () => { keyedLast = true; }, true); document.addEventListener("pointerdown", () => { keyedLast = false; }, true); }
const OWN = "[role=textbox],[role=combobox],[role=listbox],[role=menu],[role=dialog],[role=alertdialog],[role=tab],[role=separator],[role=toolbar]:not(.pk-tb),dialog,.wordsbox,.pk-activity";
function peekOwnsArrow(e) {
  if (e.key !== "ArrowUp" && e.key !== "ArrowDown") return false;
  if (e.shiftKey || e.metaKey || e.ctrlKey || e.altKey) return false;
  const t = e.target;
  if (!t || t.nodeType !== 1 || t.tagName !== "BUTTON" || !t.closest("#peek") || t.closest(OWN) || t.getAttribute("aria-haspopup")) return false;
  return !document.querySelector("[role=menu],[role=dialog],[role=alertdialog],dialog[open]");
}

// The row or card an element is in, as its item's id: the list the peek follows with the arrow keys.
const listItemOf = (el) => { const r = el && el.closest ? el.closest("#work tr[data-id], #work article[data-id]") : null; return r ? r.dataset.id : ""; };

const DASH = "—";
const text = (v) => (v === null || v === undefined || v === "" ? DASH : String(v));

// An icon in its tone's colour (#78), with the words after it: the colour is never the only way to tell what it means.
function Toned({ icon, tone, children }) { return <span class="pk-val"><span class={iconClass(tone)}><Icon name={icon} /></span>{children}</span>; }

const ROW_OF = { owner: "owner", made_by: "owner", due_date: "due", needed_by: "due", date: "due", priority: "priority", status: "status" };

function Row({ name, children, ref_, key_, ms, icon, tone = "b" }) {      // key_: which field this row shows, so it can flash when that field changes; ms: a milestone's row (row 1078), a plain row, never one of the four cells
  const f = flashed.value;
  const hit = !!(f && key_ && f.list.some((e) => e.ref === ref_ && ROW_OF[e.field] === key_));
  return <div class={`pk-row${hit ? " flash" : ""}`} data-row={key_ || undefined} data-ms-row={ms || undefined} data-flash={hit ? "1" : undefined}><dt>{icon ? <span class={`pk-rowic ${iconClass(tone)}`}><Icon name={icon} /></span> : null}{name}</dt><dd>{children}{hit ? <span class="tag chg">Changed</span> : null}</dd></div>;
}

// Row 1180: the four property cells are the chip row now (ItemChips). A flat row of chips: status, priority (a decision's from peek_priority), owner and due; each opens its popover in Edit.
function ItemChips({ row, tools, editing }) {
  const today = todayIso(), due = dueCell(row, today), pill = pillOf(row, today), who = ownerOf(row.owner), f = flashed.value;
  const hit = (key) => !!(f && f.list.some((e) => e.ref === row.id && ROW_OF[e.field] === key));
  const pop = (field) => (editing && tools && tools.PeekChipPop ? tools.PeekChipPop(row, field) : null) || undefined;
  const Live = editing && tools && tools.PeekChipLive ? tools.PeekChipLive : undefined;
  // item 448: a closed risk or issue's pill reads Closed; it keeps its rating word as the small line of the Status chip ("Red kept"; "Not rated" when it never was, item 532), here and in a published file.
  const kept = (row.kind === "risk" || row.kind === "issue") && !isOpen(row) ? colourOf(row.priority).word : "";
  const late = due.tone === "late", days = late ? /^(\d+) days? late$/.exec(due.words) : null;
  const overdue = late ? `overdue ${days ? days[1] : "1"} ${days && days[1] !== "1" ? "days" : "day"}` : "";
  const prio = row.kind === "decision" ? row.peek_priority : row.priority;      // row 1195: a decision's priority is peek_priority
  // row 1182: an open risk or issue's chip face is its colour word with the level as a small pill ("Red" + "High"), as in the design image; the icon takes the colour word's own tone (row 1257: Red, Amber, Green, as in the design image).
  const rated = (row.kind === "risk" || row.kind === "issue") && isOpen(row) && !!prio;
  // row 1256: an open risk or issue's Status chip says Open (as Closed and Cancelled say theirs); its colour is on the Rating chip.
  const openRI = (row.kind === "risk" || row.kind === "issue") && isOpen(row);
  const fixed = row.kind === "assumption" || row.kind === "dependency";
  return (
    <PeekChips>
      <PeekChip Live={Live} id={row.id} field="status" name="Status" icon="half" tone={openRI ? "b" : statusTone(row, today)} value={openRI ? "Open" : pill.text} sub={kept ? `${kept} kept` : ""} subTone={kept ? "kept" : ""} flash={hit("status")} pop={pop("status")} />
      <PeekChip Live={Live} id={row.id} field="priority" name={(row.kind === "risk" || row.kind === "issue") ? "Rating" : "Priority"} icon="bars" tone={rated ? colourOf(prio).class : priorityTone(prio)} value={rated ? colourOf(prio).word : text(prio)} sub={rated ? text(prio) : ""} subTone={rated ? `lvl ${colourOf(prio).class}` : ""}
        flash={hit("priority")} tip={fixed ? "Set from impact and likelihood" : row.kind === "risk" || row.kind === "issue" ? "Priority from impact and likelihood" : undefined} pop={pop("priority")} />
      <PeekChip Live={Live} id={row.id} field="owner" name={row.kind === "decision" ? "Decider" : "Owner"} icon="user" tone="b" value={who.text} sub={classicTheme() && row.kind === "decision" ? "made by" : ""} subTone={classicTheme() && row.kind === "decision" ? "word" : ""} flash={hit("owner")} pop={pop("owner")} />
      <PeekChip Live={Live} id={row.id} field="due" name={row.kind !== "decision" ? "Due date" : row.status === "Pending" ? "Needed-by date" : "Decision date"} icon="cal" tone={dateTone(row, today)} value={due.date}
        sub={overdue || decisionDateWord(row)} subTone={late ? "late" : decisionDateWord(row) ? "word" : ""} late={late} flash={hit("due")} pop={pop("due")} />
    </PeekChips>
  );
}

// ItemFields and Edge are also the archived peek's (ArchivedItems.jsx in the Edit part, item 450 row 39; reached with is:archived, item 1067): the same rows, read only.
// `slim` (row 1180, the live peek): the Type row and the four cells are the chip row above and the project is in the ID line, so they are not repeated; the rest sits in the collapsible Details.
export function ItemFields({ row, editing, Cell, Wording, Pick, slim = false, ClientLine = null, clientName }) {
  const today = todayIso(), due = dueCell(row, today), pill = pillOf(row, today), who = ownerOf(row.owner);
  // #448: a closed risk or issue's pill reads Closed; it keeps its rating word beside it (the prototype's "Closed · Amber"; "Not rated" when it never was, #532), here and in a published file.
  const kept = (row.kind === "risk" || row.kind === "issue") && !isOpen(row) ? colourOf(row.priority).word : "";
  const raised = typeof row.not_reviewed === "boolean" ? row.raised : row.raised_on;
  const rows = (
    <dl class="pk-fields">
      {slim ? null : <Row name="Type">{KIND_WORDS[row.kind] || row.kind}</Row>}
      {slim ? null : <>
      <Row key_="owner" ref_={row.id} name={row.kind === "decision" ? "Made by" : "Owner"}>{who.text}</Row>
      <Row key_="due" ref_={row.id} name={row.kind === "decision" && row.status === "Pending" ? "Needed by" : row.kind === "decision" ? "Made on" : "Due"}>
        <Toned icon="cal" tone={dateTone(row, today)}>{due.date}</Toned>{due.words ? <span class={`due-l${due.tone ? " " + due.tone : ""}`}> {due.words}</span> : null}
      </Row>
      {row.kind === "issue" ? <Row key_="priority" ref_={row.id} name="Rating"><Toned icon="bars" tone={priorityTone(row.priority)}>{colourOf(row.priority).word}{row.priority ? ` · ${row.priority}` : ""}</Toned></Row>      /* row 1183: an issue's Priority row is its Rating: the colour word and the level word */
        : <Row key_="priority" ref_={row.id} name="Priority"><Toned icon="bars" tone={priorityTone(row.kind === "decision" ? row.peek_priority : row.priority)}>{text(row.kind === "decision" ? row.peek_priority : row.priority)}</Toned></Row>}
      <Row key_="status" ref_={row.id} name="Status"><Toned icon="half" tone={statusTone(row, today)}>
        {Cell ? <Cell row={row} field="status" said={pill.text} place="peek"><span class={`pill ${pill.class}`}>{pill.text}</span></Cell> : <span class={`pill ${pill.class}`}>{pill.text}</span>}
        {kept ? <span class="pk-rating" data-pk-rating>{row.kind === "issue" ? ` ${kept} kept` : ` · ${kept}`}</span> : null}      {/* row 1183: a closed issue says "Red kept" under its Closed pill (the Risk ticket's sub-line) */}
      </Toned></Row>
      </>}
      {row.kind !== "decision" ? <Row name="Workstream" icon={slim ? "board" : undefined}>{Pick ? <Pick row={row} field="workstream" /> : text(row.workstream)}</Row> : null}      {/* row 1195: a decision has no workstream or milestone */}
      {row.kind !== "decision" ? <Row name="Milestone" icon={slim ? "flag" : undefined}>{Pick ? <Pick row={row} field="milestone" /> : text(row.milestone)}</Row> : null}
      {row.kind === "decision" ? <>
        {editing ? <Row name="Reasoning" ms="reasoning">{text(row.reasoning)}</Row> : null}      {/* a published file carries neither the reasoning nor the options (publish.PUBLISH_FIELDS) */}
        {editing ? <Row name="Options considered" ms="options">{text(row.options)}</Row> : null}
        <Row name="Revisit" ms="revisit">{editing && classicTheme() && !row.revisit ? <span class="muted" data-pk-prompt>Add when to look at this again.</span> : text(row.revisit)}</Row>      {/* row 1285: in Edit an empty Revisit says what to add; the view keeps the dash */}
        <Row name="Replaces" ms="replaces">{editing && classicTheme() && !row.replaces ? <span class="muted" data-pk-prompt>Add the decision this replaces.</span> : text(row.replaces)}</Row>
      </> : null}
      <Row name="Use case" icon={slim ? "flag" : undefined}>{Pick ? <Pick row={row} field="use_case" /> : text(row.uc)}</Row>
      {editing ? (slim && ClientLine ? <div class="pk-row" data-pk-client-row><dd><ClientLine row={row} /></dd></div> : <Row name={(clientName && clientName(row)) || "Shown to client"}>{row.client ? "Yes" : "No"}</Row>) : null}
      {Wording ? <Row name="Client wording" icon={slim ? "doc" : undefined}><Wording row={row} /></Row> : null}
      {!editing && fromFile.value && row.client_message ? <Row name="Client wording" ms="client_message">{row.client_message}</Row> : null}      {/* item 1111: a published file's peek draws the client wording the file carries, read only and only when there is some */}
      {!editing && fromFile.value && row.latest_update ? <Row name="Latest update" ms="latest_update"><Rich html={String(row.latest_update)} /></Row> : null}      {/* the file's latest update is already clean (publish.clean_html); no history, no editing */}
      {typeof row.not_reviewed === "boolean" ? <>
        <Row name="Raised">{showDate(row.raised)}</Row>
        <Row name="Last reviewed" icon={slim ? "clock" : undefined}>{row.last_reviewed ? showDate(row.last_reviewed) : "Not yet"}</Row>
      </> : row.raised_on ? <Row name="Raised">{showDate(row.raised_on)}</Row> : null}      {/* row 1077: a published file carries no history (no freshness, no Last reviewed) but it carries the date raised, so a client's peek keeps that row */}
    </dl>
  );
  if (!slim) return rows;
  const summary = [row.kind === "decision" ? "" : row.workstream, row.kind === "decision" ? "" : row.milestone, raised ? `Raised ${showDate(raised)}` : "", editing ? (row.client ? "Client visible" : "Client not visible") : ""];
  return <PeekDetails summary={summary}>{rows}</PeekDetails>;
}

// The read-only Source line under the fields (row 1077, the owner's ruling): where the item or milestone came from, by name. On the live page
// the Edit part reads it (tools.PeekSource, GET /api/activity, with " by <name>"); a published file draws the name its data carries (publish.select).
// The text is drawn as text; nothing is drawn when there is none.
export function SourceLine({ text }) {
  return text ? <p class="pk-source muted" data-pk-source><span class="pk-source-l">Source</span>{": "}<span>{text}</span></p> : null;
}

// Row 1078 (the owner's rulings): the milestone peek in the work item peek's format. Under the title, one flat line says the state, the
// owner and the progress; then the rows, label left and value right. The same line and rows on every peek: the editor's (MilestonePeek.jsx
// puts its controls in the same places) and a client's (the Dashboard in View, a published file), read only.
// The state: a published file carries the state it worked out and the client's word for it (publish.select); the live page works it out
// here (logic/milestones.js, as the Milestones list does). Achieved only once the milestone is achieved, with its date in View but not in Edit (the Achieved on row has it).
// The editor's peek passes dated={false}: its Achieved on row carries the date, so the date is shown once (the client's peek has no such row, so its chip keeps it).
export function MsState({ m, dated = true }) {
  const state = fromFile.value && m.state ? m.state : stateOf(m, todayIso());
  const look = LOOK[state] || LOOK.Forecast;
  const word = dated && m.status === "Done" && m.actual_date ? `Achieved on ${showDate(m.actual_date)}` : (fromFile.value && m.state_word) || state;
  return <span class={`mst c-${look[0]}`} data-ms-head="state"><MsMark name={look[1]} />{word}</span>;
}
export const MsSep = () => <span class="pk-ms-sep" aria-hidden="true">·</span>;
export function MsHead({ children }) { return <p class="pk-ms-head" data-ms-head>{children}</p>; }

// Rich words (the description, the client wording: item 1005, row 1078) as the editor shows them: cleanHtml of what is stored, through the one audited seam.
// A published file's words are already clean (publish.clean_html wrote them); the live page's come through tools.richOf (the editing index: richOrPlain,
// the cleaner), so the cleaner is never in the published bundle (tests: "the cleaner is not in a published file").
const richOf = (tools, value) => (fromFile.value ? String(value || "") : tools && tools.richOf ? tools.richOf(value) : "");
const Rich = ({ html }) => (html ? <CleanProse html={html} cls="prose pk-rich" /> : DASH);

function MilestoneFields({ m, tools }) {
  const who = ownerOf(m.owner), description = richOf(tools, m.description), wording = richOf(tools, m.client_message), latest = fromFile.value ? richOf(tools, m.latest_update) : "";
  return (
    <>
      <MsHead>
        <MsState m={m} /><MsSep />
        {who.text === DASH ? null : <><span class="pk-ms-owner" data-ms-head="owner">{who.initials ? <span class="av" aria-hidden="true">{who.initials}</span> : null}{who.text}</span><MsSep /></>}
        <span class="msl-prog" data-ms-head="progress"><MsProgress value={m.status === "Done" && m.percent_complete == null ? 100 : m.percent_complete} /></span>
      </MsHead>
      <PeekDetails summary={[m.workstream, m.forecast_date ? `Forecast ${showDate(m.forecast_date)}` : ""]}>
      <dl class="pk-fields" data-ms-fields>
        {description || !fromFile.value ? <Row name="Description" ms="description"><Rich html={description} /></Row> : null}      {/* row 560: a file carries no description for a milestone with no client wording, so a client's peek has no such row */}
        <Row name="Agreed date" ms="baseline">{showDate(m.baseline_date)}</Row>
        <Row name="Forecast date" ms="forecast">{showDate(m.forecast_date)}</Row>
        <Row name="Workstream" ms="workstream">{text(m.workstream)}</Row>
        {wording || !fromFile.value ? <Row name="Client wording" ms="client_message"><Rich html={wording} /></Row> : null}      {/* a client's peek has no empty wording row, as it has no empty description row; the editor's peek keeps both */}
        {latest ? <Row name="Latest update" ms="latest_update"><Rich html={latest} /></Row> : null}      {/* item 1185: a published file's milestone shows its latest update when it carries one (the live editor's peek has its own box) */}
      </dl>
      </PeekDetails>
    </>
  );
}

// The edge you drag. Keys work too: Left widens, Right narrows, Home resets. Double-click resets.
export function Edge() {
  const start = useRef(null);
  const down = (e) => { start.current = true; try { e.currentTarget.setPointerCapture(e.pointerId); } catch (err) { /* no capture: the move still follows */ } e.preventDefault(); };
  const move = (e) => { if (start.current) setWidth(document.documentElement.clientWidth - e.clientX); };
  const up = () => { start.current = null; };
  const key = (e) => {
    const step = e.shiftKey ? 80 : 20;
    if (e.key === "ArrowLeft") setWidth(width.value + step); else if (e.key === "ArrowRight") setWidth(width.value - step);
    else if (e.key === "Home") resetWidth(); else return;
    e.preventDefault();
  };
  return <div class="pk-edge" role="separator" aria-orientation="vertical" aria-label="Peek width" aria-valuemin={MIN} aria-valuenow={width.value}
    tabIndex={0} onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up} onDblClick={resetWidth} onKeyDown={key} />;
}

export function Peek({ tools }) {
  const p = peek.value;
  const box = useRef(null), back = useRef(null), pending = useRef(""), pendingKind = useRef("item"), opened = useRef(""), shown = useRef(""), stepped = useRef(false);
  const lastBox = useRef(null), keep = useCallback((n) => { box.current = n; if (n) { lastBox.current = n; holdScroll(n, { keys: false }); } }, []);
  const editing = !!tools && !fromFile.value && isEditing();      // every page but a Dashboard in View (row 824)
  const dashView = !!tools && !fromFile.value && classicTheme();      // row 1470: the Latest update box is drawn on a Dashboard peek in View too (Classic; a published file stays read only)
  const msEditing = !!tools && !!tools.MilestoneEdit && !fromFile.value && (mode.value === "edit" || view.value === "milestones");     // row 828: the milestone's own fields are editable on the Milestones page with no View mode, and in Edit elsewhere
  // The words box changes a work item or a milestone; a use case has no peek (its own page, UseCaseDetail, has the box). The warning bar and Latest update are an item's only.
  const forItem = !!p && p.kind !== "milestone";
  const Words = editing && !!p && tools.Words;
  const History = editing && tools.PeekHistory;      // row 1180: the history tabs (All, Activity, Updates, Source) under the body
  const MsTitle = msEditing && tools.PeekMilestoneTitle, MsLatest = (msEditing || dashView) && tools.PeekMsLatest;     // row 1078: the milestone's name is its title, changed in place (row 1180: a textarea, as the work item's)
  const TitleBox = editing && forItem && tools.PeekItemTitle, MoreBtn = editing && forItem && tools.PeekMore, MsMoreBtn = msEditing && tools.RecordMore;      // row 1180: More holds Duplicate, Archive and Delete (item 1148: a milestone's holds Archive and Delete)
  const Warn = editing && forItem && tools.PeekWarn, Latest = (editing || dashView) && forItem && tools.PeekLatest;      // the warning bar and Latest update (peek, Edit only)
  // Row 1077 (the owner's ruling): every peek, item or milestone, shows its Source, in Edit and in View alike. On the live page the Edit part
  // reads it from the server (tools.PeekSource); a published file (no tools, fromFile) draws the name its own data carries (FileSource below).
  const Source = !!tools && !fromFile.value && tools.PeekSource;
  const FileSource = fromFile.value;
  if (p) shown.current = p.id;                            // kept after the peek closes, for the focus it returns
  // Focus goes in when the peek opens and back to where it was when it closes: to the row (or card) of the item the peek shows then,
  // which after Up, Down, Previous or Next is not the one it opened on (#246).
  // A layout effect: the focus is taken and given back in the step that draws and removes the peek, not a frame later (frames arrive late on a busy runner).
  useLayoutEffect(() => {
    if (!p) return undefined;
    back.current = document.activeElement;
    opened.current = p.id;
    said.value = { text: "", n: 0 };
    const close = box.current && box.current.querySelector("[data-pk-close]");
    if (close) {
      close.focus({ preventScroll: true });      // row 1467: taking the focus never scrolls the page behind
      // Row 1285: Close takes the focus when a peek opens; with no key pressed (a click, a script) it shows no focus ring until a key is pressed or the focus moves on.
      if (classicTheme() && !keyedLast) {
        close.setAttribute("data-quiet", "");
        const off = () => { close.removeAttribute("data-quiet"); close.removeEventListener("blur", off); document.removeEventListener("keydown", off, true); };
        close.addEventListener("blur", off); document.addEventListener("keydown", off, true);
      }
    }
    return () => {
      wordsOpen.value = false;
      unsaved.value = false;
      let el = back.current;
      back.current = null;
      if (shown.current && shown.current !== opened.current) {                     // the peek moved on: the row it shows now, if it is drawn
        const sel = `#work tr[data-id="${CSS.escape(shown.current)}"], #work article[data-id="${CSS.escape(shown.current)}"] .bc-main`;
        const now = document.querySelector(sel);
        if (now) el = now;
      }
      const now = document.activeElement;                                          // a click on another row (a Shift click that closes the peek) has put the focus there already: leave it
      const elsewhere = now && now !== document.body && now.isConnected && !now.closest("#peek");
      if (!elsewhere && el && el.isConnected && el.focus) el.focus();
    };
  }, [!!p]);                                              // eslint-disable-line react-hooks/exhaustive-deps
  // Row 1467 P5: a switch to another item says the new one to a screen reader: its id and title, no other words (a step says its own place instead).
  const sawId = useRef("");
  useEffect(() => { const id = p ? p.id : ""; const was = sawId.current; sawId.current = id; if (id && was && was !== id && !stepped.current) { const t = p.kind === "milestone" ? ((data.value.milestones || []).find((x) => x.id === id) || {}).name : (rows.value.find((r) => r.id === id) || {}).title; say(`${id}: ${t || ""}`); } }, [p && p.id]);   // eslint-disable-line react-hooks/exhaustive-deps
  // After a step the focus is never left on a button that has just turned off (Next at the last item) or on the page: it goes to Close.
  useEffect(() => {
    if (!p || !stepped.current) return;
    stepped.current = false;
    const a = document.activeElement, close = box.current && box.current.querySelector("[data-pk-close]");
    if (close && (!a || a === document.body || (a.disabled && box.current.contains(a)))) close.focus({ preventScroll: true });
  }, [p && p.id]);                                        // eslint-disable-line react-hooks/exhaustive-deps
  // The peek follows the list's cursor: an arrow key that moves the focus to another row or card shows that item (the row's own key
  // handler moves the cursor; this only watches where the focus lands, so a Tab or a click away never moves the peek).
  useEffect(() => {
    if (!p || p.kind === "milestone") return undefined;
    let arrow = false;
    const down = (e) => {
      // only an arrow aimed at a row or card counts: a held key on a button in a row, or in the peek, never moves the peek
      arrow = (e.key === "ArrowUp" || e.key === "ArrowDown" || e.key === "ArrowLeft" || e.key === "ArrowRight") && !e.shiftKey && !e.metaKey && !e.ctrlKey && !e.altKey && !!listItemOf(e.target);
    };
    const off = () => { arrow = false; };               // the key coming up, or a click, ends the arrow: no timer
    const into = (e) => {
      const id = arrow ? listItemOf(e.target) : "";
      if (id && id !== shown.current) openPeek(id, "item");
    };
    document.addEventListener("keydown", down, true);
    document.addEventListener("keyup", off, true);
    document.addEventListener("pointerdown", off, true);
    document.addEventListener("focusin", into);
    return () => {
      document.removeEventListener("keydown", down, true); document.removeEventListener("keyup", off, true);
      document.removeEventListener("pointerdown", off, true); document.removeEventListener("focusin", into);
    };
  }, [!!p, p && p.kind]);                                 // eslint-disable-line react-hooks/exhaustive-deps
  // Esc closes the words box first, then the peek; two slashes outside a field open the words box (Edit only). Up and Down on one of the
  // peek's own buttons step to the item before or after (#246); every other arrow is left to whatever it was aimed at (#289).
  // Closing with an unsaved Latest update shows the bar (Save and close, Discard, Keep editing) instead of closing (row 1180).
  const askClose = () => { pending.current = ""; if (tools && tools.peekDirty && tools.peekDirty()) unsaved.value = true; else closePeek(); };
  const stepBy = (dir) => {
    const q = peek.value;                                 // the peek now, not the one this handler was made for: a second key can come before the redraw
    if (!q) return;
    const ms = q.kind === "milestone", ids = ms ? milestoneIds() : itemIds(), here = placeIn(ids, q.id);
    if (here.at < 0) { say(`${q.id} is not in the list now, so Up and Down cannot step from it. Clear the filter or choose a row.`); return; }
    const to = ids[here.at + dir];
    if (!to) { say(`${q.id}, ${here.at + 1} of ${ids.length}, the ${dir < 0 ? "first" : "last"} one`); return; }
    stepped.current = true;
    openPeek(to, q.kind);
    say(`${to}, ${here.at + dir + 1} of ${ids.length}`);
  };
  useEffect(() => {
    if (!p) return undefined;
    let last = 0;
    const onKey = (e) => {
      if (e.defaultPrevented || e.isComposing) return;
      if (e.key === "Escape") {
        if (document.querySelector("[role=menu]")) return;
        e.preventDefault();
        if (wordsOpen.value) wordsOpen.value = false; else askClose();
        return;
      }
      if (peekOwnsArrow(e)) { e.preventDefault(); stepBy(e.key === "ArrowUp" ? -1 : 1); return; }
      const t = e.target, inField = t && t.nodeType === 1 && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName));
      if (e.key === "/" && singleKeys.value && !e.metaKey && !e.ctrlKey && !e.altKey && !inField && Words) {
        if (last && performance.now() - last < 1000) { e.preventDefault(); last = 0; wordsOpen.value = true; }
        else { last = performance.now() || 1; const ask = document.querySelector("#peek [data-pk-ask]"); if (ask) { e.preventDefault(); askFrom.el = document.activeElement; ask.focus(); } }      // the first "/" puts the cursor in the footer input
      } else if (e.key !== "Shift") last = 0;
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [p && p.id, !!Words]);                               // eslint-disable-line react-hooks/exhaustive-deps
  // A click outside closes the peek (row 814): the press and the click must both be outside, so a drag that ends outside keeps it.
  useEffect(() => {
    if (!p) return undefined;
    let down = false;
    const press = (e) => { down = closesPeek(e.target); };
    const click = (e) => { const was = down; down = false; if (was && closesPeek(e.target)) askClose(); };
    // A mouse press on Close keeps the focus in the open editor: taking it would save the update before the bar can ask.
    const hold = (e) => { if (e.target.closest && e.target.closest("[data-pk-close]")) e.preventDefault(); };
    // Row 1467: a click on another item's row switches the peek. With an unsaved Latest update in the open peek the click asks first, as Close does
    // (the bar: Save and close, Discard, Keep editing); the press keeps the focus in the editor so that leaving it does not save the update unasked.
    // Three kinds of opener: a work item's row or card, a milestone's row (or its name link), a use case page's step or work item. Each gives the id and the kind to switch to.
    const opener = (t) => {
      if (!t || !t.closest || t.closest("#peek")) return null;
      const w = t.closest("#work tr[data-id], #work article[data-id], .wl-row[data-id], .wil-table tr[data-id]");
      if (w) return { id: w.dataset.id, kind: "item" };
      const m = t.closest(".msl-row[data-ms], [data-ms-open]");
      if (m) return { id: m.dataset.ms || m.dataset.msOpen, kind: "milestone" };
      const u = t.closest("[data-item], [data-stepid], li[data-step]");
      const id = u && (u.dataset.item || u.dataset.stepid || (u.querySelector("[data-stepid]") || {}).dataset?.stepid);
      return id ? { id, kind: "item" } : null;
    };
    const dirty = () => !!(tools && tools.peekDirty && tools.peekDirty());
    const keepFocus = (e) => { if (opener(e.target) && dirty()) e.preventDefault(); };
    const ask = (e) => {
      const row = opener(e.target);
      if (!row || !dirty()) return;
      e.stopPropagation(); e.preventDefault();
      pending.current = row.id; pendingKind.current = row.kind; unsaved.value = true;
    };
    document.addEventListener("pointerdown", press, true);
    document.addEventListener("mousedown", hold, true);
    document.addEventListener("mousedown", keepFocus, true);
    document.addEventListener("click", ask, true);
    document.addEventListener("click", click);
    return () => { document.removeEventListener("pointerdown", press, true); document.removeEventListener("mousedown", hold, true); document.removeEventListener("mousedown", keepFocus, true); document.removeEventListener("click", ask, true); document.removeEventListener("click", click); };
  }, [!!p]);                                              // eslint-disable-line react-hooks/exhaustive-deps
  // Closed: the panel slides out. Its node is kept as it mounts and the copy is made in a layout effect, not while rendering.
  useLayoutEffect(() => {
    if (!p && lastBox.current) { slideOut(lastBox.current, true); lastBox.current = null; }
  }, [!p]);                                               // eslint-disable-line react-hooks/exhaustive-deps
  if (p && (!data.value)) lastBox.current = null;
  if (!p || !data.value) return null;
  const milestone = p.kind === "milestone";
  const row = milestone ? null : rows.value.find((r) => r.id === p.id);
  const m = milestone ? (data.value.milestones || []).find((x) => x.id === p.id) : null;
  if (!row && !m) { lastBox.current = null; return null; }
  const near = around(milestone ? milestoneIds() : itemIds(), p.id);
  const go = (id) => id && openPeek(id, p.kind);
  const title = row ? row.title : m.name;
  return (
    <aside class={`peek${wide.value ? " wide" : ""}`} id="peek" ref={keep} aria-label={`${p.id} details`} style={wide.value ? "" : `width:${Math.min(width.value, document.documentElement.clientWidth)}px`} data-peek={p.id} data-sized={width.value !== DEFAULT ? "" : undefined}>
      <Edge />
      <PeekToolbar near={near} go={go} wide={wide.value} onWide={() => { wide.value = !wide.value; }} onClose={askClose}
        draft={editing && row && tools.peekDraft ? tools.peekDraft(row) : null} onCopy={editing && row && tools.copyLinkFor ? () => tools.copyLinkFor(row) : null}
        more={MoreBtn && row ? <MoreBtn row={row} /> : MsMoreBtn && m ? <MsMoreBtn row={m} kind="milestones" place="peek" cls="pkp-btn" id="pk-more" fixed={false} /> : null} />
      {unsaved.value && tools && tools.PeekUnsavedBar ? <tools.PeekUnsavedBar onClose={() => { const to = pending.current; pending.current = ""; if (to) openPeek(to, pendingKind.current); else closePeek(); }} onDone={() => { unsaved.value = false; }} /> : null}
      {Warn && row ? <Warn key={`w-${row.id}`} row={row} /> : null}
      <PeekIdLine id={p.id} />
      <p class="sr-only" role="status" aria-live="polite" data-pk-live>{said.value.text}</p>
      <h2 class="pk-title" tabIndex={-1}>{TitleBox && row ? <><TitleBox key={row.id} row={row} /></> : MsTitle && m ? <><MsTitle key={m.id} m={m} /></> : title}</h2>
      {row && typeof row.not_reviewed === "boolean" && notReviewed(row, todayIso()) ? <p class="pk-stale"><span class="pk-chip" data-stale>{staleWords(row.review_days || undefined)}</span></p> : null}
      {row && row.kind === "action" ? <ActionChips row={row} tools={tools} editing={editing} /> : row ? <ItemChips row={row} tools={tools} editing={editing} /> : m && msEditing ? <MilestoneChips m={m} tools={tools} editing /> : null}      {/* row 1184: the editor's milestone peek has the chip row; View and a published file keep the header line (MsHead) as before */}
      <div class="pk-body" key={p.id} data-pk-body>      {/* a new key each step: the body fades in as Previous or Next moves on */}
      <div>
          {Latest && row ? <Latest key={row.id} row={row} /> : MsLatest && m ? <MsLatest key={m.id} m={m} /> : null}      {/* item 1181: the Latest update sits above the Details */}
          {row && (row.kind === "action" || row.kind === "risk" || row.kind === "issue") ? <>      {/* row 1256: a risk's and an issue's Details are drawn like an action's */}
            {!editing && fromFile.value && (row.client_message || row.latest_update) ? <dl class="pk-fields" data-pk-file-rows>
              {row.latest_update ? <Row name="Latest update" ms="latest_update"><Rich html={String(row.latest_update)} /></Row> : null}
              {row.client_message ? <Row name="Client wording" ms="client_message">{row.client_message}</Row> : null}
            </dl> : null}
            <PeekActionBody row={row} editing={editing} Pick={editing && tools.PeekPick ? tools.PeekPick : null} ClientLine={editing && tools.PeekClientLine ? tools.PeekClientLine : null} onFile={fromFile.value} />
          </> : row ? <ItemFields row={row} editing={editing} slim clientName={editing && tools.clientRowName ? tools.clientRowName : null} ClientLine={editing && tools.PeekClientLine ? tools.PeekClientLine : null} Cell={null} Wording={editing && tools.PeekWording ? tools.PeekWording : null} Pick={editing && tools.PeekPick ? tools.PeekPick : null} /> : msEditing ? <tools.MilestoneEdit m={m} /> : <MilestoneFields m={m} tools={tools} />}
          {Source && !History ? <Source key={`s-${p.id}`} row={row || m} /> : FileSource ? <SourceLine text={(row || m).source} /> : null}      {/* with the history tabs the source is its own tab */}
        </div>
      {History && (row || m) ? <History key={p.id} id={p.id} /> : null}
      {Words && wordsOpen.value && (row || m) ? <Words key={p.id} row={row || m} kind={milestone ? "milestone" : "item"} /> : null}
      </div>
      {Words && (row || m) && tools.PeekFooter && !wordsOpen.value ? <tools.PeekFooter onAsk={() => { wordsOpen.value = true; }} /> : null}
    </aside>
  );
}
