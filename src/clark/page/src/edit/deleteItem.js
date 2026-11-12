// Delete one work item (item 658), from the row menu and from the peek: the question first (Delete / Cancel), then one step that removes the item
// with its links and labels, and a toast "<ID> deleted." with Undo. Cancel changes nothing. The words are in ../logic/rowMenu.js.
import { closePeek, item as peeked } from "../stores/report.js";
import { changeRecord } from "../stores/changes.js";
import { tableOf } from "./itemEdit.js";
import { ask } from "./Bulk.jsx";
import { deleteQuestion, deleteWords, deleteRequest } from "../logic/rowMenu.js";

/** Ask, and on Delete send the step. `place`: "menu" or "peek". A refusal is said in the toast, and nothing changes. */
export function deleteItem(row, place, from = null) {
  ask(deleteQuestion(row.id), () => {
    const w = deleteWords(row.id);
    changeRecord(deleteRequest(row.id, tableOf(row), place), { text: w.text, back: w.back, focusUndo: true })
      .then((r) => { if (r && peeked.value === row.id) closePeek(); });
  }, { from, yesLabel: "Delete" });
}
