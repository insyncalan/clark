// The Calendar view (#44a): Month (the opening scale), Week and Quarter, with Earlier, Later and Today. A chip is the state's
// mark and the name, as in the prototype (system/prototype/views.js:105); a slipped milestone also shows on its expected date as
// a dashed chip that begins "Expected: ". Only the shown scale and place is drawn. A day with milestones names them for a screen
// reader. The "Milestones in this period" list is for a phone only, as in the prototype (app.css:1297, 1306): above 700 px it is hidden.
// Keys (#481, the prototype's model, system/prototype/views.js:155-171): one day of the shown period is a tab stop (today, else the first
// day); Left and Right move a day, Up and Down a week, into the next period when they leave this one; Enter on a day with milestones goes
// to its first chip, and Enter or Space on a chip opens it; Shift+Tab or Esc on a chip (no peek open) goes back to its day. The scale is
// switched by its buttons, as in the prototype. Page Up and Page Down step a whole period (kept from #76: the prototype has no such key).
import { useState, useRef, useEffect } from "preact/hooks";
import { recall, remember } from "../logic/remember.js";
import { MsMark } from "./MsMark.jsx";
import { Icon } from "./Icon.jsx";
import { calendarChips, buckets, neighbour, periodChips, addDays, showDate, MONTHS, homeDay, inRange } from "../logic/milestones.js";
import { dayNumber } from "../workItems.js";

const DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const DAY = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const SCALES = [["week", "Week"], ["month", "Month"], ["quarter", "Quarter"]];

function Chip({ c, say, open }) {
  const Tag = open ? "button" : "span";            // plain text in a published file
  const label = c.ghost ? `Expected: ${c.name}` : c.name;
  return (
    <Tag {...(open ? { type: "button", onClick: () => open(c.id) } : {})} class={`cal-ms c-${c.colour}${c.ghost ? " ghost" : ""}${open ? "" : " plain"}`} data-ms={c.id} data-ghost={c.ghost ? "1" : "0"}
      title={`${c.name} · ${showDate(c.date)} · ${c.ghost ? "expected" : c.word}`} aria-label={`${label}, ${c.word}`}><MsMark name={c.mark} /><span>{c.ghost ? "Expected: " : ""}{c.name}</span></Tag>
  );
}

function Day({ iso, chips, today, weekday, open, label, rove }) {
  const mine = chips[iso] || [], n = mine.length;
  const long = `${DAY[weekday]} ${+iso.slice(8)} ${MONTHS[+iso.slice(5, 7) - 1]} ${iso.slice(0, 4)}${n ? `, ${n} milestone${n === 1 ? "" : "s"}` : ""}`;
  return (
    <div class={`cal-d${iso === today ? " today" : ""}${weekday > 4 ? " we" : ""}`} data-d={iso} role="group" aria-label={long} tabIndex={iso === rove ? 0 : -1} aria-describedby={iso === rove ? "cal-hint" : undefined}>
      <span class="cal-n">{label || +iso.slice(8)}</span>
      {mine.map((c, i) => <Chip key={`${c.id}${c.ghost}${i}`} c={c} open={open} />)}
    </div>
  );
}

function MonthGrid({ month, chips, today, open, rove }) {
  const first = `${month}-01`, lead = (new Date(dayNumber(first) * 86400000).getUTCDay() + 6) % 7;
  const days = new Date(Date.UTC(+month.slice(0, 4), +month.slice(5, 7), 0)).getUTCDate();
  const cells = [...Array(lead).fill(""), ...Array.from({ length: days }, (_, i) => `${month}-${String(i + 1).padStart(2, "0")}`)];
  while (cells.length % 7) cells.push("");
  return (
    <>
      <div class="cal-dow" aria-hidden="true">{DOW.map((x) => <span key={x}>{x}</span>)}</div>
      <div class="cal-g">{cells.map((iso, i) => (iso ? <Day key={iso} iso={iso} chips={chips} today={today} weekday={i % 7} open={open} rove={rove} /> : <div class="cal-d out" key={`o${i}`} />))}</div>
    </>
  );
}

// Which day is the tab stop: the day the person last moved to, if the period shown holds it, else today, else the first day (#481).
const roveDay = (day, here, today) => (day && day >= here.start && day <= here.end ? day : today >= here.start && today <= here.end ? today : here.start);
const STEP = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 };

const SCALE_KEYS = SCALES.map(([v]) => v);
const RANGE_NOTE = "The calendar can't go that far. Go back to today, or pick a date nearer to it.";

export function MsCalendar({ rows, today, open, place, client }) {
  // The scale is remembered per place, as the Timeline / Calendar choice is; a published file remembers nothing.
  const [scale, setScale] = useState(() => { const s = client || !place ? null : recall(`msv.calv.${place}`, null); return SCALE_KEYS.includes(s) ? s : "month"; });
  const chips = calendarChips(rows);
  // Where to open when today is out of range: the earliest dated mark, else the start of the year of `today` (the clock is read once, in workItems.js).
  const home = () => homeDay(rows, today);
  const [at, setAt] = useState(home);        // any day inside the period shown
  const [far, setFar] = useState(false);
  const [moved, setMoved] = useState(false);   // true once the person has changed the period, so it is announced then and not on load
  const box = useRef(null);
  // Every move asks for focus to be put back once the new period is drawn: `iso` is the day to focus (a key move), else the calendar itself.
  // The ask is state, not a ref, so a first run of the effect that a quiet page flushes late reads its own render's ask (#481).
  const [ask, setAsk] = useState({ n: 0, iso: "" });
  const bump = (iso = "") => setAsk((r) => ({ n: r.n + 1, iso }));
  const [day, setDay] = useState(null);       // the day last moved to by a key: the one tab stop of the period (#481)
  useEffect(() => {
    const el = box.current, a = document.activeElement;
    if (!ask.n) return;                     // the first draw moves nothing
    const cell = ask.iso && el ? el.querySelector(`.cal-d[data-d="${ask.iso}"]`) : null;
    if (cell) { cell.focus(); return; }
    // The button or chip that had focus is drawn again by a move: keep focus on the calendar, never let it fall to the page.
    if (el && (!a || a === document.body || !document.contains(a))) el.focus();
  }, [ask]);
  const here = buckets(scale, at, at)[0];
  const rove = roveDay(day, here, today);
  const go = (k) => { const b = neighbour(scale, at, k); if (b) { setFar(false); setMoved(true); setAt(b.start); setDay(null); } else setFar(true); bump(); };
  const toToday = () => { setFar(false); setMoved(true); setAt(home()); setDay(null); bump(); };
  // A new scale always opens on the current period, as the prototype's does (system/prototype/views.js, toToday), wherever you had gone.
  const pick = (s) => { if (!client && place) remember(`msv.calv.${place}`, s); setFar(false); setMoved(true); setScale(s); setDay(null); setAt(home()); };
  // A day moved to by a key: its period is drawn if it is one the page draws, else the calendar says so (#481).
  const stepTo = (iso) => {
    if (!inRange(iso)) { setFar(true); bump(); return; }
    setFar(false);
    if (buckets(scale, iso, iso)[0].key !== here.key) setMoved(true);
    setDay(iso); setAt(iso); bump(iso);
  };
  const keys = (e) => {
    const t = e.target, chip = t.closest ? t.closest(".cal-ms") : null, cell = chip && chip.closest(".cal-d[data-d]");
    // On a chip: Shift+Tab, or Esc with no peek open, goes back to the day it sits in (#481, the prototype's #99).
    if (cell && !e.altKey && !e.ctrlKey && !e.metaKey && ((e.key === "Tab" && e.shiftKey) || (e.key === "Escape" && !document.getElementById("peek")))) {
      e.preventDefault(); setDay(cell.dataset.d); cell.focus(); return;
    }
    if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
    const k = { PageUp: -1, PageDown: 1 }[e.key];
    if (k) { e.preventDefault(); go(k); return; }
    // Only a focused day takes the arrows, so an arrow on a button or a chip keeps its own meaning.
    if (t.matches && t.matches(".cal-d[data-d]")) {
      if (STEP[e.key]) { e.preventDefault(); stepTo(addDays(t.dataset.d, STEP[e.key])); }
      else if (e.key === "Enter") { const first = t.querySelector("button.cal-ms"); if (first) { e.preventDefault(); first.focus(); } }
    }
  };
  const inPeriod = periodChips(chips, here);
  let body;
  if (scale === "month") body = <MonthGrid month={here.key} chips={chips} today={today} open={open} rove={rove} />;
  else if (scale === "week") {
    body = (
      <>
        <div class="cal-dow" aria-hidden="true">{DOW.map((x) => <span key={x}>{x}</span>)}</div>
        <div class="cal-g cal-wk">{DOW.map((x, i) => { const iso = addDays(here.key, i); return <Day key={iso} iso={iso} chips={chips} today={today} weekday={i} open={open} rove={rove} label={`${+iso.slice(8)} ${MONTHS[+iso.slice(5, 7) - 1].slice(0, 3)}`} />; })}</div>
      </>
    );
  } else {
    body = (
      <div class="cal-q">{here.months.map((m) => (
        <div key={m}><button type="button" class="cal-qm" data-goto={m} title={`Show ${MONTHS[+m.slice(5) - 1]}`} onClick={() => { if (!client && place) remember(`msv.calv.${place}`, "month"); setScale("month"); setMoved(true); setDay(null); setAt(`${m}-01`); bump(); }}>{MONTHS[+m.slice(5) - 1]}</button>
          <MonthGrid month={m} chips={chips} today={today} open={open} rove={rove} /></div>
      ))}</div>
    );
  }
  return (
    <div class="cal" data-scale={scale} data-at={here.key} onKeyDown={keys} ref={box} tabIndex={-1} role="group" aria-label="Milestone calendar">
      <span id="cal-hint" class="sr-only">The arrow keys move between days, a week at a time with Up and Down. Enter on a day with milestones goes to the first. Shift and Tab, or Esc, goes back to the day. Page Up and Page Down move to the earlier or later period.</span>
      <span class="sr-only" role="status" aria-live="polite" data-cal-say>{moved ? `Now on ${here.label}` : ""}</span>
      <div class="cal-bar">
        <button type="button" class="ib" data-cal="-1" aria-label="Earlier" onClick={() => go(-1)}><Icon name="left" /></button>
        <button type="button" class="ib" data-cal="1" aria-label="Later" onClick={() => go(1)}><Icon name="right" /></button>
        <button type="button" class="btn" data-cal="0" onClick={toToday}>Today</button>
        <b class="cal-t">{here.label}</b>
        <span class="seg cal-sc" role="group" aria-label="Calendar scale">
          {SCALES.map(([v, t]) => <button type="button" key={v} data-scale-b={v} aria-current={String(scale === v)} onClick={() => pick(v)}>{t}</button>)}
        </span>
      </div>
      {far ? <p class="cal-far" role="status" data-cal-far>{RANGE_NOTE} <button type="button" class="btn" data-cal-home onClick={toToday}>Go to today</button></p> : null}
      {body}
      {inPeriod.length ? (
        <section class="cal-list" aria-label="Milestones in this period" data-cal-list>
          <h4>Milestones in this period</h4>
          <ul>{inPeriod.map((c, i) => (
            <li key={`${c.id}${c.ghost}${i}`} data-cl={c.id} data-ghost={c.ghost ? "1" : "0"}><span class="cal-ld">{showDate(c.date)}</span> <span class="cal-ln">{c.name}</span> <span class={`mst c-${c.colour}`}><MsMark name={c.mark} />{c.ghost ? `Expected, ${c.word}` : c.word}</span></li>
          ))}</ul>
        </section>
      ) : (
        /* item 555: the list is for a phone only, but this line is the calendar's answer, so it sits outside the list and shows at every width */
        <p class="muted cal-empty" data-cal-empty>No milestones in this period. Use Earlier or Later to find the next one{far ? "." : <>, or <button type="button" class="btn" onClick={toToday}>go to today</button>.</>}</p>
      )}
    </div>
  );
}
