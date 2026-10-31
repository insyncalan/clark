// The Calendar view (#44a): Month (the opening scale), Week and Quarter, with Earlier, Later and Today. A chip carries the
// state's mark; a slipped milestone also shows on its expected date as a dashed "Expected" chip. Only the shown scale and place
// is drawn. A day with milestones names them for a screen reader.
import { useState } from "preact/hooks";
import { MsMark } from "./MsMark.jsx";
import { Icon } from "./Icon.jsx";
import { calendarChips, buckets, bucketKey, markDates, addDays, showDate, MONTHS } from "../logic/milestones.js";
import { dayNumber } from "../workItems.js";

const DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const DAY = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const SCALES = [["week", "Week"], ["month", "Month"], ["quarter", "Quarter"]];

function Chip({ c, say, open }) {
  const Tag = open ? "button" : "span";            // plain text in a published file
  const label = c.ghost ? `Expected: ${c.name}` : c.name;
  return (
    <Tag {...(open ? { type: "button", onClick: () => open(c.id) } : {})} class={`cal-ms c-${c.colour}${c.ghost ? " ghost" : ""}${open ? "" : " plain"}`} data-ms={c.id} data-ghost={c.ghost ? "1" : "0"}
      title={`${c.name} · ${showDate(c.date)} · ${c.ghost ? "expected" : c.word}`} aria-label={`${label}, ${c.word}`}><MsMark name={c.mark} /><span>{label}</span></Tag>
  );
}

function Day({ iso, chips, today, weekday, open, label }) {
  const mine = chips[iso] || [], n = mine.length;
  const long = `${DAY[weekday]} ${+iso.slice(8)} ${MONTHS[+iso.slice(5, 7) - 1]} ${iso.slice(0, 4)}${n ? `, ${n} milestone${n === 1 ? "" : "s"}` : ""}`;
  return (
    <div class={`cal-d${iso === today ? " today" : ""}${weekday > 4 ? " we" : ""}`} data-d={iso} role="group" aria-label={long}>
      <span class="cal-n">{label || +iso.slice(8)}</span>
      {mine.map((c, i) => <Chip key={`${c.id}${c.ghost}${i}`} c={c} open={open} />)}
    </div>
  );
}

function MonthGrid({ month, chips, today, open }) {
  const first = `${month}-01`, lead = (new Date(dayNumber(first) * 86400000).getUTCDay() + 6) % 7;
  const days = new Date(Date.UTC(+month.slice(0, 4), +month.slice(5, 7), 0)).getUTCDate();
  const cells = [...Array(lead).fill(""), ...Array.from({ length: days }, (_, i) => `${month}-${String(i + 1).padStart(2, "0")}`)];
  while (cells.length % 7) cells.push("");
  return (
    <>
      <div class="cal-dow" aria-hidden="true">{DOW.map((x) => <span key={x}>{x}</span>)}</div>
      <div class="cal-g">{cells.map((iso, i) => (iso ? <Day key={iso} iso={iso} chips={chips} today={today} weekday={i % 7} open={open} /> : <div class="cal-d out" key={`o${i}`} />))}</div>
    </>
  );
}

export function MsCalendar({ rows, today, open }) {
  const [scale, setScale] = useState("month");
  const chips = calendarChips(rows);
  const dates = markDates(rows).concat(today).sort();
  const first = dates[0], last = dates[dates.length - 1];
  const nowKey = bucketKey(scale, today);
  const [at, setAt] = useState(nowKey);
  const list = buckets(scale, first, last);
  const here = list.find((b) => b.key === at) || list.find((b) => b.key === nowKey) || list[0];
  const idx = list.indexOf(here);
  const go = (k) => setAt(list[Math.max(0, Math.min(list.length - 1, idx + k))].key);
  // The new scale opens on today when today is in what is shown, else on what starts it.
  const pick = (s) => { setScale(s); setAt(bucketKey(s, here.start <= today && today <= here.end ? today : here.start)); };
  let body;
  if (scale === "month") body = <MonthGrid month={here.key} chips={chips} today={today} open={open} />;
  else if (scale === "week") {
    body = (
      <>
        <div class="cal-dow" aria-hidden="true">{DOW.map((x) => <span key={x}>{x}</span>)}</div>
        <div class="cal-g cal-wk">{DOW.map((x, i) => { const iso = addDays(here.key, i); return <Day key={iso} iso={iso} chips={chips} today={today} weekday={i} open={open} label={`${+iso.slice(8)} ${MONTHS[+iso.slice(5, 7) - 1].slice(0, 3)}`} />; })}</div>
      </>
    );
  } else {
    body = (
      <div class="cal-q">{here.months.map((m) => (
        <div key={m}><button type="button" class="cal-qm" data-goto={m} title={`Show ${MONTHS[+m.slice(5) - 1]}`} onClick={() => { setScale("month"); setAt(m); }}>{MONTHS[+m.slice(5) - 1]}</button>
          <MonthGrid month={m} chips={chips} today={today} open={open} /></div>
      ))}</div>
    );
  }
  return (
    <div class="cal" data-scale={scale} data-at={here.key}>
      <div class="cal-bar">
        <button type="button" class="ib" data-cal="-1" aria-label="Earlier" disabled={idx <= 0} onClick={() => go(-1)}><Icon name="left" /></button>
        <button type="button" class="ib" data-cal="1" aria-label="Later" disabled={idx >= list.length - 1} onClick={() => go(1)}><Icon name="right" /></button>
        <button type="button" class="btn" data-cal="0" onClick={() => setAt(nowKey)}>Today</button>
        <b class="cal-t">{here.label}</b>
        <span class="seg cal-sc" role="group" aria-label="Calendar scale">
          {SCALES.map(([v, t]) => <button type="button" key={v} data-scale-b={v} aria-current={String(scale === v)} onClick={() => pick(v)}>{t}</button>)}
        </span>
      </div>
      {body}
    </div>
  );
}
