// The 'Progress tracker' section as a reader sees it (#189): an overall bar (Actual against Planned, a health pill and a line of the
// owner's words), then each group of plan lines with its own total. Full draws a table (number, description, dates, status, weight,
// planned, achieved, and the optional counts); Half draws the bar and a short list (description, status, planned, achieved, no dates).
// It draws in View and in a published file, view only (no input, no button); Edit draws edit/TrackerEdit.jsx in its place, with the
// same pieces below. A line behind plan carries "▼ n" and, for a screen reader, the words, so colour is never the only signal.
// Every value is a text node: nothing the section holds is read as markup. The sums come from logic/tracker.js and are never stored.
import { data, fromFile } from "../stores/report.js";
import { showDate } from "../workItems.js";
import { trackerOf, totals, fill, fmt, statusWord, healthWord, behindWords, COLUMNS, WORDS } from "../logic/tracker.js";

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

export function Overall({ overall }) {
  const { actual, planned, health, note, behind, behindWords: said } = overall;
  const pct = (t) => (t === null ? DASH : `${fmt(t)}%`);
  const label = actual === null ? WORDS.none : `${WORDS.actual} ${pct(actual)}${planned === null ? "" : `, ${WORDS.planned.toLowerCase()} ${pct(planned)}`}`;
  return (
    <div class="tr-overall" data-tr-overall>
      <div class="tr-figs">
        <div class="tr-fig"><span class="tr-k">{WORDS.actual}</span><span class="tr-v num" data-tr-actual>{pct(actual)}</span></div>
        <div class="tr-fig"><span class="tr-k">{WORDS.planned}</span><span class="tr-v num" data-tr-planned>{pct(planned)}</span></div>
        {health || note ? (
          <div class="tr-health">
            {health ? <span class={`pill ${HEALTH_PILL[health]} tr-pill`} data-tr-health>{healthWord(health)}</span> : null}
            {note ? <span class="tr-note">{note}</span> : null}
          </div>
        ) : null}
      </div>
      <div class="tr-bar" role="img" aria-label={label}>
        <span class="tr-fill" style={{ width: `${fill(actual) / 10}%` }} />
        {planned !== null ? <span class="tr-mark" style={{ left: `${fill(planned) / 10}%` }} /> : null}
      </div>
      {said ? <p class="tr-behindline" data-tr-behind>{said}</p> : null}
    </div>
  );
}

// The columns a Full table draws: the fixed ones, then the counts the owner switched on.
export const columnsOf = (tracker) => COLUMNS.filter(([k]) => tracker.columns[k]);

export function GroupFull({ group, columns, extraHead, extraCell, below, foot }) {
  return (
    <table class="tracker tr-full" data-tr-group>
      <caption class="tr-cap">{group.name}</caption>
      {/* The narrow width collapses the date and count columns (visibility: collapse on the col), so every row's colSpan stays right. */}
      <colgroup>
        <col class="c-no" /><col class="c-what" /><col class="c-date" /><col class="c-date" /><col class="c-status" /><col class="c-n" /><col class="c-n" /><col class="c-n" />
        {columns.map(([k]) => <col key={k} class="c-n c-count" />)}
        {extraHead ? <col class="c-tools" /> : null}
      </colgroup>
      <thead>
        <tr>
          <th scope="col" class="t-no">{WORDS.no}</th><th scope="col" class="t-what">{WORDS.what}</th>
          <th scope="col" class="t-date">{WORDS.start}</th><th scope="col" class="t-date">{WORDS.end}</th><th scope="col" class="t-status">{WORDS.status}</th>
          <th scope="col" class="t-n">{WORDS.weight}</th><th scope="col" class="t-n">{WORDS.planned}</th><th scope="col" class="t-n">{WORDS.achieved}</th>
          {columns.map(([k, w]) => <th key={k} scope="col" class="t-n t-count">{w}</th>)}
          {extraHead || null}
        </tr>
      </thead>
      <tbody>
        {group.lines.map((l, i) => (
          below && below(i) ? below(i) : (
            <tr key={i} data-tr-line={i}>
              <td class="t-no">{l.no || DASH}</td><td class="t-what">{l.text}</td>
              <td class="t-date num">{l.start ? showDate(l.start) : DASH}</td><td class="t-date num">{l.end ? showDate(l.end) : DASH}</td>
              <td class="t-status"><StatusPill status={l.status} /></td>
              <td class="t-n num">{fmt(l.weight)}%</td>
              <td class="t-n num">{fmt(l.planned)}%</td>
              <td class="t-n num">{fmt(l.achieved)}%<Behind behind={l.behind} /></td>
              {columns.map(([k]) => <td key={k} class="t-n t-count num">{l[k] === null ? DASH : l[k]}</td>)}
              {extraCell ? extraCell(l, i) : null}
            </tr>
          )
        ))}
        {foot || null}
        {group.none && !foot ? <tr class="tr-none"><td colSpan={8 + columns.length + (extraHead ? 1 : 0)} class="quiet" data-tr-nolines>{WORDS.noLines}</td></tr> : null}
        <tr class="tr-total" data-tr-total>
          <th scope="row" colSpan={5} class="t-what">{WORDS.total}</th>
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
      {t.weightsNote ? <p class="quiet tr-weights" data-tr-weights>{t.weightsNote}</p> : null}
    </div>
  );
}
