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
import { width, wide, setWidth, resetWidth, MIN, peekTab } from "../stores/peekState.js";
import { staleWords, notReviewed } from "../filters.js";
import { KIND_WORDS, dueCell, pillOf, ownerOf, showDate, todayIso, isOpen, colourOf } from "../workItems.js";
import { slideOut } from "../peek/exit.js";
import { closesPeek } from "../peek/outside.js";
import { itemIds, milestoneIds, around, placeIn } from "../peek/list.js";
import { Icon } from "./Icon.jsx";
import { wordsOpen, flashed } from "../stores/wordsState.js";
import { statusTone, priorityTone, dateTone, iconClass } from "../iconColours.js";
import { stateOf, LOOK } from "../logic/milestones.js";
import { MsMark } from "./MsMark.jsx";
import { MsProgress } from "./MsList.jsx";
import { CleanProse } from "./CleanProse.jsx";

// Up and Down while the peek is open (#246): the peek steps to the item before or after in the list it was opened from, the same list
// Previous and Next use. What it says after a step (a polite line only a screen reader hears) is kept here; `n` makes a repeat say it again.
const said = signal({ text: "", n: 0 });
const say = (text) => { said.value = { text, n: said.value.n + 1 }; };

// Where the peek takes an arrow (#289): only Up and Down, only plain, only on one of its own buttons. A box, the width edge, a tab,
// a menu, a dialog, the words box, the activity list and the palette keep their arrows; so does the page's own scrolling, which is why a key aimed at nothing is left too.
const OWN = "[role=textbox],[role=combobox],[role=listbox],[role=menu],[role=dialog],[role=alertdialog],[role=tab],[role=separator],dialog,.wordsbox,.pk-activity";
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

function Row({ name, children, ref_, key_, ms }) {      // key_: which field this row shows, so it can flash when that field changes; ms: a milestone's row (row 1078), a plain row, never one of the four cells
  const f = flashed.value;
  const hit = !!(f && key_ && f.list.some((e) => e.ref === ref_ && ROW_OF[e.field] === key_));
  return <div class={`pk-row${hit ? " flash" : ""}`} data-row={key_ || undefined} data-ms-row={ms || undefined} data-flash={hit ? "1" : undefined}><dt>{name}</dt><dd>{children}{hit ? <span class="tag chg">Changed</span> : null}</dd></div>;
}

// ItemFields and Edge are also the archived peek's (ArchivedItems.jsx in the Edit part, item 450 row 39; reached with is:archived, item 1067): the same rows, read only.
export function ItemFields({ row, editing, Cell, Wording, Pick }) {
  const today = todayIso(), due = dueCell(row, today), pill = pillOf(row, today), who = ownerOf(row.owner);
  // #448: a closed risk or issue's pill reads Closed; it keeps its rating word beside it (the prototype's "Closed · Amber"; "Not rated" when it never was, #532), here and in a published file.
  const kept = (row.kind === "risk" || row.kind === "issue") && !isOpen(row) ? colourOf(row.priority).word : "";
  return (
    <dl class="pk-fields">
      <Row name="Type">{KIND_WORDS[row.kind] || row.kind}</Row>
      <Row key_="owner" ref_={row.id} name={row.kind === "decision" ? "Decision by" : "Owner"}>{who.text}</Row>
      <Row key_="due" ref_={row.id} name={row.kind === "decision" && row.status === "Pending" ? "Needed by" : row.kind === "decision" ? "Date" : "Due"}>
        <Toned icon="cal" tone={dateTone(row, today)}>{due.date}</Toned>{due.words ? <span class={`due-l${due.tone ? " " + due.tone : ""}`}> {due.words}</span> : null}
      </Row>
      {row.kind !== "decision" ? <Row key_="priority" ref_={row.id} name="Priority"><Toned icon="bars" tone={priorityTone(row.priority)}>{text(row.priority)}</Toned></Row> : null}
      <Row key_="status" ref_={row.id} name="Status"><Toned icon="half" tone={statusTone(row, today)}>
        {Cell ? <Cell row={row} field="status" said={pill.text} place="peek"><span class={`pill ${pill.class}`}>{pill.text}</span></Cell> : <span class={`pill ${pill.class}`}>{pill.text}</span>}
        {kept ? <span class="pk-rating" data-pk-rating> · {kept}</span> : null}
      </Toned></Row>
      <Row name="Workstream">{Pick && row.kind !== "decision" ? <Pick row={row} field="workstream" /> : text(row.workstream)}</Row>
      <Row name="Milestone">{Pick && row.kind !== "decision" ? <Pick row={row} field="milestone" /> : text(row.milestone)}</Row>
      <Row name="Use case">{Pick ? <Pick row={row} field="use_case" /> : text(row.uc)}</Row>
      {editing ? <Row name="Shown to client">{row.client ? "Yes" : "No"}</Row> : null}
      {Wording ? <Row name="Client wording"><Wording row={row} /></Row> : null}
      {!editing && fromFile.value && row.client_message ? <Row name="Client wording" ms="client_message">{row.client_message}</Row> : null}      {/* #1111: a published file's peek draws the client wording the file carries, read only and only when there is some */}
      {!editing && fromFile.value && row.kind === "action" && row.latest_update ? <Row name="Latest update" ms="latest_update"><Rich html={String(row.latest_update)} /></Row> : null}      {/* the file's latest update is already clean (publish.clean_html); no history, no editing */}
      {typeof row.not_reviewed === "boolean" ? <>
        <Row name="Raised">{showDate(row.raised)}</Row>
        <Row name="Last reviewed">{row.last_reviewed ? showDate(row.last_reviewed) : "Not yet"}</Row>
      </> : row.raised_on ? <Row name="Raised">{showDate(row.raised_on)}</Row> : null}      {/* row 1077: a published file carries no history (no freshness, no Last reviewed) but it carries the date raised, so a client's peek keeps that row */}
    </dl>
  );
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
// here (logic/milestones.js, as the Milestones list does). Achieved, with its date, only once the milestone is achieved.
export function MsState({ m }) {
  const state = fromFile.value && m.state ? m.state : stateOf(m, todayIso());
  const look = LOOK[state] || LOOK.Forecast;
  const word = m.status === "Done" && m.actual_date ? `Achieved on ${showDate(m.actual_date)}` : (fromFile.value && m.state_word) || state;
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
  const who = ownerOf(m.owner), description = richOf(tools, m.description), wording = richOf(tools, m.client_message);
  return (
    <>
      <MsHead>
        <MsState m={m} /><MsSep />
        {who.text === DASH ? null : <><span class="pk-ms-owner" data-ms-head="owner">{who.initials ? <span class="av" aria-hidden="true">{who.initials}</span> : null}{who.text}</span><MsSep /></>}
        <span class="msl-prog" data-ms-head="progress"><MsProgress value={m.status === "Done" && m.percent_complete == null ? 100 : m.percent_complete} /></span>
      </MsHead>
      <dl class="pk-fields" data-ms-fields>
        {description || !fromFile.value ? <Row name="Description" ms="description"><Rich html={description} /></Row> : null}      {/* row 560: a file carries no description for a milestone with no client wording, so a client's peek has no such row */}
        <Row name="Agreed date" ms="baseline">{showDate(m.baseline_date)}</Row>
        <Row name="Forecast date" ms="forecast">{showDate(m.forecast_date)}</Row>
        <Row name="Workstream" ms="workstream">{text(m.workstream)}</Row>
        {wording || !fromFile.value ? <Row name="Client wording" ms="client_message"><Rich html={wording} /></Row> : null}      {/* a client's peek has no empty wording row, as it has no empty description row; the editor's peek keeps both */}
      </dl>
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
  const box = useRef(null), back = useRef(null), opened = useRef(""), shown = useRef(""), stepped = useRef(false);
  const lastBox = useRef(null), keep = useCallback((n) => { box.current = n; if (n) lastBox.current = n; }, []);
  const editing = !!tools && !fromFile.value && isEditing();      // every page but a Dashboard in View (row 824)
  const msEditing = !!tools && !!tools.MilestoneEdit && !fromFile.value && (mode.value === "edit" || view.value === "milestones");     // row 828: the milestone's own fields are editable on the Milestones page with no View mode, and in Edit elsewhere
  // The words box changes a work item or a milestone; a use case has no peek (its own page, UseCaseDetail, has the box). The warning bar and Latest update are an item's only.
  const forItem = !!p && p.kind !== "milestone";
  const Words = editing && !!p && tools.Words;
  const Tabs = editing && tools.PeekTabs, Activity = editing && tools.PeekActivity;
  const MsTitle = msEditing && tools.MilestoneTitle;         // row 1078: the milestone's name is its title, changed in place
  const TitleBox = editing && forItem && tools.PeekTitle, DupBtn = editing && forItem && tools.PeekDuplicate, ArchBtn = editing && forItem && tools.PeekArchive, DelBtn = editing && forItem && tools.PeekDelete, MsArchBtn = msEditing && tools.PeekArchive;
  const Warn = editing && forItem && tools.PeekWarn, Latest = editing && forItem && tools.PeekLatest, Needed = editing && forItem && tools.PeekNeeded;      // the warning bar and Latest update (peek, Edit only)
  // Row 1077 (the owner's ruling): every peek, item or milestone, shows its Source, in Edit and in View alike. On the live page the Edit part
  // reads it from the server (tools.PeekSource); a published file (no tools, fromFile) draws the name its own data carries (FileSource below).
  const Source = !!tools && !fromFile.value && tools.PeekSource;
  const FileSource = fromFile.value;
  const showActivity = !!(Tabs && Activity && peekTab.value === "activity");
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
    if (close) close.focus();
    return () => {
      wordsOpen.value = false;
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
  // After a step the focus is never left on a button that has just turned off (Next at the last item) or on the page: it goes to Close.
  useEffect(() => {
    if (!p || !stepped.current) return;
    stepped.current = false;
    const a = document.activeElement, close = box.current && box.current.querySelector("[data-pk-close]");
    if (close && (!a || a === document.body || (a.disabled && box.current.contains(a)))) close.focus();
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
        if (wordsOpen.value) wordsOpen.value = false; else closePeek();
        return;
      }
      if (peekOwnsArrow(e)) { e.preventDefault(); stepBy(e.key === "ArrowUp" ? -1 : 1); return; }
      const t = e.target, inField = t && t.nodeType === 1 && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName));
      if (e.key === "/" && !e.metaKey && !e.ctrlKey && !e.altKey && !inField && Words) {
        if (last && performance.now() - last < 1000) { e.preventDefault(); last = 0; wordsOpen.value = true; } else last = performance.now() || 1;
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
    const click = (e) => { const was = down; down = false; if (was && closesPeek(e.target)) closePeek(); };
    document.addEventListener("pointerdown", press, true);
    document.addEventListener("click", click);
    return () => { document.removeEventListener("pointerdown", press, true); document.removeEventListener("click", click); };
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
    <aside class={`peek${wide.value ? " wide" : ""}`} id="peek" ref={keep} aria-label={`${p.id} details`} style={wide.value ? "" : `width:${Math.min(width.value, document.documentElement.clientWidth)}px`} data-peek={p.id}>
      <Edge />
      <div class="pk-bar">
        <button type="button" class="pkp-btn" data-pk-prev title="Previous item" aria-label="Previous item" disabled={!near.prev} onClick={() => go(near.prev)}><Icon name="chevleft" /></button>
        <button type="button" class="pkp-btn" data-pk-next title="Next item" aria-label="Next item" disabled={!near.next} onClick={() => go(near.next)}><Icon name="chevright" /></button>
        <span class="pk-id num">{p.id}</span>
        <span class="pk-sp" />
        {DupBtn && row ? <DupBtn row={row} /> : null}
        {ArchBtn && row ? <ArchBtn row={row} /> : null}
        {DelBtn && row ? <DelBtn row={row} /> : null}
        {MsArchBtn && m ? <MsArchBtn row={m} milestone /> : null}
        <button type="button" class="pkp-btn" data-pk-wide aria-pressed={wide.value} title={wide.value ? "Return the panel to its usual width" : "Make this panel fill the screen"} aria-label={wide.value ? "Return the panel to its usual width" : "Make this panel fill the screen"} onClick={() => { wide.value = !wide.value; }}><Icon name="expand" /></button>
        <button type="button" class="pkp-btn" data-pk-close title="Close this panel" aria-label="Close this panel" onClick={closePeek}><Icon name="x" /></button>
      </div>
      {Warn && row ? <Warn key={`w-${row.id}`} row={row} /> : null}
      <p class="sr-only" role="status" aria-live="polite" data-pk-live>{said.value.text}</p>
      <h2 class="pk-title" tabIndex={-1}>{TitleBox && row ? <TitleBox key={row.id} row={row} /> : MsTitle && m ? <MsTitle key={m.id} m={m} /> : title}</h2>
      {row && typeof row.not_reviewed === "boolean" && notReviewed(row, todayIso()) ? <p class="pk-stale"><span class="pk-chip" data-stale>{staleWords(row.review_days || undefined)}</span></p> : null}
      {Tabs ? <Tabs /> : null}
      <div class="pk-body" key={p.id} data-pk-body>      {/* a new key each step: the body fades in as Previous or Next moves on */}
      {showActivity ? <Activity key={p.id} id={p.id} />
        : <div role={Tabs ? "tabpanel" : undefined} id={Tabs ? "pk-panel-details" : undefined} aria-labelledby={Tabs ? "pk-tab-details" : undefined}>
          {row ? <ItemFields row={row} editing={editing} Cell={editing && tools.Cell ? tools.Cell : null} Wording={editing && tools.PeekWording ? tools.PeekWording : null} Pick={editing && tools.PeekPick ? tools.PeekPick : null} /> : msEditing ? <tools.MilestoneEdit m={m} /> : <MilestoneFields m={m} tools={tools} />}
          {Needed && row && row.kind !== "decision" ? <Needed key={`n-${row.id}`} row={row} /> : null}
          {Source ? <Source key={`s-${p.id}`} row={row || m} /> : FileSource ? <SourceLine text={(row || m).source} /> : null}
          {Latest && row ? <Latest key={row.id} row={row} /> : null}
        </div>}
      {Words && wordsOpen.value && (row || m) ? <Words key={p.id} row={row || m} kind={milestone ? "milestone" : "item"} /> : null}
      </div>
    </aside>
  );
}
