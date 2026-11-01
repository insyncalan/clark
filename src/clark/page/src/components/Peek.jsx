// The peek (#42a): one work item's or milestone's fields beside the list. Read only in View and in a published file: fields and
// nothing else (no history, no words box, no /api/ text). `tools.Words`, `tools.WordsButton`, `tools.PeekTabs` and
// `tools.PeekActivity` (Details and Activity, #42) are the Edit part.
// The address holds which item is open (router.js, #63); Previous and Next replace that entry, Esc and Close go through
// closePeek(). The width is dragged from the left edge (keys too), double-click resets it.
// The arrow keys (#246, #289): Up and Down on one of its buttons step like Previous and Next, an arrow that moves the focus to
// another row or card moves the peek with it, and Esc puts the focus on the row of the item shown. Nothing else takes an arrow.
import { useEffect, useRef } from "preact/hooks";
import { signal } from "@preact/signals";
import { data, rows, peek, openPeek, closePeek, mode, fromFile } from "../stores/report.js";
import { width, wide, setWidth, resetWidth, MIN, peekTab } from "../stores/peekState.js";
import { staleWords, notReviewed } from "../filters.js";
import { KIND_WORDS, dueCell, pillOf, ownerOf, showDate, todayIso } from "../workItems.js";
import { itemIds, milestoneIds, around, placeIn } from "../peek/list.js";
import { Icon } from "./Icon.jsx";
import { wordsOpen, flashed } from "../stores/wordsState.js";
import { statusTone, priorityTone, dateTone, iconClass } from "../iconColours.js";

// Up and Down while the peek is open (#246): the peek steps to the item before or after in the list it was opened from, the same list
// Previous and Next use. What it says after a step (a polite line only a screen reader hears) is kept here; `n` makes a repeat say it again.
const said = signal({ text: "", n: 0 });
const say = (text) => { said.value = { text, n: said.value.n + 1 }; };

// Where the peek takes an arrow (#289): only Up and Down, only plain, only on one of its own buttons. A box, the width edge, a tab,
// a menu, a dialog and the palette keep their arrows; so does the page's own scrolling, which is why a key aimed at nothing is left too.
const OWN = "[role=textbox],[role=combobox],[role=listbox],[role=menu],[role=dialog],[role=alertdialog],[role=tab],[role=separator],dialog";
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

function Row({ name, children, ref_, key_ }) {          // key_: which field this row shows, so it can flash when that field changes
  const f = flashed.value;
  const hit = !!(f && key_ && f.list.some((e) => e.ref === ref_ && ROW_OF[e.field] === key_));
  return <div class={`pk-row${hit ? " flash" : ""}`} data-row={key_ || undefined} data-flash={hit ? "1" : undefined}><dt>{name}</dt><dd>{children}{hit ? <span class="tag chg">Changed</span> : null}</dd></div>;
}

function ItemFields({ row, editing }) {
  const today = todayIso(), due = dueCell(row, today), pill = pillOf(row, today), who = ownerOf(row.owner);
  return (
    <dl class="pk-fields">
      <Row name="Type">{KIND_WORDS[row.kind] || row.kind}</Row>
      <Row key_="owner" ref_={row.id} name={row.kind === "decision" ? "Decision by" : "Owner"}>{who.text}</Row>
      <Row key_="due" ref_={row.id} name={row.kind === "decision" && row.status === "Pending" ? "Needed by" : row.kind === "decision" ? "Date" : "Due"}>
        <Toned icon="cal" tone={dateTone(row, today)}>{due.date}</Toned>{due.words ? <span class={`due-l${due.tone ? " " + due.tone : ""}`}> {due.words}</span> : null}
      </Row>
      {row.kind !== "decision" ? <Row key_="priority" ref_={row.id} name="Priority"><Toned icon="bars" tone={priorityTone(row.priority)}>{text(row.priority)}</Toned></Row> : null}
      <Row key_="status" ref_={row.id} name="Status"><Toned icon="half" tone={statusTone(row, today)}><span class={`pill ${pill.class}`}>{pill.text}</span></Toned></Row>
      <Row name="Workstream">{text(row.workstream)}</Row>
      <Row name="Milestone">{text(row.milestone)}</Row>
      <Row name="Use case">{text(row.uc)}</Row>
      {editing ? <Row name="Shown to client">{row.client ? "Yes" : "No"}</Row> : null}
      {typeof row.not_reviewed === "boolean" ? <>
        <Row name="Raised">{showDate(row.raised)}</Row>
        <Row name="Last reviewed">{row.last_reviewed ? showDate(row.last_reviewed) : "Not yet"}</Row>
      </> : null}
    </dl>
  );
}

function MilestoneFields({ m }) {
  return (
    <dl class="pk-fields">
      <Row name="Owner">{ownerOf(m.owner).text}</Row>
      <Row name="Agreed date">{showDate(m.baseline_date)}</Row>
      <Row name="Forecast date">{showDate(m.forecast_date)}</Row>
      <Row name="Status">{text(m.state || m.status)}</Row>
      <Row name="Workstream">{text(m.workstream)}</Row>
    </dl>
  );
}

// The edge you drag. Keys work too: Left widens, Right narrows, Home resets. Double-click resets.
function Edge() {
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
  const editing = !!tools && !fromFile.value && mode.value === "edit";
  // The words box changes work items only (sneak.py refuses a milestone), so a milestone peek has no sparkle and no `//`.
  const forItem = !!p && p.kind !== "milestone";
  const Words = editing && forItem && tools.Words, WordsBtn = editing && forItem && tools.WordsButton;
  const Tabs = editing && tools.PeekTabs, Activity = editing && tools.PeekActivity;
  const showActivity = !!(Tabs && Activity && peekTab.value === "activity");
  if (p) shown.current = p.id;                            // kept after the peek closes, for the focus it returns
  // Focus goes in when the peek opens and back to where it was when it closes: to the row (or card) of the item the peek shows then,
  // which after Up, Down, Previous or Next is not the one it opened on (#246).
  useEffect(() => {
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
      if (el && el.isConnected && el.focus) el.focus();
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
    let arrow = false, off = 0;
    const down = (e) => {
      arrow = (e.key === "ArrowUp" || e.key === "ArrowDown" || e.key === "ArrowLeft" || e.key === "ArrowRight") && !e.shiftKey && !e.metaKey && !e.ctrlKey && !e.altKey;
      clearTimeout(off); off = setTimeout(() => { arrow = false; }, 0);
    };
    const into = (e) => {
      const id = arrow ? listItemOf(e.target) : "";
      if (id && id !== shown.current) openPeek(id, "item");
    };
    document.addEventListener("keydown", down, true);
    document.addEventListener("focusin", into);
    return () => { clearTimeout(off); document.removeEventListener("keydown", down, true); document.removeEventListener("focusin", into); };
  }, [!!p, p && p.kind]);                                 // eslint-disable-line react-hooks/exhaustive-deps
  // Esc closes the words box first, then the peek; two slashes outside a field open the words box (Edit only). Up and Down on one of the
  // peek's own buttons step to the item before or after (#246); every other arrow is left to whatever it was aimed at (#289).
  const stepBy = (dir) => {
    const ms = p.kind === "milestone", ids = ms ? milestoneIds() : itemIds(), here = placeIn(ids, p.id);
    if (here.at < 0) { say(`${p.id} is not in the list now`); return; }
    const to = ids[here.at + dir];
    if (!to) { say(`${p.id}, ${here.at + 1} of ${ids.length}, the ${dir < 0 ? "first" : "last"} one`); return; }
    stepped.current = true;
    openPeek(to, p.kind);
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
  if (!p || !data.value) return null;
  const milestone = p.kind === "milestone";
  const row = milestone ? null : rows.value.find((r) => r.id === p.id);
  const m = milestone ? (data.value.milestones || []).find((x) => x.id === p.id) : null;
  if (!row && !m) return null;
  const near = around(milestone ? milestoneIds() : itemIds(), p.id);
  const go = (id) => id && openPeek(id, p.kind);
  const title = row ? row.title : m.name;
  return (
    <aside class={`peek${wide.value ? " wide" : ""}`} id="peek" ref={box} aria-label={`${p.id} details`} style={wide.value ? "" : `width:${Math.min(width.value, document.documentElement.clientWidth)}px`} data-peek={p.id}>
      <Edge />
      <div class="pk-bar">
        <button type="button" class="pkp-btn" data-pk-prev title="Previous item" aria-label="Previous item" disabled={!near.prev} onClick={() => go(near.prev)}><Icon name="chevleft" /></button>
        <button type="button" class="pkp-btn" data-pk-next title="Next item" aria-label="Next item" disabled={!near.next} onClick={() => go(near.next)}><Icon name="chevright" /></button>
        <span class="pk-id num">{p.id}</span>
        <span class="pk-sp" />
        {WordsBtn ? <WordsBtn /> : null}
        <button type="button" class="pkp-btn" data-pk-wide aria-pressed={wide.value} title={wide.value ? "Return the panel to its usual width" : "Make this panel fill the screen"} aria-label={wide.value ? "Return the panel to its usual width" : "Make this panel fill the screen"} onClick={() => { wide.value = !wide.value; }}><Icon name="expand" /></button>
        <button type="button" class="pkp-btn" data-pk-close title="Close this panel" aria-label="Close this panel" onClick={closePeek}><Icon name="x" /></button>
      </div>
      <p class="sr-only" role="status" aria-live="polite" data-pk-live key={said.value.n}>{said.value.text}</p>
      <h2 class="pk-title">{title}</h2>
      {row && typeof row.not_reviewed === "boolean" && notReviewed(row, todayIso()) ? <p class="pk-stale"><span class="pk-chip" data-stale>{staleWords(row.review_days || undefined)}</span></p> : null}
      {Tabs ? <Tabs /> : null}
      {showActivity ? <Activity key={p.id} id={p.id} />
        : <div role={Tabs ? "tabpanel" : undefined} id={Tabs ? "pk-panel-details" : undefined} aria-labelledby={Tabs ? "pk-tab-details" : undefined}>
          {row ? <ItemFields row={row} editing={editing} /> : <MilestoneFields m={m} />}
        </div>}
      {Words && wordsOpen.value && row ? <Words key={row.id} row={row} /> : null}
    </aside>
  );
}
