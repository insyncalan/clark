// The contents minimap (FR-18): short lines at the right edge; hovering or focusing it opens the list of visible sections,
// Esc or leaving closes it, a click calls onJump(id). It tracks the scroll to show the current section. The caller puts
// id={entry.anchor} (entries() in logic/minimap.js) on each section. The entries are buttons, not #links, so the address
// (and the router that reads it) is never touched; onJump scrolls the page, or with no onJump the section's anchor is scrolled to.
// At 900 px and narrower (A-D20, #141) the lines give way to an "On this page" button at the bottom right: the same button, the
// same list, but only a click, Enter, Space or an arrow key opens it (hover and plain focus do not), a click again, Esc, a click
// outside, a jump or the focus leaving closes it. The look is in shell.css under the same width.
import { useState, useRef, useEffect } from "preact/hooks";
import { entries, activeEntry, onKey } from "../logic/minimap.js";

const NARROW = "(max-width: 900px)";
const narrow = () => typeof matchMedia === "function" && matchMedia(NARROW).matches;

// Where each section's top is, from the page.
function measure(list) {
  return list.flatMap((e) => {
    const el = document.getElementById(e.anchor);
    return el ? [{ id: e.id, top: el.getBoundingClientRect().top + window.scrollY }] : [];
  });
}

export function Minimap({ sections, hiddenSections, onJump, stickyHeight = 0, counts = {} }) {
  const list = entries(sections, hiddenSections);
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState(null);
  const root = useRef(null), button = useRef(null), quiet = useRef(false);

  useEffect(() => {
    const spy = () => setCurrent(activeEntry(measure(list), window.scrollY, window.innerHeight, stickyHeight, document.documentElement.scrollHeight));
    spy();
    window.addEventListener("scroll", spy, { passive: true });
    window.addEventListener("resize", spy);
    return () => { window.removeEventListener("scroll", spy); window.removeEventListener("resize", spy); };
  }, [list.map((e) => e.anchor).join("|"), stickyHeight]);

  // The scroll is the caller's (it knows the sticky bar); by default the anchor is scrolled to. Never a #link: the hash stays as it is.
  const jump = (e) => {
    if (onJump) { onJump(e.id); return; }
    const el = document.getElementById(e.anchor);
    if (el && el.scrollIntoView) el.scrollIntoView({ block: "start" });
  };
  // Back to the top of the page (the sticky bar stays); the list closes and the focus leaves it, as after a jump.
  const top = () => {
    setOpen(false);
    if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
    window.scrollTo(0, 0);
  };
  const links = () => Array.from(root.current ? root.current.querySelectorAll("button[data-id]") : []);
  const focusAt = (i) => setTimeout(() => { const l = links()[i]; if (l) l.focus(); }, 0);   // after the list has opened (a closed one can't take focus)
  const keys = (e) => {
    const at = links().indexOf(document.activeElement);
    const next = onKey({ index: at, count: list.length, open }, e.key);
    if (!next.handled) return;
    e.preventDefault();
    if (!next.open) {
      setOpen(false);
      if (button.current && document.activeElement !== button.current) { quiet.current = true; button.current.focus(); }   // back on the button, shut
      return;
    }
    setOpen(true);
    focusAt(next.index);
  };
  // At the narrow width a click outside the open list shuts it (a button may take no focus on a click, so focusout alone can miss it).
  useEffect(() => {
    if (!open) return undefined;
    const outside = (e) => { if (narrow() && root.current && !root.current.contains(e.target)) setOpen(false); };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open]);
  const leave = (e) => { if (!root.current.contains(e.relatedTarget)) setOpen(false); };

  if (!list.length) return null;
  return (
    <nav class={`toc${open ? " open" : ""}`} aria-label="On this page" ref={root} onKeyDown={keys}
      onMouseEnter={() => { if (!narrow()) setOpen(true); }} onMouseLeave={() => { if (!root.current.contains(document.activeElement)) setOpen(false); }}
      onFocusIn={() => { if (quiet.current) quiet.current = false; else if (!narrow()) setOpen(true); }} onFocusOut={leave}>
      <button type="button" class="toc-lines" ref={button} aria-expanded={open ? "true" : "false"} aria-controls="toc-card" aria-label="On this page" onClick={() => setOpen(narrow() ? !open : true)}>
        <svg class="toc-ico" viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path d="M2 4h12M2 8h12M2 12h8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" fill="none" /></svg>
        <span class="toc-lbl" aria-hidden="true">On this page</span>
        {list.map((e) => <i key={e.id} data-tl={e.id} class={`${e.id === current ? "on" : ""}${counts[e.id] && counts[e.id].hot ? " hot" : ""}`.trim()}></i>)}
      </button>
      <div class="toc-card" id="toc-card" inert={!open}>   {/* inert at once when closed: Tab cannot enter it before the fade ends */}
        <div class="toc-h">On this page</div>
        <ul>
          {list.map((e) => (
            <li key={e.id}>
              <button type="button" data-id={e.id} class={e.id === current ? "on" : ""} aria-current={e.id === current ? "true" : undefined}
                onClick={() => { setOpen(false); if (document.activeElement && document.activeElement.blur) document.activeElement.blur(); jump(e); }}>
                <span>{e.title}</span>
                {counts[e.id] ? <em class={counts[e.id].hot ? "hot" : ""}>{counts[e.id].text}</em> : null}
              </button>
            </li>
          ))}
        </ul>
        <button type="button" class="toc-top" onClick={top}>Back to top <span aria-hidden="true">↑</span></button>
      </div>
    </nav>
  );
}
