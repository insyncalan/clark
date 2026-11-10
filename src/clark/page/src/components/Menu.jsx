// A button that opens a menu of commands (creaite v2.6.9 `system/templates/dashboard/src/components/Menu.jsx`, cut down: the
// button, the role="menu" box and the keys. The hover opening, the pointer-placed menu and the menu group are left out).
// Keyboard and names: the button has aria-haspopup="menu" and aria-expanded; Down opens it. Inside, Up, Down, Home and End move,
// Enter or Space runs an item, Esc closes it with focus back on the button, Tab or a click away closes it.
import { useEffect, useLayoutEffect, useRef, useState } from "preact/hooks";
import { Icon } from "./Icon.jsx";
import { moves } from "../stores/report.js";

// The items a key can move between: every item that is not disabled.
export const menuItemsIn = (box) => (box ? [...box.querySelectorAll("[role^=menuitem]")].filter((b) => b.getAttribute("aria-disabled") !== "true" || b.hasAttribute("data-keep")) : []);      // data-keep: a disabled row that stays reachable by the keys so its reason is read out (the client menu)

// Up, Down (wrapping), Home and End between `items`: true when the key was one of them (it is then used up).
export function menuMove(e, items) {
  const i = items.indexOf(document.activeElement);
  let to = null;
  if (e.key === "ArrowDown") to = items[(i + 1) % items.length];
  else if (e.key === "ArrowUp") to = items[(i < 0 ? 0 : i + items.length - 1) % items.length];
  else if (e.key === "Home") to = items[0];
  else if (e.key === "End") to = items[items.length - 1];
  else return false;
  e.preventDefault(); e.stopPropagation();
  if (to) to.focus({ preventScroll: true });
  return true;
}

// The role="menu" box: focus to its first item (or, with `focusChecked`, the marked one) when it opens, the keys, and a click away.
export function MenuPanel({ label, id, cls, anchor, onClose, boxRef, fixed, focusChecked, leaving, onGone, fade, children }) {
  const own = useRef(null), box = boxRef || own;
  useFadeOut(box, !!fade && !leaving, typeof fade === "string" ? fade : "");
  const closeRef = useRef(onClose); closeRef.current = onClose;
  // `fixed`: the button sits inside a scrolling box that would cut the menu off, so the menu is placed on the window under the button (above it when
  // there is no room below), its right edge on the button's (`fixed="start"`: its left edge). It is placed once, so any scroll (the row's own included) or a resize closes it.
  useLayoutEffect(() => {
    if (!fixed || !anchor || !box.current) return;
    const el = box.current, a = anchor.getBoundingClientRect(), w = el.offsetWidth, h = el.offsetHeight;
    el.style.position = "fixed"; el.style.right = "auto";
    const below = Math.round(a.bottom + 4), above = Math.round(a.top - 4 - h);
    el.style.top = `${below + h > window.innerHeight && above >= 0 ? above : below}px`;
    const edge = fixed === "start" ? a.left : a.right - w;       // "start": the menu's left edge on the button's (a button near the page's left edge), else its right edge on the button's
    el.style.left = `${Math.round(Math.max(8, Math.min(edge, window.innerWidth - w - 8)))}px`;
    const shut = () => closeRef.current("away");
    window.addEventListener("scroll", shut, true);
    window.addEventListener("resize", shut);
    return () => { window.removeEventListener("scroll", shut, true); window.removeEventListener("resize", shut); };
  }, []);
  // Row 800: opened with the mouse (the button does not show a focus ring), the first item takes the focus without a ring until a key is used.
  useLayoutEffect(() => {
    if (anchor && !anchor.matches(":focus-visible")) box.current.dataset.pointer = "1";
    const its = menuItemsIn(box.current);
    ((focusChecked && its.find((b) => b.getAttribute("aria-checked") === "true")) || its[0] || box.current).focus({ preventScroll: true });
  }, []);
  useLayoutEffect(() => {                        // not after the next frame: a click away that quick still closes it
    const away = (e) => { if (!box.current.contains(e.target) && !(anchor && anchor.contains(e.target))) closeRef.current("away"); };
    document.addEventListener("pointerdown", away, true);
    return () => document.removeEventListener("pointerdown", away, true);
  }, [anchor]);
  const keys = (e) => {
    delete box.current.dataset.pointer;
    if (menuMove(e, menuItemsIn(box.current))) return;
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onClose("esc"); }
    else if (e.key === "Tab") onClose("tab");
  };
  // Row 922: while it fades out it has no id and is no role=menu (it is not "the menu" any more: code that looks for an open menu by id or role, such as the Help peek's Esc, must not find the fading one), it is out of the tab order and the reading order (inert, aria-hidden) and takes no pointer.
  return <div class={`ddmenu on${cls ? " " + cls : ""}${leaving ? " leaving" : ""}`} id={leaving ? undefined : id} role={leaving ? "presentation" : "menu"} aria-label={label} ref={box} tabIndex={-1} onKeyDown={keys}
    inert={leaving ? true : undefined} aria-hidden={leaving ? "true" : undefined} onAnimationEnd={(e) => { if (leaving && e.target === e.currentTarget && e.animationName === "m-out" && onGone) onGone(); }}>{children}</div>;
}

// Row 922: motion is off when the computer asks for reduced motion or clark's own setting is on (the same test as the ask panel's).
const stillMotion = () => document.documentElement.dataset.motion === "reduce" || (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);

// Row 962: the fade-out of a menu or popup that is taken off the page the moment its owner stops drawing it. The copy that fades is drawn by the Edit part
// (a file of the Edit part), which puts it in `fx.copy`; the published page has none, so nothing is drawn there and none of that code is in its file.
export const fx = { copy: null };
export function useFadeOut(ref, on, wrap) {
  useLayoutEffect(() => { const el = ref.current; return () => { if (on && fx.copy) fx.copy(el, wrap); }; }, []);   // eslint-disable-line react-hooks/exhaustive-deps
}
// A plain box (tag `tag`, any props) that fades out when its owner stops drawing it: the same as useFadeOut for a box that has no component of its own.
export function Fade({ tag: Tag = "div", boxRef, wrap, ...rest }) {
  const own = useRef(null), ref = boxRef || own;
  useFadeOut(ref, true, wrap);
  return <Tag ref={ref} {...rest} />;
}

// The open state of a menu that Back or Forward (or a typed address) closes, with nothing chosen (#63). Only a menu that was already
// open before the move closes. The move count is taken when the menu is opened (in the setter, not in a render), so a menu opened a
// frame before the close effect runs (a quick click or key straight after a typed address, or in the first draw) is still known to
// have been opened on the new page and stays open. Use it where useState(false) would be.
export function useMenuState() {
  const [open, setRaw] = useState(false);
  const moved = moves.value, seen = useRef(moved), openedAt = useRef(moved);
  const setOpen = (value) => {
    const next = typeof value === "function" ? value(open) : value;
    if (next) openedAt.current = moves.peek();
    setRaw(next);
  };
  useEffect(() => { if (seen.current !== moved) { seen.current = moved; if (openedAt.current !== moved) setRaw(false); } }, [moved]);
  return [open, setOpen];
}

// A line of words followed by radio items is one group with that name, so a screen reader says "Appearance, Light, radio, checked".
function groupedItems(items, menuId) {
  const out = [];
  for (let i = 0; i < items.length; i++) {
    const it = items[i];
    if (it.lab && items[i + 1] && items[i + 1].checked !== undefined) {
      const kids = [];
      let j = i + 1;
      while (items[j] && items[j].checked !== undefined) kids.push(items[j++]);
      out.push({ group: true, id: "g-" + it.id, labelId: `${menuId || "menu"}-${it.id}`, lab: it.lab, items: kids });
      i = j - 1;
    } else out.push({ item: it });
  }
  return out;
}

// One entry of the menu: a separator, the top line, a line of words, or a command or radio item.
function entry(it, close, onPick) {
  return it.sep ? <div key={it.id} class="sep" role="separator"></div> : it.head ? <div key={it.id} class="who" role="presentation" title={it.head.title}><b>{it.head.name}</b>{it.head.line ? <small>{it.head.line}</small> : null}</div> : it.lab ? <div key={it.id} class="lab" role="presentation">{it.lab}</div> : (
    <button key={it.id} type="button" class={it.link ? "who-link" : it.pill ? "hp" : it.danger ? "mdanger" : undefined} role={it.checked === undefined ? "menuitem" : "menuitemradio"} aria-checked={it.checked === undefined ? undefined : it.checked ? "true" : "false"}
      tabIndex={-1} data-kind={it.id} onClick={() => { close("pick"); onPick(it.id); }}>
      {it.icon ? <Icon name={it.icon} cls="mico" /> : null}
      {it.checked === undefined || it.pill ? null : <span class="ck" aria-hidden="true">{it.checked ? "✓" : ""}</span>}
      {it.pill ? <span class={`hpill ${it.pill}`}>{it.name}</span> : it.word ? <span class={`ucword rag-${it.word}`}><i class="ragdot" aria-hidden="true"></i>{it.name}</span> : it.line ? <span><b>{it.name}</b><small>{it.line}</small></span> : it.name}
      {it.pill && it.checked ? <Icon name="check" cls="hck" /> : null}
    </button>
  );
}

// items: [{id, name, line?, checked?, pill?}] (`checked` true or false makes it a radio item, marked when it is the one in use; `word` "g", "a" or "r" draws the name as a status word with its coloured dot (the use case rows' own look), `pill` "g", "a" or "r" draws the name as a filled status pill, with a check mark shape after it when in use), or {id, sep: true} for a separator, or {id, lab} for a line of words that is not a command, or {id, head: {name, line, title}} for the top line (a name and, under it, a quiet line), or a command with `link` true, drawn as a link. `onPick(id)` runs after the menu has closed. With no items the button is a plain button and a click
// is `onClick()` (so a button that sometimes has a menu keeps the same element when it has none).
export function Menu({ label, items, onPick, onClick, icon, tip, ariaLabel, id, btnCls, labelCls, menuId, menuLabel, left, fixed, chevron = true, onOpen, focusChecked }) {
  const [open, setOpen] = useMenuState();
  const [, redraw] = useState(0);
  const btn = useRef(null);
  const back = useRef(false);
  const menu = items.length > 0;
  // Row 922: after it closes the menu stays drawn for its fade (opacity only), then goes; at once where motion is off. A 400 ms timer guards it,
  // and opening it again (a new `gen`) is a fresh menu, so the first item takes the focus and the drop-in runs again.
  const phase = useRef("closed"), gen = useRef(0), wasOpen = useRef(false);
  if (open && menu) phase.current = "open"; else if (phase.current === "open") phase.current = stillMotion() || !menu ? "closed" : "leaving";
  if (open && !wasOpen.current) gen.current++;
  wasOpen.current = open;
  const leaving = phase.current === "leaving";
  const gone = () => { if (phase.current === "leaving") { phase.current = "closed"; redraw((n) => n + 1); } };
  useEffect(() => { if (!leaving) return undefined; const t = setTimeout(gone, 400); return () => clearTimeout(t); }, [leaving]);
  const close = (how) => { back.current = how === "esc" || how === "pick"; setOpen(false); };
  // Focus goes back to the button only if nothing took it: an item that opens a dialog has put focus there, and the menu must not steal it.
  useEffect(() => { if (!open && back.current) { back.current = false; const at = document.activeElement; if (btn.current && (!at || at === document.body || at === btn.current || (at.closest && at.closest(".ddmenu.leaving") && btn.current.parentNode.contains(at)))) btn.current.focus(); } }, [open]);
  const opens = () => { setOpen(true); if (onOpen) onOpen(); };   // `onOpen` runs each time the menu is opened, by a click or by Down
  const onBtnKey = (e) => { if (menu && e.key === "ArrowDown" && !open) { e.preventDefault(); opens(); } };
  return (
    <span class="dd">
      <button type="button" class={btnCls || "btn"} id={id} ref={btn} aria-haspopup={menu ? "menu" : undefined} aria-expanded={menu ? (open ? "true" : "false") : undefined}
        aria-label={ariaLabel} title={tip} data-tip={tip} onKeyDown={onBtnKey} onClick={(e) => { e.preventDefault(); if (menu) { if (open) setOpen(false); else opens(); } else if (onClick) onClick(); }}>
        {icon ? <Icon name={icon} /> : null}<span class={labelCls}>{label}</span>{chevron ? <Icon name="chevdown" cls="nch" /> : null}
      </button>
      {(open || leaving) && menu ? (
        <MenuPanel key={gen.current} leaving={leaving} onGone={gone} label={menuLabel || ariaLabel || label} id={menuId} cls={left ? "left" : ""} fixed={fixed} focusChecked={focusChecked} anchor={btn.current} onClose={close}>
          {groupedItems(items, menuId).map((n) => n.group
            ? <div key={n.id} role="group" aria-labelledby={n.labelId}>
                <div class="lab" role="presentation" id={n.labelId}>{n.lab}</div>
                {n.items.map((it) => entry(it, close, onPick))}
              </div>
            : entry(n.item, close, onPick))}
        </MenuPanel>
      ) : null}
    </span>
  );
}
