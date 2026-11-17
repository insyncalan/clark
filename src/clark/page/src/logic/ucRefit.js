// Row 1277: when the Use cases rows box refits. The window's resize event can arrive after the rows already have their new layout (slow on macOS), and a late font swap changes row heights with no resize at all.
// So it also refits when the box or a row changes size (ResizeObserver) and when the fonts are ready. Returns a function that stops all three.
export function watchRefit(win, doc, ul, again) {
  let live = true;
  const go = () => { if (live) again(); };
  win.addEventListener("resize", go);
  let ro = null;
  if (typeof win.ResizeObserver === "function" && ul) {
    ro = new win.ResizeObserver(go);
    ro.observe(ul);
    [...ul.children].forEach((r) => ro.observe(r));
  }
  if (doc && doc.fonts && doc.fonts.ready) doc.fonts.ready.then(go, () => {});
  return () => { live = false; win.removeEventListener("resize", go); if (ro) ro.disconnect(); };
}
