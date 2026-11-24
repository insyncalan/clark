// The peek's Archive button (Edit only): the row menu's Archive for the item shown, so a keyboard or touch user has a route to it.
// One change, one Undo (the item is back); the peek closes with the item, as the row menu's Archive does. The request and the words
// are the row menu's own (RowMenu.jsx).
import { closePeek } from "../stores/report.js";
import { changeRecord } from "../stores/changes.js";
import { Icon } from "../components/Icon.jsx";
import { tableOf } from "./itemEdit.js";

export function PeekArchive({ row }) {
  const run = () => changeRecord({ kind: tableOf(row), op: "archive", id: row.id, place: "peek" },
    { text: `${row.id} archived. It is out of the lists and the published page.`, back: `${row.id} is back.` })
    .then((r) => { if (r) closePeek(); });
  return <button type="button" class="pkp-btn" data-pk-archive title="Archive" aria-label="Archive" onClick={run}><Icon name="archive" /></button>;
}
