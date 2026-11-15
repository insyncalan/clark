// The peek's Latest update and its 'Last updated' stamp, and the warning bar above the title (Edit only: a published file and View
// show the fields and nothing else). Every change is one request with one Undo (changeCell), and the data is read again after it so
// the stamp is the one clark wrote. The text is on the one rich editor (RichField, item 1005). Row 1179 (the owner, 14-11) lifts row 1077's
// ruling 1 for ONE control: the quiet "Draft with AI" button beside Latest update (an action's peek), which opens the AI menu (place "current")
// and then the AiCard under the field. Nothing changes in the text before Accept. An action that is shown to the client carries a 'Shown to the client' label (its latest update is published). An action has a latest update; a risk, issue or decision has the stamp only.
import { RichField } from "./RichField.jsx";
import { richOrPlain } from "../logic/richOrPlain.js";
import { data } from "../stores/report.js";
import { changeCell, say, refresh } from "../stores/changes.js";
import { showDate, todayIso } from "../workItems.js";
import { changeFor, tableOf } from "./itemEdit.js";
import { warnFor, stampText } from "./peekLatest.js";
import { Icon } from "../components/Icon.jsx";
import { PeekLatestHistory } from "./PeekLatestHistory.jsx";
import { useRef, useState } from "preact/hooks";
import { AiCard } from "./AiCard.jsx";
import { realAiClient } from "./aiClient.js";
import { menu } from "../logic/aiMenu.js";
import { token } from "../stores/report.js";

const aiClient = realAiClient({ token });
export const DRAFT_WITH_AI = "Draft with AI";      // the ticket's words (row 1179)

// The button (in the label row), and under the row the option list (the server's "current" place: Format notes, then the groups) and the card.
function useDraftAi() {
  const [step, setStep] = useState(null);       // null | "menu" | {option}
  const btn = useRef(null);
  const back = () => { setStep(null); setTimeout(() => btn.current && btn.current.focus(), 0); };
  const open = async () => { if (step) { back(); return; } await aiClient.refresh(); setStep("menu"); };
  return { step, setStep, btn, back, open };
}
function DraftButton({ ai }) {
  return (
    <button type="button" class="pk-ai" data-pk-ai ref={ai.btn} aria-label={DRAFT_WITH_AI} aria-haspopup="menu" aria-expanded={ai.step === "menu" ? "true" : "false"} onClick={ai.open}>
      <Icon name="sparkle" cls="s" />{DRAFT_WITH_AI}
    </button>
  );
}
function DraftPanel({ ai, text, onAccept }) {
  const { step } = ai;
  if (!step) return null;
  if (step === "menu") {
    const m = menu("current");
    const items = [m.format_notes, ...m.groups.flatMap((g) => g.items)].filter(Boolean);
    return (
      <div class="pk-ai-menu" role="menu" data-pk-ai-menu onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); ai.back(); } }}>
        {items.map((o, i) => <button key={o.id} type="button" role="menuitem" data-pk-ai-option={o.id} autoFocus={i === 0} title={o.line} onClick={() => ai.setStep({ option: o.id })}>{o.name}</button>)}
      </div>
    );
  }
  return <div class="pk-ai-card" data-pk-ai-card><AiCard client={aiClient} place="current" option={step.option} text={text} returnTo={ai.back} onAccept={onAccept} onClose={() => ai.setStep(null)} /></div>;
}

const raw = (row) => ((data.value && data.value[tableOf(row)]) || []).find((r) => r.id === row.id) || null;
const toClose = () => { const el = document.activeElement; if (!el || el === document.body || !el.isConnected) { const c = document.querySelector("#peek [data-pk-close]"); if (c) c.focus(); } };

// A date moved from the bar: one change, one Undo, the toast says where it went.
function move(row, date) {
  const c = changeFor(row, "due", date, todayIso());
  if (!c || c.error) { say("problem", c ? c.error : "That is already the date."); return; }
  changeCell(tableOf(row), row.id, c.changes, { text: `${row.id} moved to ${showDate(date)}.`, back: c.back, place: "peek" }).then(() => refresh()).then(toClose);
}

export function PeekWarn({ row }) {
  const w = warnFor(row, todayIso());
  if (!w) return null;
  return (
    <div class="pk-warnbar" data-pk-warn={w.kind}>
      <p class="pk-warn"><Icon name="flash" cls="s" />{w.text}</p>
      <div class="pk-fix">{w.moves.map((m) => <button key={m.date} type="button" data-pk-move={m.date} onClick={() => move(row, m.date)}>{m.label}</button>)}</div>
    </div>
  );
}

export function PeekLatest({ row }) {
  const rec = raw(row), action = row.kind === "action";
  const now = rec && rec.latest_update ? String(rec.latest_update) : "";
  const stamp = rec ? stampText(rec.updated_at) : "";
  const html = (() => { try { return richOrPlain(now); } catch (e) { return "<p>" + String(now).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") + "</p>"; } })();    // item 1005: the editor's HTML, or the plain text an older clark stored
  // The rich editor saves with Cmd/Ctrl+Enter and leaves with Esc. It closes only when clark has saved it: a refusal (the toast says why)
  // or no answer leaves it open with what was typed.
  const ai = useDraftAi();
  const save = (value) => changeCell("actions", row.id, { latest_update: value },
    { text: `Latest update of ${row.id} saved.`, back: `Latest update of ${row.id} is back as it was.`, place: "peek" })
    .then((reply) => { if (reply) refresh(); return reply; });
  return (
    <div class="pk-latest" data-pk-latest>
      {action ? <>
        <div class="pk-lab"><span id={`pk-latest-lab-${row.id}`}>Latest update</span>
          {action ? <DraftButton ai={ai} /> : null}
          {row.client ? <span class="pk-latest-client" data-pk-latest-client><Icon name="eye" cls="s" />Shown to the client</span> : null}</div>
        {action ? <DraftPanel ai={ai} text={now} onAccept={(h) => save(h)} /> : null}
        <RichField field="latest_update" id={row.id} value={html} label="Latest update" empty="Add the latest update…" save={save} viewId={`pk-latest-txt-${row.id}`} labelledBy={`pk-latest-lab-${row.id} pk-latest-txt-${row.id}`} />
      </> : null}
      {stamp ? <div class="pk-last" data-pk-last><Icon name="clock" cls="s" /> Last updated {stamp}</div> : null}
      {action ? <PeekLatestHistory key={`h-${row.id}`} id={row.id} /> : null}
    </div>
  );
}
