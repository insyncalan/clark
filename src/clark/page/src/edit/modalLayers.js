// What a modal dialog does to the rest of the page (#425): everything outside the dialog is made `inert` while it is open, so Tab,
// a screen reader and a click cannot reach the page, the peek, the ask panel, Help, the palette or a button on a toast behind it.
// `inertBehind(el)` walks up from the dialog to the page root (#app) and marks every sibling on the way, so it does not matter where
// the dialog is mounted. It gives back a function that undoes exactly what that call did:
//   - an element that was already inert (another part of the page, such as the closed contents list) is left alone, both ways;
//   - an element another open dialog made inert stays inert until the last of the dialogs holding it has closed.
// The toast region (.toasts) stays live so a screen reader still hears what the page says; the toasts already in it (they carry
// Undo and Close buttons) are made inert, and so is one that arrives while the dialog is open (a MutationObserver, disconnected on release).
const held = new Map();                                   // element -> how many open dialogs have it inert; only what this file made inert is here
const SKIP = /^(SCRIPT|STYLE|LINK|TEMPLATE|META)$/;

function behind(dialog) {
  const top = document.getElementById("app") || document.body;
  const out = [];
  let node = dialog;
  if (top.contains(dialog)) {
    while (node && node !== top) {
      const up = node.parentElement;
      if (!up) break;
      for (const sib of up.children) if (sib !== node) out.push(sib);
      node = up;
    }
  } else {
    out.push(...top.children);
  }
  const all = [];
  for (const el of out) {
    if (SKIP.test(el.tagName) || el.contains(dialog)) continue;
    if (el.matches(".toasts")) all.push(...el.querySelectorAll(".toast"));
    else all.push(el);
  }
  return all;
}

function regions(dialog) {                                // the live toast regions outside the dialog
  const top = document.getElementById("app") || document.body;
  return [...top.querySelectorAll(".toasts")].filter((r) => !r.contains(dialog));
}

export function inertBehind(dialog) {
  const mine = new Set();
  const take = (el) => {
    if (held.has(el)) { held.set(el, held.get(el) + 1); mine.add(el); }
    else if (!el.hasAttribute("inert")) { el.setAttribute("inert", ""); held.set(el, 1); mine.add(el); }
  };
  for (const el of behind(dialog)) take(el);
  // A toast that arrives while the dialog is open is made inert too; one that is removed stops being tracked.
  const watch = new MutationObserver((records) => {
    for (const rec of records) {
      for (const n of rec.addedNodes) if (n.nodeType === 1 && n.matches(".toast")) take(n);
      for (const n of rec.removedNodes) if (mine.delete(n)) held.delete(n);
    }
  });
  for (const r of regions(dialog)) watch.observe(r, { childList: true });
  let done = false;
  return () => {
    if (done) return;
    done = true;
    watch.disconnect();
    for (const el of mine) {
      const n = (held.get(el) || 1) - 1;
      if (n > 0) held.set(el, n);
      else { held.delete(el); el.removeAttribute("inert"); }
    }
  };
}
