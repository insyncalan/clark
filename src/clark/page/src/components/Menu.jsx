// A button that opens a menu of commands (creaite v2.6.9 `system/templates/dashboard/src/components/Menu.jsx`, cut down: the
// button, the role="menu" box and the keys. The hover opening, the pointer-placed menu and the menu group are left out).
// Keyboard and names: the button has aria-haspopup="menu" and aria-expanded; Down opens it. Inside, Up, Down, Home and End move,
// Enter or Space runs an item, Esc closes it with focus back on the button, Tab or a click away closes it.
import { useEffect, useLayoutEffect, useRef, useState } from "preact/hooks";
import { Icon } from "./Icon.jsx";

// The items a key can move between: every item that is not disabled.
export const menuItemsIn = (box) => (box ? [...box.querySelectorAll("[role^=menuitem]")].filter((b) => b.getAttribute("aria-disabled") !== "true") : []);

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

// The role="menu" box: focus to its first item when it opens, the keys, and a click away.
export function MenuPanel({ label, id, cls, anchor, onClose, boxRef, children }) {
  const own = useRef(null), box = boxRef || own;
  const closeRef = useRef(onClose); closeRef.current = onClose;
  useLayoutEffect(() => { (menuItemsIn(box.current)[0] || box.current).focus({ preventScroll: true }); }, []);
  useEffect(() => {
    const away = (e) => { if (!box.current.contains(e.target) && !(anchor && anchor.contains(e.target))) closeRef.current("away"); };
    document.addEventListener("pointerdown", away, true);
    return () => document.removeEventListener("pointerdown", away, true);
  }, [anchor]);
  const keys = (e) => {
    if (menuMove(e, menuItemsIn(box.current))) return;
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onClose("esc"); }
    else if (e.key === "Tab") onClose("tab");
  };
  return <div class={`ddmenu on${cls ? " " + cls : ""}`} id={id} role="menu" aria-label={label} ref={box} tabIndex={-1} onKeyDown={keys}>{children}</div>;
}

// items: [{id, name, line?}]. `onPick(id)` runs after the menu has closed. With no items the button is a plain button and a click
// is `onClick()` (so a button that sometimes has a menu keeps the same element when it has none).
export function Menu({ label, items, onPick, onClick, icon, tip, ariaLabel, id, btnCls, labelCls, menuId, menuLabel, left, chevron = true }) {
  const [open, setOpen] = useState(false);
  const btn = useRef(null);
  const back = useRef(false);
  const menu = items.length > 0;
  const close = (how) => { back.current = how === "esc" || how === "pick"; setOpen(false); };
  useEffect(() => { if (!open && back.current) { back.current = false; if (btn.current) btn.current.focus(); } }, [open]);
  const onBtnKey = (e) => { if (menu && e.key === "ArrowDown" && !open) { e.preventDefault(); setOpen(true); } };
  return (
    <span class="dd">
      <button type="button" class={btnCls || "btn"} id={id} ref={btn} aria-haspopup={menu ? "menu" : undefined} aria-expanded={menu ? (open ? "true" : "false") : undefined}
        aria-label={ariaLabel} title={tip} data-tip={tip} onKeyDown={onBtnKey} onClick={(e) => { e.preventDefault(); if (menu) setOpen(!open); else if (onClick) onClick(); }}>
        {icon ? <Icon name={icon} /> : null}<span class={labelCls}>{label}</span>{chevron ? <Icon name="chevdown" cls="nch" /> : null}
      </button>
      {open && menu ? (
        <MenuPanel label={menuLabel || ariaLabel || label} id={menuId} cls={left ? "left" : ""} anchor={btn.current} onClose={close}>
          {items.map((it) => (
            <button key={it.id} type="button" role="menuitem" tabIndex={-1} data-kind={it.id} onClick={() => { close("pick"); onPick(it.id); }}>
              {it.line ? <span><b>{it.name}</b><small>{it.line}</small></span> : it.name}
            </button>
          ))}
        </MenuPanel>
      ) : null}
    </span>
  );
}
