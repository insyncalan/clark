// A rich field being edited (#66): clarkEditor with its toolbar, the bubble over a selection, the "/" menu and the link box.
// The only coupling to the rest of the page is two callbacks: onSave(html) (returns a promise: the reply, or null when the save
// failed, and then the field stays open; a text instead says why in the field, and it stays open) and onClose(back). `back` is true when the person closed it from the keyboard (Esc, or
// Cmd or Ctrl + Enter), so the field's view takes the focus again (#188); it is false when the focus went elsewhere on its own.
// Cmd or Ctrl + Enter saves, so does leaving the field; Esc puts the old text back. Every button is a real button with a plain-words name. Text is never drawn as markup here: the editor owns its own
// document.
import { useEffect, useLayoutEffect, useRef, useState } from "preact/hooks";
import { clarkEditor, SanitiseError } from "../core/editor.js";
import { href } from "../logic/cleanHtml.js";
import { Menu, Fade } from "../components/Menu.jsx";
import { Icon } from "../components/Icon.jsx";
import { actionIcon } from "../menuIcons.js";
import { AiFlow, DRAFT_WITH_AI } from "./DraftAi.jsx";
import { classicTheme } from "../components/Contents.jsx";
import { aiClient } from "./aiShared.js";

const BAR = [
  ["bold", "B", "Bold"], ["italic", "I", "Italic"], ["strike", "S", "Strikethrough"], ["colour", "A", "Font colour"],
  "|", ["bullet", "•", "Bulleted list"], ["numbered", "1.", "Numbered list"], ["checklist", "☑", "Checklist"],
  ["quote", "❝", "Quote"], ["rule", "―", "Divider"], "|", ["link", "Link", "Link"], "|", ["undo", "↶", "Undo"], ["redo", "↷", "Redo"],
];
// Row 1288 (Classic only, Cards keeps its own toolbar and words): Quote and Divider share one drop-down ("1C"), the bubble ends with Ask AI..., the "/" menu ends with Ask AI... and its filter box says Filter blocks...
const MORE = [["quote", "Quote"], ["rule", "Divider"]];
export const ASK_AI = "Ask AI\u2026";
const MORE_WORDS = "More blocks: Quote, Divider";
const FILTER_WORDS = "Filter blocks\u2026";
const BUBBLE_ALL = [["bold", "B", "Bold"], ["italic", "I", "Italic"], ["strike", "S", "Strikethrough"], ["colour", "A", "Font colour"], ["link", "Link", "Link"]];
// Row 1364: font colour. Words are exactly these (logged in NEW-WORDS.md); the names are also the tooltip and the aria-label of each swatch.
const COLOUR_WORDS = [["grey", "Grey"], ["brand", "Brand"], ["red", "Red"], ["amber", "Amber"], ["green", "Green"], ["blue", "Blue"]];
const AUTOMATIC = "Automatic";
const STYLES = [["paragraph", "Text"], ["h1", "Heading 1"], ["h2", "Heading 2"], ["h3", "Heading 3"]];
const SLASH = [["h1", "Heading 1"], ["h2", "Heading 2"], ["h3", "Heading 3"], ["bullet", "Bulleted list"], ["numbered", "Numbered list"],
  ["checklist", "Checklist"], ["quote", "Quote"], ["rule", "Divider"]];
const SLASH_ICON = { h1: "tline", h2: "tline", h3: "tline", bullet: "dots", numbered: "bars", checklist: "check", quote: "doc", rule: "circleminus" };      // row 1138: the / menu's icons
export const TOO_LONG = "That is too long to save. Shorten it and try again.";
const BAD_LINK = "That address can't be used. Start it with https://, http:// or mailto:";

// Where to draw a floating box so that it stays inside the window.
function place(box, x, y) {
  const w = box.offsetWidth, h = box.offsetHeight;
  const left = Math.max(8, Math.min(x - w / 2, window.innerWidth - w - 8));
  const top = Math.max(8, Math.min(y, window.innerHeight - h - 8));
  box.style.left = `${Math.round(left)}px`;
  box.style.top = `${Math.round(top)}px`;
}

// The font colour button and its palette (row 1364): one button (a bold A, underlined in the colour at the selection), a box of Automatic and six
// swatches under it. Down or Enter opens it; Left, Right, Up, Down, Home and End move; Enter chooses (the text takes the focus again); Esc closes it with the focus back on the button.
function ColourButton({ h, hold, tick, refocus }) {
  const [open, setOpen] = useState(false);
  const btn = useRef(null), box = useRef(null);
  const cur = h ? h.colour() : null;
  const items = () => (box.current ? [...box.current.querySelectorAll("button")] : []);
  useLayoutEffect(() => {
    if (!open || !box.current) return;
    const b = box.current, r = b.getBoundingClientRect();
    if (r.right > window.innerWidth - 8) b.classList.add("end");              // no room to the right: its right edge on the button's
    const its = items();
    (its[cur ? 1 + COLOUR_WORDS.findIndex(([n]) => n === cur) : 0] || its[0]).focus({ preventScroll: true });
    const outside = (e) => { if (!b.contains(e.target) && !(btn.current && btn.current.contains(e.target))) setOpen(false); };
    document.addEventListener("pointerdown", outside, true);
    return () => document.removeEventListener("pointerdown", outside, true);
  }, [open]);
  const choose = (name) => { refocus(); h.run("colour", name); setOpen(false); tick((n) => n + 1); };      // refocus first: the palette's own button is about to go, and that must not count as leaving the field
  const barKeys = (e) => { if (e.key === "ArrowDown" && !open) { e.preventDefault(); setOpen(true); } };
  const keys = (e) => {
    const its = items(), i = its.indexOf(document.activeElement), last = its.length - 1;
    let to = null;
    if (e.key === "ArrowRight") to = (i + 1) % its.length;
    else if (e.key === "ArrowLeft") to = (i + last) % its.length;
    else if (e.key === "ArrowDown") to = i === 0 ? 1 : i + 4 <= last ? i + 4 : i;           // Automatic, then the grid of four a row
    else if (e.key === "ArrowUp") to = i - 4 >= 1 ? i - 4 : 0;
    else if (e.key === "Home") to = 0;
    else if (e.key === "End") to = last;
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); setOpen(false); if (btn.current) btn.current.focus(); return; }
    else if (e.key === "Tab") { setOpen(false); return; }
    else return;
    e.preventDefault(); e.stopPropagation();
    if (its[to]) its[to].focus({ preventScroll: true });
  };
  return (
    <span class="rt-colour">
      <button type="button" ref={btn} class={`rt-btn${open ? " on" : ""}`} aria-label="Font colour" title="Font colour" aria-haspopup="menu" aria-expanded={open ? "true" : "false"}
        onMouseDown={hold} onKeyDown={barKeys} onClick={() => setOpen(!open)}><span class="rt-A" data-colour={cur || undefined}>A</span></button>
      {open ? (
        <div class="rt-pal" ref={box} role="menu" aria-label="Font colour" onKeyDown={keys}>
          <button type="button" class="rt-pal-auto" role="menuitemradio" aria-checked={cur ? "false" : "true"} tabIndex={-1} onMouseDown={hold} onClick={() => choose(null)}>
            {AUTOMATIC}<span class="rt-tick" aria-hidden="true">{cur ? "" : "✓"}</span></button>
          <div class="rt-grid" role="presentation">
            {COLOUR_WORDS.map(([n, w]) => (
              <button type="button" key={n} class={`rt-sw rt-sw-${n}`} role="menuitemradio" aria-checked={cur === n ? "true" : "false"} aria-label={w} title={w} tabIndex={-1}
                onMouseDown={hold} onClick={() => choose(n)}>A</button>
            ))}
          </div>
        </div>
      ) : null}
    </span>
  );
}

// Row 1179: with `ai` (a place) a right-click on selected text, or Shift+F10 / the Menu key, opens the AI menu of that place over the selection; no selection
// leaves the browser's own menu. Accept puts the suggestion in place of the selection (one more edit in the open box; it is saved like any other).
export function RichText({ value, label, onSave, onClose, oneLine = false, ai = null }) {
  const host = useRef(null), root = useRef(null), bubble = useRef(null), slashBox = useRef(null), ed = useRef(null), linkIn = useRef(null);
  const [h, setH] = useState(null);                           // the editor, once it exists (the first draw has none)
  const [, tick] = useState(0);
  const [problem, setProblem] = useState("");
  const [linkOpen, setLinkOpen] = useState(false);
  const [slash, setSlash] = useState(null);                 // { query, items, at } or null
  const [sel, setSel] = useState(null);                     // { x, y } over a non-empty selection
  const [aiAt, setAiAt] = useState(null);                   // the AI menu over a selection: { x, y, text, from, to } or null
  const aiBox = useRef(null), aiOpen = useRef(false);
  const slashRef = useRef(null); slashRef.current = slash;
  const askRef = useRef(null); askRef.current = () => askFromSlash();
  const classic = classicTheme();
  const askLine = () => !!ai && classicTheme();               // the "/" menu's foot line (Classic only, and only where the field has an AI place)
  const busy = useRef(false), closed = useRef(false), keep = useRef(false);
  const props = useRef({}); props.current = { onSave, onClose };

  const leave = (back) => { if (!closed.current) { closed.current = true; props.current.onClose(back === true); } };
  const finish = async (back = true) => {
    if (busy.current || closed.current) return;
    const h = ed.current;
    if (!h.dirty()) { leave(back); return; }
    let html;
    try { html = h.html(); } catch (e) { if (e instanceof SanitiseError) { setProblem(TOO_LONG); return; } throw e; }
    busy.current = true;
    const r = await props.current.onSave(html);
    busy.current = false;
    if (r !== null && r !== false && typeof r !== "string") leave(back);
    else setProblem(typeof r === "string" ? r : "");
  };
  const finishRef = useRef(finish); finishRef.current = finish;

  const slashState = (h) => {
    if (oneLine) return null;
    const { $from, empty } = h.editor.state.selection;
    const para = $from.parent;
    if (empty && para.type.name === "paragraph" && $from.parentOffset === para.content.size && /^\/[a-z0-9 ]{0,20}$/i.test(para.textContent)) {
      const q = para.textContent.slice(1).trim().toLowerCase();
      const items = SLASH.filter(([, n]) => n.toLowerCase().includes(q));
      return items.length ? { query: q, items, at: 0, from: $from.start(), to: $from.pos } : null;
    }
    return null;
  };
  const chooseSlash = (name) => {
    const s = slashRef.current;
    if (!s) return;
    const h = ed.current;
    h.editor.chain().focus().deleteRange({ from: s.from, to: s.to }).run();
    h.run(name);
    setSlash(null);
  };

  // Row 1288 (Classic, "4C"): the "Ask AI..." line at the foot of the "/" menu opens the same AI menu as the right-click. It takes the field's own text
  // (the "/" words left out) and, on Accept, the suggestion replaces the "/" words.
  const askFromSlash = async () => {
    const s = slashRef.current;
    if (!s || !ai || !ed.current) return;
    const doc = ed.current.editor.state.doc;
    const text = `${doc.textBetween(0, s.from, "\n", "\n")}\n${doc.textBetween(s.to, doc.content.size, "\n", "\n")}`.trim();
    const r = slashBox.current.getBoundingClientRect();
    aiOpen.current = true;
    await aiClient().refresh();
    setSlash(null);
    setAiAt({ x: r.left + r.width / 2, y: r.bottom + 4, text, from: s.from, to: s.to });
  };

  useLayoutEffect(() => {
    const keyHook = (e) => {
      const s = slashRef.current;
      if (!s) {                                                // a one-line field (item 1005): Enter saves, as in a plain box; Shift+Enter is not a line break either
        if (oneLine && e.key === "Enter" && !e.metaKey && !e.ctrlKey) { e.preventDefault(); finishRef.current(true); return true; }
        return false;
      }
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        const n = s.items.length + (askLine() ? 1 : 0);
        setSlash({ ...s, at: (s.at + (e.key === "ArrowDown" ? 1 : n - 1)) % n });
        return true;
      }
      if (e.key === "Enter" && !e.metaKey && !e.ctrlKey) { e.preventDefault(); if (s.at >= s.items.length) askRef.current(); else chooseSlash(s.items[s.at][0]); return true; }
      if (e.key === "Escape") { e.preventDefault(); setSlash(null); return true; }
      return false;
    };
    const made = clarkEditor(host.current, {
      profile: "rich", html: value || "", keyHook, oneLine,
      onSave: () => finishRef.current(true), onCancel: () => leave(true),
      onError: (e) => { if (e instanceof SanitiseError) setProblem(TOO_LONG); else throw e; },
      onChange: (handle) => {
        setProblem("");
        setSlash(slashState(handle));
        const { from, to, empty } = handle.editor.state.selection;
        if (empty) setSel(null);
        else { const a = handle.editor.view.coordsAtPos(from), b = handle.editor.view.coordsAtPos(to); setSel({ x: (a.left + b.right) / 2, y: Math.min(a.top, b.top) - 44 }); }
        tick((n) => n + 1);
      },
    });
    ed.current = made;
    setH(made);
    made.editor.view.focus();                     // at once, in this step (the editor's own focus waits for a frame, and a late frame left the box open but not focused)
    made.focus();
    return () => { made.destroy(); ed.current = null; };
  }, []);

  // Keep the bubble and the "/" menu inside the window.
  useLayoutEffect(() => { if (sel && bubble.current) place(bubble.current, sel.x, sel.y < 8 ? sel.y + 70 : sel.y); }, [sel]);
  useLayoutEffect(() => {
    if (slash && slashBox.current && ed.current) {
      const c = ed.current.editor.view.coordsAtPos(slash.to);
      place(slashBox.current, c.left + slashBox.current.offsetWidth / 2, c.bottom + 4);
    }
  }, [slash]);
  useEffect(() => { if (linkOpen && linkIn.current) { linkIn.current.focus(); linkIn.current.select(); } }, [linkOpen]);

  // The AI menu (row 1179): over a non-empty selection only.
  const openAi = async (x, y) => {
    if (!ai || oneLine || !ed.current) return false;
    const { from, to, empty } = ed.current.editor.state.selection;
    if (empty) return false;
    const text = ed.current.editor.state.doc.textBetween(from, to, "\n", "\n");
    if (!text.trim()) return false;
    aiOpen.current = true;                                     // from now on the focus moving into the menu and the card is not 'leaving the field'
    await aiClient().refresh();
    setAiAt({ x, y, text, from, to });
    return true;
  };
  const aiDone = () => { aiOpen.current = false; setAiAt(null); if (ed.current) ed.current.editor.view.focus(); };
  const aiAccept = (html) => {
    const a = aiAt;
    if (a && ed.current) ed.current.editor.chain().focus().insertContentAt({ from: a.from, to: a.to }, html).run();
  };
  useLayoutEffect(() => { if (aiAt && aiBox.current) place(aiBox.current, aiAt.x, aiAt.y); }, [aiAt]);
  const onContext = (e) => {
    if (!ai || oneLine || !host.current || !host.current.contains(e.target)) return;
    const s = ed.current && ed.current.editor.state.selection;
    if (!s || s.empty) return;                                // no selection: the browser's own menu
    e.preventDefault(); e.stopPropagation();
    openAi(e.clientX, e.clientY);
  };
  const onKeyAi = (e) => {
    if (!ai || oneLine || !(e.key === "ContextMenu" || (e.key === "F10" && e.shiftKey)) || !host.current.contains(e.target)) return;
    const s = ed.current && ed.current.editor.state.selection;
    if (!s || s.empty) return;
    e.preventDefault(); e.stopPropagation();
    const c = ed.current.editor.view.coordsAtPos(s.from);
    openAi(c.left, c.bottom + 4);
  };

  // Leaving the whole field (focus goes outside it, and outside its floating boxes) saves.
  const away = (e) => {
    const to = e.relatedTarget;
    const inside = (n) => (root.current && root.current.contains(n)) || (bubble.current && bubble.current.contains(n)) || (slashBox.current && slashBox.current.contains(n));   // contains(null) is false
    if (inside(to)) return;
    // No target and the page reports no focus: a window left (the active element stays in the field) unless the focus is already on something outside (macOS order).
    if (!to && document.hasFocus() === false && (!document.activeElement || document.activeElement === document.body || inside(document.activeElement))) return;
    if (keep.current || aiOpen.current) return;                  // a menu or the link box just closed: its focus is being put back (the AI menu and card are part of the field)
    const look = (again) => {
      if (aiOpen.current) return;
      const at = document.activeElement;
      if (inside(at)) {
        if (again && to) setTimeout(() => look(false), 50);     // the focus was sent outside but the active element has not moved yet (macOS): look once more
        return;
      }
      finishRef.current(false);
    };
    setTimeout(() => look(true), 0);
  };

  // Focus back to the text after a menu or the link box closed: after their own focus handling has finished.
  const refocus = () => {
    keep.current = true;
    setTimeout(() => { if (ed.current) ed.current.editor.view.focus(); }, 40);
    setTimeout(() => { keep.current = false; }, 400);
  };
  const hold = (e) => e.preventDefault();                    // a button never takes the focus from the text
  const press = (name) => {
    if (name === "link") { setLinkOpen(true); return; }
    h.run(name); tick((n) => n + 1);
  };
  const button = ([name, glyph, words]) => name === "colour" ? <ColourButton key={name} h={h} hold={hold} tick={tick} refocus={refocus} /> : (
    <button type="button" key={name} class={`rt-btn${h && h.active(name) ? " on" : ""}`} aria-label={words} title={words}
      aria-pressed={["undo", "redo", "rule", "link"].includes(name) ? undefined : (h && h.active(name) ? "true" : "false")}
      onMouseDown={hold} onClick={() => press(name)}>{glyph}</button>
  );
  const applyLink = () => {
    const v = linkIn.current.value.trim();
    if (!v) { h.run("unlink"); setLinkOpen(false); refocus(); return; }
    const a = /^[a-z][a-z0-9+.-]*:/i.test(v) || v.startsWith("#") ? v : `https://${v}`;
    if (!href(a)) { setProblem(BAD_LINK); return; }
    h.run("link", a); setProblem(""); setLinkOpen(false); refocus();
  };
  const noColour = !classicTheme();
  const BUBBLE = BUBBLE_ALL.filter((b) => !(noColour && b[0] === "colour"));      // row 1364: the font colour is Classic only; Cards has no palette CSS and keeps its bar as it was
  const more = ["quote", "rule"].filter((n) => !oneLine && classic && n);
  const bar = (oneLine ? BAR.filter((b) => b === "|" || b[0] === "undo" || b[0] === "redo") : BAR.filter((b) => !(classic && (b[0] === "quote" || b[0] === "rule")))).filter((b) => !(noColour && b[0] === "colour")).filter((b, i, a) => b !== "|" || (i > 0 && a[i - 1] !== "|" && i < a.length - 1));
  const moreIdx = bar.findIndex((b) => b !== "|" && b[0] === "checklist") + 1;
 const current = h ? STYLES.find(([n]) => n !== "paragraph" && h.active(n)) : null;
  // Row 1288: the style menu is the toolbar's first button and, in Classic, the bubble's first button (the mock-up's 3D): one menu, drawn twice.
  const styleMenu = (btnCls) => <Menu label={current ? current[1] : "Text"} ariaLabel={`Text style: ${current ? current[1] : "Text"}`} btnCls={btnCls} left
    items={STYLES.map(([n, w]) => ({ id: n, name: w, icon: actionIcon("textStyle"), checked: current ? current[0] === n : n === "paragraph" }))} onPick={(n) => { h.run(n); tick((x) => x + 1); refocus(); }} />;

  return (
    <div class="rt" ref={root} data-rt aria-label={label || "Rich text"} onFocusOut={away} onContextMenu={onContext} onKeyDown={onKeyAi}>
      <div class="rt-bar" role="toolbar" aria-label="Formatting">
        {!oneLine && styleMenu("rt-btn rt-style")}
        {bar.map((b, i) => [b === "|" ? <span class="rt-sep" key={i} aria-hidden="true" /> : button(b),
          more.length && i + 1 === moreIdx ? <Menu key="more" label="❝" ariaLabel={MORE_WORDS} tip={MORE_WORDS} btnCls="rt-btn rt-more"
            items={MORE.map(([n, w]) => ({ id: n, name: w, icon: actionIcon("textStyle") }))} onPick={(n) => { h.run(n); tick((x) => x + 1); refocus(); }} /> : null])}
        <span class="rt-keys">Cmd+Enter saves. Esc cancels.</span>
      </div>
      {linkOpen ? (
        <div class="rt-link" role="group" aria-label="Link">
          <input ref={linkIn} type="text" aria-label="Link address" placeholder="https://example.com" value={h ? h.linkAddress() : ""}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); e.stopPropagation(); applyLink(); } else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); setLinkOpen(false); setProblem(""); refocus(); } }} />
          <button type="button" class="rt-btn" onClick={applyLink}>Apply</button>
          <button type="button" class="rt-btn" onClick={() => { setLinkOpen(false); setProblem(""); refocus(); }}>Cancel</button>
        </div>
      ) : null}
      <div class="rt-host prose" ref={host} />
      {problem ? <p class="rt-problem" role="alert">{problem}</p> : null}
      {sel && !linkOpen && !oneLine ? <div class="rt-bubble" ref={bubble} role="toolbar" aria-label="Format the selection">{classic ? styleMenu("rt-btn rt-style rt-bubble-style") : null}{BUBBLE.map(button)}
        {ai ? <button type="button" class="rt-btn rt-bubble-ai" data-rt-bubble-ai onMouseDown={hold} onClick={() => { const r = bubble.current.getBoundingClientRect(); openAi(r.left + r.width / 2, r.bottom + 4); }}>{classic ? ASK_AI : DRAFT_WITH_AI}</button> : null}</div> : null}
      {aiAt ? <div class="rt-ai" ref={aiBox} data-rt-ai><AiFlow place={ai} text={aiAt.text} floating boxRef={null} onAccept={aiAccept} onDone={aiDone} /></div> : null}
      {slash ? (
        <Fade class="rt-slash" boxRef={slashBox} role="listbox" aria-label="Insert">
          {classic ? <div class="rt-slash-filter" data-rt-slash-filter data-ph={FILTER_WORDS}>{slash.query}</div> : null}
          {slash.items.map(([n, w], i) => (
            <button type="button" key={n} role="option" aria-selected={i === slash.at ? "true" : "false"} class={`rt-opt${i === slash.at ? " on" : ""}`}
              onMouseDown={hold} onClick={() => chooseSlash(n)}><Icon name={SLASH_ICON[n] || "tline"} cls="mi" />{w}</button>
          ))}
          {askLine() ? <><hr class="rt-slash-rule" /><button type="button" role="option" aria-selected={slash.at >= slash.items.length ? "true" : "false"} class={`rt-opt rt-ask${slash.at >= slash.items.length ? " on" : ""}`}
            onMouseDown={hold} onClick={askFromSlash}>{ASK_AI}</button></> : null}
        </Fade>
      ) : null}
    </div>
  );
}
