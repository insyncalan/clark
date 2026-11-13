// The peek's "More actions" menu (item 658, Edit only): the row menu's peek actions in one list, Delete last in the warning colour.
// Each entry runs what its own peek button runs (PeekDuplicate, PeekArchive); Delete asks the row menu's question (deleteItem).
import { Menu } from "../components/Menu.jsx";
import { duplicateFromPeek } from "./PeekDuplicate.jsx";
import { archiveFromPeek } from "./PeekArchive.jsx";
import { deleteItem } from "./deleteItem.js";

const ITEMS = [
  { id: "duplicate", name: "Duplicate", icon: "plus" },
  { id: "archive", name: "Archive", icon: "archive" },
  { id: "sep", sep: true },
  { id: "delete", name: "Delete", icon: "trash", danger: true },
];

export function PeekMore({ row }) {
  const pick = (id) => {
    if (id === "duplicate") duplicateFromPeek(row);
    else if (id === "archive") archiveFromPeek(row);
    else if (id === "delete") { const b = document.getElementById("pk-more"); if (b) b.focus(); deleteItem(row, "peek"); }      // Cancel or Esc in the question gives the focus back to this button, not to the closing menu
  };
  return <Menu items={ITEMS} onPick={pick} icon="dots" label="" ariaLabel="More actions" tip="More actions" id="pk-more" btnCls="pkp-btn" chevron={false} menuLabel="More actions" />;
}
