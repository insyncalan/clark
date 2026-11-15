// The right-click menu of a record's row (row 1203, the Use cases page): Archive, then Delete last in the warning colour, the same two steps as
// the More actions button's (RecordMore.jsx). Opened by a right click, the menu key or Shift+F10 on the row; Esc closes it with the focus back on the row's name.
import { MenuPanel } from "../components/Menu.jsx";
import { Icon } from "../components/Icon.jsx";
import { RECORD_ITEMS, recordPick } from "./RecordMore.jsx";

/** `at`: { row, x, y, from } (the record, the point, the element that takes the focus back); `kind`: "use_cases"; `onClose`: called with nothing. */
export function RecordContextMenu({ at, kind, onClose }) {
  const anchor = { getBoundingClientRect: () => ({ left: at.x, right: at.x, top: at.y, bottom: at.y, width: 0, height: 0 }), contains: () => false, matches: () => false };
  const shut = (why) => {
    onClose();
    if (why === "esc" || why === "tab") setTimeout(() => { if (at.from && at.from.isConnected) at.from.focus({ preventScroll: true }); }, 0);
  };
  const pick = (what) => { shut("pick"); recordPick(what, at.row, kind, "cell", at.from); };
  return (
    <MenuPanel label="Use case actions" id="ucl-ctx" anchor={anchor} fixed="start" onClose={shut}>
      {RECORD_ITEMS.map((it) => it.sep ? <div key={it.id} class="sep" role="separator"></div> : (
        <button key={it.id} type="button" class={it.danger ? "danger" : undefined} role="menuitem" tabIndex={-1} data-kind={it.id} onClick={() => pick(it.id)}>{it.icon ? <Icon name={it.icon} cls="mi" /> : null}{it.name}</button>
      ))}
    </MenuPanel>
  );
}
