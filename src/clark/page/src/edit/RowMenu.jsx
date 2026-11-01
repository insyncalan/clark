// The right-click menu on a work item (#97): a row of the table or a card of the board, by a right click, the menu key or Shift+F10.
// Draft email to the owner (opens the Draft email dialog over a draft clark builds for this one item, POST /api/draft-email: nothing is sent, and the To line is left empty until the People list, #115), the peek, Change status, Move due date and Change owner (each a short list), Show to or Hide from the client, Copy link, Copy ID,
// Duplicate and Archive. Each entry does what its button elsewhere does: a change is one step with Undo in the toast (the cells'
// own words and requests, itemEdit.js), Archive is clark's archive step (never a delete, FR-43c). What each entry offers is in
// ../logic/rowMenu.js. An entry that can't be used is listed with its reason under it. In View the changes are listed but greyed.
// The keys are the menus': Up, Down, Home and End move, Enter or Space runs, Right opens a list, Left or Back returns, Esc closes
// with focus back on the row. One item at a time: the table has no ticked rows yet, so there is nothing to act on together.
import { signal } from "@preact/signals";
import { useEffect, useLayoutEffect, useRef, useState } from "preact/hooks";
import { data, project, mode, view, openPeek, item as peeked, closePeek } from "../stores/report.js";
import { itemRows, announce } from "../stores/work.js";
import { changeCell, changeRecord, say } from "../stores/changes.js";
import { readDraftEmail, sendEmailSent } from "../api.js";
import { DraftEmail } from "../components/DraftEmail.jsx";
import { todayIso } from "../workItems.js";
import { format } from "../router.js";
import { MenuPanel } from "../components/Menu.jsx";
import { Icon } from "../components/Icon.jsx";
import { people, tableOf, canClearDue } from "./itemEdit.js";
import { DuePick } from "./cells/DuePick.jsx";
import { draftEntry, eyeChange, draftRequest, draftState, NOT_OFFERED, statusList, dueList, ownerList, duplicateRequest, rawOf, pickChange, linkFor, VIEW_ONLY } from "../logic/rowMenu.js";
import { openCard } from "./Board.jsx";
import { workSelection } from "../stores/selection.js";

const ROW = "tr[data-id], article.bcard";
const draftOpen = signal(null);                // null, or { id, items, state, draft, today, from }: the Draft email dialog over the page
const state = signal(null);                    // null, or { id, x, y, level: "" | "status" | "due" | "owner", pick: bool, from: the element to give focus back to }

// The element a menu belongs to, and where focus goes back to: a table row, or a card's own button.
const homeOf = (el) => (el.matches("article.bcard") ? el.querySelector(".bc-main") || el : el);
function refocus(id) {
  setTimeout(() => {
    const now = document.activeElement;
    if (now && now !== document.body && now.isConnected) return;
    const el = document.querySelector(`tr[data-id="${CSS.escape(id)}"], article.bcard[data-id="${CSS.escape(id)}"]`);
    if (el) homeOf(el).focus({ preventScroll: true });
  }, 0);
}

function openFor(el, x, y) {
  if (!el.dataset.id) return;
  state.value = { id: el.dataset.id, x, y, level: "", pick: false, from: homeOf(el) };
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
      openFor(el, kbd ? r.left + 24 : e.clientX, kbd ? r.bottom : e.clientY);
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
  const fail = () => { announce.value = "The browser did not copy it."; say("note", "The browser did not copy it. Select the text and press ⌘C instead."); };
  try { navigator.clipboard.writeText(text).then(done, fail); } catch (e) { fail(); }
};

function entries(row, level, edit, d, today) {
  const dr = draftEntry(row, d), why = edit ? "" : VIEW_ONLY;
  const back = { id: "back", name: "Back" };
  if (level === "status") {
    const l = statusList(row);
    return [...l.map((s) => ({ id: "s:" + s, name: s })), ...(l.length ? [] : [{ id: "none", lab: "There is no other status to give this item." }]), { id: "sep", sep: true }, back];
  }
  if (level === "owner") {
    const l = ownerList(people(d), row);
    return [...l.map((n) => ({ id: "o:" + n, name: n })), ...(l.length ? [] : [{ id: "none", lab: "No one else is named in this project yet." }]), { id: "sep", sep: true }, back];
  }
  if (level === "due") {
    return [...dueList(today).map((x) => ({ id: "d:" + x.day, name: x.name, line: x.line })), { id: "pick", name: "Pick a date" },
      ...(canClearDue(row) ? [{ id: "d:", name: "No date" }] : []), { id: "sep", sep: true }, back];
  }
  const edits = (id, name) => ({ id, name, sub: id !== "eye", disabled: !edit, why: edit ? "" : "rm-why-view" });
  return [
    { id: "draft", name: dr.name, line: dr.reason, disabled: dr.disabled },
    { id: "peek", name: "Open the peek" },
    { id: "sep1", sep: true },
    ...(edit ? [] : [{ id: "lab1", lab: why, dom: "rm-why-view" }]),
    edits("status", "Change status"), edits("due", "Move due date"), edits("owner", "Change owner"),
    edits("eye", eyeChange(row).name),
    { id: "sep2", sep: true },
    { id: "link", name: "Copy link to this item" }, { id: "copyid", name: "Copy ID" },
    { id: "sep3", sep: true },
    { id: "dup", name: "Duplicate", disabled: !edit, why: edit ? "" : "rm-why-view" }, { id: "archive", name: "Archive", disabled: !edit, why: edit ? "" : "rm-why-view" },
  ];
}

function Panel({ s }) {
  const row = itemRows.value.find((r) => r.id === s.id), d = data.value, edit = mode.value === "edit";
  const wrap = useRef(null), today = todayIso();
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
  }, [s.level]);
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
    if (id === "back") return set({ level: "" });
    if (id === "status" || id === "due" || id === "owner") return set({ level: id });
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
      return readDraftEmail(code, draftRequest(row.id)).then((r) => {
        if (!r.ok) { say("note", r.message); refocus(row.id); return; }
        if (project.value !== code) return;                      // the person went to another project meanwhile: nothing to open
        draftOpen.value = { id: row.id, items: r.reply.items, state: draftState(r.reply), draft: r.reply.draft, today: todayIso(), from };
      });
    }
    if (id === "peek") { close("pick"); openCard(row.id); return undefined; }
    if (id === "link") { close("pick"); copied(linkFor(row, project.value, location.origin + location.pathname, format), `Link to ${row.id} copied.`); return undefined; }
    if (id === "copyid") { close("pick"); copied(row.id, `${row.id} copied.`); return undefined; }
    if (id === "archive") {
      return record({ kind: tableOf(row), op: "archive", id: row.id, place: "menu" }, { text: `${row.id} archived. It is out of the lists and the published page.`, back: `${row.id} is back.` })
        .then((r) => { if (r && peeked.value === row.id) closePeek(); });
    }
    if (id === "dup") {
      const raw = rawOf(d, row);
      if (!raw) return undefined;
      return record(duplicateRequest(raw, tableOf(row)), { text: `Copy of ${row.id} added.`, back: "" });
    }
    return undefined;
  };
  const keys = (e) => {                            // Right opens a list, Left goes back; Up, Down, Esc and the rest are MenuPanel's
    const at = document.activeElement;
    if (e.key === "ArrowRight" && at && at.dataset.sub) { e.preventDefault(); e.stopPropagation(); run(at.dataset.rm); }
    else if (e.key === "ArrowLeft" && s.level) { e.preventDefault(); e.stopPropagation(); set({ level: "" }); }
  };
  const list = entries(row, s.level, edit, d, today);
  const label = s.level ? `${{ status: "Change status", due: "Move due date", owner: "Change owner" }[s.level]} of ${row.id}` : `Actions for ${row.id}`;
  return (
    <div class="rowmenu" ref={wrap} data-rowmenu={row.id} style="left:-10000px;top:0" onKeyDown={keys}>
      {s.pick ? null : <MenuPanel key={s.level} label={label} cls="rm" onClose={close}>
        {list.map((it) => it.sep ? <div key={it.id} class="sep" role="separator"></div> : it.lab ? <div key={it.id} id={it.dom} class="lab" role="presentation">{it.lab}</div> : (
          <button key={it.id} type="button" role="menuitem" tabIndex={-1} data-rm={it.id} data-sub={it.sub ? "1" : undefined}
            aria-haspopup={it.sub ? "menu" : undefined} aria-disabled={it.disabled ? "true" : undefined}
            aria-describedby={(it.disabled || it.id === "draft") && (it.line || it.why) ? (it.why || "rm-why-" + it.id) : undefined} onClick={() => { if (!it.disabled) run(it.id); }}>
            <span class="rm-t"><b>{it.id === "back" ? "‹ Back" : it.name}</b>{it.line ? <small id={"rm-why-" + it.id}>{it.line}</small> : null}</span>
            {it.sub ? <Icon name="right" cls="rm-go" /> : null}
          </button>
        ))}
      </MenuPanel>}
      {s.pick ? (
        <DuePick row={row} anchor={{ current: s.from }} today={today}
          onPick={(v) => { const c = pickChange(row, "due", v, today); if (c && c.error) return c.error; change("due", v); return ""; }}
          onClose={(back) => { state.value = null; if (back && s.from.isConnected) s.from.focus({ preventScroll: true }); }} />
      ) : null}
    </div>
  );
}

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
const BEHIND = ["#main", ".top"];                // made inert while the Draft email is open

// The Draft email over the page (modal: focus stays inside, Esc closes, focus goes back to the row). It holds the draft the server built;
// each change in the dialog (the kind, the ticks, the options) asks for a new one, and the last answer wins. It sends and saves nothing.
function DraftHost({ d }) {
  const root = useRef(null), asked = useRef(0);
  const edit = mode.value === "edit";                 // View writes nothing (FR-11): no onSent, and "I sent it" is greyed
  const close = () => {
    const from = d.from, id = d.id;
    draftOpen.value = null;
    setTimeout(() => { if (from && from.isConnected) from.focus({ preventScroll: true }); else refocus(id); }, 0);
  };
  useEffect(() => {
    const first = root.current && root.current.querySelector("input, button");
    if (first) first.focus();
    const held = BEHIND.map((q) => document.querySelector(q)).filter(Boolean);
    held.forEach((el) => el.setAttribute("inert", ""));
    return () => held.forEach((el) => el.removeAttribute("inert"));
  }, []);
  useEffect(() => { if (view.value !== "work") draftOpen.value = null; }, [view.value]);        // another page: the dialog goes with it
  useEffect(() => { if (!data.value || !itemRows.value.some((r) => r.id === d.id)) draftOpen.value = null; }, [itemRows.value]);   // the item went
  const onChange = (next) => {
    const n = ++asked.current;
    draftOpen.value = { ...draftOpen.value, state: next };           // the ticks and options show at once; the email follows
    let body;
    try { body = draftRequest(d.id, next); } catch (e) { say("note", e.message); return; }
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
      <DraftEmail items={d.items} state={d.state} draft={d.draft} today={d.today} onChange={onChange} onClose={close} onSent={edit ? (entry) => sendEmailSent(project.value, entry) : undefined} sentOff={edit ? "" : VIEW_ONLY} none={NOT_OFFERED} />
    </div>
  );
}

export function RowMenu() {
  useOpeners();
  const s = state.value, d = draftOpen.value;
  return <>{s ? <Panel s={s} /> : null}{d ? <DraftHost key={d.id} d={d} /> : null}</>;
}
