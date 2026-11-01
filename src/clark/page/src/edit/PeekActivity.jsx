// The peek's tabs in Edit (#42): Details (the fields) and Activity (who changed what, how and when, newest first, from
// GET /api/activity). Edit only: View and a published file show the fields and nothing else, so nothing here is in them.
// Every value is drawn as text, never as markup. The tabs follow the usual keys: Left and Right move, Home and End jump.
import { useEffect, useLayoutEffect, useRef, useState } from "preact/hooks";
import { project, data } from "../stores/report.js";
import { peekTab } from "../stores/peekState.js";
import { readActivity } from "./activityApi.js";
import { createSelection } from "../stores/selection.js";
import { undoSeveral } from "../stores/changes.js";
import { ownClick, noTextRange } from "../components/pick.js";
import { whyNot, chooseable, stepsOf, CONFIRM_ABOVE } from "./activityUndo.js";
import { UndoBar } from "./ActivityUndo.jsx";

const TABS = [["details", "Details"], ["activity", "Activity"]];
const LOADING = "Reading the history…";
const MISSING = "This item is not in the open lists (it may be archived), so its history is not shown here.";
const FAILED = "The history could not be read just now. Close the peek and open it again to try once more.";

export function PeekTabs() {
  const list = useRef(null);
  const key = (e) => {
    const i = TABS.findIndex(([k]) => k === peekTab.value);
    const to = e.key === "ArrowRight" ? (i + 1) % TABS.length : e.key === "ArrowLeft" ? (i + TABS.length - 1) % TABS.length
      : e.key === "Home" ? 0 : e.key === "End" ? TABS.length - 1 : -1;
    if (to < 0) return;
    e.preventDefault();
    peekTab.value = TABS[to][0];
    const btn = list.current && list.current.querySelector(`[data-pk-tab=${TABS[to][0]}]`);
    if (btn) btn.focus();
  };
  return (
    <div class="pk-tabs" role="tablist" aria-label="Item details and history" ref={list} onKeyDown={key}>
      {TABS.map(([k, label]) => {
        const on = peekTab.value === k;
        return <button key={k} type="button" role="tab" id={`pk-tab-${k}`} aria-controls={`pk-panel-${k}`} aria-selected={on ? "true" : "false"}
          tabIndex={on ? 0 : -1} class={`pk-tab${on ? " on" : ""}`} data-pk-tab={k} onClick={() => { peekTab.value = k; }}>{label}</button>;
      })}
    </div>
  );
}

function Change({ r }) {
  if (r.kind === "Created") return <p class="pa-what"><span class="pa-kind">Created</span>{r.to ? <span> {r.to}</span> : null}</p>;
  if (r.kind === "Comment") return <p class="pa-what"><span class="pa-kind">Comment</span> {r.to}</p>;
  const pieces = Array.isArray(r.diff) && r.diff.length ? r.diff : null;
  return (
    <p class="pa-what">
      {r.kind !== "Changed" ? <span class="pa-kind">{r.kind} </span> : null}
      <span class="pa-f">{r.field}</span>{": "}
      {pieces ? pieces.map((p, i) => (p.op === "removed" ? <del key={i}>{p.text}</del> : p.op === "added" ? <ins key={i}>{p.text}</ins> : <span key={i}>{p.text}</span>))
        : <>
          <span class="pa-from">{r.from || "nothing"}</span><span aria-hidden="true">{" → "}</span><span class="sr-only"> to </span><span class="pa-to">{r.to || "nothing"}</span>
        </>}
      {r.diff_note ? <span class="muted pa-note"> {r.diff_note}</span> : null}
    </p>
  );
}

// The steps drawn on the tab, in the order drawn, once each (the selection's order for a Shift range).
const drawnSteps = (root) => {
  const out = [];
  root.querySelectorAll("[data-activity-row][data-step]").forEach((e) => { if (!out.includes(e.dataset.step)) out.push(e.dataset.step); });
  return out;
};

export function PeekActivity({ id }) {
  const [got, setGot] = useState(null);           // null: reading; {ok, view}
  const [phase, setPhase] = useState(null);       // null, or {kind: "reading" | "preview" | "sure" | "working" | "problem", ...}
  const [sel] = useState(createSelection);        // this tab's own selection: in memory, gone with the tab
  const panel = useRef(null), head = useRef(null), undoBtn = useRef(null);
  const d = data.value;                           // a change anywhere replaces the data, so the tab reads again
  useEffect(() => {
    let live = true;
    readActivity(project.value, id).then((r) => { if (live) setGot(r); });
    return () => { live = false; };
  }, [id, d]);                                    // eslint-disable-line react-hooks/exhaustive-deps
  const rows = got && got.ok ? got.view.rows : [];
  const ticks = chooseable(rows);
  const mine = ticks.join(",");
  // After the rows are drawn again: a change that left the list leaves the selection, and an open preview is read afresh by asking again.
  useLayoutEffect(() => { if (panel.current) { const o = drawnSteps(panel.current); sel.sync(o, o); } }, [mine]);   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => sel.clear(), []);         // eslint-disable-line react-hooks/exhaustive-deps
  const chosen = sel.ids.value;                   // the selection changes: redraw; a preview of another choice is no longer true
  const key = chosen.join(",");
  useEffect(() => { setPhase((p) => (p && (p.kind === "preview" || p.kind === "sure" || p.kind === "problem") ? null : p)); }, [key]);
  // Esc: first closes an open preview, then clears the selection; the peek stays. It runs before the peek's own Esc.
  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== "Escape" || e.defaultPrevented || e.isComposing) return;
      if (document.querySelector("[role=menu]")) return;
      const t = e.target;
      if (t && t.nodeType === 1 && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) && t.type !== "checkbox") return;
      if (phase && phase.kind === "working") return;
      if (phase && phase.kind !== "reading") { e.preventDefault(); e.stopPropagation(); setPhase(null); if (undoBtn.current) undoBtn.current.focus(); return; }
      if (sel.size.value > 0) { e.preventDefault(); e.stopPropagation(); sel.clear(); setPhase(null); }
    };
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
  }, [phase]);                                    // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (phase && (phase.kind === "preview" || phase.kind === "sure") && head.current) head.current.focus(); }, [phase && phase.kind]);

  const order = () => (panel.current ? drawnSteps(panel.current) : []);
  const pick = (e, step, tick) => {
    const how = tick ? { add: true, range: e.shiftKey } : { add: e.metaKey || e.ctrlKey, range: e.shiftKey };
    if (!tick && String(window.getSelection ? window.getSelection() : "").length) return;     // the person is selecting text
    sel.click(step, how, order());
  };
  const onRow = (e, step) => { if (ownClick(e.target, e.currentTarget)) pick(e, step, false); };
  const preview = async () => {
    const steps = stepsOf(sel.ids.value);
    setPhase({ kind: "reading" });
    const r = await undoSeveral(steps, { preview: true });
    if (sel.ids.value.join(",") !== key) return;                      // the choice changed while it read
    setPhase(r.ok ? { kind: "preview", reply: r.reply } : { kind: "problem", message: r.message });
  };
  const go = async (sure) => {
    const steps = stepsOf(sel.ids.value);
    if (steps.length > CONFIRM_ABOVE && !sure) { setPhase({ kind: "sure", reply: phase.reply }); return; }
    setPhase({ kind: "working" });
    const r = await undoSeveral(steps, { confirm: steps.length > CONFIRM_ABOVE });
    if (r.ok) { sel.clear(); setPhase(null); if (panel.current) panel.current.focus(); }
    else setPhase({ kind: "problem", message: r.message });
  };
  const back = () => { setPhase(null); if (undoBtn.current) undoBtn.current.focus(); };

  let body;
  if (!got) body = <p class="muted pa-none" data-activity-loading>{LOADING}</p>;
  else if (!got.ok && got.missing) body = <p class="muted pa-none" data-activity-missing>{MISSING}</p>;
  else if (!got.ok) body = <p class="muted pa-none" data-activity-failed>{FAILED}</p>;
  else if (!got.view.rows.length) body = <p class="muted pa-none" data-activity-empty>{got.view.empty || "Nothing has changed on this item yet."}</p>;
  else {
    const state = sel.groupState(ticks);
    body = (
      <>
        {ticks.length ? (
          <label class="pa-all" data-pa-all-label>
            <input type="checkbox" class="gtick" data-pa-all checked={state === "checked"} ref={(el) => { if (el) el.indeterminate = state === "mixed"; }}
              onChange={() => sel.toggleGroup(ticks)} />
            <span>Select all changes that can be undone</span>
          </label>
        ) : null}
        <ol class="pa-list" data-activity-rows>
          {got.view.rows.map((r, i) => {
            const why = whyNot(r), step = String(r.step), on = !why && sel.has(step);
            return (
              <li key={i} class={`pa-row${on ? " picked" : ""}`} data-activity-row data-step={why ? undefined : step} data-picked={on ? "1" : undefined}
                onMouseDown={why ? undefined : noTextRange} onClick={why ? undefined : (e) => onRow(e, step)}>
                <div class="pa-line">
                  {why ? <span class="pa-notick" /> : (
                    <span class="gtick-hit">
                      <input type="checkbox" class="gtick" data-pa-tick={step} checked={on} aria-label={`Select this change: ${r.field || r.kind}, ${r.when_text}`}
                        onClick={(e) => { e.stopPropagation(); pick(e, step, true); }} onChange={() => {}} />
                    </span>
                  )}
                  <div class="pa-body">
                    <p class="pa-meta"><span class="pa-who">{r.who || "Someone on this computer"}</span>{r.how ? <span> · {r.how}</span> : null}<span> · {r.when_text}</span></p>
                    <Change r={r} />
                    {why ? <p class="muted pa-why" data-pa-why>{why}</p> : null}
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      </>
    );
  }
  return (
    <section class="pk-activity" role="tabpanel" id="pk-panel-activity" aria-labelledby="pk-tab-activity" tabIndex={0} data-activity aria-busy={got ? "false" : "true"} ref={panel}>
      <p class="sr-only" role="status" aria-live="polite" data-pa-live>{phase && phase.kind === "working" ? "Undoing…" : sel.live.value}</p>
      <UndoBar sel={sel} phase={phase} onUndo={preview} onGo={() => go(false)} onSure={() => go(true)} onBack={back} undoBtn={undoBtn} head={head} />
      {body}
      {got && got.ok && got.view.closing ? <p class="muted pa-none">{got.view.closing}</p> : null}
    </section>
  );
}
