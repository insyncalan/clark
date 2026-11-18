// The peek's Archive step (More actions, Edit only): the row menu's Archive for the item shown, so a keyboard or touch user has a route to it.
// One change, one Undo (the item is back); the peek closes with the item, as the row menu's Archive does. The request and the words
// are the row menu's own (RowMenu.jsx).
import { closePeek } from "../stores/report.js";
import { changeRecord } from "../stores/changes.js";
import { tableOf } from "./itemEdit.js";

// The archive step with its words, shared by the button and the "More actions" menu (PeekMore.jsx).
export function archiveFromPeek(row, milestone = false) {      // row 867: the milestone peek has the same button and words
  // Row 1054: the milestone peek closes with its item, so focus would drop to the page; it goes to the next row, or to the toast's Undo.
  const nextId = () => { const mine = milestone && document.querySelector(`li.msl-row[data-ms="${row.id}"]`); const n = mine && mine.nextElementSibling; return n ? n.getAttribute("data-ms") : ""; };
  const settle = (next) => setTimeout(() => {
    const cell = next && document.querySelector(`li.msl-row[data-ms="${next}"] .msl-cells`);
    const el = cell || document.querySelector(".toast [data-undo]");
    if (el) el.focus();
  }, 0);
  const run = () => { const next = nextId(); return changeRecord({ kind: milestone ? "milestones" : tableOf(row), op: "archive", id: row.id, place: "peek" },
    { text: `${row.id} archived. It is out of the lists and the published page.`, back: `${row.id} is back.`, focusUndo: !(milestone && next),
      // after Undo the focus goes to the restored row, as the row menu does
      focus: `tr[data-id="${CSS.escape(row.id)}"], article.bcard[data-id="${CSS.escape(row.id)}"] .bc-main` })
    .then((r) => { if (r) { if (milestone) settle(next); closePeek(); } }); };
  return run();
}
