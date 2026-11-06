// The 'Progress tracker' section as a reader sees it (#189): an overall tile (Achieved against Planned in a bar, a status chip and a line of the
// words), then each group of plan lines with its own total. Full draws a table (number, description, dates, status, weight,
// planned, achieved, and the optional counts); Half draws the bar and a short list (description, status, planned, achieved, no dates).
// It draws in View and in a published file, view only (no input, no button); Edit draws edit/TrackerEdit.jsx in its place, with the
// same pieces below. A line behind plan carries "▼ n" and, for a screen reader, the words, so colour is never the only signal.
// Every value is a text node: nothing the section holds is read as markup. The sums come from logic/tracker.js and are never stored.
import { useEffect, useState } from "preact/hooks";
import { data, fromFile } from "../stores/report.js";
import { showDate } from "../workItems.js";
import { trackerOf, totals, fill, fmt, lineFill, markEdge, statusWord, healthWord, behindWords, COLUMNS, WORDS } from "../logic/tracker.js";

const DASH = "—";
const HEALTH_PILL = { ontrack: "g", atrisk: "a", offtrack: "r" };
const STATUS_PILL = { planned: "n", inprogress: "v", completed: "g", late: "r" };

// A fit's name from the slot the section sits in: only a whole row is Full.
export const fitOf = (slot) => (slot === "full" ? "full" : "half");

export const StatusPill = ({ status }) => <span class={`pill ${STATUS_PILL[status] || "n"} tr-status`}>{statusWord(status)}</span>;

// "▼ 5" and, for a screen reader, "5 points behind plan"; nothing when the line is not behind.
export const Behind = ({ behind }) => (behind > 0
  ? <span class="tr-behind" title={behindWords(behind)}><span aria-hidden="true">▼ {fmt(behind)}</span>{" "}<span class="sr">{behindWords(behind)}</span></span>
  : null);

// The Overall part, as the approved tile (#930): one tinted tile with the two figures (Achieved and Planned), the bar with a "Planned n%"
// label over the mark and a 0% to 100% scale under it, then the status chip and the words. The chip is the author's pick when there is
// one, else what the rule gives from the gap (logic/tracker.js healthRule); the words are the owner's own (the overall's note) when
// there are any, else the automatic words. `size` is the tracker's template setting (Large, Medium, Small, Compact). In Edit, `words`
// replaces the words with the field that edits them in place (edit/TrackerWords.jsx); View and a published file draw them as text.
// The bar says it in words to a screen reader; the label and the scale are drawn for the eye only.
export function Overall({ overall, size = "medium", words = null }) {
  const { actual, planned, shownHealth, note, auto } = overall;
  const pct = (t) => (t === null ? DASH : `${fmt(t)}%`);
  const label = actual === null ? WORDS.none : `${WORDS.actual} ${pct(actual)}${planned === null ? "" : `, ${WORDS.planned.toLowerCase()} ${pct(planned)}`}`;
  const edge = planned === null ? "" : markEdge(planned);
  const said = note || auto;
  return (
    <div class={`tr-overall tr-size-${size}`} data-tr-overall data-size={size}>
      <div class="tr-tile" data-tr-tile>
        <div class="tr-nums">
          <div class="tr-fig"><span class="tr-k">{WORDS.actual}</span>{" "}<span class="tr-v num" data-tr-actual>{pct(actual)}</span></div>
          <div class="tr-fig tr-fig-planned"><span class="tr-k">{WORDS.planned}</span>{" "}<span class="tr-v num" data-tr-planned>{pct(planned)}</span></div>
        </div>
        <div class="tr-side">
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
          {shownHealth || said || words ? (
            <div class="tr-stat">
              {shownHealth ? <span class={`pill ${HEALTH_PILL[shownHealth]} tr-pill tr-chip`} data-tr-health>{healthWord(shownHealth)}</span> : null}
              {words || (said ? <span class="tr-words" data-tr-words title={said}>{said}</span> : null)}
            </div>
          ) : null}
        </div>
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

export function GroupFull({ group, columns: shown, extraHead, extraCell, below, foot, empty = WORDS.noLines }) {
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
        {group.none && !foot ? <tr class="tr-none"><td colSpan={colCount(narrow, columns, !!extraHead)} class="quiet" data-tr-nolines>{empty}</td></tr> : null}
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

export function GroupHalf({ group, extraCell, below, foot, empty = WORDS.noLines }) {
  return (
    <section class="tr-half" data-tr-group>
      <h3 class="tr-cap">{group.name}<span class="tr-sub num"> {fmt(group.planned)}% {WORDS.planned.toLowerCase()}, {fmt(group.achieved)}% {WORDS.achieved.toLowerCase()}<Behind behind={group.behind} /></span></h3>
      {group.none && !foot ? <p class="quiet" data-tr-nolines>{empty}</p> : (
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
      <Overall overall={t.overall} size={tracker.size} />
      {t.groups.map((g, i) => (fit === "full" ? <GroupFull key={i} group={g} columns={columnsOf(tracker)} /> : <GroupHalf key={i} group={g} />))}
    </div>
  );
}
