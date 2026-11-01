// The 'Progress tracker' section as a reader sees it (#189): an overall bar (Actual against Planned, a health pill and a line of the
// owner's words), then each group of plan lines with its own total. Full draws a table (number, description, dates, status, weight,
// planned, achieved, and the optional counts); Half draws the bar and a short list (description, status, planned, achieved, no dates).
// It draws in View and in a published file, view only (no input, no button); Edit draws edit/TrackerEdit.jsx in its place, with the
// same pieces below. A line behind plan carries "▼ n" and, for a screen reader, the words, so colour is never the only signal.
// Every value is a text node: nothing the section holds is read as markup. The sums come from logic/tracker.js and are never stored.
import { useEffect, useState } from "preact/hooks";
import { data, fromFile, asAt } from "../stores/report.js";
import { showDate, todayIso } from "../workItems.js";
import { trackerOf, totals, fill, fmt, lineFill, markEdge, statusWord, healthWord, behindWords, COLUMNS, WORDS } from "../logic/tracker.js";

const DASH = "—";
const HEALTH_PILL = { ontrack: "g", atrisk: "a", offtrack: "r" };
const STATUS_PILL = { planned: "n", inprogress: "v", completed: "g", late: "r" };

// A fit's name from the slot the section sits in: only a whole row is Full.
export const fitOf = (slot) => (slot === "full" ? "full" : "half");

export const StatusPill = ({ status }) => <span class={`pill ${STATUS_PILL[status] || "n"} tr-status`}>{statusWord(status)}</span>;

// "▼ 5" and, for a screen reader, "5 points behind plan"; nothing when the line is not behind.
export const Behind = ({ behind }) => (behind > 0
  ? <span class="tr-behind"><span aria-hidden="true">▼ {fmt(behind)}</span><span class="sr">{behindWords(behind)}</span></span>
  : null);

// The Overall part, as the approved weekly-snapshot design draws it (#451): three tiles (Project health, Actual "of the whole project",
// Planned "by <date>"), then the bar with a "Planned n%" label over the mark and a 0% to 100% scale under it. The date is the day the file
// was published (or today, in the app), the same day every other section reads as "now". The reading is for the picture: the bar says it
// in words to a screen reader, and the label and scale are drawn for the eye only.
export function Overall({ overall }) {
  const { actual, planned, health, note, behind, behindWords: said } = overall;
  const pct = (t) => (t === null ? DASH : `${fmt(t)}%`);
  const by = fromFile.value && asAt.value ? asAt.value : todayIso();
  const label = actual === null ? WORDS.none : `${WORDS.actual} ${pct(actual)}${planned === null ? "" : `, ${WORDS.planned.toLowerCase()} ${pct(planned)}`}`;
  const edge = planned === null ? "" : markEdge(planned);
  return (
    <div class="tr-overall" data-tr-overall>
      <div class="tr-tiles">
        <div class="tr-tile tr-tile-health" data-tr-tile>
          <span class="tr-k">{WORDS.healthTile}</span>
          <span class="tr-hrow">
            {health ? <span class={`pill ${HEALTH_PILL[health]} tr-pill`} data-tr-health>{healthWord(health)}</span> : <span class="tr-v num">{DASH}</span>}
            {" "}
            {said || note ? (
              <span class="tr-reason">
                {said ? <span class="tr-behindline" data-tr-behind>{said}</span> : null}
                {said && note ? " " : null}
                {note ? <span class="tr-note">{note}</span> : null}
              </span>
            ) : null}
          </span>
        </div>
        <div class="tr-tile" data-tr-tile>
          <span class="tr-k">{WORDS.actual}</span>
          <span class="tr-v num" data-tr-actual>{pct(actual)}</span>
          {" "}
          <span class="tr-d">{WORDS.actualOf}</span>
        </div>
        <div class="tr-tile" data-tr-tile>
          <span class="tr-k">{WORDS.planned}</span>
          <span class="tr-v num" data-tr-planned>{pct(planned)}</span>
          {" "}
          {planned !== null ? <span class="tr-d num">{WORDS.plannedBy} {showDate(by)}</span> : null}
        </div>
      </div>
      <div class="tr-barw">
        <div class="tr-bar" role="img" aria-label={label} data-tr-bar>
          <span class="tr-fill" style={{ width: `${fill(actual) / 10}%` }} />
          {planned !== null ? (
            <span class="tr-mark" style={{ left: `${fill(planned) / 10}%` }}>
              <span class={`tr-mark-label${edge ? ` tr-edge-${edge}` : ""}`} data-tr-mark-label aria-hidden="true">{WORDS.planned} {pct(planned)}</span>
            </span>
          ) : null}
        </div>
        <div class="tr-scale num" data-tr-scale aria-hidden="true"><span>{WORDS.scaleStart}</span><span>{WORDS.scaleEnd}</span></div>
      </div>
    </div>
  );
}

// The columns a Full table draws: the fixed ones, then the counts the owner switched on.
export const columnsOf = (tracker) => COLUMNS.filter(([k]) => tracker.columns[k]);

// At 900 px and narrower the date and count columns are not drawn at all (a cell that is merely hidden would leave every colSpan
// counting columns that are not there), so each row's colSpan is the number of columns it really has.
const QUERY = "(max-width: 900px)";
const narrowNow = () => typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia(QUERY).matches;
export function useNarrow() {
  const [narrow, setNarrow] = useState(narrowNow);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return undefined;
    const mq = window.matchMedia(QUERY);
    const on = () => setNarrow(mq.matches);
    on();
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return narrow;
}
// How many columns a Full table has: no, description, status, weight, planned, achieved (and, when wide, start, end and the counts shown), then a tools column in Edit.
export const colCount = (narrow, columns, tools) => (narrow ? 6 : 8 + columns.length) + (tools ? 1 : 0);

export function GroupFull({ group, columns: shown, extraHead, extraCell, below, foot }) {
  const narrow = useNarrow();
  const columns = narrow ? [] : shown;
  const date = (cell) => (narrow ? null : cell);
  return (
    <table class="tracker tr-full" data-tr-group>
      <caption class="tr-cap">{group.name}</caption>
      <thead>
        <tr>
          <th scope="col" class="t-no">{WORDS.no}</th><th scope="col" class="t-what">{WORDS.what}</th>
          {date(<th scope="col" class="t-date">{WORDS.start}</th>)}{date(<th scope="col" class="t-date">{WORDS.end}</th>)}<th scope="col" class="t-status">{WORDS.status}</th>
          <th scope="col" class="t-n">{WORDS.weight}</th><th scope="col" class="t-n">{WORDS.planned}</th><th scope="col" class="t-n t-ach">{WORDS.achieved}</th>
          {columns.map(([k, w]) => <th key={k} scope="col" class="t-n t-count">{w}</th>)}
          {extraHead || null}
        </tr>
      </thead>
      <tbody>
        {group.lines.map((l, i) => (
          below && below(i) ? below(i) : (
            <tr key={i} data-tr-line={i}>
              <td class="t-no">{l.no || DASH}</td><td class="t-what">{l.text}</td>
              {date(<td class="t-date num">{l.start ? showDate(l.start) : DASH}</td>)}{date(<td class="t-date num">{l.end ? showDate(l.end) : DASH}</td>)}
              <td class="t-status"><StatusPill status={l.status} /></td>
              <td class="t-n num">{fmt(l.weight)}%</td>
              <td class="t-n num">{fmt(l.planned)}%</td>
              <td class="t-n t-ach num"><span class="tr-ach"><span class="tr-pbar" aria-hidden="true"><i style={{ width: `${lineFill(l)}%` }} /></span><b>{fmt(l.achieved)}%</b><Behind behind={l.behind} /></span></td>
              {columns.map(([k]) => <td key={k} class="t-n t-count num">{l[k] === null ? DASH : l[k]}</td>)}
              {extraCell ? extraCell(l, i) : null}
            </tr>
          )
        ))}
        {foot || null}
        {group.none && !foot ? <tr class="tr-none"><td colSpan={colCount(narrow, columns, !!extraHead)} class="quiet" data-tr-nolines>{WORDS.noLines}</td></tr> : null}
        <tr class="tr-total" data-tr-total>
          <th scope="row" colSpan={narrow ? 3 : 5} class="t-what">{WORDS.total}</th>
          <td class="t-n num">{fmt(group.weight)}%</td><td class="t-n num">{fmt(group.planned)}%</td><td class="t-n num">{fmt(group.achieved)}%<Behind behind={group.behind} /></td>
          {columns.map(([k]) => <td key={k} class="t-n t-count" />)}
          {extraHead ? <td /> : null}
        </tr>
      </tbody>
    </table>
  );
}

export function GroupHalf({ group, extraCell, below, foot }) {
  return (
    <section class="tr-half" data-tr-group>
      <h3 class="tr-cap">{group.name}<span class="tr-sub num"> {fmt(group.planned)}% {WORDS.planned.toLowerCase()}, {fmt(group.achieved)}% {WORDS.achieved.toLowerCase()}<Behind behind={group.behind} /></span></h3>
      {group.none && !foot ? <p class="quiet" data-tr-nolines>{WORDS.noLines}</p> : (
        <ul class="tr-list">
          {group.lines.map((l, i) => (
            below && below(i) ? below(i) : (
              <li key={i} data-tr-line={i}>
                <span class="tr-text">{l.text}</span>
                <StatusPill status={l.status} />
                <span class="tr-nums num"><span class="sr">{WORDS.planned} </span>{fmt(l.planned)}% <span aria-hidden="true">/</span> <span class="sr">{WORDS.achieved} </span>{fmt(l.achieved)}%<Behind behind={l.behind} /></span>
                {extraCell ? extraCell(l, i) : null}
              </li>
            )
          ))}
          {foot || null}
        </ul>
      )}
    </section>
  );
}

export function Tracker({ section, slot }) {
  data.value;                                   // read, so a change to the sections draws again
  const tracker = trackerOf(section, fromFile.value);
  const t = totals(tracker);
  if (!t.groups.length && t.overall.actual === null && !t.overall.health && !t.overall.note) return null;
  const fit = fitOf(slot);
  return (
    <div class={`sec-tracker tr-${fit}`} data-tracker data-fit={fit}>
      <Overall overall={t.overall} />
      {t.groups.map((g, i) => (fit === "full" ? <GroupFull key={i} group={g} columns={columnsOf(tracker)} /> : <GroupHalf key={i} group={g} />))}
    </div>
  );
}
