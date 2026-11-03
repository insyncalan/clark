// The one filter line above the Work items table (#153; the prototype is #145). It replaces the "Filter by" row and the type and
// Open / Closed switches. The rules (reading a line, suggestions, plain-words messages, saved views) are in ../logic/filterLine.js;
// this file is the controls: removable chips, a combobox with a listbox of suggestions, a live region for plain-words messages, hint
// chips while the line is focused, "/" to focus it, saved views as tabs and one View menu. Keys: arrows choose, Enter accepts,
// Backspace in an empty box removes the last chip, Esc closes the open list.
import { useEffect, useRef, useState } from "preact/hooks";
import { signal } from "@preact/signals";
import { rows as allRows, project, filterCtx, fromFile, peek } from "../stores/report.js";
import { lineText, setLine, local } from "../stores/line.js";
import * as FL from "../logic/filterLine.js";
import { Menu } from "./Menu.jsx";

// A saved view whose line the filter line no longer reads (a word it does not know) stays on the tabs with a plain message, and can be renamed
// or archived like any other (#589). The one view left out is a starting view the page cannot answer yet (Waiting on the client, while
// is:needed is not on): FL.heldBack. Choosing a view that cannot be read does not touch the line.

// The field list, the x in the box, the core tabs and the tab's ▾ menu (#640).
import { useLayoutEffect } from "preact/hooks";
import { MenuPanel, useMenuState } from "./Menu.jsx";
import { Icon } from "./Icon.jsx";

// Which saved view is chosen, per project, for this visit. A page change keeps it; a reload goes back to the view the line matches.
const chosen = signal({});
const viewsRev = signal(0);

const ws = FL.words;
const lastWord = (draft) => (!draft || /\s$/.test(draft) ? "" : ws(draft).slice(-1)[0] || "");

function viewsOf(code) { void viewsRev.value; return FL.viewsGet(local(), code); }
function saveViews(code, views) { FL.viewsPut(local(), code, views); viewsRev.value++; }

// The line without a chip or a word, by its place in the order shown (chips first, then words).
function dropAt(line, i, rows, ctx) {
  const p = FL.parse(line, rows, ctx);
  if (i < p.chips.length) return FL.removeChip(line, i, rows, ctx);
  return FL.format({ chips: p.chips, words: p.words.filter((_, k) => k !== i - p.chips.length) });
}

// Add typed text to the line. Returns {line, left, said}: the new line, the words that could not be used (they stay in the box) and
// what to say. A word with an error is never applied.
export function commit(line, text, rows, ctx) {
  const p = FL.parse(text, rows, ctx), said = p.errors.map((e) => e.msg), left = p.errors.map((e) => e.raw);
  const good = p.chips;
  let keep = FL.parse(line, rows, ctx);
  const states = (c) => c.field === "is" && !c.not && c.values.length === 1 && (c.values[0] === "open" || c.values[0] === "closed");
  if (good.some(states)) keep = { chips: keep.chips.filter((c) => !states(c)), words: keep.words };       // is:closed takes the place of is:open
  const merged = FL.normalise(`${FL.format(keep)} ${FL.format({ chips: good, words: p.words })}`, rows, ctx);
  return { line: merged, left, said: [...said, ...p.notes] };
}

function Chips({ parsed, onRemove }) {
  return (
    <>
      {parsed.chips.map((c, i) => (
        <span class="fchip" key={`c${i}${c.text}`} data-chip={c.field} title={c.say}>
          <span class="ft">{c.text}</span>
          <button type="button" data-fx={c.field} aria-label={`Remove the filter ${c.text}. ${c.say}`} onClick={() => onRemove(i)}>{"×"}</button>
        </span>
      ))}
      {parsed.words.map((w, k) => (
        <span class="fchip word" key={`w${k}${w}`} data-chip="word" title={`Title contains ${w}`}>
          <span class="ft">{w}</span>
          <button type="button" data-fx="word" aria-label={`Remove the search word ${w}`} onClick={() => onRemove(parsed.chips.length + k)}>{"×"}</button>
        </span>
      ))}
    </>
  );
}

// Freshness (#94): the two plain values, each a toggle for the line's word. The words are the line's own (is:quiet, is:incomplete) and are
// never shown alone: the menu and the chips read "Not reviewed in 14 days" and "No owner or no date".
const FRESH = ["quiet", "incomplete"];
function FreshnessMenu() {
  const rows = allRows.value, ctx = filterCtx(), line = lineText.value;
  const parsed = FL.parse(line, rows, ctx);
  const on = (w) => parsed.chips.some((c) => c.field === "is" && !c.not && c.values.length === 1 && c.values[0] === w);
  const items = FL.offers("is", rows, ctx).filter(([v]) => FRESH.includes(v)).map(([v, label]) => ({ id: v, name: label, on: on(v) }));
  const pick = (w) => {
    if (on(w)) {
      const at = parsed.chips.findIndex((c) => c.field === "is" && !c.not && c.values.length === 1 && c.values[0] === w);
      setLine(FL.removeChip(line, at, rows, ctx));
    } else setLine(commit(line, `is:${w}`, rows, ctx).line);
  };
  return <Menu label="Freshness" ariaLabel="Freshness" id="freshMenu" btnCls="btn sm" menuId="freshMenuList" menuLabel="Freshness" items={items.map((i) => ({ id: i.id, name: i.on ? `${i.name} (on)` : i.name }))} onPick={pick} />;
}

// The ▾ beside the open tab's name (#640): that tab's menu. The tabs row scrolls inside its own box at narrow widths, so the menu is
// placed against the window (position: fixed, under the ▾) rather than inside the row, where the row would clip it.
function TabMenu({ view, items, onPick }) {
  const [open, setOpen] = useMenuState();
  const btn = useRef(null), panel = useRef(null), back = useRef(false);
  const close = (how) => { back.current = how === "esc"; setOpen(false); };
  useLayoutEffect(() => {
    if (!open || !panel.current || !btn.current) return;
    const r = btn.current.getBoundingClientRect(), p = panel.current;
    p.style.top = `${Math.round(r.bottom + 4)}px`;
    p.style.left = `${Math.round(Math.max(8, Math.min(r.left, window.innerWidth - p.offsetWidth - 8)))}px`;
  }, [open]);
  useEffect(() => { if (!open && back.current) { back.current = false; if (btn.current) btn.current.focus(); } }, [open]);
  return (
    <>
      <button type="button" class="vtabm" id="vtabMenu" ref={btn} aria-haspopup="menu" aria-expanded={open ? "true" : "false"} aria-label={`${view.name} view options`} title={`${view.name} view options`}
        onClick={() => setOpen(!open)} onKeyDown={(e) => { if (e.key === "ArrowDown" && !open) { e.preventDefault(); setOpen(true); } }}>
        <Icon name="chevdown" />
      </button>
      {open ? (
        <MenuPanel label={`${view.name} view`} id="vtabMenuList" cls="vtabmenu" anchor={btn.current} onClose={close} boxRef={panel}>
          {items.map((it) => it.sep ? <div key={it.id} class="sep" role="separator"></div> : (
            <button key={it.id} type="button" role="menuitem" tabIndex={-1} data-kind={it.id} onClick={() => { close("pick"); onPick(it.id); }}>{it.name}</button>
          ))}
        </MenuPanel>
      ) : null}
    </>
  );
}

function SavedViews() {
  const code = project.value, rows = allRows.value, ctx = filterCtx(), line = lineText.value;
  const all = viewsOf(code), shown = FL.userViews(FL.visibleViews(all)).filter((v) => !FL.heldBack(v, rows, ctx));
  const trouble = (v) => FL.viewTrouble(v, rows, ctx);
  const nameBox = useRef(null);
  const [form, setForm] = useState(null);                 // null, or {mode: "saveas" | "rename", name, error}
  const mine = chosen.value[code];
  // The tab that is on: one of the core five (#640) or one of the person's own views. `active` is only ever the person's own view, so
  // Save changes, Rename and Archive never reach a core tab; `on` is whichever tab is on, for the dot and the tab's own ▾ menu.
  const tabs = [...FL.CORE_VIEWS, ...shown];
  const on = tabs.find((v) => v.id === mine) || tabs.find((v) => !trouble(v) && !FL.differs(v, line, rows, ctx)) || null;
  const active = on && !on.core ? on : null;
  const said = on ? trouble(on) : "";
  const dirty = !!on && !said && FL.differs(on, line, rows, ctx);
  const pick = (v) => { chosen.value = { ...chosen.value, [code]: v.id }; if (!trouble(v)) setLine(FL.normalise(v.line, rows, ctx)); };
  const tabItems = [];
  if (active && dirty) tabItems.push({ id: "save", name: "Save changes" });
  if (dirty) tabItems.push({ id: "discard", name: "Discard changes" });
  tabItems.push({ id: "saveas", name: "Save as a new view…" });
  if (active) { tabItems.push({ id: "rename", name: "Rename…" }); tabItems.push({ id: "archive", name: "Archive" }); }
  const back = FL.userViews(FL.archivedViews(all)).filter((v) => !FL.heldBack(v, rows, ctx));
  if (back.length) tabItems.push({ id: "sep-back", sep: true }, ...back.map((v) => ({ id: `restore:${v.id}`, name: `Bring back ${v.name}${trouble(v) ? " (cannot be used now)" : ""}` })));
  const act = (id) => {
    if (id === "save" && active) { const r = FL.saveView(all, active.id, FL.normalise(line, rows, ctx)); if (r.ok) saveViews(code, r.views); }
    else if (id === "saveas") setForm({ mode: "saveas", name: "", error: "" });
    else if (id === "rename" && active) setForm({ mode: "rename", name: active.name, error: "" });
    else if (id === "archive" && active) {
      const r = FL.archiveView(all, active.id);
      if (r.ok) { saveViews(code, r.views); chosen.value = { ...chosen.value, [code]: "" }; }
    } else if (id.startsWith("restore:")) {
      const r = FL.restoreView(all, id.slice(8));
      if (r.ok) saveViews(code, r.views); else setForm({ mode: "note", name: "", error: r.message });
    }
  };
  const submit = (e) => {
    e.preventDefault();
    const r = form.mode === "rename" ? FL.renameView(all, active.id, form.name) : FL.addView(all, form.name, FL.normalise(line, rows, ctx));
    if (!r.ok) { setForm({ ...form, error: r.message }); return; }
    saveViews(code, r.views);
    if (form.mode === "saveas") chosen.value = { ...chosen.value, [code]: r.id };
    setForm(null);
  };
  // The name box takes focus once the menu has given focus back to its button (it does that in an effect of its own, so we go a moment later).
  useEffect(() => {
    if (!form || form.mode === "note") return undefined;
    const t = setTimeout(() => { if (nameBox.current) nameBox.current.focus(); }, 40);
    return () => clearTimeout(t);
  }, [form && form.mode]);
  const items = [];
  if (active && dirty) items.push({ id: "save", name: `Save changes to ${active.name}` });
  items.push({ id: "saveas", name: "Save this line as a new view…" });
  if (active) { items.push({ id: "rename", name: `Rename ${active.name}…` }); items.push({ id: "archive", name: `Archive ${active.name}` }); }
  for (const v of FL.archivedViews(all).filter((v) => !FL.heldBack(v, rows, ctx))) items.push({ id: `restore:${v.id}`, name: `Bring back ${v.name}${trouble(v) ? " (cannot be used now)" : ""}` });
  return (
    <div class="fviews">
      <div class="vtabs" role="group" aria-label="Saved views">
        {tabs.map((v) => {
          const isOn = !!on && on.id === v.id, dot = isOn && dirty, bad = trouble(v);
          // The open tab carries a small ▾ beside its name with that tab's own menu (#640, as GitHub's); not in a file opened from disc.
          const menu = isOn && !fromFile.value ? <TabMenu view={v} items={tabItems} onPick={(id) => (id === "discard" ? pick(v) : act(id))} /> : null;
          if (bad) {          // no count: the line is not applied, so there is nothing to count
            return (
              <span class={`vtabw${isOn ? " on" : ""}`} key={v.id}>
                <button type="button" class="vtab" data-view-id={v.id} data-broken="true" aria-pressed={isOn ? "true" : "false"} title={bad} onClick={() => pick(v)}
                  aria-label={`${v.name}, cannot be used any more`}>
                  <span>{v.name}</span>
                </button>{menu}
              </span>
            );
          }
          return (
            <span class={`vtabw${isOn ? " on" : ""}`} key={v.id}>
              <button type="button" class="vtab" data-view-id={v.id} data-core={v.core ? "true" : undefined} aria-pressed={isOn ? "true" : "false"} onClick={() => pick(v)}
                aria-label={`${v.name}, ${FL.viewCount(v, rows, ctx)} items${dot ? ", the line has changes you have not saved" : ""}`}>
                <span>{v.name}</span><em class="num">{FL.viewCount(v, rows, ctx)}</em>{dot ? <i class="fdot" data-dot aria-hidden="true"></i> : null}
              </button>{menu}
            </span>
          );
        })}
        {fromFile.value ? null : <button type="button" class="vnew" id="vnew" onClick={() => setForm({ mode: "saveas", name: "", error: "" })}><Icon name="plus" />New view</button>}
      </div>
      <FreshnessMenu />
      {fromFile.value ? null : <Menu label="View" ariaLabel="View" id="viewMenu" btnCls="btn sm" menuId="viewMenuList" menuLabel="View" items={items} onPick={act} />}
      {form ? (
        <form class="vform" onSubmit={submit} onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); setForm(null); } }}>
          {form.mode === "note" ? null : (
            <>
              <label for="vname">{form.mode === "rename" ? "New name for this view" : "Name for the new view"}</label>
              <input id="vname" type="text" value={form.name} maxLength={FL.MAX_NAME} ref={nameBox} onInput={(e) => setForm({ ...form, name: e.target.value, error: "" })} />
              <button type="submit" class="btn sm" id="vsave">Save</button>
            </>
          )}
          <button type="button" class="btn sm" onClick={() => setForm(null)}>{form.mode === "note" ? "Close" : "Cancel"}</button>
          <span class="vmsg" role="status">{form.error}</span>
        </form>
      ) : null}
      <p class="vbad" role="status" data-vbad>{said}</p>
    </div>
  );
}

export function FilterLine() {
  const rows = allRows.value, ctx = filterCtx(), line = lineText.value, parsed = FL.parse(line, rows, ctx);
  const [draft, setDraft] = useState("");
  const [focused, setFocused] = useState(false);
  const [active, setActive] = useState(-1);
  const [closed, setClosed] = useState(false);               // Esc closed the list; typing opens it again
  const [forced, setForced] = useState(false);               // the list was asked for with the arrow keys on an empty box
  const [said, setSaid] = useState([]);
  const box = useRef(null), input = useRef(null), quiet = useRef(false);
  // With no word being typed, the list is the field list (#640, as GitHub's): it opens when you click or Tab into the box, or press
  // Down; with a word being typed, it is the suggestions for that word, as before. `forced` is "asked for" (a click, Tab or Down).
  const word = lastWord(draft), fieldsOnly = word === "";
  const options = !focused ? [] : fieldsOnly ? FL.fieldList() : FL.suggest(word, rows, ctx);
  const listed = focused && !closed && options.length > 0 && (!fieldsOnly || forced);
  const ask = () => { if (quiet.current) { quiet.current = false; return; } setClosed(false); setForced(true); };
  // Focus back in the box after a click on a chip's x or the box's x, without opening the field list (focus events run at once).
  const refocus = () => { if (!input.current || document.activeElement === input.current) return; quiet.current = true; input.current.focus(); quiet.current = false; };
  // The x in the box (#640): back to the starting line, the same as Clear all, in one step; the focus stays in the box.
  const canClear = FL.canClear(line, rows, ctx) || draft.trim() !== "";
  const clearAll = () => {
    if (line !== FL.BASE) setLine(FL.BASE);
    const code = project.value;
    if (code) chosen.value = { ...chosen.value, [code]: FL.CORE_VIEWS[0].id };
    setDraft(""); setActive(-1); setForced(false); setSaid(["Filter cleared"]);
    refocus();
  };
  const apply = (next) => {
    if (next !== line) setLine(next);
  };
  const submit = (text) => {
    const r = commit(line, text, rows, ctx);
    apply(r.line);
    setDraft(r.left.join(" "));
    setSaid(r.said);
    setActive(-1); setClosed(false); setForced(false);
  };
  const remove = (i) => { setSaid([]); apply(dropAt(line, i, rows, ctx)); refocus(); };
  const accept = (o) => {
    const base = !draft || /\s$/.test(draft) ? draft : FL.settled(draft);
    if (o.kind === "field") { setDraft(base + o.ins); setActive(-1); setSaid([]); if (input.current) input.current.focus(); }
    else submit(base + o.ins);
  };
  const onKeyDown = (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (!options.length) return;
      e.preventDefault();
      if (!listed) { setClosed(false); setForced(true); setActive(e.key === "ArrowDown" ? 0 : options.length - 1); return; }
      setActive(e.key === "ArrowDown" ? (active + 1) % options.length : (active <= 0 ? options.length : active) - 1);   // both ways round, as the prototype's
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (listed && active >= 0 && options[active]) accept(options[active]);
      else if (draft.trim()) submit(draft);
    } else if (e.key === "Backspace" && !draft) {
      const n = parsed.chips.length + parsed.words.length;
      if (n) { e.preventDefault(); setSaid([]); apply(dropAt(line, n - 1, rows, ctx)); }
    } else if (e.key === "Escape" && listed) {
      e.preventDefault(); e.stopPropagation(); setClosed(true); setActive(-1);
    } else if (e.key === "Tab" && listed) {
      setClosed(true); setActive(-1);                                   // Tab moves on (to the x, when it shows) with the list shut
    }
  };
  // "/" focuses the line, except while typing in a field or when a dialog or menu is open.
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
  useEffect(() => { if (listed && active >= 0) { const el = document.getElementById(`fo-${active}`); if (el && el.scrollIntoView) el.scrollIntoView({ block: "nearest" }); } }, [active, listed]);
  const notes = [...said, ...(draft ? [] : [...parsed.errors.map((e) => e.msg), ...parsed.notes].filter((n) => !said.includes(n)))];
  const hints = FL.hints(ctx);
  const useHint = (h) => { setDraft((d) => (d && !/\s$/.test(d) ? d + " " : d) + h.text); setActive(-1); setSaid([]); if (input.current) input.current.focus(); };
  return (
    <div class="fline-wrap" ref={box}
      onFocusIn={() => setFocused(true)}
      onFocusOut={(e) => { if (!e.relatedTarget || !box.current.contains(e.relatedTarget)) { setFocused(false); setClosed(false); setForced(false); setActive(-1); } }}>
      <SavedViews />
      <div class={`fline${focused ? " on" : ""}`} data-fline>
        <Chips parsed={parsed} onRemove={remove} />
        <input ref={input} id="fline-input" type="text" role="combobox" autocomplete="off" spellcheck={false}
          aria-label="Filter work items" aria-autocomplete="list" aria-expanded={listed ? "true" : "false"} aria-controls={listed ? "fline-list" : undefined}
          aria-activedescendant={listed && active >= 0 ? `fo-${active}` : undefined} aria-describedby="fline-msg"
          placeholder={parsed.chips.length || parsed.words.length ? "" : FL.PLACEHOLDER} value={draft}
          onInput={(e) => { setDraft(e.target.value); setActive(-1); setClosed(false); setSaid([]); }} onKeyDown={onKeyDown} onFocus={ask} onClick={ask} />
        <span class="fkey" aria-hidden="true">Press <kbd>/</kbd></span>
        {canClear ? <button type="button" class="fclear" id="fline-clear" aria-label="Clear the filter" title="Clear the filter" onClick={clearAll}><Icon name="x" /></button> : null}
        {listed ? (
          <ul class={`flist${fieldsOnly ? " ffields" : ""}`} id="fline-list" role="listbox" aria-label={fieldsOnly ? "Filter by field" : "Suggestions"}>
            {options.map((o, i) => (
              <li key={o.ins} id={`fo-${i}`} role="option" aria-selected={i === active ? "true" : "false"} class={`fopt ${o.kind}`} data-ins={o.ins} data-field={o.field}
                onMouseDown={(e) => e.preventDefault()} onClick={() => accept(o)}>
                {o.icon ? <Icon name={o.icon} cls="fic" /> : null}
                <span class="fl1">{o.label}</span>
                <span class="fl2">{o.gloss || o.note}</span>
                {o.n !== undefined ? <span class="c num">{o.n}</span> : null}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
      {
        // Always drawn, hidden unless the line is focused and no list is open (#640: the examples never show with the list): the room
        // stays, so a click that moves focus away from the line does not shift the page under the pointer.
        <div class={`fhints${focused && !listed ? " on" : ""}`} role="group" aria-label="Examples" aria-hidden={focused && !listed ? undefined : "true"}>
          <span class="fhl">Try</span>
          {hints.map((h) => <button type="button" key={h.text} class="fhint" title={h.gloss} onMouseDown={(e) => e.preventDefault()} onClick={() => useHint(h)}>{h.text}</button>)}
        </div>
      }
      <p class="fmsg" id="fline-msg" role="status" aria-live="polite">{notes.join(" ")}</p>
    </div>
  );
}
