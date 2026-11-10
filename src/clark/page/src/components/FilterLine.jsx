// The one filter line above the Work items table. The box holds the whole line as text (issue 662): it is read by the parser of
// logic/filterQueryParse.js and shown with its tokens drawn over the text (field names plain, values as coloured chips, a token that cannot be
// used underlined in red with its words), the match count sits inside the box on the right, an x clears it, and the list changes about 400 ms
// after the last key, not on Enter. The pure parts (pieces, messages, the rows a line shows) are in logic/filterQueryUi.js; saved views as
// tabs and the one View menu stay as they were (row 813 took the Freshness menu away; its words stay in the typed line). The list of suggestions (fields, then a field's values) is step 5 of the issue. "/" focuses the line only where nothing took the key first.
import { useEffect, useLayoutEffect, useRef, useState } from "preact/hooks";
import { signal } from "@preact/signals";
import { rows as allRows, project, filterCtx, fromFile, peek } from "../stores/report.js";
import { lineText, setLine, local } from "../stores/line.js";
import * as FL from "../logic/filterLine.js";
import * as Q from "../logic/filterQueryUi.js";
import { Menu, Fade } from "./Menu.jsx";
import { Icon } from "./Icon.jsx";
import { work, setWork, announce } from "../stores/work.js";
import { say } from "../stores/changes.js";
import { GROUPS, LANE_GROUPS, groupLabel, boardGroup } from "../logic/board.js";

export const PAUSE = 400;                                // ms after the last key before the typed line is applied (the owner's 300 to 500)

// A saved view whose line the filter line no longer reads (a word it does not know) stays on the tabs with a plain message, and can be renamed
// or deleted like any other, so a view that cannot be read can still be fixed or removed. The one view left out is a starting view the page cannot answer yet (Waiting on the client, while
// is:needed is not on): Q.heldBackQuery. Choosing a view that cannot be read does not touch the line.

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
  return { items: out, label: `View: ${onBoard ? "board" : board ? "table" : ""}${board ? ", " : ""}grouped by ${groupLabel(g)}${lane !== "none" ? `, ${groupLabel(lane).toLowerCase()} lanes` : ""}` };
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
      <Menu label="" ariaLabel="Group by" ariaDescription={lay.label} tip="Group by" icon="group" chevron={false} id="viewMenu" btnCls="btn sm vgb" menuId="viewMenuList" menuLabel={lay.label} items={lay.items} onPick={pickLayout} />
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
  const all = viewsOf(code), shown = FL.visibleViews(all).filter((v) => !Q.heldBackQuery(v, rows, ctx));
  const trouble = (v) => Q.troubleQuery(v, rows, ctx);
  const nameBox = useRef(null);
  const [form, setForm] = useState(null);                 // null, or {mode: "rename" | "delete" | "note", name, error}; a new view has no form now (row 1073), so "saveas" is only ever a menu id
  const mine = chosen.value[code];
  const matching = shown.find((v) => !trouble(v) && !Q.differsQuery(v, line, rows, ctx)) || null;
  const active = shown.find((v) => v.id === mine) || matching;
  const said = active ? trouble(active) : "";
  const dirty = !!active && !said && Q.differsQuery(active, line, rows, ctx);
  // Row 844: the view the line matched stays the chosen tab when the line is then changed, so the dot shows on it and Discard changes has a view to go back to.
  useEffect(() => { if (matching && !shown.some((v) => v.id === mine)) chosen.value = { ...chosen.value, [code]: matching.id }; }, [matching && matching.id, code]);
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
    if (/^(layout|group|lane):/.test(id)) pickLayout(id);
    else if (id === "discard" && active) { pick(active); const el = document.querySelector('.vtab[aria-pressed="true"]'); if (el) el.focus(); }
    else if (id === "save" && active) { const r = FL.saveView(all, active.id, line.trim()); if (r.ok) { saveViews(code, r.views); say("done", `View saved: ${active.name}`); } }
    else if (id === "saveas") {          // row 1073: made at once, named View 1, View 2 ...; Rename… changes the name
      const r = FL.addView(all, FL.nextViewName(all), line.trim());
      if (!r.ok) { say("problem", r.message); return; }
      saveViews(code, r.views);
      chosen.value = { ...chosen.value, [code]: r.id };
    }
    else if (id === "rename" && active) setForm({ mode: "rename", name: active.name, error: "" });
    else if (id === "delete" && active) setForm({ mode: "delete", name: "", error: "" });
  };
  // The form's input goes with the form, so focus is handed to the button that opened it (the tab's own menu for a rename or a delete) a moment after it closes.
  const closeForm = () => {
    const mode = form && form.mode;
    setForm(null);
    const order = mode === "rename" || mode === "delete" ? ["viewTabMenu", "viewNew", "viewMenu"] : ["viewNew", "viewMenu", "viewTabMenu"];
    setTimeout(() => { const el = order.map((id) => document.getElementById(id)).find(Boolean); if (el) el.focus(); }, 0);
  };
  const submit = (e) => {
    e.preventDefault();
    if (form.mode === "delete") {
      const r = FL.deleteView(all, active.id);
      if (r.ok) { saveViews(code, r.views); chosen.value = { ...chosen.value, [code]: "" }; closeForm(); } else setForm({ ...form, error: r.message });
      return;
    }
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
  if (active && dirty && !core) tabItems.push({ id: "save", name: "Save changes" });
  tabItems.push({ id: "saveas", name: "Save as a new view…" });
  if (active) { tabItems.push({ id: "rename", name: "Rename…" }); tabItems.push({ id: "delete", name: "Delete" }); }
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
              <span class="vt" key={v.id}>
                <button type="button" class="vtab" data-view-id={v.id} data-broken="true" aria-pressed={on ? "true" : "false"} title={bad} onClick={() => pick(v)}
                  aria-label={`${v.name}, cannot be used any more`}>
                  <span>{v.name}</span>
                </button>{arrow}
              </span>
            );
          }
          return (
            <span class="vt" key={v.id}>
              <button type="button" class="vtab" data-view-id={v.id} aria-pressed={on ? "true" : "false"} onClick={() => pick(v)}
                aria-label={`${v.name}, ${count} items${dot ? ", the line has changes you have not saved" : ""}`}>
                <span>{v.name}</span><em class="num">{count}</em>{dot ? <i class="fdot" data-dot aria-hidden="true"></i> : null}
              </button>{arrow}
            </span>
          );
        })}
        {fromFile.value ? null : <button type="button" class="vnew" id="viewNew" onClick={() => act("saveas")}>{"+ New view"}</button>}
      </div>
      {fromFile.value || !dirty ? null : (
        <span class="fvacts">
          {core ? null : <button type="button" class="btn sm" id="fvSave" onClick={() => act("save")}>Save view</button>}
          <button type="button" class="link" id="fvRevert" onClick={() => act("discard")}>Discard changes</button>
        </span>
      )}
      </div>
      {form ? (
        <form class="vform" onSubmit={submit} onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); closeForm(); } }}>
          {form.mode === "delete" ? (
            <>
              <span class="vask" id="vask">Delete this view?</span>
              <button type="submit" class="btn sm" id="vdelete" ref={nameBox}>Delete</button>
            </>
          ) : form.mode === "note" ? null : (
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

export function FilterLine({ board }) {
  const code = project.value, rows = allRows.value, ctx = filterCtx(), line = lineText.value;
  const first = useRef(null);
  if (first.current === null) first.current = Q.splitLine(line, rows, ctx);
  const live = useRef({ chips: first.current.chips, draft: first.current.rest });     // what the box holds right now, for a key that comes before the next draw
  const [chips, setChipsRaw] = useState(first.current.chips);   // row 845: the complete filters, each a chip with its own remove button
  const [draft, setDraftRaw] = useState(first.current.rest);    // the text in the box (plain words and the word being typed); the line (lineText) is what the list shows, and follows chips and box after a pause
  const [focused, setFocused] = useState(false);
  const [caret, setCaret] = useState(0);
  const [active, setActive] = useState(-1);                   // the suggestion the arrows are on (-1: none)
  const [armed, setArmed] = useState(false);                 // row 931: Space or Arrow Down opened the list; entering the box, a choice and Esc close it
  const [gloss, setGloss] = useState("");                    // the plain meaning of the chip the pointer or focus is on, shown in the examples line
  const setChips = (v) => { live.current.chips = v; setChipsRaw(v); };
  const setDraft = (v) => { live.current.draft = v; setDraftRaw(v); };
  const input = useRef(null), over = useRef(null), box = useRef(null), timer = useRef(0), applied = useRef(line), want = useRef(null);
  // A change that did not come from this box (a tab, a switch, Clear filter, another project) puts its line in the box and drops a pending apply.
  useLayoutEffect(() => {      // before paint: a late run would wipe what was typed just after a tab was chosen
    const now = lineText.value;      // the line as it is now, not as the draw that scheduled this saw it: a key can apply a newer one before the effect runs
    if (now !== applied.current) { clearTimeout(timer.current); applied.current = now; const s = Q.splitLine(now, rows, ctx); setChips(s.chips); setDraft(s.rest); }
  }, [line]);
  useEffect(() => () => clearTimeout(timer.current), []);
  const apply = (text) => { applied.current = text; setLine(text); };
  const later = (text) => { clearTimeout(timer.current); timer.current = setTimeout(() => { if (text !== lineText.value) apply(text); }, PAUSE); };
  // A change of the text: filters the caret has moved past become chips, the rest stays in the box.
  const edit = (text, at) => {
    const c = Q.commitDraft(text, at === undefined ? text.length : at, rows, ctx), next = c.chips.length ? [...live.current.chips, ...c.chips] : live.current.chips;
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
  const parsed = Q.parseFor(draft, rows, ctx), shown = Q.pieces(draft, parsed, focused ? caret : undefined);
  const matches = Q.rowsFor(rows, line, ctx).length;
  const words = shown.filter((p) => p.cls === "err" && p.message).map((p) => p.message);
  const notes = [...words, ...(Q.wantsMe(Q.parseFor(Q.joinLine(chips, draft), rows, ctx), ctx) ? [Q.NO_ME] : [])];
  const options = focused ? Q.withCounts(Q.suggestions(draft, caret, rows, ctx), chips, rows, ctx) : [];
  const wordNow = Q.wordAt(draft, caret).word;
  const listed = focused && armed && options.length > 0;
  const pick = (o) => {
    const r = Q.accept(draft, caret, o);
    want.current = r.caret; edit(r.text, r.caret); setActive(-1); setArmed(false);
    if (input.current) input.current.focus();
  };
  const clear = () => {
    clearTimeout(timer.current);
    chosen.value = { ...chosen.value, [code]: "" };
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
  useEffect(() => { if (listed && active >= 0) { const el = document.getElementById(`fo-${active}`); if (el && el.scrollIntoView) el.scrollIntoView({ block: "nearest" }); } }, [active, listed]);
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
      if (!input.current || peek.value) return;          // an open peek keeps "/" for its own words box
      e.preventDefault();
      input.current.focus();
    };
    document.addEventListener("keydown", slash);
    return () => document.removeEventListener("keydown", slash);
  }, []);
  const meaning = (c) => { const p = FL.parse(c, rows, ctx); return p.errors.length || !p.chips[0] ? c : p.chips[0].say; };      // a chip in plain words, as the prototype says it (the word itself when the line cannot read it)
  // Row 808: the list floats over the page just under the box (it is out of the flow), so opening it pushes no row or card down.
  // Item 954: it floats just under the box when the message line is empty, and under that line when it says something, so it never covers the message
  // (the unknown-field error is there). The message line is after the examples' room; the list is out of the flow, so it sits where it is written.
  const suggestions = listed ? (
    <Fade tag="ul" class="flist" id="fline-list" role="listbox" aria-label="Suggestions">
      {options.map((o, i) => (
        <li key={`${o.ins}|${o.label}`} id={`fo-${i}`} role="option" aria-selected={i === active ? "true" : "false"} class={`fopt ${o.kind}`} data-ins={o.ins}
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
      <SavedViews board={board} />
      <div class={`fline${focused ? " on" : ""}${words.length ? " bad" : ""}`} data-fline data-line={Q.joinLine(chips, draft)}>
        {chips.length ? (
          <span class="fchips" data-fchips>
            {chips.map((c, i) => {
              const name = Q.chipName(c, rows, ctx);
              return (
                <span class="fchip" key={`${i}|${c}`} data-chip={c} data-gloss={`${c}: ${meaning(c)}`}
                  onMouseEnter={() => setGloss(`${c}: ${meaning(c)}`)} onMouseLeave={() => setGloss("")} onFocusIn={() => setGloss(`${c}: ${meaning(c)}`)} onFocusOut={() => setGloss("")}>{c}
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
          <input ref={input} id="fline-input" type="text" role="combobox" autocomplete="off" spellcheck={false} aria-expanded={listed ? "true" : "false"} aria-controls={listed ? "fline-list" : undefined}
            aria-activedescendant={listed && active >= 0 ? `fo-${active}` : undefined}
            aria-label="Filter work items" aria-autocomplete="list" aria-describedby="fline-msg"
            placeholder={chips.length ? undefined : FL.PLACEHOLDER} value={draft}
            onFocus={() => { setArmed(false); readCaret(); }}
            onInput={(e) => { edit(e.target.value, e.target.selectionStart || 0); setCaret(e.target.selectionStart || 0); setActive(-1); }} onKeyDown={onKeyDown} onKeyUp={readCaret} onClick={readCaret}
            onScroll={() => { if (over.current && input.current) over.current.scrollLeft = input.current.scrollLeft; }} />
        </div>
        <span class="fcount num" id="fline-count" data-fcount>{`${matches} of ${rows.length}`}</span>
        {draft || chips.length ? <button type="button" class="fx" id="fline-x" aria-label="Clear filter" title="Clear filter" onMouseDown={(e) => e.preventDefault()} onClick={clear}>{"×"}</button> : null}
        <ViewIcons board={board} />
      </div>
      {notes.length ? null : suggestions}
      {/* Row 833: the note comes before the examples, which float (out of the flow) from where they stand: under the note, never over it. */}
      <p class={`fmsg${words.length ? " bad" : ""}`} id="fline-msg" role="status" aria-live="polite">{notes.join(" ")}</p>
      {
        // Always drawn, hidden unless the line is focused: the room stays, so a click that moves focus away from the line does not shift the page under the pointer.
        // The examples and the list of suggestions are never shown together: while the list is open the examples keep their room but are hidden.
        <div class={`fhints${focused && !listed ? " on" : ""}`} role="group" aria-label="Examples" aria-hidden={focused && !listed ? undefined : "true"}>
          <span class="fgloss" id="fline-gloss" aria-hidden="true" hidden={!gloss}>{gloss}</span>
        </div>
      }
      {notes.length ? suggestions : null}
    </div>
  );
}
