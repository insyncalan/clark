// The Classic theme's left Contents column (row 1318): the visible sections as a list beside the report, the current one marked while the
// page scrolls. It uses the same entries and scroll rule as the Minimap (logic/minimap.js), so the two always agree; the Minimap itself is
// the Cards theme's navigation and is not drawn in Classic. The entries are buttons, never #links, so the address is never touched.
// Fewer than two sections draw nothing. The look is in the theme's rules.css (the block for row 1318); a page with no Theme draws none of this.
import { useState, useEffect, useRef } from "preact/hooks";
import { entries, activeEntry, clickLock } from "../logic/minimap.js";

// A Theme's CSS is layered in <style id="theme"> (page.layer_theme); with no Theme (Cards) the element is absent.
export const classicTheme = () => typeof document !== "undefined" && !!document.getElementById("theme");

function measure(list) {
  return list.flatMap((e) => {
    const el = document.getElementById(e.anchor);
    return el ? [{ id: e.id, top: el.getBoundingClientRect().top + window.scrollY }] : [];
  });
}

export function Contents({ sections, hiddenSections, onJump, stickyHeight = 0 }) {
  const list = entries(sections, hiddenSections);
  const [current, setCurrent] = useState(null);
  const lock = useRef(null);
  if (!lock.current) lock.current = clickLock();
  useEffect(() => {
    const spy = () => setCurrent(lock.current.get() || activeEntry(measure(list), window.scrollY, window.innerHeight, typeof stickyHeight === "function" ? stickyHeight() : stickyHeight, document.documentElement.scrollHeight));
    spy();
    window.addEventListener("scroll", spy, { passive: true });
    window.addEventListener("resize", spy);
    return () => { window.removeEventListener("scroll", spy); window.removeEventListener("resize", spy); };
  }, [list.map((e) => e.anchor).join("|"), stickyHeight]);
  useEffect(() => () => lock.current.release(), []);     // the mark is let go on unmount or on the reader's own input, never because the anchors or the sticky height changed
  if (list.length < 2) return null;
  return (
    <nav class="cnt" aria-label="Contents">
      <div class="cnt-h">Contents</div>
      <ul>
        {list.map((e) => (
          <li key={e.id}>
            <a href={`#${e.anchor}`} data-entry={e.id} class={e.id === current ? "on" : ""} aria-current={e.id === current ? "true" : undefined} onClick={(ev) => { ev.preventDefault(); lock.current.hold(e.id); setCurrent(e.id); onJump(e.id); }}>{e.title}</a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
