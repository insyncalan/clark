// The "More actions" menu of a use case or a milestone (item 1148, Edit only): Archive, then Delete last in the warning colour, as a work item's has
// (PeekMore.jsx). Delete asks the same question and takes the same step (deleteItem), and a record something points at is refused by name.
// A use case's row on the Use cases page and its own page carry it, and so do a milestone's row on the Milestones page and its peek.
import { Menu } from "../components/Menu.jsx";
import { change } from "../stores/changes.js";
import { deleteItem } from "./deleteItem.js";
import { archiveFromPeek } from "./PeekArchive.jsx";

const ITEMS = [
  { id: "archive", name: "Archive", icon: "archive" },
  { id: "sep", sep: true },
  { id: "delete", name: "Delete", icon: "trash", danger: true },
];

/** `kind`: "use_cases" or "milestones". `place`: "cell" (a row, a page) or "peek". `onArchived`/`onDeleted`: what the page does after the step. */
export function RecordMore({ row, kind, place = "cell", cls = "ib", id, tab, fixed = true, onArchived, onDeleted }) {
  const mid = id || `rec-more-${row.id}`;
  const pick = (what) => {
    if (what === "archive") {
      if (kind === "milestones") archiveFromPeek(row, true);
      else change({ kind, op: "archive", id: row.id, place }, "Use case archived. It can be restored.").then((r) => { if (r && onArchived) onArchived(r); });
    } else if (what === "delete") {
      const b = document.getElementById(mid); if (b) b.focus();      // Cancel or Esc in the question gives the focus back to this button, not to the closing menu
      deleteItem(row, place, null, kind, onDeleted);
    }
  };
  return <Menu items={ITEMS} onPick={pick} icon="dots" label="" ariaLabel="More actions" tip="More actions" id={mid} btnCls={cls} chevron={false} menuLabel="More actions" fixed={fixed} tab={tab} />;
}
