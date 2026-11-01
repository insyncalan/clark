// A change an answer suggested (#47e), shown in the ask panel as a card: the row now and after Apply, both from the server's dry
// run of the saved data (never the answer's words), an Apply button, a separate Confirm for a change from an answer that read the
// person's files, a plain line when it can't be made, and "Done." with Undo (the board's own undo route, through api.js) once saved.
// Every value is a text node; nothing here is read as markup. While asking is off nothing on a card can be pressed.
import { useState } from "preact/hooks";
import { project, reread, token } from "../stores/report.js";
import { sendUndo } from "../api.js";
import { showDate } from "../workItems.js";
import { panelState } from "./askPanelState.js";
import * as W from "./askWords.js";

const DATE = /^\d{4}-\d{2}-\d{2}$/;
const shown = (v) => (v === null || v === undefined || v === "" ? W.NOT_SET : typeof v === "string" && DATE.test(v) ? showDate(v) : String(v));
// The server's refusals are fixed plain sentences (ask_apply.py); anything else is replaced by the page's own words.
export const fixedLine = (m, fallback) => (typeof m === "string" && m.length > 0 && m.length <= 300 && !/[\u0000-\u001f<>]/.test(m) ? m : fallback);

export async function askPost(path, body) {
  try {
    const r = await fetch(path, { method: "POST", headers: { "X-Clark-Token": token(), "Content-Type": "application/json" }, body: JSON.stringify(body), cache: "no-store" });
    return { status: r.status, body: await r.json().catch(() => null) };
  } catch (e) {
    return { status: 0, body: null };
  }
}

/** The turn that holds a reply's dry run: {plans, fromSource, passages}. */
export function ChangeCards({ turn }) {
  const passages = Array.isArray(turn.passages) ? turn.passages.filter((p) => p && typeof p.label === "string") : [];
  return (
    <div class="ask-changes" data-ask-changes>
      {turn.fromSource && passages.length ? (
        <div class="ask-passages">
          {passages.map((p, i) => (
            <figure key={i} class="ask-passage" data-ask-passage>
              <figcaption><span class="muted">{W.FROM_FILE}: </span>{p.label}</figcaption>
              <blockquote>{typeof p.text === "string" ? p.text : ""}</blockquote>
            </figure>
          ))}
        </div>
      ) : null}
      {(turn.plans || []).map((plan, i) => <ChangeCard key={i} plan={plan} fromSource={!!turn.fromSource} passages={passages.length} />)}
    </div>
  );
}

function ChangeCard({ plan, passages }) {
  const [state, setState] = useState("offered");       // offered | saving | done | undoing | undone | failed
  const [ticked, setTicked] = useState(false);
  const [line, setLine] = useState("");
  const [step, setStep] = useState(null);
  const live = panelState.value === "ready";

  if (!plan || plan.ok !== true) {
    return <p class="ask-refused" data-ask-refused>{fixedLine(plan && plan.message, W.REFUSED_LINE)}</p>;
  }
  const confirm = plan.needs_confirm === true;
  const before = plan.before && typeof plan.before === "object" ? plan.before : null;
  const after = plan.after && typeof plan.after === "object" ? plan.after : {};
  const fields = Array.isArray(plan.fields) ? plan.fields.filter((f) => typeof f === "string") : [];
  const kind = plan.kind === "raid" && typeof after.type === "string" ? after.type : W.KIND_NAMES[plan.kind] || "";

  async function apply() {
    if (!live || state !== "offered" || (confirm && !ticked)) return;
    setState("saving");
    setLine(W.APPLYING_LINE);
    const r = await askPost("/api/ask/change/apply", confirm ? { project: project.value, offer: plan.offer, confirm: true } : { project: project.value, offer: plan.offer });
    const b = r.body;
    if (r.status === 200 && b && b.ok === true && Number.isInteger(b.apply_id)) {
      setStep(b.undoable === false ? null : b.apply_id);
      setState("done");
      setLine(W.DONE_LINE);
      reread(project.value);
      return;
    }
    if (r.status === 409 && b && b.code === "asking_off") panelState.value = "off";
    setState("failed");
    setLine(r.status === 400 || r.status === 409 ? fixedLine(b && b.message, W.NOT_SAVED_LINE) : W.NOT_SAVED_LINE);
  }

  async function undo() {
    if (!live || state !== "done" || step === null) return;
    setState("undoing");
    const r = await sendUndo(project.value, step);
    if (r.ok) { setState("undone"); setLine(W.UNDONE_LINE); reread(project.value); return; }
    setState("done");
    setLine(W.UNDO_FAILED_LINE);
  }

  // Enter alone never applies a change that needs Confirm: the box must be ticked, then Apply pressed (a click or Space).
  const applyKey = (e) => { if (confirm && e.key === "Enter") e.preventDefault(); };

  return (
    <section class="ask-change" data-ask-change data-ref={plan.ref || ""}>
      <header class="ask-change-head">
        <strong>{plan.new ? W.NEW_HEAD : W.CHANGE_HEAD}</strong>
        <span class="muted">{plan.new ? kind : plan.ref || ""}</span>
      </header>
      <table class="ask-diff">
        <thead><tr><th scope="col">{W.FIELD}</th><th scope="col">{W.NOW}</th><th scope="col">{W.AFTER}</th></tr></thead>
        <tbody>
          {fields.map((f) => (
            <tr key={f} data-field={f}>
              <th scope="row">{W.FIELD_NAMES[f] || f}</th>
              <td data-before>{shown(before ? before[f] : null)}</td>
              <td data-after>{shown(after[f])}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {confirm && state === "offered" && live ? (
        <div class="ask-confirm">
          <p class="ask-confirm-line">{passages ? W.CONFIRM_LINE : W.CONFIRM_NO_PASSAGE_LINE}</p>
          <label><input type="checkbox" data-ask-confirm checked={ticked} onChange={(e) => setTicked(e.currentTarget.checked)}
            onKeyDown={(e) => { if (e.key === "Enter") e.preventDefault(); }} /> {W.CONFIRM_BOX}</label>
        </div>
      ) : null}
      {state === "offered" && live ? (
        <div class="ask-change-actions">
          <button type="button" class="btn primary sm" data-ask-apply disabled={confirm && !ticked} onKeyDown={applyKey} onClick={apply}>{W.APPLY}</button>
        </div>
      ) : null}
      {line ? (
        <p class={`ask-change-line${state === "failed" ? " problem" : ""}`} data-ask-line role="status">
          {line}
          {state === "done" && step !== null && live ? <> <button type="button" class="btn sm quiet" data-ask-undo onClick={undo}>{W.UNDO}</button></> : null}
        </p>
      ) : null}
    </section>
  );
}
