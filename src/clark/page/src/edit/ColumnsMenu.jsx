// Row 1222: the columns menu of a Work items or Milestones table. A right click on the heading row, the Menu key or Shift+F10 on a focused heading, or
// the visible Columns button at the right end of it, opens ONE menu of every column that table can show (logic/tableColumns.js), each with a tick when it
// is on. A press turns a column on or off at once (the menu stays open for the next); the title (name) and the status are ticked, greyed, and say why.
// "Show the standard columns" is the foot. The choice is kept for each table and each project in this browser only. This file is a part of Edit: a
// published file does not have it, so a client's page has no menu and no words of it.
// A table calls useColumns(table) once; it puts `rowProps` on its heading row, `button` inside it, and draws `menu` once (null while it is shut).
import { useLayoutEffect, useRef, useState } from "preact/hooks";
import { project, data } from "../stores/report.js";
import { change } from "../stores/changes.js";
import { announce } from "../stores/work.js";
import { MenuPanel } from "../components/Menu.jsx";
import { Icon } from "../components/Icon.jsx";
import { classicTheme } from "../components/Contents.jsx";
import { defsOf, shownIds, toggled, readChoice, writeChoice, standardIds, movable, savedOrder, inOrder, moveColumn, withOrder } from "../logic/tableColumns.js";
import { columnIcon, actionIcon } from "../menuIcons.js";
import * as W from "../logic/columnsWords.js";

const asked = (e) => e.key === "ContextMenu" || (e.key === "F10" && e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey);
const typing = (t) => !!(t && t.closest && (t.isContentEditable || t.closest("input, textarea, select")));

// `css`: the tick is drawn by the stylesheet and the reason is set off by a space, so a row reads "Status Always shown..." as text (the Use cases table, row 1325).
// Row 1534 (Work items only): `type` is the type switch ("action", "risk" or "decision" have an order of their own, saved with the project and published; "all" keeps the standard order).
export function useColumns(table, css = false, type = "all") {
  const code = project.value, [mem, setMem] = useState({}), [at, setAt] = useState(null), box = useRef(null);
  const shown = mem[code] || readChoice(table, code);
  // Row 1499 (pick 7B): the Work items menu in the Classic look is a heading and tick lines only: the Status can be unticked, the title is always drawn and is not
  // listed, there is no standard reset. Cards (no Classic theme) keeps the menu of row 1222 as it was, Status greyed and always shown.
  const classic = table === "work" && classicTheme();
  const lockedIn = (c) => c.locked || (table === "work" && !classic && c.id === "status");
  // The menu is placed under the heading it was opened from (MenuPanel); a long one is moved up, or cut and scrolled, so all of it is inside the window.
  useLayoutEffect(() => {
    const el = box.current;
    if (!at || !el) return;
    const h = el.offsetHeight, room = window.innerHeight - 16;
    if (h > room) { el.style.maxHeight = `${room}px`; el.style.top = "8px"; return; }
    const top = parseFloat(el.style.top) || 0;
    if (top + h > window.innerHeight - 8) el.style.top = `${Math.max(8, window.innerHeight - h - 8)}px`;
  }, [at]);
  const ordering = table === "work", canMove = ordering && movable(type), co = data.value && data.value.project ? data.value.project.column_orders : null;
  const out = shownIds(table, shown), drawn = ordering && !classic && !out.includes("status") ? ["status", ...out] : out;      // Cards: the Status stays always shown, even after it was unticked in the Classic look
  const ordered = ordering ? inOrder(drawn, savedOrder(co, type)) : drawn;
  const listed = ordering ? ordered.map((id) => defsOf(table).find((c) => c.id === id)).concat(defsOf(table).filter((c) => !ordered.includes(c.id))) : defsOf(table);      // the menu lists the columns in the table's order, the hidden ones after
  const labelOfId = (id) => (defsOf(table).find((c) => c.id === id) || {}).label || id;
  // The order is saved with the project through the one writer (no toast: the key Cmd or Ctrl+Z puts it back). The page draws the new order at once and takes it back if it was refused.
  const saveOrder = async (ids, words) => {
    const was = co, next = withOrder(co, type, ids);
    const draw = (text) => { const d = data.value; if (d && d.project) data.value = { ...d, project: { ...d.project, column_orders: text } }; };
    draw(JSON.stringify(next));
    announce.value = words;
    const r = await change({ kind: "projects", op: "update", changes: { column_orders: next }, place: "menu" }, "", { silent: true });
    if (!r) draw(was === undefined || was === null ? "{}" : was);
  };
  const moveTo = (to, id) => { saveOrder(to, W.MOVED(labelOfId(id), to.indexOf(id) + 1, to.length)); };
  const step = (id, delta) => {
    const to = moveColumn(ordered, id, delta);
    if (!to) return;
    moveTo(to, id);
    const el = document.querySelector(`[data-cw-table="${table}"][data-cw-head="${id}"]`);      // the heading keeps the focus, so the next key moves it again
    if (el && el.focus) el.focus({ preventScroll: true });
  };
  const standardOrder = () => defsOf(table).map((c) => c.id).filter((id) => ordered.includes(id));
  const resetOrder = () => { if (savedOrder(co, type).length) saveOrder(standardOrder(), W.RESET_ORDER); };
  // A drag of a heading (pointer: a mouse, a pen or a finger): a press that moves less than 5 px is a click and does what it did; a drag shows the drop place, a drop on another heading of the same row moves the
  // column there, a drop anywhere else or Esc cancels. The Status and the Item are not dragged and nothing is dropped in front of them.
  const headProps = (id) => {
    if (!canMove || id === "status" || id === "item") return {};
    return {
      "data-move": "",
      onKeyDown: (e) => {
        if (!(e.altKey && e.shiftKey) || e.ctrlKey || e.metaKey || (e.key !== "ArrowLeft" && e.key !== "ArrowRight")) return;
        e.preventDefault(); e.stopPropagation();
        step(id, e.key === "ArrowLeft" ? -1 : 1);
      },
      onPointerDown: (e) => {
        if (e.button || (e.target.closest && e.target.closest(".cgrip, button"))) return;
        const th = e.currentTarget, row = th.parentElement, x0 = e.clientX, y0 = e.clientY;
        let moving = false, before;
        const heads = () => Array.from(row.querySelectorAll("th[data-col]"));
        const clear = () => heads().forEach((t) => { t.classList.remove("col-dragging", "col-drop-before", "col-drop-after"); });
        const target = (m) => { const el = document.elementFromPoint(m.clientX, m.clientY), t = el && el.closest ? el.closest("th[data-col]") : null; return t && t.parentElement === row ? t : null; };
        const move = (m) => {
          if (!moving && Math.hypot(m.clientX - x0, m.clientY - y0) < 5) return;
          moving = true; clear(); th.classList.add("col-dragging"); before = undefined;
          const t = target(m), tid = t && t.getAttribute("data-col");
          if (!t || tid === id) return;
          const all = heads().map((h) => h.getAttribute("data-col")), after = all.indexOf(tid) > all.indexOf(id);
          before = after ? (all[all.indexOf(tid) + 1] || null) : tid;
          t.classList.add(after ? "col-drop-after" : "col-drop-before");
        };
        const done = (drop) => {
          document.removeEventListener("pointermove", move); document.removeEventListener("pointerup", up); document.removeEventListener("pointercancel", cancel); document.removeEventListener("keydown", key, true);
          clear();
          if (!moving) return;
          const quiet = (c) => { c.stopPropagation(); c.preventDefault(); };      // the click that ends a drag is not a click on the heading
          document.addEventListener("click", quiet, { capture: true, once: true }); setTimeout(() => document.removeEventListener("click", quiet, true), 0);
          if (drop && before !== undefined) { const to = moveColumn(ordered, id, null, before); if (to) moveTo(to, id); }
        };
        const up = () => done(true), cancel = () => done(false), key = (k) => { if (k.key === "Escape") { k.stopPropagation(); done(false); } };
        document.addEventListener("pointermove", move); document.addEventListener("pointerup", up); document.addEventListener("pointercancel", cancel); document.addEventListener("keydown", key, true);
      },
    };
  };
  const from = at && at.closest ? at.closest("[data-col]") : null, fromId = from ? from.getAttribute("data-col") : null;      // the heading the menu was opened from: "Move left" and "Move right" move that column
  const moveItems = () => (canMove ? (
    <>
      <div class="sep" role="separator"></div>
      <button type="button" role="menuitem" data-move-left="" tabIndex={-1} aria-disabled={fromId && moveColumn(ordered, fromId, -1) ? undefined : "true"} onClick={() => { if (fromId) step(fromId, -1); }}>{W.MOVE_LEFT}</button>
      <button type="button" role="menuitem" data-move-right="" tabIndex={-1} aria-disabled={fromId && moveColumn(ordered, fromId, 1) ? undefined : "true"} onClick={() => { if (fromId) step(fromId, 1); }}>{W.MOVE_RIGHT}</button>
      <button type="button" role="menuitem" data-order-reset="" tabIndex={-1} aria-disabled={savedOrder(co, type).length ? undefined : "true"} onClick={resetOrder}>{W.RESET_ORDER}</button>
    </>
  ) : null);
  const set = (next) => { writeChoice(table, code, next); setMem({ ...mem, [code]: next }); };
  const close = (how) => { const a = at; setAt(null); if (how === "esc" && a && a.isConnected) { if (!a.matches("button, [tabindex]")) a.setAttribute("tabindex", "-1"); a.focus({ preventScroll: true }); } };
  const open = (el) => setAt(el);
  const rowProps = {
    onContextMenu: (e) => { if (typing(e.target)) return; e.preventDefault(); open(e.target.closest("th, button, [data-col]") || e.currentTarget); },
    onKeyDown: (e) => { if (!asked(e) || typing(e.target)) return; e.preventDefault(); e.stopPropagation(); open(e.target.closest("th, button, [data-col]") || e.currentTarget); },
  };
  // place: "ms" (the milestones heading, a tab stop), undefined (a work table heading: mouse only, so the grid stays one tab stop) or "key" (the one
  // button outside the grid, drawn only when focused, so a keyboard has a way in). Only the one that opened the menu says it is expanded.
  const button = (place) => { const cls = place === "ms" ? "msl-cols-btn" : place === "key" ? "cols-btn cols-kbd" : "cols-btn"; return (
    <button type="button" class={cls} data-cbk={place || "head"} tabIndex={place === "ms" || place === "key" ? undefined : -1} aria-label={W.UNRULED_BUTTON} aria-haspopup="menu"
      aria-expanded={place !== "head" && place !== undefined && at && at.getAttribute("data-cbk") === place ? "true" : "false"} title={W.UNRULED_BUTTON_TIP} data-tip={W.UNRULED_BUTTON_TIP}
      onClick={(e) => { e.stopPropagation(); if (at === e.currentTarget) setAt(null); else open(e.currentTarget); }}><Icon name="columns" /></button>
  ); };
  const press = (id, label) => {
    const next = toggled(table, shown, id);
    set(next);
    announce.value = W.UNRULED_ANNOUNCE(label, next.includes(id));
  };
  const menu = at && classic ? (
    <MenuPanel label={W.PANEL_HEADING} cls="cols-menu cm-7b" anchor={at} fixed="start" boxRef={box} onClose={close}>
      <h5 class="cm-head">{W.PANEL_HEADING}</h5>
      {listed.filter((c) => c.id !== "item").map((c) => {
        const on = shown.includes(c.id);
        return (
          <button key={c.id} type="button" role="menuitemcheckbox" aria-checked={on ? "true" : "false"} data-col-name={c.label} tabIndex={-1} onClick={() => press(c.id, c.label)}>
            <span class="tk" aria-hidden="true">{on ? "✓" : ""}</span>{c.label}
          </button>
        );
      })}
      {moveItems()}
    </MenuPanel>
  ) : at ? (
    <MenuPanel label={W.UNRULED_MENU_LABEL} cls="cols-menu" anchor={at} fixed="start" boxRef={box} onClose={close}>
      {listed.map((c) => {
        const on = shown.includes(c.id);
        return (
          <button key={c.id} type="button" role="menuitemcheckbox" aria-checked={on ? "true" : "false"} aria-disabled={lockedIn(c) ? "true" : undefined} data-keep={lockedIn(c) ? "" : undefined}
            data-col-name={c.label} tabIndex={-1} aria-describedby={lockedIn(c) ? `cols-why-${c.id}` : undefined} onClick={() => { if (!lockedIn(c)) press(c.id, c.label); }}>
            <Icon name={columnIcon(c.id)} cls="mi" />
            <span class="ck" aria-hidden="true" data-on={css && on ? "" : undefined}>{css ? "" : on ? "✓" : ""}</span>
            <span class="cols-name">{c.label}{lockedIn(c) && css ? " " : null}{lockedIn(c) ? <small class="cols-why" id={`cols-why-${c.id}`}>{W.UNRULED_LOCKED_REASON}</small> : null}</span>
          </button>
        );
      })}
      <div class="sep" role="separator"></div>
      <button type="button" role="menuitem" data-cols-standard="" tabIndex={-1} onClick={() => { set(standardIds(table)); announce.value = W.UNRULED_ANNOUNCE_STANDARD; }}><Icon name={actionIcon("columnsStandard")} cls="mi" />{W.UNRULED_STANDARD}</button>
      {moveItems()}
    </MenuPanel>
  ) : null;
  return { shown: ordered, headProps, has: (id) => shown.includes(id), rowProps, button, menu };
}
