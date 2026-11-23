// Row 1277: when the Use cases rows box refits. The window's resize event can arrive after the rows already have their new layout (slow on macOS), and a late font swap changes row heights with no resize at all.
// So it also refits when the box or a row changes size (ResizeObserver) and when the fonts are ready. Returns a function that stops all three.
// again() clears the remembered closed heights and refits (the window or the fonts changed). soft() refits and keeps them: a row opening or closing
// fires the observer, and an open row's closed height is only in that memory, so clearing it there would drop the row from the fit and move the box.
export function watchRefit(win, doc, ul, again, soft) {
  let live = true;
  const go = (e) => { if (live) again(e); };       // again(event) for the resize event, again() for the fonts
  const near = () => { if (live) (soft || again)(); };
  win.addEventListener("resize", go);
  let ro = null;
  if (typeof win.ResizeObserver === "function" && ul) {
    ro = new win.ResizeObserver(near);
    ro.observe(ul);
    [...ul.children].forEach((r) => ro.observe(r));
  }
  if (doc && doc.fonts && doc.fonts.ready && doc.fonts.status !== "loaded") doc.fonts.ready.then(() => go(), () => {});       // the effect re-runs on every render (a row opening): fonts already loaded changed nothing
  return () => { live = false; win.removeEventListener("resize", go); if (ro) ro.disconnect(); };
}
