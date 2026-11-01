// The 'Needs from you' section as a reader sees it (#121): a table of what is needed, from whom and by when. It draws in View and in a
// published file, view only (no input, no button); Edit draws edit/NeedsEdit.jsx in its place. A row that is left out is not drawn, and
// a date before today (a published file reads "today" as the day it was published) carries the word Overdue as well as its colour.
// Every value is a text node: nothing the section holds is read as markup.
import { data, asAt, fromFile } from "../stores/report.js";
import { todayIso } from "../workItems.js";
import { rowsOf, shownRows, dueOf, kindWord, WORDS } from "../logic/needs.js";

const DASH = "—";

// Today for the section: the day a file was published, or the clock's day on the page clark serves.
export const needsToday = () => (fromFile.value && asAt.value ? asAt.value : todayIso());

export function NeedsTable({ rows, today }) {
  return (
    <table class="needs">
      <thead>
        <tr><th scope="col" class="n-what">{WORDS.what}</th><th scope="col" class="n-from">{WORDS.from}</th><th scope="col" class="n-by">{WORDS.by}</th></tr>
      </thead>
      <tbody>
        {rows.map((r, i) => {
          const due = dueOf(r, today);
          return (
            <tr key={i}>
              <td class="n-what"><span class="tag n-kind">{kindWord(r.kind)}</span> <span class="n-text">{r.what}</span></td>
              <td class="n-from">{r.from || DASH}</td>
              <td class="n-by num">{r.by ? due.text : <span class="muted">{DASH}</span>}{due.overdue ? <> <span class="pill r n-over">{WORDS.overdue}</span></> : null}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export function Needs({ section }) {
  data.value;                                   // read, so a change to the sections draws again
  const rows = shownRows(rowsOf(section, fromFile.value));
  if (!rows.length) return null;
  return <div class="sec-needs" data-needs><NeedsTable rows={rows} today={needsToday()} /></div>;
}
