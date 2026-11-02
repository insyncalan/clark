// The Calendar view (#44a): Month (the opening scale), Week and Quarter, with Earlier, Later and Today. A chip is the state's
// mark and the name, as in the prototype (system/prototype/views.js:105); a slipped milestone also shows on its expected date as
// a dashed chip that begins "Expected: ". Only the shown scale and place is drawn. A day with milestones names them for a screen
// reader. Each day is a tab stop (one of them at a time, the way the prototype does it): the arrows move by a day or a week, Enter
// goes to the day's first chip, Esc or Shift+Tab comes back. The "Milestones in this period" list is for a phone only, as in the
// prototype (app.css:1297, 1306): above 700 px it is hidden.
import { useState, useRef, useEffect } from "preact/hooks";
import { recall, remember } from "../logic/remember.js";
import { MsMark } from "./MsMark.jsx";
import { Icon } from "./Icon.jsx";
import { calendarChips, buckets, neighbour, periodChips, addDays, showDate, MONTHS, homeDay, dayStep, tabDay } from "../logic/milestones.js";
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

function Day({ iso, chips, today, weekday, open, label, stop }) {
  const mine = chips[iso] || [], n = mine.length;
  const long = `${DAY[weekday]} ${+iso.slice(8)} ${MONTHS[+iso.slice(5, 7) - 1]} ${iso.slice(0, 4)}${n ? `, ${n} milestone${n === 1 ? "" : "s"}` : ""}`;
  return (
    <div class={`cal-d${iso === today ? " today" : ""}${weekday > 4 ? " we" : ""}`} data-d={iso} tabIndex={iso === stop ? 0 : -1} role="group" aria-label={long}>
      <span class="cal-n">{label || +iso.slice(8)}</span>
      {mine.map((c, i) => <Chip key={`${c.id}${c.ghost}${i}`} c={c} open={open} />)}
    </div>
  );
}

function MonthGrid({ month, chips, today, open, stop }) {
  const first = `${month}-01`, lead = (new Date(dayNumber(first) * 86400000).getUTCDay() + 6) % 7;
  const days = new Date(Date.UTC(+month.slice(0, 4), +month.slice(5, 7), 0)).getUTCDate();
  const cells = [...Array(lead).fill(""), ...Array.from({ length: days }, (_, i) => `${month}-${String(i + 1).padStart(2, "0")}`)];
  while (cells.length % 7) cells.push("");
  return (
    <>
      <div class="cal-dow" aria-hidden="true">{DOW.map((x) => <span key={x}>{x}</span>)}</div>
      <div class="cal-g">{cells.map((iso, i) => (iso ? <Day key={iso} iso={iso} chips={chips} today={today} weekday={i % 7} open={open} stop={stop} /> : <div class="cal-d out" key={`o${i}`} />))}</div>
    </>
  );
}

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
  const [sel, setSel] = useState("");         // the day last chosen with the keys; it is the tab stop while its period is shown
  const want = useRef("");                // a day to put focus on once it is drawn
  const [moved, setMoved] = useState(false);   // true once the person has changed the period, so it is announced then and not on load
  const box = useRef(null);
  const [tick, setTick] = useState(0);        // bumped on every move, so focus can be put back once the new period is drawn
  useEffect(() => {
    if (want.current) { const d = box.current && box.current.querySelector(`.cal-d[data-d="${want.current}"]`); if (d) { want.current = ""; d.focus(); } return; }
    // The button or chip that had focus is drawn again by a move: keep focus on the calendar, never let it fall to the page.
    const el = box.current, a = document.activeElement;
    if (tick && el && (!a || a === document.body || !document.contains(a))) el.focus();
  }, [tick, sel, at]);
  const here = buckets(scale, at, at)[0];
  const go = (k) => { setSel(""); const b = neighbour(scale, at, k); if (b) { setFar(false); setMoved(true); setAt(b.start); } else setFar(true); setTick((n) => n + 1); };
  const toToday = () => { setSel(""); setFar(false); setMoved(true); setAt(home()); setTick((n) => n + 1); };
  // A new scale always opens on the current period, as the prototype's does (system/prototype/views.js, toToday), wherever you had gone.
  const pick = (s) => { if (!client && place) remember(`msv.calv.${place}`, s); setSel(""); setFar(false); setMoved(true); setScale(s); setAt(home()); };
  const stop = tabDay(here, sel, today);
  // Put focus back on the day a chip sits in (Shift+Tab or Esc from the chip).
  const back = (iso) => { setSel(iso); want.current = iso; const d = box.current && box.current.querySelector(`.cal-d[data-d="${iso}"]`); if (d) { want.current = ""; d.focus(); } };
  const keys = (e) => {
    const t = e.target, chip = t.classList && t.classList.contains("cal-ms") ? t.closest(".cal-d[data-d]") : null;
    // From a chip, Shift+Tab, or Esc when no peek is open, goes back to the day it sits in.
    if (chip && ((e.key === "Tab" && e.shiftKey) || (e.key === "Escape" && !document.getElementById("peek")))) { e.preventDefault(); back(chip.dataset.d); return; }
    if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
    const k = { PageUp: -1, PageDown: 1 }[e.key];
    if (k) { e.preventDefault(); go(k); return; }
    const onDay = t.classList && t.classList.contains("cal-d") && t.dataset.d, onBox = t === box.current;
    if (!onDay && !onBox) return;
    if (e.key === "Enter") { const c = onDay && t.querySelector("button.cal-ms"); if (c) { e.preventDefault(); c.focus(); } return; }
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)) return;
    const to = dayStep(onDay || stop, e.key);
    e.preventDefault();
    if (!to) { setFar(true); return; }
    setFar(false); if (buckets(scale, to, to)[0].key !== here.key) setMoved(true);
    want.current = to; setSel(to); setAt(to); setTick((n) => n + 1);
  };
  const inPeriod = periodChips(chips, here);
  let body;
  if (scale === "month") body = <MonthGrid month={here.key} chips={chips} today={today} open={open} stop={stop} />;
  else if (scale === "week") {
    body = (
      <>
        <div class="cal-dow" aria-hidden="true">{DOW.map((x) => <span key={x}>{x}</span>)}</div>
        <div class="cal-g cal-wk">{DOW.map((x, i) => { const iso = addDays(here.key, i); return <Day key={iso} iso={iso} chips={chips} today={today} weekday={i} open={open} stop={stop} label={`${+iso.slice(8)} ${MONTHS[+iso.slice(5, 7) - 1].slice(0, 3)}`} />; })}</div>
      </>
    );
  } else {
    body = (
      <div class="cal-q">{here.months.map((m) => (
        <div key={m}><button type="button" class="cal-qm" data-goto={m} title={`Show ${MONTHS[+m.slice(5) - 1]}`} onClick={() => { if (!client && place) remember(`msv.calv.${place}`, "month"); setScale("month"); setSel(""); setMoved(true); setAt(`${m}-01`); setTick((n) => n + 1); }}>{MONTHS[+m.slice(5) - 1]}</button>
          <MonthGrid month={m} chips={chips} today={today} open={open} stop={stop} /></div>
      ))}</div>
    );
  }
  return (
    <div class="cal" data-scale={scale} data-at={here.key} onKeyDown={keys} ref={box} tabIndex={-1} role="group" aria-label="Milestone calendar" aria-describedby="cal-hint">
      <span id="cal-hint" class="sr-only">Tab to a day, then the arrows move by a day or a week, Enter goes to its first milestone, and Escape comes back to the day. Page Up and Page Down move to the earlier or later period.</span>
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
      <section class="cal-list" aria-label="Milestones in this period" data-cal-list>
        <h4>Milestones in this period</h4>
        {inPeriod.length ? (
          <ul>{inPeriod.map((c, i) => (
            <li key={`${c.id}${c.ghost}${i}`} data-cl={c.id} data-ghost={c.ghost ? "1" : "0"}><span class="cal-ld">{showDate(c.date)}</span> <span class="cal-ln">{c.name}</span> <span class={`mst c-${c.colour}`}><MsMark name={c.mark} />{c.ghost ? `Expected, ${c.word}` : c.word}</span></li>
          ))}</ul>
        ) : (
          <p class="muted cal-empty" data-cal-empty>No milestones in this period. Use Earlier or Later to find the next one{far ? "." : <>, or <button type="button" class="btn" onClick={toToday}>go to today</button>.</>}</p>
        )}
      </section>
    </div>
  );
}
