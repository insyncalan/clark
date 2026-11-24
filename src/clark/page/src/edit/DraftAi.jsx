// Row 1179: the AI flow of a rich field, shared by the quiet "Draft with AI" button (the peek's Latest update) and the right-click menu
// (RichText.jsx). The menu is the master editor's menu of the place "current" (logic/aiMenu.js menu(), the server's list in ai_menu.py): Format
// notes (only when the text has two lines or more, as the server holds it), Improve, Structure, then Ask…. Making a new item from the text
// ("Make into") is not in this slice. A choice opens the card (AiCard.jsx; Ask… first asks for the person's own instruction). Nothing changes in
// the field before Accept. This is not the Draft email feature (RowMenu.jsx, DraftEmail.jsx): two names, two features.
import { useEffect, useRef, useState } from "preact/hooks";
import { AiCard } from "./AiCard.jsx";
import { aiClient } from "./aiShared.js";
import { menu, OPTIONS } from "../logic/aiMenu.js";
import { Icon } from "../components/Icon.jsx";
import { classicTheme } from "../components/Contents.jsx";

export const DRAFT_WITH_AI = "Draft with AI";

const lines = (text) => String(text || "").split("\n").filter((l) => l.trim()).length;

// The option list. Arrow keys move, Enter picks, Esc closes (the owner puts the focus back).
export function AiMenuList({ place, text, onPick, onClose, boxRef = null, floating = false }) {
  const m = menu(place), own = useRef(null), box = boxRef || own;
  useEffect(() => { const b = box.current && box.current.querySelector("button"); if (b) b.focus(); }, []);
  if (!m) return null;
  // Row 1288 (Classic, "5B"): one line per item, its description as the browser's own tooltip (title), a small icon in the group's colour (Improve purple, Structure green, Ask amber).
  const classic = classicTheme();
  const item = (o, kind = "structure") => classic ? (
    <button key={o.id} type="button" role="menuitem" class="aim-opt" data-ai-option={o.id} title={o.line} onClick={() => onPick(o.id)}>
      <Icon name={kind === "ask" ? "pencil" : kind === "improve" ? "sparkle" : "bars"} cls={`aim-ic aim-ic-${kind}`} /><span class="aim-nm">{o.name}</span>
    </button>
  ) : (
    <button key={o.id} type="button" role="menuitem" class="aim-opt" data-ai-option={o.id} onClick={() => onPick(o.id)}>
      <span class="aim-nm">{o.name}</span><span class="aim-ds">{o.line}</span>
    </button>
  );
  const key = (e) => {
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onClose(); return; }
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const bs = [...box.current.querySelectorAll("button")], i = bs.indexOf(document.activeElement);
      bs[(i + (e.key === "ArrowDown" ? 1 : bs.length - 1)) % bs.length].focus();
    }
  };
  return (
    <div class={`aim${floating ? " aim-float" : ""}`} role="menu" aria-label={DRAFT_WITH_AI} data-ai-menu ref={box} onKeyDown={key}>
      {m.format_notes && lines(text) >= 2 ? <>{item(m.format_notes, "structure")}<hr /></> : null}
      {m.groups.map((g, i) => <div key={g.label} role="group" aria-label={g.label}>{i ? <hr /> : null}<div class="aim-gl" aria-hidden="true">{g.label}</div>{g.items.map((o) => item(o, g.label === "Improve" ? "improve" : "structure"))}</div>)}
      <hr />{item(m.ask, "ask")}
    </div>
  );
}

// Ask…: the person's own instruction. Enter asks, Esc goes back.
function AskBox({ onGo, onClose }) {
  const r = useRef(null);
  useEffect(() => { if (r.current) r.current.focus(); }, []);
  return (
    <div class="aim-ask" data-ai-ask>
      <input ref={r} type="text" aria-label={OPTIONS.custom[1]} maxLength={400} autoComplete="off"
        onKeyDown={(e) => {
          if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onClose(); }
          else if (e.key === "Enter" && !e.isComposing) { e.preventDefault(); e.stopPropagation(); const v = e.currentTarget.value.trim(); if (v) onGo(v); }
        }} />
    </div>
  );
}

// The whole flow once opened: menu -> (Ask…) -> card. `text` is what goes to Claude; `onAccept(html)` is called by Accept; `onDone(how)` when
// the flow ends for any reason (so the owner puts the focus back).
export function AiFlow({ place, text, onAccept, onDone, floating = false, boxRef = null }) {
  const [step, setStep] = useState({ at: "menu" });
  const client = aiClient();
  if (step.at === "menu") return <AiMenuList place={place} text={text} floating={floating} boxRef={boxRef} onClose={() => onDone("esc")} onPick={(id) => setStep(id === "custom" ? { at: "ask" } : { at: "card", option: id })} />;
  if (step.at === "ask") return <AskBox onClose={() => setStep({ at: "menu" })} onGo={(instruction) => setStep({ at: "card", option: "custom", instruction })} />;
  return <div class="aim-card" data-ai-card><AiCard client={client} place={place} option={step.option} instruction={step.instruction || ""} text={text} returnTo={() => {}} onAccept={onAccept} onClose={(how) => onDone(how)} /></div>;
}

// The button beside a field's heading, and the flow under the row. `open` is true while the flow is shown.
export function useDraftAi() {
  const [open, setOpen] = useState(false), btn = useRef(null);
  const toggle = async () => { if (open) { setOpen(false); return; } await aiClient().refresh(); setOpen(true); };
  const done = () => { setOpen(false); if (btn.current) btn.current.focus(); };
  return { open, btn, toggle, done };
}
export function DraftButton({ ai }) {
  return (
    <button type="button" class="pk-ai" data-pk-ai ref={ai.btn} aria-label={DRAFT_WITH_AI} aria-haspopup="menu" aria-expanded={ai.open ? "true" : "false"} onClick={ai.toggle}>
      <Icon name="sparkle" cls="s" />{DRAFT_WITH_AI}
    </button>
  );
}
export function DraftPanel({ ai, place, text, onAccept }) {
  return ai.open ? <div class="pk-ai-panel" data-pk-ai-panel><AiFlow place={place} text={text} onAccept={onAccept} onDone={ai.done} /></div> : null;
}
