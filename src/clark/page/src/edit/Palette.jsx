// The command palette (#198), Edit parts only. Cmd or Ctrl+K opens it from anywhere, even in a box; Esc or the same keys close it
// and focus goes back where it was. A native <dialog> opened as a modal (Tab stays inside, as in Publish). The search box is a
// combobox over a listbox: Up and Down move (wrapping, past any result that cannot run now), Enter runs, a click runs. The keys
// are heard on `window` in the capture phase, so they come before Help's own Esc.
import { useEffect, useRef, useState } from "preact/hooks";
import { paletteOpen, search, step, runResult } from "./palette.js";
import { view, projectsState, loadProjects } from "../stores/report.js";

const MAC = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform || "");
export const KEY_WORDS = MAC ? "⌘K" : "Ctrl+K";

let opener = null, box = null;
const restore = () => {
  const el = opener; opener = null;
  const main = document.getElementById("main");
  const to = el && el.isConnected ? el : null;
  if (to && typeof to.focus === "function") to.focus();
  else if (main && main.tabIndex < 0) { main.tabIndex = -1; main.focus(); }
};

/** Close the palette; `back` puts focus where it was (Esc, the key again), not when something was chosen. */
export function closePalette(back) {
  if (box && box.open) box.close();
  paletteOpen.value = false;
  if (back) restore(); else opener = null;
}
export function openPalette() {
  if (paletteOpen.value) return;
  const a = document.activeElement;
  opener = a && a !== document.body ? a : null;
  paletteOpen.value = true;
  if (projectsState.value !== "ready") loadProjects();          // the project list is read when the address names a project, so read it now
}

function onKey(e) {
  const k = (e.key || "").toLowerCase();
  if (k === "k" && (e.metaKey || e.ctrlKey) && !e.altKey && !e.shiftKey && !e.isComposing) {
    if (!paletteOpen.value && document.querySelector("dialog[open]")) return;          // another dialog has the page: leave it be
    e.preventDefault(); e.stopImmediatePropagation();
    if (e.repeat) return;
    if (paletteOpen.value) closePalette(true); else openPalette();
  } else if (e.key === "Escape" && paletteOpen.value) {
    e.preventDefault(); e.stopImmediatePropagation();
    closePalette(true);
  }
}

export function Palette() {
  useEffect(() => { window.addEventListener("keydown", onKey, true); return () => window.removeEventListener("keydown", onKey, true); }, []);
  return paletteOpen.value ? <Box /> : null;
}

function Box() {
  const el = useRef(null), input = useRef(null), list = useRef(null);
  const [q, setQ] = useState("");
  const [at, setAt] = useState(-1);
  view.value;                                         // the results follow the page the palette sits over
  const results = search(q);
  const active = at >= 0 && at < results.length && !results[at].disabled ? at : step(results, -1, 1);
  useEffect(() => {
    const d = el.current;
    if (d && !d.open) d.showModal();
    box = d;
    if (input.current) input.current.focus();
    return () => { if (d && d.open) d.close(); if (box === d) box = null; };
  }, []);
  useEffect(() => {
    const row = list.current && list.current.querySelector("[aria-selected=true]");
    if (row && row.scrollIntoView) row.scrollIntoView({ block: "nearest" });
  }, [active, q]);
  const choose = (r) => { if (!r || r.disabled) return; closePalette(false); runResult(r); };
  const keys = (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); setAt(step(results, active, e.key === "ArrowDown" ? 1 : -1)); }
    else if (e.key === "Home" || e.key === "End") { e.preventDefault(); setAt(step(results, e.key === "Home" ? -1 : results.length, e.key === "Home" ? 1 : -1)); }
    else if (e.key === "Enter" && !e.isComposing) { e.preventDefault(); choose(results[active]); }
  };
  const live = results.length ? `${results.length} ${results.length === 1 ? "result" : "results"}` : "Nothing matches.";
  return (
    <dialog id="palette" class="dlg pal" aria-label="Go to or do" ref={el} onCancel={(e) => { e.preventDefault(); closePalette(true); }}>
      <div class="pal-q">
        <input type="text" id="palette-q" role="combobox" aria-expanded="true" aria-controls="palette-list" aria-autocomplete="list" aria-activedescendant={active >= 0 ? "pal-" + results[active].id : undefined}
          placeholder="Type a command, page, project, work item or milestone" aria-label="Search commands, pages, projects, work items and milestones"
          autocomplete="off" spellcheck={false} ref={input} value={q} onInput={(e) => { setQ(e.currentTarget.value); setAt(-1); }} onKeyDown={keys} />
      </div>
      <ul id="palette-list" class="pal-list" role="listbox" aria-label="Results" ref={list}>
        {results.map((r, i) => (
          <li key={r.id} id={"pal-" + r.id} role="option" class={`pal-row${i === active ? " on" : ""}${r.disabled ? " off" : ""}`} data-kind={r.kind} aria-selected={i === active ? "true" : "false"}
            aria-disabled={r.disabled ? "true" : undefined} onMouseMove={() => { if (!r.disabled && i !== active) setAt(i); }} onMouseDown={(e) => e.preventDefault()} onClick={() => choose(r)}>
            <span class="pal-kind">{r.kind}</span>
            <span class="pal-label">{r.label}</span>
            {r.more ? <span class="pal-more muted num">{r.more}</span> : null}
            {r.current ? <span class="pal-more muted">You are here</span> : null}
            {r.disabled ? <span class="pal-why muted">{r.disabled}</span> : null}
          </li>
        ))}
      </ul>
      <p class="pal-none muted" hidden={results.length > 0}>Nothing matches “{q}”. Try a work item’s ID or a word from its title.</p>
      <p class="sr-only" role="status" aria-live="polite">{live}</p>
    </dialog>
  );
}
