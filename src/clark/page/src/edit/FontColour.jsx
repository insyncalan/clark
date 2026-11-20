// Row 1364 (Classic only): the Font colour entry of the rich editor's toolbar and bubble, and its palette. One button after Strikethrough; it opens
// a small palette under itself: "Automatic" (no colour) and six swatches that name the theme's own tokens (the look is in the Theme's rules.css).
// Keys: Enter, Space or Down on the button opens it with the focus on the chosen entry; arrows move over Automatic and the grid (4 to a row);
// Enter or Space chooses; Esc closes and the focus returns to the button; Tab closes. A click on a swatch applies it to the selection.
import { useEffect, useRef, useState } from "preact/hooks";
import { SWATCHES } from "../core/fontColour.js";

export const FONT_COLOUR = "Font colour";
export const AUTOMATIC = "Automatic";
const PER_ROW = 4;

// h: the editor's handle (colour(), run("colour", name)); after: called once a colour is chosen (the editor redraws its buttons and takes the focus back).
export function FontColourButton({ h, after }) {
  const [open, setOpen] = useState(false);
  const wrap = useRef(null), btn = useRef(null), items = useRef([]);
  const current = h ? h.colour() : null;
  const focusAt = (i) => { const n = items.current[i]; if (n) n.focus(); };
  const show = () => { setOpen(true); setTimeout(() => focusAt(current ? SWATCHES.findIndex(([n]) => n === current) + 1 : 0), 0); };
  const close = (back) => { setOpen(false); if (back && btn.current) btn.current.focus(); };
  const choose = (name) => { h.run("colour", name); setOpen(false); after(); };

  useEffect(() => {
    if (!open) return undefined;
    const outside = (e) => { if (wrap.current && !wrap.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", outside, true);
    return () => document.removeEventListener("mousedown", outside, true);
  }, [open]);

  const move = (e) => {
    const at = items.current.indexOf(document.activeElement), last = SWATCHES.length;
    const keys = { ArrowRight: at + 1, ArrowLeft: at - 1, Home: 0, End: last,
      ArrowDown: at === 0 ? 1 : (at + PER_ROW <= last ? at + PER_ROW : at), ArrowUp: at <= PER_ROW ? 0 : at - PER_ROW };
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(true); return; }
    if (e.key === "Tab") { close(true); return; }
    if ((e.key === "Enter" || e.key === " ") && items.current.includes(document.activeElement)) { e.preventDefault(); e.stopPropagation(); document.activeElement.click(); return; }
    if (e.key in keys) { e.preventDefault(); e.stopPropagation(); focusAt(Math.max(0, Math.min(last, keys[e.key]))); }
  };
  const sw = (name) => `rt-c-${name}`;

  return (
    <span class="rt-fc" ref={wrap} onFocusOut={(e) => { if (open && e.relatedTarget && !wrap.current.contains(e.relatedTarget)) setOpen(false); }}>
      <button type="button" ref={btn} class={`rt-btn rt-fc-btn${open ? " on" : ""}`} aria-label={FONT_COLOUR} title={FONT_COLOUR} aria-haspopup="menu" aria-expanded={open ? "true" : "false"}
        onMouseDown={(e) => e.preventDefault()} onClick={() => (open ? close(false) : show())}
        onKeyDown={(e) => { if (e.key === "ArrowDown" && !open) { e.preventDefault(); show(); } }}>
        <span class="rt-fc-a" aria-hidden="true"><span class="rt-fc-g">A</span><span class={`rt-fc-bar${current ? ` ${sw(current)}` : ""}`} /></span>
      </button>
      {open ? (
        <div class="rt-fc-pal" role="menu" aria-label={FONT_COLOUR} onKeyDown={move}>
          <button type="button" role="menuitemradio" aria-checked={current ? "false" : "true"} class="rt-fc-auto" tabIndex={-1} ref={(n) => { items.current[0] = n; }} onClick={() => choose(null)}>
            <span class="rt-fc-tick" aria-hidden="true">{current ? "" : "✓"}</span>{AUTOMATIC}
          </button>
          <div class="rt-fc-grid">
            {SWATCHES.map(([name, words], i) => (
              <button type="button" key={name} role="menuitemradio" aria-checked={current === name ? "true" : "false"} aria-label={words} title={words} tabIndex={-1}
                class={`rt-fc-sw${current === name ? " on" : ""}`} ref={(n) => { items.current[i + 1] = n; }} onClick={() => choose(name)}><span class={sw(name)} aria-hidden="true">A</span></button>
            ))}
          </div>
        </div>
      ) : null}
    </span>
  );
}
