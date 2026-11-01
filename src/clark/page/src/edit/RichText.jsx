// A rich field being edited (#66): clarkEditor with its toolbar, the bubble over a selection, the "/" menu and the link box.
// The only coupling to the rest of the page is two callbacks: onSave(html) (returns a promise: the reply, or null when the save
// failed, and then the field stays open) and onClose(back). `back` is true when the person closed it from the keyboard (Esc, or
// Cmd or Ctrl + Enter), so the field's view takes the focus again (#188); it is false when the focus went elsewhere on its own.
// Cmd or Ctrl + Enter saves, so does leaving the field; Esc puts the old text back. Every button is a real button with a plain-words name. Text is never drawn as markup here: the editor owns its own
// document.
import { useEffect, useLayoutEffect, useRef, useState } from "preact/hooks";
import { clarkEditor, SanitiseError } from "../core/editor.js";
import { href } from "../logic/cleanHtml.js";
import { Menu } from "../components/Menu.jsx";
import { useEditorAi } from "./editorAi.jsx";
import { getAiClient } from "./aiClient.js";
import { WORDS } from "../logic/aiMenu.js";

const BAR = [
  ["bold", "B", "Bold"], ["italic", "I", "Italic"], ["strike", "S", "Strikethrough"],
  "|", ["bullet", "•", "Bulleted list"], ["numbered", "1.", "Numbered list"], ["checklist", "☑", "Checklist"],
  ["quote", "❝", "Quote"], ["rule", "―", "Divider"], "|", ["link", "Link", "Link"], "|", ["undo", "↶", "Undo"], ["redo", "↷", "Redo"],
];
const BUBBLE = [["bold", "B", "Bold"], ["italic", "I", "Italic"], ["strike", "S", "Strikethrough"], ["link", "Link", "Link"]];
const STYLES = [["paragraph", "Text"], ["h1", "Heading 1"], ["h2", "Heading 2"], ["h3", "Heading 3"]];
const SLASH = [["h1", "Heading 1"], ["h2", "Heading 2"], ["h3", "Heading 3"], ["bullet", "Bulleted list"], ["numbered", "Numbered list"],
  ["checklist", "Checklist"], ["quote", "Quote"], ["rule", "Divider"]];
const TOO_LONG = "That is too long to save. Shorten it and try again.";
const BAD_LINK = "That address can't be used. Start it with https://, http:// or mailto:";

// Where to draw a floating box so that it stays inside the window.
function place(box, x, y) {
  const w = box.offsetWidth, h = box.offsetHeight;
  const left = Math.max(8, Math.min(x - w / 2, window.innerWidth - w - 8));
  const top = Math.max(8, Math.min(y, window.innerHeight - h - 8));
  box.style.left = `${Math.round(left)}px`;
  box.style.top = `${Math.round(top)}px`;
}

// aiPlace: the AI menu's place for this field (logic/aiMenu.js); null leaves the AI out. aiClient: where suggestions come from (tests hand
// in a fake one). onMakeInto(kind, text): Make into, offered only when it is given.
export function RichText({ value, label, onSave, onClose, aiPlace = "current", aiClient, onMakeInto }) {
  const host = useRef(null), root = useRef(null), bubble = useRef(null), slashBox = useRef(null), ed = useRef(null), linkIn = useRef(null);
  const [h, setH] = useState(null);                           // the editor, once it exists (the first draw has none)
  const [, tick] = useState(0);
  const [problem, setProblem] = useState("");
  const [linkOpen, setLinkOpen] = useState(false);
  const [slash, setSlash] = useState(null);                 // { query, items, at } or null
  const [sel, setSel] = useState(null);                     // { x, y } over a non-empty selection
  const slashRef = useRef(null); slashRef.current = slash;
  const busy = useRef(false), closed = useRef(false), keep = useRef(false);
  const props = useRef({}); props.current = { onSave, onClose };
  const aiBtn = useRef(null), aiKey = useRef(null);
  const ai = useEditorAi({ h, place: aiPlace, client: aiClient || getAiClient(), onMakeInto, setProblem });
  aiKey.current = ai.key;

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
    if (r !== null && r !== false) leave(back);
    else setProblem("");
  };
  const finishRef = useRef(finish); finishRef.current = finish;

  const slashState = (h) => {
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

  useLayoutEffect(() => {
    const keyHook = (e) => {
      if (aiKey.current(e)) return true;
      const s = slashRef.current;
      if (!s) return false;
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        setSlash({ ...s, at: (s.at + (e.key === "ArrowDown" ? 1 : s.items.length - 1)) % s.items.length });
        return true;
      }
      if (e.key === "Enter" && !e.metaKey && !e.ctrlKey) { e.preventDefault(); chooseSlash(s.items[s.at][0]); return true; }
      if (e.key === "Escape") { e.preventDefault(); setSlash(null); return true; }
      return false;
    };
    const made = clarkEditor(host.current, {
      profile: "rich", html: value || "", keyHook,
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

  // Leaving the whole field (focus goes outside it, and outside its floating boxes) saves.
  const away = (e) => {
    const to = e.relatedTarget;
    if (to && (root.current.contains(to) || (bubble.current && bubble.current.contains(to)) || (slashBox.current && slashBox.current.contains(to)))) return;
    if (!to && document.hasFocus() === false) return;
    if (keep.current) return;                  // a menu or the link box just closed: its focus is being put back
    setTimeout(() => {
      const at = document.activeElement;
      if (at && at !== document.body && (root.current.contains(at) || (bubble.current && bubble.current.contains(at)))) return;
      finishRef.current(false);
    }, 0);
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
  const button = ([name, glyph, words]) => (
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
  const current = h ? STYLES.find(([n]) => n !== "paragraph" && h.active(n)) : null;

  return (
    <div class="rt" ref={root} data-rt aria-label={label || "Rich text"} onFocusOut={away}>
      <div class="rt-bar" role="toolbar" aria-label="Formatting">
        <Menu label={current ? current[1] : "Text"} ariaLabel="Text style" btnCls="rt-btn rt-style" left
          items={STYLES.map(([n, w]) => ({ id: n, name: w }))} onPick={(n) => { h.run(n); tick((x) => x + 1); refocus(); }} />
        {BAR.map((b, i) => (b === "|" ? <span class="rt-sep" key={i} aria-hidden="true" /> : button(b)))}
        {aiPlace ? <button type="button" class="rt-btn rt-ai" ref={aiBtn} aria-label={WORDS.ai} title="AI (Alt+/)" aria-haspopup="menu"
          aria-expanded={ai.list ? "true" : "false"} onMouseDown={hold} onClick={() => ai.open(aiBtn.current)}>{WORDS.ai}</button> : null}
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
      {ai.card}
      {problem ? <p class="rt-problem" role="alert">{problem}</p> : null}
      {sel && !linkOpen ? (
        <div class="rt-bubble" ref={bubble} role="toolbar" aria-label="Format the selection">
          {BUBBLE.map(button)}
          {aiPlace ? (
            <span class="rt-ai-zone" role="group" aria-label={WORDS.ai}>
              <span class="rt-sep" aria-hidden="true" />
              <button type="button" class="rt-btn rt-ai" aria-haspopup="menu" onMouseDown={hold} onClick={(e) => ai.open(bubble.current)}>{WORDS.ai}</button>
            </span>
          ) : null}
        </div>
      ) : null}
      {ai.list}
      {slash ? (
        <div class="rt-slash" ref={slashBox} role="listbox" aria-label="Insert">
          {slash.items.map(([n, w], i) => (
            <button type="button" key={n} role="option" aria-selected={i === slash.at ? "true" : "false"} class={`rt-opt${i === slash.at ? " on" : ""}`}
              onMouseDown={hold} onClick={() => chooseSlash(n)}>{w}</button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
