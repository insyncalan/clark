// The Add button (creaite v2.6.9 `system/templates/dashboard/src/components/work/NewTile.jsx`, rewritten: creaite's tile
// opened a form and had a Record / Ask-for-a-decision menu; clark's tile says the page's own word and calls `onAdd(kind)`).
// A "+" that grows to its words on hover and on keyboard focus ("Add action", "Add milestone", "Add project", "Add use case").
// Its name and tooltip always hold the full words. With `items` it opens a menu of kinds ([{kind, word}]: Add item on Work
// items' All, Add risk or issue); with none, a click is `onAdd(kind)` at once. The words come from the caller (filters.js addPlan
// for Work items), so the word follows the type switch. Editing itself comes with #65 to #67.
import { Menu } from "./Menu.jsx";

export function NewTile({ word, kind, items, onAdd, id = "newBtn" }) {
  const list = items || [];
  return (
    <Menu label={word} ariaLabel={word} tip={word} icon="plus" labelCls="w" id={id} btnCls={`newb${list.length ? " hasmenu" : ""}`} menuId={`${id}Menu`}
      menuLabel={word} chevron={list.length > 0} items={list.map((it) => ({ id: it.kind, name: it.word }))} onPick={(k) => onAdd(k)} onClick={() => onAdd(kind)} />
  );
}
