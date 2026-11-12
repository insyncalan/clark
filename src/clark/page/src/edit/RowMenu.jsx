// The right-click menu on a work item (#97): a row of the table or a card of the board, by a right click, the menu key or Shift+F10.
// Draft email to the owner (opens the Draft email dialog over a draft clark builds for this one item, POST /api/draft-email: nothing is sent, and the To line is left empty until the People list, #115), the peek, Change status, Move due date and Change owner (each a short list), Show to or Hide from the client, Copy link, Copy ID,
// Duplicate and Archive. Each entry does what its button elsewhere does: a change is one step with Undo in the toast (the cells'
// own words and requests, itemEdit.js), Archive is clark's archive step (never a delete, FR-43c). What each entry offers is in
// ../logic/rowMenu.js. An entry that can't be used is listed with its reason under it. On a Dashboard in View the changes are listed but greyed.
// The keys are the menus': Up, Down, Home and End move, Enter or Space runs, Right opens a list, Left or Back returns, Esc closes
// with focus back on the row. One item at a time: the table has no ticked rows yet, so there is nothing to act on together.
import { signal } from "@preact/signals";
import { useEffect, useLayoutEffect, useRef, useState } from "preact/hooks";
import { data, project, view, openPeek, item as peeked, closePeek } from "../stores/report.js";
import { itemRows, announce } from "../stores/work.js";
import { changeCell, changeRecord, say } from "../stores/changes.js";
import { readDraftEmail, sendEmailSent } from "../api.js";
import { DraftEmail } from "../components/DraftEmail.jsx";
import { todayIso } from "../workItems.js";
import { format } from "../router.js";
import { MenuPanel, menuMove, menuItemsIn, useFadeOut } from "../components/Menu.jsx";
import { Icon } from "../components/Icon.jsx";
import { people, tableOf, canClearDue } from "./itemEdit.js";
import { readPeople } from "./peopleApi.js";
import { DuePick } from "./cells/DuePick.jsx";
import { draftEntry, eyeChange, draftRequest, draftState, recipientOf, NOT_OFFERED, statusList, dueList, ownerList, duplicateRequest, duplicateWords, rawOf, pickChange, linkFor, VIEW_ONLY } from "../logic/rowMenu.js";
import { openCard } from "./Board.jsx";
import { deleteItem } from "./deleteItem.js";
import { isEditing } from "../logic/editing.js";
import { workSelection } from "../stores/selection.js";

// The owner link (a person's id) is read here, in the editor, from the data the item came from: the shared row builder never carries it,
// so a published file holds no trace of it (#115).
const withOwnerLink = (row, d) => {
  if (!row || !d) return row;
  const all = [...(d.actions || []), ...(d.raid || []), ...(d.decisions || [])], src = all.find((r) => r.id === row.id);
  return src && typeof src.owner_id === "string" ? { ...row, owner_id: src.owner_id } : row;
};

const ROW = "tr[data-id], article.bcard";
const draftOpen = signal(null);                // null, or { id, items, state, draft, today, from }: the Draft email dialog over the page
const state = signal(null);                    // null, or { id, x, y, fly: "" | "status" | "due" | "owner" (the short list open beside its entry), focusFly: bool, pick: bool, from: the element to give focus back to }

// The element a menu belongs to, and where focus goes back to: a table row, or a card's own button.
const homeOf = (el) => (el.matches("article.bcard") ? el.querySelector(".bc-main") || el : el);
function refocus(id) {
  const back = () => {
    const now = document.activeElement;
    if (now && now !== document.body && now.isConnected) return;
    const el = document.querySelector(`tr[data-id="${CSS.escape(id)}"], article.bcard[data-id="${CSS.escape(id)}"]`);
    if (el) homeOf(el).focus({ preventScroll: true });
  };
  setTimeout(back, 0);
  setTimeout(back, 150);                        // row 848: the change redraws the row after the first look, and the redrawn row had lost the focus; if nothing holds it by then, the row does
}

let opened = 0;                                // counts the opens, so only the last one draws
function openFor(el, x, y, pointer) {
  if (!el.dataset.id) return;
  const at = ++opened;
  // a dismiss while the list is still being read (Escape, or a press anywhere) cancels this open: the menu never appears after it
  const stop = () => { document.removeEventListener("keydown", onKey, true); document.removeEventListener("pointerdown", cancel, true); };
  const cancel = () => { if (at === opened) opened++; stop(); };
  const onKey = (e) => { if (e.key === "Escape") cancel(); };
  document.addEventListener("keydown", onKey, true);
  document.addEventListener("pointerdown", cancel, true);
  // #1048: the People list is read first, so the Draft email entry has its reason line from the first paint (the menu never changes size once open, row 848)
  readPeople().then((r) => {
    stop();
    if (at !== opened || !el.isConnected) return;                  // a later open, or the row went, while the list was read
    state.value = { id: el.dataset.id, x, y, fly: "", focusFly: false, pick: false, from: homeOf(el), pointer: !!pointer, reg: r.ok ? r.people : null };      // row 979: `pointer` marks a mouse open, so the first entry shows no ring until a key is used
  });
}

// A right click, or the menu key or Shift+F10 on the focused row or card (the key opens beside the row, not at the pointer).
// While one or more rows are selected (#195) this menu stands down, and leaves the event alone (no preventDefault): the
// multi-select menu (#196) owns the right click and the keys then (the Head's ruling).
function useOpeners() {
  useEffect(() => {
    const onContext = (e) => {
      if (view.value !== "work" || !e.target.closest || workSelection.size.value >= 1) return;
      const el = e.target.closest(ROW);
      if (!el || e.target.isContentEditable || e.target.closest("input, textarea, select, .cpop, .ddmenu, .rowmenu")) return;
      e.preventDefault();
      const kbd = e.clientX === 0 && e.clientY === 0;             // a key made this one: there is no pointer to put the menu at
      const r = el.getBoundingClientRect();
      openFor(el, kbd ? r.left + 24 : e.clientX, kbd ? r.bottom : e.clientY, !kbd);
    };
    const onKey = (e) => {
      if (view.value !== "work" || workSelection.size.value >= 1 || !(e.key === "ContextMenu" || (e.key === "F10" && e.shiftKey))) return;
      const at = document.activeElement, el = at && at.closest ? at.closest(ROW) : null;
      if (!el || at.isContentEditable || at.closest(".cpop, .ddmenu, .rowmenu, input, textarea")) return;
      e.preventDefault();
      const r = el.getBoundingClientRect();
      openFor(el, r.left + 24, r.bottom);
    };
    document.addEventListener("contextmenu", onContext, true);
    document.addEventListener("keydown", onKey, true);
    return () => { document.removeEventListener("contextmenu", onContext, true); document.removeEventListener("keydown", onKey, true); };
  }, []);
}

const copied = (text, said) => {
  const done = () => { announce.value = said; say("done", said); };
  const fail = () => {                          // item 612: the ⌘C hint only when there is a selection to copy
    const sel = typeof window.getSelection === "function" ? String(window.getSelection() || "") : "";
    announce.value = "The browser did not copy it.";
    say("note", sel.trim() ? "The browser did not copy it. Select the text and press ⌘C instead." : "The browser did not copy it.");
  };
  try { navigator.clipboard.writeText(text).then(done, fail); } catch (e) { fail(); }
};

function entries(row, level, edit, d, today, reg) {
  const dr = draftEntry(row, reg ? { ...d, people: reg } : d), why = edit ? "" : VIEW_ONLY;
  if (!reg && !dr.disabled) dr.reason = "";         // the list is still being read (or could not be): no reason is given yet
  if (level === "status") {
    const l = statusList(row);
    return [...l.map((s) => ({ id: "s:" + s, name: s })), ...(l.length ? [] : [{ id: "none", lab: "There is no other status to give this item." }])];
  }
  if (level === "owner") {
    const l = ownerList(people(d), row);
    return [...l.map((n) => ({ id: "o:" + n, name: n })), ...(l.length ? [] : [{ id: "none", lab: "No one else is named in this project yet." }])];
  }
  if (level === "due") {
    return [...dueList(today).map((x) => ({ id: "d:" + x.day, name: x.name, line: x.line })), { id: "pick", name: "Pick a date" },
      ...(canClearDue(row) ? [{ id: "d:", name: "No date" }] : [])];
  }
  const edits = (id, name, icon) => ({ id, name, icon, sub: edit && id !== "eye", disabled: !edit, why: edit ? "" : "rm-why-view" });
  return [
    { id: "draft", name: dr.name, icon: "pencil", line: dr.reason, disabled: dr.disabled },
    { id: "peek", name: "Open the peek", icon: "expand" },
    { id: "sep1", sep: true },
    ...(edit ? [] : [{ id: "lab1", lab: why, dom: "rm-why-view" }]),
    edits("status", "Change status", "half"), edits("due", "Move due date", "cal"), edits("owner", "Change owner", "user"),
    edits("eye", eyeChange(row).name, row.client ? "eyeoff" : "eye"),
    { id: "sep2", sep: true },
    { id: "link", name: "Copy link to this item", icon: "ext" }, { id: "copyid", name: "Copy ID", icon: "doc" },
    { id: "sep3", sep: true },
    { id: "dup", name: "Duplicate", icon: "plus", disabled: !edit, why: edit ? "" : "rm-why-view" }, { id: "archive", name: "Archive", icon: "archive", disabled: !edit, why: edit ? "" : "rm-why-view" },
    ...(edit ? [{ id: "delete", name: "Delete", icon: "trash", danger: true }] : []),         // item 658: not offered when the page is read only
  ];
}

// A short list (status, due date, owner) open beside its entry: its own box on the window, placed once beside the entry (on the left
// when the right has no room), so the menu itself never moves or changes size (row 848). Up and Down move in it, Left or Esc
// go back to the entry.
function Fly({ level, entries: list, focus, wrap, hover, keep, onPick, onLeave, onClose }) {
  const box = useRef(null);
  useLayoutEffect(() => {
    const el = box.current, menu = wrap.current, at = menu && menu.querySelector(`[data-rm=${level}]`);
    if (!el || !at) return;
    const a = at.getBoundingClientRect(), m = menu.getBoundingClientRect(), w = el.offsetWidth, h = el.offsetHeight;
    const right = m.right + w + 8 <= window.innerWidth;
    el.style.left = `${Math.round(right ? m.right - 2 : Math.max(8, m.left - w + 2))}px`;
    el.style.top = `${Math.round(Math.max(8, Math.min(a.top - 4, window.innerHeight - h - 8)))}px`;
    if (focus) (menuItemsIn(el)[0] || el).focus({ preventScroll: true });
  }, []);
  useFadeOut(box, true, "rowmenu");
  const keys = (e) => {
    if (menuMove(e, menuItemsIn(box.current))) return;
    if (e.key === "ArrowLeft" || e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onLeave(); }
    else if (e.key === "Tab") onClose("tab");
  };
  return (
    <div class="ddmenu on rm-fly" role="menu" ref={box} tabIndex={-1} style="left:-10000px;top:0" aria-label={{ status: "Change status", due: "Move due date", owner: "Change owner" }[level]}
      onKeyDown={keys} onPointerEnter={keep} onPointerLeave={() => hover("")}>
      {list.map((it) => it.lab ? <div key={it.id} class="lab" role="presentation">{it.lab}</div> : (
        <button key={it.id} type="button" role="menuitem" tabIndex={-1} data-rm={it.id} onClick={() => onPick(it.id)}>
          <span class="rm-t"><b>{it.name}</b>{it.line ? <small>{it.line}</small> : null}</span>
        </button>
      ))}
    </div>
  );
}

const REST = 140;      // ms the pointer rests on an entry before its list opens (row 979)

function Panel({ s }) {
  const row = withOwnerLink(itemRows.value.find((r) => r.id === s.id), data.value), d = data.value, edit = true;     // Work items are always editable: View and Edit exist only on the Dashboard (ruled 02-11-2026); this menu is an Edit part, so a published file never draws it
  const wrap = useRef(null), today = todayIso();
  const reg = s.reg;                              // #1048: the People list, read before the menu opens (null when it could not be read)
  const set = (patch) => { state.value = { ...state.value, ...patch }; };
  const close = (how) => {
    const from = s.from;
    state.value = null;
    if ((how === "esc" || how === "pick") && from && from.isConnected) from.focus({ preventScroll: true });
  };
  useLayoutEffect(() => {                         // inside the window, the same rule the pickers have
    const el = wrap.current;
    if (!el) return;
    const w = el.offsetWidth, h = el.offsetHeight;
    el.style.left = `${Math.round(Math.max(8, Math.min(s.x, window.innerWidth - w - 8)))}px`;
    el.style.top = `${Math.round(Math.max(8, Math.min(s.y, window.innerHeight - h - 8)))}px`;
  }, []);                                         // placed once: a list opening beside an entry never moves or resizes the menu (row 848)
  const timer = useRef(0);
  useEffect(() => () => clearTimeout(timer.current), []);
  const hover = (id) => {                         // a pointer on an entry that opens a list opens it; on another entry it closes after a short grace (the list is on the way)
    clearTimeout(timer.current);
    if (id) {      // row 979: a list opens (or swaps for another) only after the pointer has rested on its entry, so a pointer passing over entries does not mount a list at each
      if (state.value && state.value.fly !== id) timer.current = setTimeout(() => { if (state.value && state.value.fly !== id) set({ fly: id, focusFly: false }); }, REST);
      return;
    }
    timer.current = setTimeout(() => { if (state.value && !state.value.focusFly) set({ fly: "" }); }, 250);
  };
  useLayoutEffect(() => {      // row 979: opened by the mouse, the first entry takes the focus without a ring until a key is used (MenuPanel cannot know: its anchor is null on the first draw)
    const box = s.pointer && wrap.current && wrap.current.querySelector(":scope > .ddmenu");
    if (box) box.dataset.pointer = "1";
  }, []);
  useEffect(() => { if (!row) state.value = null; }, [row]);          // the item went (archived, or another project): nothing to act on
  if (!row) return null;

  const change = (field, value) => {
    const c = pickChange(row, field, value, today);
    if (c && c.error) { say("note", c.error); return; }
    close("pick");
    if (c) changeCell(c.table, c.id, c.changes, { text: c.words, back: c.back, always: row.kind === "decision" && field === "status" && value === "Made" }).then(() => refocus(row.id));
  };
  const record = (req, done) => { close("pick"); return changeRecord(req, done).then((r) => { refocus(row.id); return r; }); };
  const run = (id) => {
    if (id === "status" || id === "due" || id === "owner") return set({ fly: id, focusFly: true });
    if (id === "pick") return set({ pick: true });
    if (id.startsWith("s:")) return change("status", id.slice(2));
    if (id.startsWith("o:")) return change("owner", id.slice(2));
    if (id.startsWith("d:")) return change("due", id.slice(2));
    if (id === "eye") {
      const c = eyeChange(row);
      close("pick");
      return changeCell(c.table, c.id, c.changes, { text: c.words, back: c.back }).then(() => refocus(row.id));
    }
    if (id === "draft") {
      const from = s.from, code = project.value;
      close("pick");
      const owner = typeof row.owner_id === "string" ? row.owner_id : "";
      const found = reg ? Promise.resolve(reg) : readPeople().then((r) => (r.ok ? r.people : []));
      return found.then((list) => { const who = recipientOf(list, owner); return readDraftEmail(code, draftRequest(row.id, null, who)).then((r) => [r, who]); }).then(([r, who]) => {
        if (!r.ok) { say("note", r.message); refocus(row.id); return; }
        if (project.value !== code) return;                      // the person went to another project meanwhile: nothing to open
        draftOpen.value = { id: row.id, items: r.reply.items, state: draftState(r.reply), draft: r.reply.draft, today: todayIso(), from, who, person: typeof row.owner_id === "string" ? row.owner_id : "" };
      });
    }
    if (id === "peek") { close("pick"); openCard(row.id); return undefined; }
    if (id === "link") { close("pick"); copied(linkFor(row, project.value, location.origin + location.pathname, format), `Link to ${row.id} copied.`); return undefined; }
    if (id === "copyid") { close("pick"); copied(row.id, `${row.id} copied.`); return undefined; }
    if (id === "archive") {
      const rows = Array.from(document.querySelectorAll(ROW)), at = rows.findIndex((el) => el.dataset.id === row.id), nb = rows[at + 1] || rows[at - 1];   // row 865: the row leaves, so focus goes to its neighbour
      const sel = (id) => `tr[data-id="${CSS.escape(id)}"], article.bcard[data-id="${CSS.escape(id)}"] .bc-main`;
      return record({ kind: tableOf(row), op: "archive", id: row.id, place: "menu" }, { text: `${row.id} archived. It is out of the lists and the published page.`, back: `${row.id} is back.`, focus: sel(row.id) })
        .then((r) => { if (r && peeked.value === row.id) closePeek(); if (r && nb && nb.dataset.id) refocus(nb.dataset.id); });
    }
    if (id === "delete") { close("pick"); deleteItem(row, "menu", row.id); return undefined; }
    if (id === "dup") {
      const raw = rawOf(d, row);
      if (!raw) return undefined;
      return record(duplicateRequest(raw, tableOf(row)), (reply) => duplicateWords(row, reply.ref))
        .then((r) => { if (r && r.ref) openCard(r.ref); });              // #442: the copy opens, as in the prototype
    }
    return undefined;
  };
  const keys = (e) => {                            // Right opens a list, Left goes back; Up, Down, Esc and the rest are MenuPanel's
    const at = document.activeElement;
    if (e.key === "ArrowRight" && at && at.dataset.sub) { e.preventDefault(); e.stopPropagation(); run(at.dataset.rm); }
  };
  const list = entries(row, "", edit, d, today, reg);
  return (
    <div class="rowmenu" ref={wrap} data-rowmenu={row.id} style="left:-10000px;top:0" onKeyDown={keys}>
      {s.pick ? null : <MenuPanel label={`Actions for ${row.id}`} cls="rm" fade="rowmenu" anchor={wrap.current} onClose={close}>
        {list.map((it) => it.sep ? <div key={it.id} class="sep" role="separator"></div> : it.lab ? <div key={it.id} id={it.dom} class="lab" role="presentation">{it.lab}</div> : (
          <button key={it.id} type="button" class={it.danger ? "danger" : undefined} role="menuitem" tabIndex={-1} data-rm={it.id} data-sub={it.sub ? "1" : undefined}
            aria-haspopup={it.sub ? "menu" : undefined} aria-expanded={it.sub ? (s.fly === it.id ? "true" : "false") : undefined}
            onPointerEnter={(e) => { if (e.pointerType !== "touch") hover(it.sub ? it.id : ""); }} aria-disabled={it.disabled ? "true" : undefined}
            aria-describedby={(it.disabled || it.id === "draft") && (it.line || it.why) ? (it.why || "rm-why-" + it.id) : undefined} onClick={() => { if (!it.disabled) run(it.id); }}>
            {it.icon ? <Icon name={it.icon} cls="rm-ic" /> : null}
            <span class="rm-t"><b>{it.id === "back" ? "‹ Back" : it.name}</b>{it.line ? <small id={"rm-why-" + it.id}>{it.line}</small> : null}</span>
            {it.sub ? <Icon name="right" cls="rm-go" /> : null}
          </button>
        ))}
      </MenuPanel>}
      {s.fly && !s.pick ? <Fly key={s.fly} level={s.fly} entries={entries(row, s.fly, edit, d, today, reg)} focus={s.focusFly} wrap={wrap} hover={hover} keep={() => clearTimeout(timer.current)}
        onPick={run} onLeave={() => { set({ fly: "", focusFly: false }); const b = wrap.current && wrap.current.querySelector(`[data-rm=${s.fly}]`); if (b) b.focus({ preventScroll: true }); }} onClose={close} /> : null}
      {s.pick ? (
        <DuePick row={row} anchor={{ current: s.from }} today={today}
          onPick={(v) => { const c = pickChange(row, "due", v, today); if (c && c.error) return c.error; change("due", v); return ""; }}
          onClose={(back) => { state.value = null; if (back && s.from.isConnected) s.from.focus({ preventScroll: true }); }} />
      ) : null}
    </div>
  );
}

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
// While the Draft email is open everything outside it is inert: at every level from the dialog up to the body, each sibling off its path
// (the page, the top bar, the peek, the ask panel, Help, the palette). One that mounts later is held as it appears. Only what this
// function set is released again, so an element that was inert before stays so.
function holdBehind(scrim) {
  const mine = new Set();
  const sweep = () => {
    for (let n = scrim; n && n !== document.body; n = n.parentNode) {
      for (const sib of n.parentNode ? n.parentNode.children : []) {
        if (sib !== n && !sib.hasAttribute("inert") && !/^(SCRIPT|STYLE|LINK)$/.test(sib.tagName)) { sib.setAttribute("inert", ""); mine.add(sib); }
      }
    }
  };
  sweep();
  const watch = typeof MutationObserver === "function" ? new MutationObserver(sweep) : null;
  if (watch) watch.observe(document.body, { childList: true, subtree: true });
  return () => { if (watch) watch.disconnect(); mine.forEach((el) => el.removeAttribute("inert")); };
}

// The Draft email over the page (modal: focus stays inside, Esc closes, focus goes back to the row). It holds the draft the server built;
// each change in the dialog (the kind, the ticks, the options) asks for a new one, and the last answer wins. It sends and saves nothing.
function DraftHost({ d }) {
  const root = useRef(null), asked = useRef(0);
  const edit = isEditing();                          // a Dashboard in View writes nothing (FR-11): no onSent, and "I sent it" is greyed; Work items have no mode (row 824)
  const close = () => {
    const from = d.from, id = d.id;
    draftOpen.value = null;
    setTimeout(() => { if (from && from.isConnected) from.focus({ preventScroll: true }); else refocus(id); }, 0);
  };
  useEffect(() => {
    const first = root.current && root.current.querySelector("input, button");
    if (first) first.focus();
    const box = root.current && root.current.querySelector(".de");
    if (box) box.setAttribute("aria-modal", "true");
    return root.current ? holdBehind(root.current) : undefined;
  }, []);
  useEffect(() => { if (view.value !== "work") draftOpen.value = null; }, [view.value]);        // another page: the dialog goes with it
  useEffect(() => { if (!data.value || !itemRows.value.some((r) => r.id === d.id)) draftOpen.value = null; }, [itemRows.value]);   // the item went
  const onChange = (next) => {
    const n = ++asked.current;
    draftOpen.value = { ...draftOpen.value, state: next };           // the ticks and options show at once; the email follows
    let body;
    try { body = draftRequest(d.id, next, d.who); } catch (e) { say("note", e.message); return; }
    readDraftEmail(project.value, body).then((r) => {
      if (n !== asked.current || !draftOpen.value) return;
      if (!r.ok) { say("note", r.message); return; }
      draftOpen.value = { ...draftOpen.value, state: draftState(r.reply, next), draft: r.reply.draft, items: r.reply.items };
    });
  };
  const keys = (e) => {
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); return; }
    if (e.key !== "Tab" || !root.current) return;
    const all = Array.from(root.current.querySelectorAll(FOCUSABLE));
    if (!all.length) return;
    const first = all[0], last = all[all.length - 1];
    if (!root.current.contains(document.activeElement)) { e.preventDefault(); first.focus(); }
    else if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  };
  return (
    <div class="ad-scrim" data-draft-email={d.id} ref={root} onKeyDown={keys} onPointerDown={(e) => { if (e.target === e.currentTarget) close(); }}>
      <DraftEmail items={d.items} state={d.state} draft={d.draft} today={d.today} onChange={onChange} onClose={close} onSent={edit ? (entry) => sendEmailSent(project.value, entry, { person: d.person, tone: d.draft ? d.draft.tone : null, reply_by: d.state ? d.state.replyBy : "" }) : undefined} sentOff={edit ? "" : VIEW_ONLY} none={NOT_OFFERED} />
    </div>
  );
}

export function RowMenu() {
  useOpeners();
  const s = state.value, d = draftOpen.value;
  return <>{s ? <Panel s={s} /> : null}{d ? <DraftHost key={d.id} d={d} /> : null}</>;
}
