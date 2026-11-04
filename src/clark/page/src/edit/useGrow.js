// One shared way for a text box to size itself (item 660). Opens at three lines, grows as the person types and always keeps one blank
// line below the last one; it shrinks as text is deleted, down to the three lines. The corner handle (CSS resize) is the person's own
// say: once they drag it the box is marked data-sized and stays as they set it until its text is emptied or it is opened again.
import { useLayoutEffect, useRef } from "preact/hooks";

const LINES = 3;

export function fitGrow(el) {
  if (!el) return;
  if (el.dataset.sized) { if (el.value || el.textContent) return; delete el.dataset.sized; }
  if (!el.getClientRects().length) return;                    // hidden: measure again when it is shown
  const cs = getComputedStyle(el);
  const size = parseFloat(cs.fontSize) || 16;
  const line = parseFloat(cs.lineHeight) || size * 1.2;
  const box = cs.boxSizing === "border-box";
  const pad = (parseFloat(cs.paddingTop) || 0) + (parseFloat(cs.paddingBottom) || 0);
  const edge = (parseFloat(cs.borderTopWidth) || 0) + (parseFloat(cs.borderBottomWidth) || 0);
  el.style.minHeight = "0px";
  el.style.height = "0px";
  const content = el.scrollHeight;
  if (!content) { el.style.height = ""; el.style.minHeight = ""; return; }
  const floor = LINES * line + (box ? pad + edge : 0);
  const want = Math.max(floor, content - pad + line + (box ? pad + edge : 0));
  el.style.height = `${Math.ceil(want)}px`;
  el.style.minHeight = `${Math.ceil(floor)}px`;
  el.dataset.last = String(el.offsetHeight);
  const max = parseFloat(cs.maxHeight);
  el.style.overflowY = max && el.offsetHeight >= max - 1 ? "auto" : "hidden";
}

export function useGrow(ref, value) {
  const cur = useRef({ el: null, off: null });
  // Runs after every draw: a box that is drawn later (opened on a click) gets its listeners when it appears.
  useLayoutEffect(() => {
    const el = ref.current, c = cur.current;
    if (el === c.el) return;
    if (c.off) c.off();
    c.el = el; c.off = null;
    if (!el) return;
    const fit = () => fitGrow(el);
    const up = () => { if (Math.abs(el.offsetHeight - Number(el.dataset.last || 0)) > 2) el.dataset.sized = "1"; };
    let width = 0;
    const watch = typeof ResizeObserver === "function" ? new ResizeObserver(() => { if (el.clientWidth !== width) { width = el.clientWidth; fit(); } }) : null;
    el.addEventListener("input", fit);
    el.addEventListener("focus", fit);
    el.addEventListener("pointerup", up);
    window.addEventListener("resize", fit);
    if (watch) watch.observe(el);
    c.off = () => {
      el.removeEventListener("input", fit); el.removeEventListener("focus", fit); el.removeEventListener("pointerup", up);
      window.removeEventListener("resize", fit); if (watch) watch.disconnect();
    };
    fit();
  });
  useLayoutEffect(() => () => { if (cur.current.off) cur.current.off(); }, []);
  useLayoutEffect(() => { fitGrow(ref.current); }, [value]);
}
