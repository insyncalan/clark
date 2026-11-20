// Row 1292 (S12): the Draft beside the ask panel (mock-up image 09). It opens to the left of the panel, the text is editable, and nothing is in the
// report until "Add to the report": a menu offers each Text section (replace its text) and a new Text section (after the one the draft is for, or at
// the end). One change, so one Undo. Copy puts the formatted text and the plain text on the clipboard. Closing leaves the report as it was.
import { useLayoutEffect, useRef, useState } from "preact/hooks";
import { data } from "../stores/report.js";
import { change } from "../stores/changes.js";
import { Icon } from "../components/Icon.jsx";
import { classicTheme } from "../components/Contents.jsx";
import { draft, panelWidth, clampWidth } from "./askPanelState.js";
import { choices, request } from "./askDraft.js";
import * as W from "./askWords.js";

export function AskDraft() {
  const d = draft.value;
  const doc = useRef(null), addBtn = useRef(null);
  const [menu, setMenu] = useState(false), [note, setNote] = useState("");
  // A different draft sets the text again; edits to the same one are the person's and are never put back.
  useLayoutEffect(() => { if (d && doc.current) doc.current.innerHTML = d.html; setMenu(false); setNote(""); }, [d]);
  // The Esc listener is put on when the sheet is drawn (a layout effect, not after the paint) and reads the menu from a ref, so an Esc that comes the
  // moment the sheet or its menu appears is the sheet's: it never sees the menu as shut (and closes the whole sheet) or finds no listener yet.
  const menuNow = useRef(false);
  menuNow.current = menu;
  useLayoutEffect(() => {
    if (!d) return undefined;
    const esc = (e) => {
      if (e.key !== "Escape" || !e.target.closest || !e.target.closest("#ask-draft")) return;
      e.preventDefault(); e.stopPropagation();
      if (menuNow.current) { menuNow.current = false; setMenu(false); if (addBtn.current) addBtn.current.focus(); } else { draft.value = null; const b = document.getElementById("ask-box"); if (b) b.focus(); }
    };
    document.addEventListener("keydown", esc, true);
    return () => document.removeEventListener("keydown", esc, true);
  }, [d]);
  if (!d) return null;

  const sections = (data.value && data.value.report_sections) || [];
  const text = () => (doc.current ? doc.current.innerText : "");

  async function copy() {
    try {
      const html = doc.current.innerHTML, plain = text();
      if (window.ClipboardItem) await navigator.clipboard.write([new ClipboardItem({ "text/html": new Blob([html], { type: "text/html" }), "text/plain": new Blob([plain], { type: "text/plain" }) })]);
      else await navigator.clipboard.writeText(plain);
      setNote(W.DRAFT_COPIED);
    } catch (e) { setNote(W.DRAFT_COPY_FAILED); }
  }

  async function put(c) {
    let made = null;
    try { made = request(c, doc.current.innerHTML, d.title, sections); } catch (e) { made = null; }
    if (!made) { setMenu(false); setNote(W.DRAFT_EMPTY); return; }
    const reply = await change(made.req, made.done);
    if (reply) draft.value = null;       // saved: the sheet has done its work; the toast has the Undo
    else setMenu(false);                 // refused: the toast says why and the draft stays
  }

  const classic = classicTheme(), list = choices(sections, d.sec, classic);
  return (
    <section id="ask-draft" class="ask-draft" role="complementary" aria-label={W.DRAFT_TITLE} style={{ right: clampWidth(panelWidth.value) + "px", "--ad-r": clampWidth(panelWidth.value) + "px" }}>
      <header class="ad-h">
        <h2>{W.DRAFT_TITLE}</h2>
        <span class="ad-hint">{W.DRAFT_HINT}</span>
        <button type="button" class="pkp-btn" id="ask-draft-close" title={W.DRAFT_CLOSE} aria-label={W.DRAFT_CLOSE} onClick={() => { draft.value = null; }}><Icon name="x" /></button>
      </header>
      {d.via && d.via.length ? <p class="ad-note" id="ask-draft-via">{W.DRAFT_VIA(d.via.join(" and "))}</p> : null}
      <div class="ad-doc" id="ask-draft-doc" ref={doc} contentEditable="true" role="textbox" aria-multiline="true" aria-label={W.DRAFT_TEXT_LABEL} spellcheck="true" />
      <p class="ad-note" id="ask-draft-note" role="status" aria-live="polite">{note}</p>
      <footer class="ad-f">
        <button type="button" class="btn primary" id="ask-draft-add" ref={addBtn} aria-haspopup="menu" aria-expanded={menu ? "true" : "false"} onClick={() => setMenu(!menu)}>{W.DRAFT_ADD}</button>
        <button type="button" class="btn" id="ask-draft-copy" onClick={copy}>{W.DRAFT_COPY}</button>
        {menu ? (
          <div class="ad-menu" id="ask-draft-menu" role="menu" aria-label={W.DRAFT_MENU_LABEL}>
            {list.map((c, i) => <button type="button" role="menuitem" key={i} data-kind={c.kind} data-id={c.id || undefined} data-after={c.after || undefined} onClick={() => put(c)}><Icon name={c.kind === "replace" ? "doc" : "plus"} />{classic && c.kind === "replace" ? <span>Replace the text of <b>{c.title}</b> <span class="ad-count">{c.tail}</span></span> : c.label}</button>)}
          </div>
        ) : null}
      </footer>
    </section>
  );
}
