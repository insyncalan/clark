// The AI menu of a rich field (item 1179): the list menu("current") gives, drawn as a role=menu box at a point on the window. It opens from the
// Draft with AI button (under it) and from a right-click, Shift+F10 or the Menu key over selected text (at the pointer or the selection).
// Props: at {x, y}, onPick({option, instruction}), onClose(how). Esc closes it (how = "esc"); the owner puts the focus back in the editor.
// There are no Make-into entries here yet. Ask... shows one line to type; Enter sends it.
import { useEffect, useLayoutEffect, useRef, useState } from "preact/hooks";
import { menu, WORDS } from "../logic/aiMenu.js";
import { Icon } from "../components/Icon.jsx";
import { menuItemsIn, menuMove } from "../components/Menu.jsx";

export function AiMenu({ at, onPick, onClose }) {
  const box = useRef(null), ask = useRef(null);
  const [asking, setAsking] = useState(false);
  const m = menu("current");
  const closeRef = useRef(onClose); closeRef.current = onClose;
  useLayoutEffect(() => {
    const el = box.current, w = el.offsetWidth, h = el.offsetHeight;
    el.style.left = `${Math.round(Math.max(8, Math.min(at.x, window.innerWidth - w - 8)))}px`;
    el.style.top = `${Math.round(Math.max(8, Math.min(at.y, window.innerHeight - h - 8)))}px`;
  }, []);
  useEffect(() => {
    const t = setTimeout(() => { const its = menuItemsIn(box.current); (its[0] || box.current).focus({ preventScroll: true }); }, 60);     // after the editor has taken its own focus
    const esc = (e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); closeRef.current("esc"); } };
    const away = (e) => { if (!box.current.contains(e.target)) closeRef.current("away"); };
    document.addEventListener("keydown", esc, true);
    document.addEventListener("pointerdown", away, true);
    return () => { clearTimeout(t); document.removeEventListener("keydown", esc, true); document.removeEventListener("pointerdown", away, true); };
  }, []);
  useEffect(() => { if (asking && ask.current) ask.current.focus(); }, [asking]);
  if (!m) return null;
  const item = (it) => (
    <button type="button" key={it.id} role="menuitem" tabIndex={-1} data-ai-option={it.id} title={it.line}
      onClick={() => onPick({ option: it.id, instruction: "" })}><Icon name="sparkle" cls="mi" />{it.name}</button>
  );
  return (
    <div class="pk-ai-menu" data-ai-menu role="menu" aria-label="Draft with AI" ref={box} tabIndex={-1}
      onKeyDown={(e) => { if (e.key === "Tab") { closeRef.current("esc"); return; } if (e.target === ask.current) return; menuMove(e, menuItemsIn(box.current)); }}>
      {m.format_notes ? item(m.format_notes) : null}
      {m.groups.map((g) => (
        <div key={g.label} role="group" aria-label={g.label}>
          <div class="lab" role="presentation">{g.label}</div>
          {g.items.map(item)}
        </div>
      ))}
      {asking
        ? <input ref={ask} type="text" class="pk-ai-ask" aria-label={m.ask.name} placeholder={m.ask.line}
            onKeyDown={(e) => { if (e.key === "Enter" && e.target.value.trim()) { e.preventDefault(); onPick({ option: "custom", instruction: e.target.value.trim() }); } }} />
        : <button type="button" role="menuitem" tabIndex={-1} data-ai-option="custom" title={m.ask.line} onClick={() => setAsking(true)}>{m.ask.name}</button>}
      <p class="pk-ai-sends">{WORDS.sends}</p>
    </div>
  );
}
