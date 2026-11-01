// The AI in an editor. `useEditorAi` is the one function that attaches the AI to a rich editor: it gives the editor
// its list (the bubble's AI zone, the toolbar's AI button and Alt+/ open the same one), the suggestion card under the field, and Accept
// as ONE editor step. The options for a place come from one function (logic/aiList.js aiEntries). Nothing here changes the text before Accept.
//
//   const ai = useEditorAi({ h, place, client, onMakeInto, setProblem })
//   ai.open(anchorElement | null)   the list on the chosen text, or on the whole field when nothing is chosen
//   ai.key(event)                   true when the key was Alt+/ (it opened the list)
//   ai.list, ai.card                what to draw (inside the field's own box, so leaving them is not leaving the field)
//
// The list is a menu, not a trap: Up and Down move, Enter chooses, Esc closes with the focus back in the editor, and Tab closes it and
// puts the focus back in the editor too. Ask… swaps the list for one line (Enter sends, Esc closes).
import { useLayoutEffect, useRef, useState } from "preact/hooks";
import { AiCard } from "./AiCard.jsx";
import { aiEntries } from "../logic/aiList.js";
import { WORDS } from "../logic/aiMenu.js";
import { forEditor } from "../core/richHtml.js";
import { closeHistory } from "../core/editor.js";
import { menuItemsIn, menuMove } from "../components/Menu.jsx";

const GAP = "\n\n";

// What the AI would work on: the chosen text, or the whole field when nothing is chosen.
export function aiTarget(h) {
  const ed = h.editor, doc = ed.state.doc;
  const { from, to, empty } = ed.state.selection;
  const a = empty ? 0 : from, b = empty ? doc.content.size : to;
  let paragraphs = 0;
  doc.nodesBetween(a, b, (n) => { if (n.isTextblock && n.textContent.trim()) paragraphs += 1; });
  return { from: a, to: b, selected: !empty, text: doc.textBetween(a, b, GAP, " "), paragraphs };
}

// The reply is put in as ONE transaction, so one Undo takes it back. A reply of one paragraph goes into a chosen run of words inside one
// paragraph as words (it does not split the paragraph). False, and nothing changed, when the text is no longer what the question was about.
export function acceptAi(h, target, html) {
  const ed = h.editor, doc = ed.state.doc;
  if (target.to > doc.content.size || doc.textBetween(target.from, target.to, GAP, " ") !== target.text) return false;
  let body = forEditor(html);
  const inline = target.selected && doc.resolve(target.from).sameParent(doc.resolve(target.to)) && doc.resolve(target.from).parent.isTextblock;
  const one = /^<p>([\s\S]*)<\/p>$/.exec(body);
  if (inline && one && !/<p[\s>]/.test(one[1])) body = one[1];
  // This step is its own, not joined to the typing before it (the history joins edits made within half a second): the same
  // transaction says "close the history", so it starts a new group.
  return ed.chain().command(({ tr }) => { closeHistory(tr); return true; })
    .insertContentAt({ from: target.from, to: target.to }, body).run();
}

const isSlash = (e) => e.altKey && !e.metaKey && !e.ctrlKey && (e.code === "Slash" || e.key === "/");

function AiList({ entries, line, ask, place, onPick, onAsk, onClose, boxRef }) {
  const own = useRef(null), box = boxRef || own, input = useRef(null);
  useLayoutEffect(() => {
    if (ask) { if (input.current) input.current.focus({ preventScroll: true }); return; }
    (menuItemsIn(box.current)[0] || box.current).focus({ preventScroll: true });
  }, [ask]);
  const keys = (e) => {
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onClose("esc"); return; }
    if (e.key === "Tab") { e.preventDefault(); e.stopPropagation(); onClose("tab"); return; }
    if (!ask) menuMove(e, menuItemsIn(box.current));
  };
  if (ask) {
    return (
      <div class="rt-slash rt-ai-list" ref={box} role="group" aria-label="Ask" onKeyDown={keys} data-ai-list="ask">
        <input ref={input} class="rt-ai-ask" type="text" maxLength={400} aria-label={WORDS.askLabel} placeholder={WORDS.askLabel}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.isComposing) { e.preventDefault(); e.stopPropagation(); const v = e.currentTarget.value.trim(); if (v) onAsk(v); } }} />
      </div>
    );
  }
  const groups = [];
  for (const en of entries) {
    const last = groups[groups.length - 1];
    if (last && last.label === en.group) last.items.push(en); else groups.push({ label: en.group, items: [en] });
  }
  return (
    <div class="rt-slash rt-ai-list" ref={box} role="menu" aria-label={WORDS.ai} tabIndex={-1} onKeyDown={keys} data-ai-list="menu" data-place={place}>
      {line ? <p class="rt-ai-line">{line}</p> : null}
      {groups.map((g, gi) => (
        <div role="group" aria-label={g.label || undefined} key={gi}>
          {g.label ? <p class="rt-ai-h" aria-hidden="true">{g.label}</p> : null}
          {g.items.map((en) => (
            <button type="button" role="menuitem" key={en.key} class="rt-opt" data-ai={en.type === "make" ? en.key : en.id}
              aria-disabled={en.off ? "true" : undefined} title={en.line || undefined}
              onClick={() => { if (!en.off) onPick(en); }}>{en.name}</button>
          ))}
        </div>
      ))}
    </div>
  );
}

export function useEditorAi({ h, place, client, onMakeInto, setProblem }) {
  const [list, setList] = useState(null);                  // { x, y, up, target, ask } or null
  const [card, setCard] = useState(null);                  // { target, option, instruction, n } or null
  const box = useRef(null), count = useRef(0);

  const focusEditor = (target) => {
    const ed = h.editor;                      // view.focus() at once: tiptap's own focus() waits a frame, and a list that is removed meanwhile would drop the focus out of the field
    ed.view.focus();
    if (target && target.selected && target.to <= ed.state.doc.content.size) ed.commands.setTextSelection({ from: target.from, to: target.to });
  };
  const close = () => { const t = list && list.target; focusEditor(t); setList(null); };

  const open = (anchor) => {
    if (!h || !place) return;
    const t = aiTarget(h);
    let x, y, up = null;
    if (anchor) { const r = anchor.getBoundingClientRect(); x = r.left + r.width / 2; y = r.bottom + 4; up = r.top - 4; }
    else { const c = h.editor.view.coordsAtPos(t.to); x = c.left; y = c.bottom + 4; up = c.top - 4; }
    setList({ x, y, up, target: t, ask: false });
  };

  // Put the list inside the window: below its anchor, or above it when there is no room below; never past either side.
  useLayoutEffect(() => {
    const el = box.current;
    if (!list || !el) return;
    const w = el.offsetWidth, hh = el.offsetHeight;
    const top = list.y + hh > window.innerHeight - 8 && list.up !== null ? list.up - hh : list.y;
    el.style.left = `${Math.round(Math.max(8, Math.min(list.x - w / 2, window.innerWidth - w - 8)))}px`;
    el.style.top = `${Math.round(Math.max(8, Math.min(top, window.innerHeight - hh - 8)))}px`;
  }, [list]);

  const status = client.status();
  const off = status === "off" || status === "not_signed_in";
  const t = list && list.target;
  const entries = !t ? [] : aiEntries(place, { paragraphs: t.paragraphs, selected: t.selected, canMake: typeof onMakeInto === "function" && t.selected && !!t.text.trim() })
    .map((e) => ({ ...e, off: e.type !== "make" && (off || !t.text.trim()) }));
  const line = !t ? "" : off ? (status === "off" ? WORDS.off : WORDS.notSignedIn) : !t.text.trim() ? WORDS.nothing : "";

  const ask = (option, instruction, tg) => { focusEditor(tg); setList(null); setCard({ target: tg, option, instruction, n: ++count.current }); };
  const pick = (en) => {
    if (en.type === "make") { focusEditor(t); setList(null); onMakeInto(en.id, t.text); return; }
    if (en.type === "ask") { setList({ ...list, ask: true }); return; }
    ask(en.id, "", t);
  };

  const accepted = (html) => {
    const tg = card.target;
    if (!acceptAi(h, tg, html)) setProblem && setProblem(WORDS.changed);
  };

  return {
    open,
    key(e) { if (isSlash(e)) { e.preventDefault(); open(null); return true; } return false; },
    list: list ? (
      <AiList key="list" entries={entries} line={line} ask={list.ask} place={place} boxRef={box} onPick={pick}
        onAsk={(v) => ask("custom", v, list.target)} onClose={close} />
    ) : null,
    card: card ? (
      <AiCard key={card.n} client={client} place={place} option={card.option} text={card.target.text} instruction={card.instruction}
        returnTo={(how) => (how === "accept" ? h.editor.view.focus() : focusEditor(card.target))} onAccept={accepted} onClose={() => setCard(null)} />
    ) : null,
  };
}
