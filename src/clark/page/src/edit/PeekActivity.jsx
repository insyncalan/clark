// The peek's tabs in Edit (#42): Details (the fields) and Activity (who changed what, how and when, newest first, from
// GET /api/activity). Edit only: View and a published file show the fields and nothing else, so nothing here is in them.
// Every value is drawn as text, never as markup. The tabs follow the usual keys: Left and Right move, Home and End jump.
import { useEffect, useLayoutEffect, useRef, useState } from "preact/hooks";
import { zoneFetch } from "../api.js";
import { project, data, token } from "../stores/report.js";
import { peekTab } from "../stores/peekState.js";
import { readActivity } from "./activityApi.js";
import { createSelection } from "../stores/selection.js";
import { undoSeveral } from "../stores/changes.js";
import { ownClick, noTextRange } from "../components/pick.js";
import { whyNot, chooseable, stepsOf, CONFIRM_ABOVE, SENT_KIND } from "./activityUndo.js";
import { UndoBar } from "./ActivityUndo.jsx";
import { SourceLine } from "../components/Peek.jsx";
import { Icon } from "../components/Icon.jsx";
import { showDate } from "../workItems.js";

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

// The Source line under the fields on the live page (Edit and View): where the item or milestone came from, by name, and nothing else: no person
// (activity_read.source_line), drawn by the shared SourceLine (components/Peek.jsx; a published file draws its own data with it, row 1077).
// Nothing is drawn while it is read, when it is empty or when the read fails.
export function PeekSource({ row }) {
  const [text, setText] = useState("");
  const d = data.value;
  useEffect(() => {
    let live = true;
    readActivity(project.value, row.id).then((r) => { if (live) setText(r.ok && typeof r.view.source === "string" ? r.view.source : ""); });
    return () => { live = false; };
  }, [row.id, d]);                                // eslint-disable-line react-hooks/exhaustive-deps
  return <SourceLine text={text} />;
}

// A stored day (YYYY-MM-DD, as a date field keeps it) is read DD-MM-YYYY, as everywhere else and as the approved mockup draws it; any other text is left as it is.
const dayWords = (v) => (/^\d{4}-\d{2}-\d{2}$/.test(String(v || "")) ? showDate(v) : v);

function Change({ r }) {
  if (r.kind === "Created") return <p class="pa-what"><span class="pa-kind">Created</span>{r.to ? <span> {r.to}</span> : null}</p>;
  if (r.kind === "Comment") return <p class="pa-what"><span class="pa-kind">Comment</span> {r.to}</p>;
  if (r.kind === SENT_KIND) return <p class="pa-what">{r.to}</p>;            // row 983: the one sentence, as it is (no field name, no from and to)
  const pieces = Array.isArray(r.diff) && r.diff.length ? r.diff : null;
  return (
    <p class="pa-what">
      {r.kind !== "Changed" ? <span class="pa-kind">{r.kind} </span> : null}
      <span class="pa-f">{r.field}</span>{": "}
      {pieces ? pieces.map((p, i) => (p.op === "removed" ? <del key={i}>{p.text}</del> : p.op === "added" ? <ins key={i}>{p.text}</ins> : <span key={i}>{p.text}</span>))
        : <>
          <span class="pa-from">{dayWords(r.from) || "nothing"}</span><span aria-hidden="true">{" → "}</span><span class="sr-only"> to </span><span class="pa-to">{dayWords(r.to) || "nothing"}</span>
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

// Row 1180: the history under the body. Four tabs (All, Activity, Updates, Source), each with its count; one read of the item's history feeds the
// tabs and the list. An update row is a change of the Latest update field; every other change is an activity row.
const HTABS = [["all", "All"], ["activity", "Activity"], ["updates", "Updates"], ["source", "Source"]];
const isUpdate = (r) => r.field === "Latest update" && r.kind !== "Created" && r.kind !== "Comment";

export function PeekHistory({ id }) {
  const [got, setGot] = useState(null);
  const list = useRef(null);
  const d = data.value;
  useEffect(() => {
    let live = true;
    readActivity(project.value, id).then((r) => { if (live) setGot(r); });
    return () => { live = false; };
  }, [id, d]);                                    // eslint-disable-line react-hooks/exhaustive-deps
  const rows = got && got.ok ? got.view.rows : [];
  const ups = rows.filter(isUpdate).length;
  const src = got && got.ok && got.view.source ? 1 : 0;
  const count = { all: rows.length + src, activity: rows.length - ups, updates: ups, source: src };
  const tab = peekTab.value;
  const key = (e) => {
    const i = Math.max(0, HTABS.findIndex(([k]) => k === tab));
    const to = e.key === "ArrowRight" ? (i + 1) % HTABS.length : e.key === "ArrowLeft" ? (i + HTABS.length - 1) % HTABS.length
      : e.key === "Home" ? 0 : e.key === "End" ? HTABS.length - 1 : -1;
    if (to < 0) return;
    e.preventDefault();
    peekTab.value = HTABS[to][0];
    const btn = list.current && list.current.querySelector(`[data-pk-htab=${HTABS[to][0]}]`);
    if (btn) btn.focus();
  };
  return (
    <section class="pk-history" data-pk-history>
      <div class="pk-tabs" role="tablist" aria-label="History" ref={list} onKeyDown={key} data-pk-htabs>
        {HTABS.map(([k, label]) => {
          const on = tab === k;
          return <button key={k} type="button" role="tab" id={`pk-htab-${k}`} aria-controls="pk-hpanel" aria-selected={on ? "true" : "false"}
            tabIndex={on ? 0 : -1} class={`pk-tab${on ? " on" : ""}`} data-pk-htab={k} onClick={() => { peekTab.value = k; }}>{label}{" "}<span class="pk-hcount">{count[k]}</span></button>;
        })}
      </div>
      {tab === "source" ? <div role="tabpanel" id="pk-hpanel" aria-labelledby="pk-htab-source">{src ? <HistorySource view={got.view} /> : null}</div>
        : <PeekActivity key={`${id}-${tab}`} id={id} shared={got} show={tab} />}
    </section>
  );
}

// The Source row: one sentence (the source's name, then "Open source"), the full path as the hover text. An address that starts with http opens
// in a new tab; any other source goes to the server, which judges the file again (the same route as the Ask panel's PDF sources).
function HistorySource({ view }) {
  const path = view.source_path || "";
  const web = /^https?:\/\//i.test(path);
  const open = () => {
    zoneFetch("/api/ask/open-source", { method: "POST", headers: { "Content-Type": "application/json", "X-Clark-Token": token() }, body: JSON.stringify({ project: project.value, file: path, page: null }) }).catch(() => {});
  };
  return (
    <p class="pk-hsrc" data-pk-hrow="source" title={path}>
      <Icon name="link" cls="s pk-hicon" />
      <span class="pk-hsrc-t">{view.source}</span>{" · "}
      {web ? <a href={path} target="_blank" rel="noopener noreferrer" data-pk-open-source>Open source</a>
        : <button type="button" class="linklike" data-pk-open-source onClick={open}>Open source</button>}
    </p>
  );
}

export function PeekActivity({ id, shared = null, show = "all" }) {
  const [own, setGot] = useState(null);           // null: reading; {ok, view}
  const got = shared || own;                      // the history above reads once for its tabs and hands the read down
  const [phase, setPhase] = useState(null);       // null, or {kind: "reading" | "preview" | "sure" | "working" | "problem", ...}
  const [sel] = useState(createSelection);        // this tab's own selection: in memory, gone with the tab
  const panel = useRef(null), head = useRef(null), undoBtn = useRef(null);
  const d = data.value;                           // a change anywhere replaces the data, so the tab reads again
  useEffect(() => {
    if (shared) return undefined;
    let live = true;
    readActivity(project.value, id).then((r) => { if (live) setGot(r); });
    return () => { live = false; };
  }, [id, d]);                                    // eslint-disable-line react-hooks/exhaustive-deps
  const every = got && got.ok ? got.view.rows : [];
  const rows = show === "updates" ? every.filter(isUpdate) : show === "activity" ? every.filter((r) => !isUpdate(r)) : every;
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
  else if (!rows.length) body = <p class="muted pa-none" data-activity-empty>{got.view.empty || "Nothing has changed on this item yet."}</p>;
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
          {rows.map((r, i) => {
            const note = r.kind === SENT_KIND, why = note ? "" : whyNot(r), step = String(r.step), off = note || !!why, on = !off && sel.has(step);
            return (
              <li key={i} class={`pa-row${on ? " picked" : ""}`} data-activity-row data-pk-hrow={isUpdate(r) ? "update" : "activity"} data-step={off ? undefined : step} data-picked={on ? "1" : undefined}
                onMouseDown={off ? undefined : noTextRange} onClick={off ? undefined : (e) => onRow(e, step)}>
                <div class="pa-line">
                  {off ? <span class="pa-notick" /> : (
                    <span class="gtick-hit">
                      <input type="checkbox" class="gtick" data-pa-tick={step} checked={on} aria-label={`Select this change: ${r.field || r.kind}, ${r.when_text}`}
                        onClick={(e) => { e.stopPropagation(); pick(e, step, true); }} onChange={() => {}} />
                    </span>
                  )}
                  <Icon name={isUpdate(r) ? "doc" : "clock"} cls="s pk-hicon" />
                  <div class="pa-body">
                    <p class="pa-meta"><span class="pa-who">{r.who || "Someone on this computer"}</span>{r.how ? <span> · {r.how}</span> : null}<span> · {r.when_text}</span></p>
                    <Change r={r} />
                    {r.from_file ? <p class="muted pa-from-file" data-pa-from-file>{r.from_file}</p> : null}
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
    <section class="pk-activity" role="tabpanel" id="pk-hpanel" aria-labelledby={`pk-htab-${show}`} tabIndex={0} data-activity aria-busy={got ? "false" : "true"} ref={panel}>
      <p class="sr-only" role="status" aria-live="polite" data-pa-live>{phase && phase.kind === "working" ? "Undoing…" : sel.live.value}</p>
      <UndoBar sel={sel} phase={phase} onUndo={preview} onGo={() => go(false)} onSure={() => go(true)} onBack={back} undoBtn={undoBtn} head={head} />
      {body}
      {show === "all" && got && got.ok && got.view.source ? <HistorySource view={got.view} /> : null}
      {got && got.ok && got.view.closing && show !== "updates" ? <p class="muted pa-none">{got.view.closing}</p> : null}
    </section>
  );
}
