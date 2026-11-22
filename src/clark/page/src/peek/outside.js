// A click outside the peek closes it (row 814), as Esc does. What does not: a press inside the peek, on a row, card or item link
// (those move the peek to another item, row 1467: also the Dashboard's table rows, milestone rows and the use case page's steps and items), an archived peek or archived row (they replace it), or inside a menu, a list of choices, a dialog or a toast that stands over the page.
const KEEPS = "#peek, .pk-arch, tr[data-arch-id], [role=menu], [role=listbox], [role=dialog], [role=alertdialog], dialog, .toast, #work tr[data-id], #work article[data-id], .wl-row, .wil-table tr[data-id], .msl-row, [data-step], [data-stepid], [data-item], [data-ms-open], .idl, [data-open]";      // row 1467: a Dashboard table row, a milestone row and a use case page step or item open a peek too: they switch it

/** True when a press that began on `target` is a click outside the peek that should close it. */
export function closesPeek(target) {
  return !!target && target.nodeType === 1 && target.isConnected && !target.closest(KEEPS);
}
