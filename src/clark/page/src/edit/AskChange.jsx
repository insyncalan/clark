// A change an answer suggested (#47e), shown in the ask panel as a card: the row now and after Apply, both from the server's dry
// run of the saved data (never the answer's words), an Apply button, a separate Confirm for a change from an answer that read the
// person's files, a plain line when it can't be made, and "Done." with Undo (the board's own undo route, through api.js) once saved.
// Every value is a text node; nothing here is read as markup. While asking is off nothing on a card can be pressed.
import { useEffect, useRef, useState } from "preact/hooks";
import { project, reread, token } from "../stores/report.js";
import { sendUndo, sendUndoMany, zoneFetch } from "../api.js";
import { showDate } from "../workItems.js";
import { plainText } from "../logic/cleanHtml.js";
import { classicTheme } from "../components/Contents.jsx";
import { panelState, turns } from "./askPanelState.js";
import * as W from "./askWords.js";

const DATE = /^\d{4}-\d{2}-\d{2}$/;
const shown = (v) => (v === null || v === undefined || v === "" ? W.NOT_SET : typeof v === "string" && DATE.test(v) ? showDate(v) : String(v));
const shownIn = (f, v) => (f === "standing" && typeof v === "string" && v !== "" ? shown(plainText(v)) : shown(v));      // "Where it stands" is rich text: its words, not its tags
// The server's refusals are fixed plain sentences (ask_apply.py); anything else is replaced by the page's own words.
export const fixedLine = (m, fallback) => (typeof m === "string" && m.length > 0 && m.length <= 300 && !/[\u0000-\u001f<>]/.test(m) ? m : fallback);

export async function askPost(path, body) {
  try {
    const r = await zoneFetch(path, { method: "POST", headers: { "X-Clark-Token": token(), "Content-Type": "application/json" }, body: JSON.stringify(body), cache: "no-store" });
    return { status: r.status, body: await r.json().catch(() => null) };
  } catch (e) {
    return { status: 0, body: null };
  }
}

// A card's saved state lives on the turn (found again by its plans, which every copy of the turn shares), so it survives the panel
// being closed and opened again. The turn is replaced, never changed in place.
const keepCard = (turn, index, more) => {
  turns.value = turns.value.map((t) => t.plans !== turn.plans ? t
    : { ...t, cards: { ...(t.cards || {}), [index]: { ...((t.cards && t.cards[index]) || {}), ...more } } });
};
const keepGroup = (turn, more) => { turns.value = turns.value.map((t) => t.plans !== turn.plans ? t : { ...t, group: { ...(t.group || {}), ...more } }); };
const cardOf = (turn, i) => (turn.cards && turn.cards[i]) || {};

// The item's own ID as a link to it, where the board can show it (a work item or a milestone); a decision is shown as its ID.
function ItemLink({ plan }) {
  const ref = typeof plan.ref === "string" ? plan.ref : "";
  const href = plan.kind === "actions" || plan.kind === "raid" ? `#work&p=${encodeURIComponent(project.value)}&item=${encodeURIComponent(ref)}`
    : plan.kind === "milestones" ? `#milestones&p=${encodeURIComponent(project.value)}&ms=${encodeURIComponent(ref)}` : "";
  return href ? <a class="ask-change-ref" data-ask-item href={href}>{ref}</a> : <strong class="ask-change-ref" data-ask-item>{ref}</strong>;
}

// Save one offer. Returns the Undo step (an integer), null when saved but not undoable, or false when it was not saved.
async function applyOne(turn, index, plan, confirmed) {
  keepCard(turn, index, { state: "saving", line: W.APPLYING_LINE });
  const r = await askPost("/api/ask/change/apply", confirmed ? { project: project.value, offer: plan.offer, confirm: true } : { project: project.value, offer: plan.offer });
  const b = r.body;
  if (r.status === 200 && b && b.ok === true && Number.isInteger(b.apply_id)) {
    const step = b.undoable === false ? null : b.apply_id;
    keepCard(turn, index, { state: "done", line: W.DONE_LINE, step });
    if (classicTheme() && Array.isArray(b.stale)) markStale(turn, b.stale);      // row 1293: another change to this item, now out of date, shows the server's line in place of its Apply
    reread(project.value);
    return step;
  }
  if (r.status === 409 && b && b.code === "asking_off") panelState.value = "off";
  keepCard(turn, index, { state: "failed", line: r.status === 400 || r.status === 409 ? fixedLine(b && b.message, W.NOT_SAVED_LINE) : W.NOT_SAVED_LINE });
  return false;
}

/** The turn that holds a reply's dry run: {plans, fromSource, passages}. */
export function ChangeCards({ turn }) {
  const passages = Array.isArray(turn.passages) ? turn.passages.filter((p) => p && typeof p.label === "string") : [];
  const plans = turn.plans || [];
  const group = turn.group || {};
  const live = panelState.value === "ready";
  const classic = classicTheme();            // row 1292: every piece of the new card is Classic only; Cards draws the card as it was
  // Apply all: only when two or more are still offered and none needs the Confirm box (that choice is always made one card at a time).
  const offered = plans.map((p, i) => i).filter((i) => plans[i] && plans[i].ok === true && (cardOf(turn, i).state || "offered") === "offered");
  const allOk = classic && !plans.some((p) => p && p.ok === true && p.needs_confirm === true) && !group.state;
  async function applyAll() {
    if (!live || !allOk || offered.length < 2) return;
    const steps = [];
    let saved = 0;
    for (const i of offered) {
      const step = await applyOne(turn, i, plans[i], false);
      if (step !== false) saved++;
      if (Number.isInteger(step)) steps.push(step);
      if (panelState.value === "off") break;           // asking was turned off: nothing more is applied, the cards left stay offered
    }
    keepGroup(turn, { state: "done", steps, line: saved === offered.length ? W.ALL_DONE_LINE(saved) : saved ? W.ALL_PARTLY_LINE(saved, offered.length) : "", solo: steps.length === saved });
  }
  async function undoAll() {
    if (!live || group.state !== "done" || !group.solo) return;
    keepGroup(turn, { state: "undoing" });
    const r = await sendUndoMany(project.value, group.steps);    // one request: the server undoes them all (newest first) as one new step
    if (!r.ok) { keepGroup(turn, { state: "done", line: W.UNDO_FAILED_LINE }); reread(project.value); return; }
    const left = new Set(r.reply.skipped.map((e) => e && e.step).filter((n) => Number.isInteger(n)));
    if (r.reply.skipped.length && !left.size) group.steps.forEach((n) => left.add(n));          // a skipped line with no step: none is known to be undone
    const stuck = group.steps.filter((n) => left.has(n));
    plans.forEach((p, i) => {
      const c = cardOf(turn, i);
      if (c.state !== "done") return;
      if (left.has(c.step)) keepCard(turn, i, { state: "done", line: W.UNDO_FAILED_LINE });          // a change not undone is named by its own card
      else keepCard(turn, i, { state: "undone", line: W.UNDONE_LINE });
    });
    if (stuck.length) keepGroup(turn, { state: "done", steps: stuck, line: W.UNDO_FAILED_LINE });
    else keepGroup(turn, { state: "undone", line: W.ALL_UNDONE_LINE });
    reread(project.value);
  }
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
      {allOk && live && offered.length > 1 ? (
        <div class="ask-change-actions"><button type="button" class="btn sm" data-ask-apply-all onClick={applyAll}>{W.APPLY_ALL(offered.length)}</button></div>
      ) : null}
      {group.line ? (
        <p class="ask-change-line" data-ask-group-line role="status">
          {group.line}
          {group.state === "done" && group.solo && group.steps.length && live ? <> <button type="button" class="btn sm quiet" data-ask-undo-all onClick={undoAll}>{W.UNDO_ALL}</button></> : null}
        </p>
      ) : null}
      {plans.map((plan, i) => <ChangeCard key={i} plan={plan} turn={turn} index={i} passages={passages.length} />)}
    </div>
  );
}

/** Row 1293: the cards of `turn` whose offer the server says is stale get the server's line and no Apply (the card's "failed" state, which has none). */
function markStale(turn, stale) {
  const said = new Map(stale.filter((x) => x && typeof x.offer === "string").map((x) => [x.offer, fixedLine(x.message, W.NOT_SAVED_LINE)]));
  turns.value = turns.value.map((t) => {
    if (t.plans !== turn.plans) return t;
    const cards = { ...(t.cards || {}) };
    (t.plans || []).forEach((p, i) => {
      if (p && said.has(p.offer) && ((cards[i] && cards[i].state) || "offered") === "offered") cards[i] = { ...(cards[i] || {}), state: "failed", line: said.get(p.offer) };
    });
    return { ...t, cards };
  });
}

// The card's state (offered | saving | done | undoing | undone | failed, its line and Undo step) lives on the turn, not in the card, so it
// survives the panel being closed and opened again (the panel draws nothing while closed). The turn is replaced, never changed in place.
function ChangeCard({ plan, turn, index, passages }) {
  const kept = (turn.cards && turn.cards[index]) || {};
  const state = kept.state || "offered", line = kept.line || "", step = kept.step === undefined ? null : kept.step;
  const classic = classicTheme();
  const grouped = !!(turn.group && turn.group.state && turn.group.solo);          // one Undo for the lot sits above the cards (when one change can't be undone there is none, and each card keeps its own)
  const [ticked, setTicked] = useState(false);
  const setState = (v) => keepCard(turn, index, { state: v }), setLine = (v) => keepCard(turn, index, { line: v });
  const live = panelState.value === "ready";
  // Apply and Undo leave the card when pressed; focus goes to the status line (which holds Undo) unless the person has moved on elsewhere.
  const card = useRef(null), lineRef = useRef(null), was = useRef(state);
  useEffect(() => {
    const before = was.current;
    was.current = state;
    if (before === state || !["saving", "done", "undoing", "undone", "failed"].includes(state) || !lineRef.current) return;
    const at = document.activeElement;
    if (!at || at === document.body || (card.current && card.current.contains(at))) lineRef.current.focus({ preventScroll: true });
  }, [state]);

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
    await applyOne(turn, index, plan, confirm);
  }

  async function undo() {
    if (!live || state !== "done" || step === null || grouped) return;
    setState("undoing");
    const r = await sendUndo(project.value, step);
    if (r.ok) { setState("undone"); setLine(W.UNDONE_LINE); reread(project.value); return; }
    setState("done");
    setLine(W.UNDO_FAILED_LINE);
  }

  // Enter alone never applies a change that needs Confirm: the box must be ticked, then Apply pressed (a click or Space).
  const applyKey = (e) => { if (confirm && e.key === "Enter") e.preventDefault(); };

  return (
    <section class="ask-change" data-ask-change data-ref={plan.ref || ""} ref={card}>
      {classic ? (
        <header class="ask-change-head">
          {plan.new ? <strong>{W.NEW_HEAD}</strong> : <ItemLink plan={plan} />}
          {plan.new ? <span class="muted">{kind}</span> : typeof plan.title === "string" && plan.title ? <span class="ask-change-title" data-ask-title>{plan.title}</span> : null}
          {!plan.new && typeof plan.owner === "string" && plan.owner !== "" ? <span class="muted ask-change-owner" data-ask-owner>{W.FIELD_NAMES[plan.kind === "decisions" ? "made_by" : "owner"]}: {plan.owner}</span> : null}
        </header>
      ) : (
        <header class="ask-change-head">
          <strong>{plan.new ? W.NEW_HEAD : W.CHANGE_HEAD}</strong>
          <span class="muted">{plan.new ? kind : plan.ref || ""}</span>
        </header>
      )}
      {classic ? (
        <div class="ask-diff" role="list">
          {fields.map((f) => (
            <div key={f} class="ask-diff-row" role="listitem" data-field={f}>
              <span class="ask-diff-field" data-label>{W.FIELD_NAMES[f] || f}</span>
              <del class="ask-old" data-before>{shownIn(f, before ? before[f] : null)}</del>
              <span aria-hidden="true">{"\u2192"}</span>
              <mark class="ask-new" data-after>{shownIn(f, after[f])}</mark>
            </div>
          ))}
        </div>
      ) : (
        <table class="ask-diff">
          <thead><tr><th scope="col">{W.FIELD}</th><th scope="col">{W.NOW}</th><th scope="col">{W.AFTER}</th></tr></thead>
          <tbody>
            {fields.map((f) => (
              <tr key={f} data-field={f}>
                <th scope="row">{W.FIELD_NAMES[f] || f}</th>
                <td data-before>{shownIn(f, before ? before[f] : null)}</td>
                <td data-after>{shownIn(f, after[f])}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {classic && typeof plan.why === "string" && plan.why ? <p class="ask-why" data-ask-why><span class="muted">{W.WHY}: </span>{plan.why}</p> : null}
      {confirm && state === "offered" && live ? (
        <div class="ask-confirm">
          <p class="ask-confirm-line">{passages ? W.CONFIRM_LINE : W.CONFIRM_NO_PASSAGE_LINE}</p>
          <label><input type="checkbox" data-ask-confirm checked={ticked} onChange={(e) => setTicked(e.currentTarget.checked)}
            onKeyDown={(e) => { if (e.key === "Enter") e.preventDefault(); }} /> {W.CONFIRM_BOX}</label>
        </div>
      ) : null}
      {classicTheme() && state === "offered" && typeof plan.duplicate === "string" && plan.duplicate ? (
        <p class="ask-duplicate" data-ask-duplicate>{fixedLine(plan.duplicate, "")}</p>      // Row 1293: a warning above Apply; Apply stays
      ) : null}
      {state === "offered" && live ? (
        <div class="ask-change-actions">
          <button type="button" class="btn primary sm" data-ask-apply disabled={confirm && !ticked} onKeyDown={applyKey} onClick={apply}>{W.APPLY}</button>
          {classic ? <button type="button" class="btn sm quiet" data-ask-not-now onClick={() => { setState("dismissed"); setLine(W.NOT_NOW_LINE); }}>{W.NOT_NOW}</button> : null}
        </div>
      ) : null}
      {line ? (
        <p class={`ask-change-line${state === "failed" ? " problem" : ""}`} data-ask-line role="status" tabindex="-1" ref={lineRef}>
          {line}
          {state === "dismissed" ? <> <button type="button" class="btn sm quiet" data-ask-bring-back onClick={() => { setState("offered"); setLine(""); }}>{W.BRING_BACK}</button></> : null}
          {state === "done" && step !== null && live && !grouped ? <> <button type="button" class="btn sm quiet" data-ask-undo onClick={undo}>{W.UNDO}</button></> : null}
        </p>
      ) : null}
    </section>
  );
}
