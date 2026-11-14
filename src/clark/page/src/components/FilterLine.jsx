// The one filter line above the Work items table. The box holds the whole line as text (issue 662): it is read by the parser of
// logic/filterQueryParse.js and shown with its tokens drawn over the text (field names plain, values as coloured chips, a token that cannot be
// used underlined in red with its words), the match count sits inside the box on the right, an x clears it, and the list changes about 400 ms
// after the last key, not on Enter. The pure parts (pieces, messages, the rows a line shows) are in logic/filterQueryUi.js; saved views as
// tabs and the one View menu stay as they were (row 813 took the Freshness menu away; its words stay in the typed line). The list of suggestions (fields, then a field's values) is step 5 of the issue. "/" focuses the line only where nothing took the key first.
import { ImportExport } from "./ImportExport.jsx";
import { useEffect, useLayoutEffect, useRef, useState } from "preact/hooks";
import { signal } from "@preact/signals";
import { rows as allRows, project, filterCtx, fromFile, peek } from "../stores/report.js";
import { lineText, setLine, local } from "../stores/line.js";
import * as FL from "../logic/filterLine.js";
import * as Q from "../logic/filterQueryUi.js";
import { Menu, Fade } from "./Menu.jsx";
import { Icon } from "./Icon.jsx";
import { work, setWork, announce } from "../stores/work.js";
import { say, sayLocalUndo } from "../stores/changes.js";
import { GROUPS, LANE_GROUPS, groupLabel, boardGroup } from "../logic/board.js";

export const PAUSE = 400;                                // ms after the last key before the typed line is applied (the owner's 300 to 500)

// A saved view whose line the filter line no longer reads (a word it does not know) stays on the tabs with a plain message, and can be renamed
// or deleted like any other, so a view that cannot be read can still be fixed or removed. The one view left out is a starting view the page cannot answer yet (an earlier version's Waiting on the client, whose
// is:needed word item 1158 took out): Q.heldBackQuery. Choosing a view that cannot be read does not touch the line.

// Which saved view is chosen, per project, for this visit. A page change keeps it; a reload goes back to the view the line matches.
const chosen = signal({});
const viewsRev = signal(0);

function viewsOf(code) { void viewsRev.value; return FL.viewsGet(local(), code); }
function saveViews(code, views) { FL.viewsPut(local(), code, views); viewsRev.value++; }


// The View menu's Group by and Swimlanes entries (row 812: Table and Board are the two-icon switch beside it; the prototype's words: "Group by", then on the board "Swimlanes" with
// "No lanes", "Workstream lanes", "Type lanes"; the lane Group by uses is not offered). `board` is false where there is no board.
export function layoutItems(w, board) {
  const onBoard = board && w.view === "board", g = onBoard ? boardGroup(w.group) : w.group;
  const lane = onBoard && w.lane && w.lane !== g && LANE_GROUPS.includes(w.lane) ? w.lane : "none";
  const out = [];
  out.push({ id: "lab-group", lab: "Group by" }, ...GROUPS.filter((x) => !onBoard || x.id !== "nothing").map((x) => ({ id: `group:${x.id}`, name: x.label, checked: x.id === g })));
  if (onBoard) out.push({ id: "sep-lanes", sep: true }, { id: "lab-lanes", lab: "Swimlanes" }, { id: "lane:none", name: "No lanes", checked: lane === "none" },
    ...LANE_GROUPS.filter((x) => x !== g).map((x) => ({ id: `lane:${x}`, name: `${groupLabel(x)} lanes`, checked: lane === x })));
  return { items: out, label: `Group by: ${groupLabel(g)}${lane !== "none" ? `, ${groupLabel(lane).toLowerCase()} lanes` : ""}` };
}

// Row 812: the list and the board as a two-icon switch (row 1084 names the buttons "List" and "Board"; "Layout" names the pair).
function LayoutSwitch() {
  const onBoard = work.value.view === "board";
  return (
    <div class="seg lsw" role="group" aria-label="Layout">
      {["table", "board"].map((k) => {
        const word = k === "table" ? "List" : "Board";
        return <button type="button" key={k} data-lay={k} aria-label={word} title={word} aria-pressed={onBoard === (k === "board") ? "true" : "false"} onClick={() => pickLayout(`layout:${k}`)}><Icon name={k} /></button>;
      })}
    </div>
  );
}

// Row 1084: List, Board and Group by are three icon buttons at the right end of the filter box line (they were at the right of the tab row).
// Group by is the one View menu (grouping, and on the board the swimlanes) as an icon-only button named "Group by".
function ViewIcons({ board }) {
  if (fromFile.value) return null;
  const lay = layoutItems(work.value, !!board);
  return (
    <span class="vicons">
      {board ? <LayoutSwitch /> : null}
      <Menu label="" ariaLabel={lay.label} tip="Group by" icon="group" chevron={false} id="viewMenu" btnCls="btn sm vgb" menuId="viewMenuList" menuLabel="Group by" items={lay.items} onPick={pickLayout} />
    </span>
  );
}

function pickLayout(id) {
  const [what, v] = id.split(":");
  if (what === "layout") { setWork({ view: v }); announce.value = v === "board" ? `Showing the board, grouped by ${groupLabel(boardGroup(work.value.group))}.` : "Showing the table."; }
  else if (what === "group") { const lane = work.value.lane; setWork({ group: v, lane: lane === v ? null : lane }); announce.value = `Grouped by ${groupLabel(v)}.`; }
  else if (what === "lane") { setWork({ lane: v === "none" ? null : v }); announce.value = v === "none" ? "No lanes." : `${groupLabel(v)} lanes.`; }
}

function SavedViews({ board }) {
  const code = project.value, rows = allRows.value, ctx = filterCtx(), line = lineText.value;
  const [moving, setMoving] = useState(null);             // row 1071: the id of the tab Move view is moving with the arrow keys, or null
  const [draft, setDraft] = useState(null);               // row 1071: while a tab is dragged, the ids of the tabs in the order shown; saved when it is let go
  const drag = useRef(null), swallow = useRef(false);
  const all = viewsOf(code), here = FL.visibleViews(all).filter((v) => !Q.heldBackQuery(v, rows, ctx));
  const shown = draft && draft.length === here.length && draft.every((id) => here.some((v) => v.id === id)) ? draft.map((id) => here.find((v) => v.id === id)) : here;
  const trouble = (v) => Q.troubleQuery(v, rows, ctx);
  const nameBox = useRef(null);
  const [form, setForm] = useState(null);                 // null, or {mode: "rename" | "note", name, error}; a new view has no form now (row 1073), so "saveas" is only ever a menu id, and Delete view has no question (row 1071)
  const mine = chosen.value[code];
  const matching = shown.find((v) => !trouble(v) && !Q.differsQuery(v, line, rows, ctx)) || null;
  const active = shown.find((v) => v.id === mine) || matching;
  const said = active ? trouble(active) : "";
  const dirty = !!active && !said && Q.differsQuery(active, line, rows, ctx);
  // Row 844: the view the line matched stays the chosen tab when the line is then changed, so the dot shows on it and Discard changes has a view to go back to.
  const afterDelete = useRef(null);      // what was chosen right after a Delete view: "", or the view the effect below then picked by itself (no click)
  useEffect(() => { if (chosen.value[code] !== mine) return; /* a slow effect from an older render must not undo a tab chosen since, such as the Undo of a delete */ if (matching && !shown.some((v) => v.id === mine)) { chosen.value = { ...chosen.value, [code]: matching.id }; if (afterDelete.current !== null) afterDelete.current = matching.id; } }, [matching && matching.id, code]);
  const click = (e, v) => { if (swallow.current) { swallow.current = false; e.preventDefault(); return; } pick(v); };      // the click that ends a drag chooses nothing
  const pick = (v) => { chosen.value = { ...chosen.value, [code]: v.id }; if (!trouble(v)) setLine(v.line); };
  // The open tab and its arrow are brought into view inside the scrolling row (the row alone moves, never the page).
  const tabsBox = useRef(null);
  useEffect(() => {
    const show = () => {
      const row = tabsBox.current, on = row && row.querySelector('.vtab[aria-pressed="true"]');
      if (!on) return;
      const at = (on.parentElement || on).getBoundingClientRect(), box = row.getBoundingClientRect();
      if (at.right > box.right) row.scrollLeft += at.right - box.right;
      else if (at.left < box.left) row.scrollLeft -= box.left - at.left;
    };
    show();
    window.addEventListener("resize", show);      // a narrower window can push the open tab out of the box
    return () => window.removeEventListener("resize", show);
  }, [active && active.id, shown.length, dirty]);      // dirty: Save view and Discard changes take room beside the tabs, so the open tab is brought into view again
  const act = (id) => {
    const fromNew = !!document.activeElement && document.activeElement.id === "viewNew";      // the + New view button keeps the focus; a menu arrow's focus goes with its list
    if (/^(layout|group|lane):/.test(id)) pickLayout(id);
    else if (id === "discard" && active) { pick(active); const el = document.querySelector('.vtab[aria-pressed="true"]'); if (el) el.focus(); }
    else if (id === "save" && active) { const r = FL.saveView(all, active.id, line.trim()); if (r.ok) { saveViews(code, r.views); say("done", `View saved: ${active.name}`); } }
    else if (id === "saveas") {          // row 1073: made at once, named View 1, View 2 ...; Rename… changes the name
      const r = FL.addView(all, FL.nextViewName(all), line.trim());
      if (!r.ok) { say("problem", r.message); return; }
      saveViews(code, r.views);
      chosen.value = { ...chosen.value, [code]: r.id };
      setTimeout(() => { if (!fromNew) focusTab(r.id); }, 0);      // the arrow that had the focus goes with the old open tab: the new tab takes it; + New view keeps its own focus
    }
    else if (id === "rename" && active) setForm({ mode: "rename", name: active.name, error: "" });
    else if (id === "move" && active) { setMoving(active.id); announce.value = `Moving ${active.name}. Press Left or Right arrow to move it, Enter to finish.`; setTimeout(() => focusTab(active.id), 60); }
    else if (id === "duplicate" && active) {
      const r = FL.duplicateView(all, active.id);
      if (!r.ok) { say("problem", r.message); return; }
      saveViews(code, r.views); chosen.value = { ...chosen.value, [code]: r.id };
      announce.value = `Duplicated as ${r.views.find((v) => v.id === r.id).name}.`;
      setTimeout(() => focusTab(r.id), 0);      // the arrow that had the focus goes with the old open tab: the copy's tab takes it
    } else if (id === "delete" && active) {
      // Row 1071: no question first; the message at the foot of the page has Undo, which puts the view back where it was
      const at = all.findIndex((v) => v.id === active.id), gone = active, r = FL.deleteView(all, gone.id);
      if (!r.ok) { say("problem", r.message); return; }
      saveViews(code, r.views); chosen.value = { ...chosen.value, [code]: "" }; afterDelete.current = "";
      sayLocalUndo("done", `View deleted: ${gone.name}`, () => {
        const b = FL.insertView(viewsOf(code), gone, at);
        if (!b.ok) { say("problem", b.message); return; }          // a name taken since, say, is told, never silent
        saveViews(code, b.views);
        const now = chosen.value[code];          // the restored view is chosen only if no other tab was chosen since the delete
        if (!now || now === gone.id || now === afterDelete.current) chosen.value = { ...chosen.value, [code]: gone.id };
      }, code);
      setTimeout(() => { const el = document.getElementById("viewNew"); if (el) el.focus(); }, 0);
    }
  };
  const focusTab = (id) => { const el = document.querySelector(`.vtab[data-view-id="${id}"]`); if (el && document.activeElement !== el) el.focus(); };
  const shownIds = shown.map((v) => v.id);
  // The tab being moved keeps the focus when the order changes (a moved element may lose it), and the move ends when the focus goes elsewhere.
  useEffect(() => { if (moving) focusTab(moving); }, [moving, shownIds.join(",")]);
  useEffect(() => {
    if (!moving) return undefined;
    const away = (e) => { if (!(e.target.closest && e.target.closest(`.vtab[data-view-id="${moving}"]`))) setMoving(null); };
    document.addEventListener("pointerdown", away, true);
    return () => document.removeEventListener("pointerdown", away, true);
  }, [moving]);
  // Keys go to the page while a tab is being moved, not to the tab: a moved tab may lose the focus for a moment, and a key pressed then must still count.
  const live = useRef(null);
  live.current = () => {
    const ids = FL.visibleViews(viewsOf(code)).filter((x) => !Q.heldBackQuery(x, rows, ctx)).map((x) => x.id);      // read again each time: two keys can come before the page has drawn the first move
    const v = shown.find((x) => x.id === moving);
    return v && ids.includes(v.id) ? { v, ids, code } : null;
  };
  useLayoutEffect(() => {          // a layout effect: the keys count from the moment the tab shows it is being moved
    if (!moving) return undefined;
    const onKey = (e) => {
      const c = live.current();
      if (!c) return;
      if (e.key === "Enter" || e.key === "Escape") { e.preventDefault(); e.stopPropagation(); setMoving(null); announce.value = `${c.v.name} is tab ${c.ids.indexOf(c.v.id) + 1} of ${c.ids.length}.`; return; }
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      e.preventDefault(); e.stopPropagation();
      const i = c.ids.indexOf(c.v.id), j = i + (e.key === "ArrowLeft" ? -1 : 1);
      if (j < 0 || j >= c.ids.length) return;
      const ids = c.ids.slice(); ids[i] = ids[j]; ids[j] = c.v.id;
      const r = FL.reorderViews(viewsOf(c.code), ids);
      if (r.ok) { saveViews(c.code, r.views); announce.value = `${c.v.name} moved to tab ${j + 1} of ${ids.length}.`; }
    };
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
  }, [moving]);
  // Row 1071: pick a tab up with the mouse (or a pen) and drag it left or right. A press that does not move is a click (it chooses the tab). Esc puts it back.
  // A finger keeps scrolling the row, so touch uses Move view.
  const pressTab = (e, v) => {
    if (e.button !== 0 || e.pointerType === "touch" || moving || drag.current || shownIds.length < 2) return;
    const btn = e.currentTarget, d = { id: v.id, x0: e.clientX, y0: e.clientY, pid: e.pointerId, on: false, dead: false, ids: shownIds.slice(), from: shownIds.join(",") };
    drag.current = d;
    const stop = (ev) => ev.preventDefault();
    const finish = () => {
      document.removeEventListener("pointermove", move, true); document.removeEventListener("pointerup", up, true); document.removeEventListener("pointercancel", cancel, true);
      document.removeEventListener("keydown", key, true); document.removeEventListener("selectstart", stop, true); document.removeEventListener("dragstart", stop, true);
      document.documentElement.classList.remove("vdragging"); drag.current = null;
      if (d.on) { swallow.current = true; setTimeout(() => { swallow.current = false; }, 0); }
    };
    const move = (ev) => {
      if (d.dead) return;
      if (!d.on) {
        if (Math.abs(ev.clientX - d.x0) < 5 && Math.abs(ev.clientY - d.y0) < 5) return;
        d.on = true; document.documentElement.classList.add("vdragging");
        try { btn.setPointerCapture(d.pid); } catch (x) { /* the press has ended already */ }
        const sel = window.getSelection && window.getSelection(); if (sel) sel.removeAllRanges();
        setDraft(d.ids);
      }
      ev.preventDefault();
      const row = tabsBox.current, box = row.getBoundingClientRect();
      if (ev.clientX < box.left + 24) row.scrollLeft -= 14; else if (ev.clientX > box.right - 24) row.scrollLeft += 14;
      const others = [...row.querySelectorAll(".vt")].filter((el) => el.querySelector(".vtab").dataset.viewId !== d.id);
      const want = others.filter((el) => { const r = el.getBoundingClientRect(); return r.left + r.width / 2 < ev.clientX; }).length;
      const rest = d.ids.filter((id) => id !== d.id);
      if (d.ids.indexOf(d.id) !== want) { rest.splice(want, 0, d.id); d.ids = rest; setDraft(rest); }
    };
    const up = () => {
      const was = d.on && !d.dead && d.ids.join(",") !== d.from;
      finish();
      if (was) {
        setDraft(null);
        const r = FL.reorderViews(viewsOf(code), d.ids);
        if (r.ok) { saveViews(code, r.views); announce.value = `${v.name} moved to tab ${d.ids.indexOf(d.id) + 1} of ${d.ids.length}.`; }
      } else if (d.on) setDraft(null);
    };
    const cancel = () => { finish(); if (d.on) setDraft(null); };
    const key = (ev) => {
      if (ev.key !== "Escape" || d.dead) return;
      ev.preventDefault(); ev.stopPropagation();
      d.dead = true; if (d.on) setDraft(null);
      document.documentElement.classList.remove("vdragging");
    };
    document.addEventListener("pointermove", move, true); document.addEventListener("pointerup", up, true); document.addEventListener("pointercancel", cancel, true);
    document.addEventListener("keydown", key, true); document.addEventListener("selectstart", stop, true); document.addEventListener("dragstart", stop, true);
  };
  // The form's input goes with the form, so focus is handed to the button that opened it (the tab's own menu for a rename or a delete) a moment after it closes.
  const closeForm = () => {
    const mode = form && form.mode;
    setForm(null);
    const order = mode === "rename" ? ["viewTabMenu", "viewNew", "viewMenu"] : ["viewNew", "viewMenu", "viewTabMenu"];
    setTimeout(() => { const el = order.map((id) => document.getElementById(id)).find(Boolean); if (el) el.focus(); }, 0);
  };
  const submit = (e) => {
    e.preventDefault();
    const r = FL.renameView(all, active.id, form.name);
    if (!r.ok) { setForm({ ...form, error: r.message }); return; }
    saveViews(code, r.views);
    closeForm();
  };
  // The name box takes focus once the menu has given focus back to its button (it does that in an effect of its own, so we go a moment later).
  useEffect(() => {
    if (!form || form.mode === "note") return undefined;
    const t = setTimeout(() => { if (nameBox.current) nameBox.current.focus(); }, 40);
    return () => clearTimeout(t);
  }, [form && form.mode]);
  // The open tab's own menu (the small arrow beside its name): Save changes only while the dot shows and never on a core view; Rename and Delete on any view, a core one too. Save view and Discard changes sit beside the tabs while the dot shows (Save view never on a core view).
  const core = !!active && FL.isCoreView(active);
  const tabItems = [];
  if (active && dirty && !core) tabItems.push({ id: "save", name: "Save changes", icon: "check" });
  tabItems.push({ id: "saveas", name: "Save as a new view…", icon: "plus" });
  if (active) {      // row 1071: the four words the issue approves, each with its icon; Delete view in red
    tabItems.push({ id: "rename", name: "Rename view", icon: "pencil" });
    if (shown.length > 1) tabItems.push({ id: "move", name: "Move view", icon: "move" });
    tabItems.push({ id: "duplicate", name: "Duplicate view", icon: "copy" });
    tabItems.push({ id: "delete", name: "Delete view", icon: "trash", danger: true });
  }
  return (
    <div class="fviews">
      <div class="fvrow">
      <div class="vtabs" role="group" aria-label="Saved views" ref={tabsBox}>
        {shown.map((v) => {
          const on = !!active && active.id === v.id, dot = on && dirty, bad = trouble(v), count = bad ? 0 : Q.rowsFor(rows, v.line, ctx).length;
          // the small arrow sits right beside the open tab's name
          const arrow = on && !fromFile.value ? <Menu label="" ariaLabel={`Options for ${v.name}`} id="viewTabMenu" btnCls="vtabmenu" menuId="viewTabMenuList" fixed="start" menuLabel={`Options for ${v.name}`} items={tabItems} onPick={act} /> : null;
          if (bad) {          // no count: the line is not applied, so there is nothing to count
            return (
              <span class="vt" key={v.id} data-lifted={draft && drag.current && drag.current.id === v.id ? "" : undefined}>
                <button type="button" class="vtab" data-view-id={v.id} data-broken="true" aria-pressed={on ? "true" : "false"} data-moving={moving === v.id ? "" : undefined} title={bad} onClick={(e) => click(e, v)} onPointerDown={(e) => pressTab(e, v)}
                  aria-label={`${v.name}, cannot be used any more`}>
                  <span>{v.name}</span>
                </button>{arrow}
              </span>
            );
          }
          return (
            <span class="vt" key={v.id} data-lifted={draft && drag.current && drag.current.id === v.id ? "" : undefined}>
              <button type="button" class="vtab" data-view-id={v.id} aria-pressed={on ? "true" : "false"} data-moving={moving === v.id ? "" : undefined} onClick={(e) => click(e, v)} onPointerDown={(e) => pressTab(e, v)}
                aria-label={`${v.name}, ${count} ${count === 1 ? "item" : "items"}${dot ? ", the line has changes you have not saved" : ""}`}>
                <span>{v.name}</span><em class="num">{count}</em>{dot ? <i class="fdot" data-dot aria-hidden="true"></i> : null}
              </button>{arrow}
            </span>
          );
        })}
      </div>
      {fromFile.value ? null : <button type="button" class="vnew" id="viewNew" onClick={() => act("saveas")}>{"+ New view"}</button>}
      {fromFile.value || !dirty ? null : (
        <span class="fvacts">
          {core ? null : <button type="button" class="btn sm" id="fvSave" onClick={() => act("save")}>Save view</button>}
          <button type="button" class="link" id="fvRevert" onClick={() => act("discard")}>Discard changes</button>
        </span>
      )}
      </div>
      {form ? (
        <form class="vform" onSubmit={submit} onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); closeForm(); } }}>
          {form.mode === "note" ? null : (
            <>
              <label for="vname">New name for this view</label>
              <input id="vname" type="text" value={form.name} maxLength={FL.MAX_NAME} ref={nameBox} onInput={(e) => setForm({ ...form, name: e.target.value, error: "" })} />
              <button type="submit" class="btn sm" id="vsave">Save</button>
            </>
          )}
          <button type="button" class="btn sm" onClick={closeForm}>{form.mode === "note" ? "Close" : "Cancel"}</button>
          <span class="vmsg" role="status">{form.error}</span>
        </form>
      ) : null}
      <p class="vbad" role="status" data-vbad>{said}</p>
    </div>
  );
}

// The ids of the Work items line's parts (its tests and the help name them); a page with a line of its own passes its own set.
export const WORK_IDS = { input: "fline-input", list: "fline-list", count: "fline-count", x: "fline-x", msg: "fline-msg", gloss: "fline-gloss", opt: "fo" };

// Row 1085: the box alone, as one piece any page can draw over its own line: `line` is the line to show and `now()` reads it as it is this moment,
// `apply(text)` makes it the page's line, `rows` and `ctx` are what the line reads, `extra` its schema (the Work items line passes none; a page's own
// schema, filterQueryParse.ownSchema, makes the box know only that page's fields), `ids` its element ids, `label` the box's name, `hints` the Try row
// (null: no row and no gloss), `meaning(chip)` a chip's plain words for the gloss, `notes(parsed)` more to say under the box, `onClear` what else the x
// does, `head` what stands over the box inside its focus (the Work items saved views), and `tail` what stands at the right end of the box line (the Work items import/export and view icons). The Work items line (FilterLine, below) is this box with its stores.
export function LineBox({ head, line, now, apply: applyLine, rows, ctx, extra, ids = WORK_IDS, label, hints = null, meaning = null, notes: moreNotes = null, onClear = null, tail = null }) {
  const first = useRef(null);
  if (first.current === null) first.current = Q.splitLine(line, rows, ctx, extra);
  const live = useRef({ chips: first.current.chips, draft: first.current.rest });     // what the box holds right now, for a key that comes before the next draw
  const [chips, setChipsRaw] = useState(first.current.chips);   // row 845: the complete filters, each a chip with its own remove button
  const [draft, setDraftRaw] = useState(first.current.rest);    // the text in the box (plain words and the word being typed); the line (lineText) is what the list shows, and follows chips and box after a pause
  const [focused, setFocused] = useState(false);
  const [caret, setCaret] = useState(0);
  const [active, setActive] = useState(-1);                   // the suggestion the arrows are on (-1: none)
  const [armed, setArmed] = useState(false);                 // row 931: Space or Arrow Down opened the list; entering the box, a choice that ends the word and Esc close it
  const [gloss, setGloss] = useState("");                    // the plain meaning of the chip the pointer or focus is on, shown in the examples line
  const setChips = (v) => { live.current.chips = v; setChipsRaw(v); };
  const setDraft = (v) => { live.current.draft = v; setDraftRaw(v); };
  const input = useRef(null), over = useRef(null), box = useRef(null), timer = useRef(0), applied = useRef(line), want = useRef(null);
  // A change that did not come from this box (a tab, a switch, Clear filter, another project) puts its line in the box and drops a pending apply.
  useLayoutEffect(() => {      // before paint: a late run would wipe what was typed just after a tab was chosen
    const cur = now();      // the line as it is now, not as the draw that scheduled this saw it: a key can apply a newer one before the effect runs
    if (cur !== applied.current) { clearTimeout(timer.current); applied.current = cur; const s = Q.splitLine(cur, rows, ctx, extra); setChips(s.chips); setDraft(s.rest); }
  }, [line]);
  useEffect(() => () => clearTimeout(timer.current), []);
  const apply = (text) => { applied.current = text; applyLine(text); };
  const later = (text) => { clearTimeout(timer.current); timer.current = setTimeout(() => { if (text !== now()) apply(text); }, PAUSE); };
  // A change of the text: filters the caret has moved past become chips, the rest stays in the box.
  const edit = (text, at) => {
    const c = Q.commitDraft(text, at === undefined ? text.length : at, rows, ctx, extra), next = c.chips.length ? [...live.current.chips, ...c.chips] : live.current.chips;
    if (c.chips.length) { setChips(next); want.current = c.caret; }
    setDraft(c.text); later(Q.joinLine(next, c.text));
  };
  const dropChip = (i) => {
    clearTimeout(timer.current);
    const next = live.current.chips.filter((_, j) => j !== i);
    setChips(next); apply(Q.joinLine(next, live.current.draft));
    if (input.current) input.current.focus();
  };
  const readCaret = () => { if (input.current) setCaret(input.current.selectionStart || 0); };
  // The tokens are drawn in a layer over the (clear-text) input: it follows the input's own sideways scroll. A caret put by a choice is set here, after the draw.
  useLayoutEffect(() => {
    if (want.current !== null && input.current) { const at = want.current; want.current = null; input.current.setSelectionRange(at, at); setCaret(at); }
    if (over.current && input.current) over.current.scrollLeft = input.current.scrollLeft;
  });
  const parsed = Q.parseFor(draft, rows, ctx, extra), shown = Q.pieces(draft, parsed, focused ? caret : undefined, extra);
  const matches = Q.rowsFor(rows, line, ctx, extra).length;
  const words = shown.filter((p) => p.cls === "err" && p.message).map((p) => p.message);
  const notes = [...words, ...(moreNotes ? moreNotes(Q.parseFor(Q.joinLine(chips, draft), rows, ctx, extra)) : [])];
  const options = focused ? Q.withCounts(Q.suggestions(draft, caret, rows, ctx, extra), chips, rows, ctx, extra) : [];
  const wordNow = Q.wordAt(draft, caret).word;
  const listed = focused && armed && options.length > 0;
  const pick = (o) => {
    const r = Q.accept(draft, caret, o);
    want.current = r.caret; edit(r.text, r.caret); setActive(-1); setArmed(!o.close);   // item 1058: a key (no close) keeps the list open, now on its values
    if (input.current) input.current.focus();
  };
  const clear = () => {
    clearTimeout(timer.current);
    if (onClear) onClear();
    setChips([]); setDraft(""); apply("");
    if (input.current) input.current.focus();
  };
  const onKeyDown = (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (!options.length || (!listed && e.key === "ArrowUp")) return;
      e.preventDefault();
      if (!listed) { setArmed(true); setActive(0); return; }
      setActive(e.key === "ArrowDown" ? (active + 1) % options.length : (active < 0 ? options.length : active) - 1);
    } else if (((e.key === "Backspace" && e.target.selectionStart === 0 && e.target.selectionEnd === 0) || (e.key === "Delete" && live.current.draft === "")) && live.current.chips.length) {
      e.preventDefault(); dropChip(live.current.chips.length - 1);        // an empty box takes the last chip away (Delete too, item 1014)
    } else if ((e.key === "Backspace" || e.key === "Delete") && e.target.selectionStart === e.target.selectionEnd && Q.dropWordAt(live.current.draft, e.target.selectionStart, e.key)) {
      e.preventDefault();        // item 1014: the caret right after a half-typed field:value takes the whole word away, not one letter at a time
      const r = Q.dropWordAt(live.current.draft, e.target.selectionStart, e.key);
      want.current = r.caret; edit(r.text, r.caret); setActive(-1);
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (listed && active >= 0 && options[active]) pick(options[active]);
    } else if (e.key === "Tab" && listed && !e.shiftKey && (active >= 0 || wordNow !== "")) {
      e.preventDefault();
      pick(options[active >= 0 ? active : 0]);
    } else if (e.key === " " && !e.ctrlKey && !e.metaKey && !e.altKey) {
      setArmed(true);                                          // the space itself is typed as always; the list follows it
    } else if (e.key === "Escape" && listed) {
      e.preventDefault(); e.stopPropagation(); setArmed(false); setActive(-1);
    }
  };
  // Leaving the line closes the list. While the button is still down (a click on a row or card took the focus) the closing waits for the
  // button to come up, so the click still lands on the row under the pointer.
  const down = useRef(false), late = useRef(false);
  const leave = () => {
    if (down.current) { late.current = true; return; }
    setFocused(false); setArmed(false); setActive(-1);
  };
  useEffect(() => {
    const press = () => { down.current = true; };
    const lift = () => { down.current = false; if (late.current) { late.current = false; if (!box.current || !box.current.contains(document.activeElement)) leave(); } };
    // The button comes up as a pointerup, or as a mouseup or a click when a row drawn again took the pointer's capture with it.
    const ups = ["pointerup", "pointercancel", "mouseup", "click", "lostpointercapture"];
    document.addEventListener("pointerdown", press, true);
    ups.forEach((n) => document.addEventListener(n, lift, true));
    return () => { document.removeEventListener("pointerdown", press, true); ups.forEach((n) => document.removeEventListener(n, lift, true)); };
  }, []);
  useEffect(() => { if (listed && active >= 0) { const el = document.getElementById(`${ids.opt}-${active}`); if (el && el.scrollIntoView) el.scrollIntoView({ block: "nearest" }); } }, [active, listed]);
  const aim = (p) => (e) => {          // a press on an underlined token puts the caret at its end (the layer sits over the box)
    e.preventDefault();
    if (input.current) { input.current.focus(); input.current.setSelectionRange(p.end, p.end); readCaret(); }
  };
  // "/" focuses the line only where nothing took the key first. In the app the ask panel's capture handler does, so this does not run
  // there and the page does not advertise it; it stays for a page without that handler.
  useEffect(() => {
    const slash = (e) => {
      if (e.key !== "/" || e.ctrlKey || e.metaKey || e.altKey || e.defaultPrevented) return;
      const t = e.target, tag = t && t.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || (t && t.isContentEditable)) return;
      if (document.querySelector('[role="dialog"], [aria-modal="true"], [role="menu"]')) return;
      if (!input.current || peek.value || !input.current.getClientRects().length) return;          // an open peek keeps "/" for its own words box; a line that is not on the screen (its page is hidden behind a use case's own page) takes nothing
      e.preventDefault();
      input.current.focus();
    };
    document.addEventListener("keydown", slash);
    return () => document.removeEventListener("keydown", slash);
  }, []);
  const useHint = (h) => { const t = (draft && !/\s$/.test(draft) ? draft + " " : draft) + h.text + " "; want.current = t.length; edit(t); if (input.current) input.current.focus(); };
  const glossOf = (c) => (meaning ? `${c}: ${meaning(c)}` : "");                 // a chip's gloss only where the page gives its chips plain words
  // Row 808: the list floats over the page just under the box (it is out of the flow), so opening it pushes no row or card down.
  // Item 954: it floats just under the box when the message line is empty, and under that line when it says something, so it never covers the message
  // (the unknown-field error is there). The message line is after the examples' room; the list is out of the flow, so it sits where it is written.
  const suggestions = listed ? (
    <Fade tag="ul" class="flist" id={ids.list} role="listbox" aria-label="Suggestions">
      {options.map((o, i) => (
        <li key={`${o.ins}|${o.label}`} id={`${ids.opt}-${i}`} role="option" aria-selected={i === active ? "true" : "false"} class={`fopt ${o.kind}`} data-ins={o.ins}
          onMouseDown={(e) => e.preventDefault()} onClick={() => pick(o)}>
          {o.icon ? <Icon name={o.icon} /> : null}
          {o.tone ? <i class={`fdv ${o.tone}`} data-tone={o.tone} aria-hidden="true"></i> : null}
          <span class="fl1">{o.label}</span>
          {o.note ? <span class="fl2">{o.note}</span> : null}
          {o.n !== undefined ? <span class="c num" data-n={o.n}>{o.n}</span> : null}
        </li>
      ))}
    </Fade>
  ) : null;
  return (
    <div class="fline-wrap" ref={box}
      onFocusIn={() => setFocused(true)}
      onFocusOut={(e) => { if (!e.relatedTarget || !box.current.contains(e.relatedTarget)) leave(); }}>
      {head}
      <div class="fline-row">
      <div class={`fline${focused ? " on" : ""}${words.length ? " bad" : ""}`} data-fline data-line={Q.joinLine(chips, draft)}>
        {chips.length ? (
          <span class="fchips" data-fchips>
            {chips.map((c, i) => {
              const name = Q.chipName(c, rows, ctx, extra), g = glossOf(c);
              return (
                <span class="fchip" key={`${i}|${c}`} data-chip={c} data-gloss={g || undefined}
                  onMouseEnter={() => setGloss(g)} onMouseLeave={() => setGloss("")} onFocusIn={() => setGloss(g)} onFocusOut={() => setGloss("")}>{c}
                  <button type="button" data-fx={c} aria-label={`Remove the ${name} filter`} onMouseDown={(e) => e.preventDefault()} onClick={() => dropChip(i)}>{"×"}</button>
                </span>
              );
            })}
          </span>
        ) : null}
        <div class="fedit">
          <div class="fhi" ref={over} aria-hidden="true" data-fhi>
            <span class="fhs">{shown.map((p, i) => (
              p.cls === "err"
                ? <span key={i} class="fk k-err" data-tok="err" title={p.message || undefined} onMouseDown={aim(p)}>{p.text}</span>
                : <span key={i} class={`fk k-${p.cls}${p.tone ? ` ${p.tone}` : ""}`} data-tok={p.cls}>{p.text}</span>
            ))}</span>
          </div>
          <input ref={input} id={ids.input} type="text" role="combobox" autocomplete="off" spellcheck={false} aria-expanded={listed ? "true" : "false"} aria-controls={listed ? ids.list : undefined}
            aria-activedescendant={listed && active >= 0 ? `${ids.opt}-${active}` : undefined}
            aria-label={label} aria-autocomplete="list" aria-describedby={ids.msg}
            placeholder={chips.length ? undefined : FL.PLACEHOLDER} value={draft}
            onFocus={() => { setArmed(false); readCaret(); }}
            onInput={(e) => { edit(e.target.value, e.target.selectionStart || 0); setCaret(e.target.selectionStart || 0); setActive(-1); }} onKeyDown={onKeyDown} onKeyUp={readCaret} onClick={readCaret}
            onScroll={() => { if (over.current && input.current) over.current.scrollLeft = input.current.scrollLeft; }} />
        </div>
        <span class="fcount num" id={ids.count} data-fcount>{`${matches} of ${rows.length}`}</span>
        {draft || chips.length ? <button type="button" class="fx" id={ids.x} aria-label="Clear filter" title="Clear filter" onMouseDown={(e) => e.preventDefault()} onClick={clear}>{"×"}</button> : null}
      </div>
        {tail ? <div class="fline-tail">{tail}</div> : null}
      </div>
      {notes.length ? null : suggestions}
      {/* Row 833: the note comes before the examples, which float (out of the flow) from where they stand: under the note, never over it. */}
      <p class={`fmsg${words.length ? " bad" : ""}`} id={ids.msg} role="status" aria-live="polite">{notes.join(" ")}</p>
      {
        // Always drawn, hidden unless the line is focused: the room stays, so a click that moves focus away from the line does not shift the page under the pointer.
        // The examples and the list of suggestions are never shown together: while the list is open the examples keep their room but are hidden.
        // A page that gives neither hints nor chip words (the Use cases page, row 1085) has no examples row; the Work items line has the gloss only (main removed its Try row).
        hints || meaning ? (
          <div class={`fhints${focused && !listed ? " on" : ""}`} role="group" aria-label="Examples" aria-hidden={focused && !listed ? undefined : "true"}>
            {hints ? <span class="fhl">Try</span> : null}
            {hints ? hints.map((h) => <button type="button" key={h.text} class="fhint" title={h.gloss} onMouseDown={(e) => e.preventDefault()} onClick={() => useHint(h)}>{h.text}</button>) : null}
            <span class="fgloss" id={ids.gloss} aria-hidden="true" hidden={!gloss}>{gloss}</span>
          </div>
        ) : null
      }
      {notes.length ? suggestions : null}
    </div>
  );
}

// The Work items line: the box over the app's line store (stores/line.js), with the saved views over it, each chip's plain words and the owner:me note.
export function FilterLine({ board, tools }) {
  const code = project.value, rows = allRows.value, ctx = filterCtx(), line = lineText.value;
  const meaning = (c) => { const p = FL.parse(c, rows, ctx); return p.errors.length || !p.chips[0] ? c : p.chips[0].say; };      // a chip in plain words, as the prototype says it (the word itself when the line cannot read it)
  return (
    <LineBox head={<SavedViews board={board} />} line={line} now={() => lineText.value} apply={setLine} rows={rows} ctx={ctx} label="Filter work items"
      tail={<>{tools && !fromFile.value ? <ImportExport tools={tools} line /> : null}<ViewIcons board={board} /></>} meaning={meaning} notes={(p) => (Q.wantsMe(p, ctx) ? [Q.NO_ME] : [])} onClear={() => { chosen.value = { ...chosen.value, [code]: "" }; }} />
  );
}
