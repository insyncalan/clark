// Row 1219: scrolling over a panel that sits over the page only ever scrolls the panel, never the page behind it.
// CSS (overscroll-behavior-y: contain on the panel's scrolling areas) does it for a panel that scrolls; a panel that does not
// overflow, or one that has reached its top or bottom in some browsers, hands the scroll on, so these handlers stop it as well.
// Sideways wheel movement (the Back and Forward swipe, item 1136) is never touched, and neither is a scroll inside a scroller
// that can still move that way.

const EDITABLE = "input, textarea, select, [contenteditable], [role=separator], [role=slider], [role=listbox], [role=menu], [role=tab]";
const PRESSABLE = "button, a[href], summary, [role=button]";

function scrolls(el, dy) {
  const cs = getComputedStyle(el);
  if (!/auto|scroll/.test(cs.overflowY) || el.scrollHeight <= el.clientHeight + 1) return false;
  return dy < 0 ? el.scrollTop > 0 : el.scrollTop + el.clientHeight < el.scrollHeight - 1;
}

// Is there a scroller between `from` and `panel` (the panel included) that can still move in the direction `dy`?
function canMove(from, panel, dy) {
  for (let e = from; e && e.nodeType === 1; e = e.parentElement) {
    if (scrolls(e, dy)) return true;
    if (e === panel) break;
  }
  return false;
}

// The scroller a key should move: the nearest one around the target, else the first shown one inside the panel.
function keyScroller(from, panel) {
  const can = (e) => /auto|scroll/.test(getComputedStyle(e).overflowY) && e.scrollHeight > e.clientHeight + 1;
  for (let e = from; e && e.nodeType === 1; e = e.parentElement) { if (can(e)) return e; if (e === panel) break; }
  return [...panel.querySelectorAll("*")].find((e) => e.offsetParent !== null && can(e)) || null;
}

export function holdScroll(panel, { keys: withKeys = true } = {}) {
  if (!panel || panel.__held) return undefined;
  panel.__held = true;
  let y0 = 0;
  const wheel = (e) => {
    if (e.ctrlKey || Math.abs(e.deltaX) > Math.abs(e.deltaY) || !e.deltaY) return;   // a pinch, or a sideways swipe: not ours
    if (!canMove(e.target, panel, e.deltaY)) e.preventDefault();
  };
  const start = (e) => { y0 = e.touches && e.touches[0] ? e.touches[0].clientY : 0; };
  const move = (e) => {
    if (!e.cancelable || !e.touches || !e.touches[0] || e.touches.length > 1) return;
    const dy = y0 - e.touches[0].clientY;      // finger up = content moves down
    if (dy && !canMove(e.target, panel, dy)) e.preventDefault();
  };
  const keys = (e) => {
    const k = e.key;
    if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey) return;
    if (![" ", "PageUp", "PageDown", "Home", "End", "ArrowUp", "ArrowDown"].includes(k)) return;
    const t = e.target;
    if (t && t.closest && (t.closest(EDITABLE) || (k === " " && t.closest(PRESSABLE)))) return;
    e.preventDefault();                          // the page behind never takes the key
    const s = keyScroller(t, panel);
    if (!s) return;
    const page = Math.max(40, s.clientHeight * 0.9), up = k === "PageUp" || k === "ArrowUp" || (k === " " && e.shiftKey);
    if (k === "Home") s.scrollTop = 0;
    else if (k === "End") s.scrollTop = s.scrollHeight;
    else s.scrollTop += (up ? -1 : 1) * (k === "ArrowUp" || k === "ArrowDown" ? 40 : page);
  };
  panel.addEventListener("wheel", wheel, { passive: false });
  panel.addEventListener("touchstart", start, { passive: true });
  panel.addEventListener("touchmove", move, { passive: false });
  if (withKeys) panel.addEventListener("keydown", keys);
  return () => {
    panel.removeEventListener("wheel", wheel); panel.removeEventListener("touchstart", start);
    panel.removeEventListener("touchmove", move); panel.removeEventListener("keydown", keys); panel.__held = false;
  };
}
