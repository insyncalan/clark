// Row 1222: the columns menu of a Work items or Milestones table. A right click on the heading row, the Menu key or Shift+F10 on a focused heading, or
// the visible Columns button at the right end of it, opens ONE menu of every column that table can show (logic/tableColumns.js), each with a tick when it
// is on. A press turns a column on or off at once (the menu stays open for the next); the title (name) and the status are ticked, greyed, and say why.
// "Show the standard columns" is the foot. The choice is kept for each table and each project in this browser only. This file is a part of Edit: a
// published file does not have it, so a client's page has no menu and no words of it.
// A table calls useColumns(table) once; it puts `rowProps` on its heading row, `button` inside it, and draws `menu` once (null while it is shut).
import { useLayoutEffect, useRef, useState } from "preact/hooks";
import { project } from "../stores/report.js";
import { announce } from "../stores/work.js";
import { MenuPanel } from "../components/Menu.jsx";
import { Icon } from "../components/Icon.jsx";
import { classicTheme } from "../components/Contents.jsx";
import { defsOf, shownIds, toggled, readChoice, writeChoice, standardIds } from "../logic/tableColumns.js";
import { columnIcon, actionIcon } from "../menuIcons.js";
import * as W from "../logic/columnsWords.js";

const asked = (e) => e.key === "ContextMenu" || (e.key === "F10" && e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey);
const typing = (t) => !!(t && t.closest && (t.isContentEditable || t.closest("input, textarea, select")));

// The menu is placed under the heading it was opened from (MenuPanel); a long one is moved up, or cut and scrolled, so all of it is inside the window.
// Row 1286 (B-M5b): MenuPanel cut the box to the window height but left its top under the heading, so its foot was below the window (164 high: top 38,
// bottom 186). Classic only (Cards keeps its own placement, below). The move waits one microtask (before the first paint) so it runs after MenuPanel's own placement, whatever order the effects run in.
export function ColsPanel(props) {
  const box = useRef(null);
  useLayoutEffect(() => {
    if (!classicTheme()) return;
    queueMicrotask(() => {
      const el = box.current;
      if (!el || !el.isConnected) return;
      const bar = document.querySelector(".top"), floor = Math.max(8, bar && getComputedStyle(bar).position === "sticky" ? Math.ceil(bar.getBoundingClientRect().bottom) + 8 : 8);      // the sticky top bar is the floor: the menu never goes under it
      const h = el.offsetHeight, room = window.innerHeight - floor - 8;
      if (h > room) { el.style.maxHeight = `${room}px`; el.style.top = `${floor}px`; return; }
      const top = parseFloat(el.style.top) || 0;
      if (top < floor) el.style.top = `${floor}px`;
      else if (top + h > window.innerHeight - 8) el.style.top = `${Math.max(floor, window.innerHeight - h - 8)}px`;
    });
  }, []);
  return <MenuPanel {...props} boxRef={props.boxRef || box} />;
}

// `css`: the tick is drawn by the stylesheet and the reason is set off by a space, so a row reads "Status Always shown..." as text (the Use cases table, row 1325).
export function useColumns(table, css = false) {
  const code = project.value, [mem, setMem] = useState({}), [at, setAt] = useState(null), box = useRef(null);
  const shown = mem[code] || readChoice(table, code);
  // Row 1499 (pick 7B): the Work items menu in the Classic look is a heading and tick lines only: the Status can be unticked, the title is always drawn and is not
  // listed, there is no standard reset. Cards (no Classic theme) keeps the menu of row 1222 as it was, Status greyed and always shown.
  const classic = table === "work" && classicTheme();
  const lockedIn = (c) => c.locked || (table === "work" && !classic && c.id === "status");
  // Cards: the menu is placed under the heading it was opened from (MenuPanel); a long one is moved up, or cut and scrolled, so all of it is inside the window. (Classic: ColsPanel.)
  useLayoutEffect(() => {
    const el = box.current;
    if (!at || !el) return;
    const h = el.offsetHeight, room = window.innerHeight - 16;
    if (h > room) { el.style.maxHeight = `${room}px`; el.style.top = "8px"; return; }
    const top = parseFloat(el.style.top) || 0;
    if (top + h > window.innerHeight - 8) el.style.top = `${Math.max(8, window.innerHeight - h - 8)}px`;
  }, [at]);
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
    <ColsPanel label={W.PANEL_HEADING} cls="cols-menu cm-7b" anchor={at} fixed="start" onClose={close}>
      <h5 class="cm-head">{W.PANEL_HEADING}</h5>
      {defsOf(table).filter((c) => c.id !== "item").map((c) => {
        const on = shown.includes(c.id);
        return (
          <button key={c.id} type="button" role="menuitemcheckbox" aria-checked={on ? "true" : "false"} data-col-name={c.label} tabIndex={-1} onClick={() => press(c.id, c.label)}>
            <span class="tk" aria-hidden="true">{on ? "✓" : ""}</span>{c.label}
          </button>
        );
      })}
    </ColsPanel>
  ) : at ? (
    <ColsPanel label={W.UNRULED_MENU_LABEL} cls="cols-menu" anchor={at} fixed="start" boxRef={classicTheme() ? undefined : box} onClose={close}>
      {defsOf(table).map((c) => {
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
    </ColsPanel>
  ) : null;
  const out = shownIds(table, shown), drawn = table === "work" && !classic && !out.includes("status") ? ["status", ...out] : out;      // Cards: the Status stays always shown, even after it was unticked in the Classic look
  return { shown: drawn, has: (id) => shown.includes(id), rowProps, button, menu };
}
