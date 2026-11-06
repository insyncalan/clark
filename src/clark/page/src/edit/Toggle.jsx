// View or Edit, in the top bar (on the Dashboard, a pill at the left of the report bar: ReportBar draws it, TopBar then does not).
// Only a page that clark serves has it: a published file has no Edit button. Switching changes
// what is drawn and nothing else: no reload, no address change, no history entry, nothing saved. On the Dashboard the plain keys V
// and E do the same (keys.js, listened for from boot, so the key works whichever bar draws the switch).
import { mode, data } from "../stores/report.js";
import { singleKeys } from "../stores/keyPrefs.js";
import { useEffect, useLayoutEffect, useRef } from "preact/hooks";

// row 884: where the pill's thumb sits (the pressed button, measured from the View button), so the stylesheet can slide it.
function measure(el) {
  const v = el && el.querySelector('[data-mode="view"]'), on = el && el.querySelector('[aria-pressed="true"]');
  if (!v || !on || !v.offsetWidth) return;
  el.style.setProperty("--vw", v.offsetWidth + "px");
  el.style.setProperty("--tx", (on.offsetLeft - v.offsetLeft) + "px");
  el.style.setProperty("--sx", String(on.offsetWidth / v.offsetWidth));
}

export function Toggle({ pill }) {      // pill: the Dashboard's, drawn at the left of the report bar (#665); otherwise the top bar's
  const box = useRef(null), watch = useRef({ el: null, ro: null });
  useLayoutEffect(() => {       // on each render, and again when the pill or its buttons change size (a resize, a late font) or the fonts load
    if (!pill) return;
    const el = box.current;
    measure(el);
    if (el === watch.current.el) return;
    if (watch.current.ro) watch.current.ro.disconnect();
    watch.current = { el, ro: null };
    if (!el) return;
    if (typeof ResizeObserver === "function") {
      const ro = new ResizeObserver(() => measure(box.current));
      ro.observe(el);
      el.querySelectorAll(".mode").forEach((b) => ro.observe(b));
      watch.current.ro = ro;
    }
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => measure(box.current));
  });
  useEffect(() => () => { if (watch.current.ro) watch.current.ro.disconnect(); }, []);
  if (!data.value) return null;       // row 826: Settings has no switch, with a project or without (Add project needs no mode)
  const editing = mode.value === "edit";
  return (
    <span class={pill ? "modes seg glide" : "modes"} ref={box} role="group" aria-label="View or Edit">
      <button type="button" class="mode" data-mode="view" title={singleKeys.value ? "View (V)" : "View"} aria-keyshortcuts={singleKeys.value ? "V" : undefined} aria-pressed={editing ? "false" : "true"} onClick={() => { mode.value = "view"; }}>View</button>
      <button type="button" class="mode" data-mode="edit" title={singleKeys.value ? "Edit (E)" : "Edit"} aria-keyshortcuts={singleKeys.value ? "E" : undefined} aria-pressed={editing ? "true" : "false"} onClick={() => { mode.value = "edit"; }}>{pill ? <svg class="tb-ico" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M13.5 3.5l3 3L7 16H4v-3z" /></svg> : null}Edit</button>
    </span>
  );
}
