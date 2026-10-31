// Where keyboard focus goes once a change has been made and the sections redrawn. A moved section keeps its element (the list is
// keyed), but the browser can still drop focus when a node is moved, so the control that had focus gets it back: `keep` runs after
// the change has settled and the new order is drawn (a timer after the redraw's own microtask). A change that failed also gets
// its focus put back, so a person is not left at the top of the page.
const SELECTOR = { handle: "[data-drag]", options: "[data-options]", title: "[data-title]" };

function put(id, part) {
  const el = document.querySelector(`.secs > .sec[data-id="${id}"] ${SELECTOR[part]}`);
  if (!el) return;
  el.focus();
  if (part === "title" && window.getSelection) {         // a new section's title is selected, ready to be typed over
    if (el.select) el.select();
    else { const r = document.createRange(); r.selectNodeContents(el); const s = getSelection(); s.removeAllRanges(); s.addRange(r); }
  }
}

// Wait for `promise` (a change, resolving to its reply or null), then focus `part` of section `id`; id "new" means the section
// the reply made. Resolves to the same reply.
export function keep(promise, id, part) {
  return promise.then((reply) => {
    const target = id === "new" ? (reply && reply.ref) : id;
    if (target) setTimeout(() => put(target, part), 0);
    return reply;
  });
}
