// Settings › Version and updates: what is installed, "Review X.Y.Z" or "Up to date.", Choose zip…, the Review panel (Install is a
// second click), and Undo update (arm, then confirm). Edit parts only (a published file has no Settings). The server decides and
// checks everything; this draws its answers in plain words (logic/update.js). `api`, `reload`, `sleep` and `copy` are seams for
// the tests; the page passes none of them.
import { useEffect, useRef, useState } from "preact/hooks";
import * as A from "./updateApi.js";
import * as L from "../logic/update.js";

const REAL = { status: A.updateStatus, review: A.reviewUpdate, install: A.installUpdate, arm: A.armUndo, undo: A.undoUpdate, who: A.whoAnswers };
const realCopy = (t) => navigator.clipboard.writeText(t);

export function Update({ api = REAL, reload = () => window.location.reload(), sleep = (ms) => new Promise((r) => setTimeout(r, ms)), copy = realCopy }) {
  const [state, setState] = useState({ phase: "loading", st: null, message: "" });
  const [panel, setPanel] = useState(null);           // null, or {id, view, reinstall}
  const [again, setAgain] = useState(null);           // the source to review again with Install again: "downloads" or "file"
  const [armed, setArmed] = useState(null);           // null, or {id, choice, line}
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const heading = useRef(null);
  const disarm = useRef(null);

  async function load() {
    setState((s) => ({ ...s, phase: "loading" }));
    const r = await api.status();
    if (r.status === 200 && r.body && r.body.ok === true) {
      const v = L.statusView(r.body);
      setState({ phase: "ready", st: v, message: "" });
      if (v.notice) setMsg({ kind: "info", text: v.notice });
    } else setState({ phase: "failed", st: null, message: L.answerWords(r.status, r.body) });
  }
  useEffect(() => { load(); return () => clearTimeout(disarm.current); }, []);
  useEffect(() => { if (panel && heading.current) heading.current.focus(); }, [panel]);

  async function review(from, reinstall) {
    setBusy(true);
    setMsg(null);
    setAgain(null);
    setPanel(null);
    const r = await api.review(from, reinstall);
    setBusy(false);
    if (r.status === 200 && r.body && r.body.ok === true && r.body.cancelled) { setMsg({ kind: "info", text: L.CANCELLED }); return; }
    if (r.status === 200 && r.body && r.body.ok === true && r.body.review) {
      setPanel({ id: r.body.review_id, view: L.reviewView(r.body.review), reinstall: !!reinstall });
      return;
    }
    if (r.body && r.body.again === true) setAgain(from);
    setMsg({ kind: "error", text: L.answerWords(r.status, r.body) });
  }

  async function restarted(r) {
    if (r.status === 200 && r.body && r.body.ok === true && r.body.restart === true) {
      setMsg({ kind: "info", text: typeof r.body.message === "string" ? r.body.message.slice(0, 300) : "" });
      const how = await L.waitForRestart(api.who, sleep);
      if (how === "reload") { reload(); return; }
      setBusy(false);
      setMsg({ kind: "error", text: L.SLOW });
      return;
    }
    setBusy(false);
    setMsg({ kind: "error", text: L.answerWords(r.status, r.body) });
  }

  async function install() {
    setBusy(true);
    const id = panel.id;
    setPanel(null);
    await restarted(await api.install(id));
  }

  async function arm() {
    setBusy(true);
    setMsg(null);
    const r = await api.arm();
    setBusy(false);
    if (r.status === 200 && r.body && r.body.ok === true) {
      setArmed({ id: r.body.arm_id, choice: r.body.choice === "full" ? "full" : "app_only", line: String(r.body.line || "").slice(0, 400) });
      clearTimeout(disarm.current);
      disarm.current = setTimeout(() => { setArmed(null); setMsg({ kind: "info", text: L.DISARMED }); }, 5000);
      return;
    }
    setMsg({ kind: "error", text: L.answerWords(r.status, r.body) });
  }

  async function confirmUndo() {
    clearTimeout(disarm.current);
    const a = armed;
    setArmed(null);
    setBusy(true);
    await restarted(await api.undo(a.id, a.choice === "app_only"));
  }

  async function copyNotes() {
    try { await copy(panel.view.notes); setMsg({ kind: "info", text: L.COPIED }); } catch (e) { setMsg({ kind: "error", text: L.NOT_COPIED }); }
  }

  const st = state.st;
  return (
    <section class="frame setting" id="update">
      <h2>{L.TITLE}</h2>
      <p class="muted">{L.INTRO}</p>
      {state.phase === "loading" ? <p class="muted">{L.LOADING}</p> : null}
      {state.phase === "failed" ? <p class="error">{state.message} <button type="button" class="btn sm" data-update-again onClick={load}>{L.LABELS.tryAgain}</button></p> : null}
      {st ? (
        <>
          <p id="update-installed"><b>{st.installed}</b></p>
          {st.blocked ? <p id="update-blocked">{st.blocked}</p> : (
            <div class="row">
              {st.review ? <button type="button" class="btn pri" data-review disabled={busy} onClick={() => review("downloads", false)}>{st.review}</button>
                : <p id="update-line" class="muted">{st.line}</p>}
              <button type="button" class="btn" data-choose disabled={busy} onClick={() => review("file", false)}>{L.LABELS.choose}</button>
              {again ? <button type="button" class="btn" data-install-again disabled={busy} onClick={() => review(again, true)}>{L.LABELS.installAgain}</button> : null}
            </div>
          )}
          {st.last ? (
            <div class="row" id="update-last">
              <p class="muted">{st.last}</p>
              {armed ? (
                <>
                  <p id="update-armed">{armed.line}</p>
                  <button type="button" class="btn pri" data-undo-confirm disabled={busy} onClick={confirmUndo}>
                    {armed.choice === "full" ? L.LABELS.undoConfirm : L.LABELS.appOnly}</button>
                </>
              ) : <button type="button" class="btn" data-undo disabled={busy} onClick={arm}>{L.LABELS.undo}</button>}
            </div>
          ) : null}
        </>
      ) : null}
      {panel ? (
        <div class="backup-panel" id="update-panel" role="region" aria-labelledby="update-heading">
          <p id="update-heading" tabIndex={-1} ref={heading}><b>{panel.view.heading}</b></p>
          <pre class="update-notes" id="update-notes">{panel.view.notes}</pre>
          {panel.view.hasNotes ? <div class="row"><button type="button" class="btn sm" data-copy onClick={copyNotes}>{L.LABELS.copy}</button></div> : null}
          {panel.view.byHand ? <p>{panel.view.byHand}</p> : null}
          <details class="update-files">
            <summary>{L.LABELS.files}</summary>
            {panel.view.lists.map((l) => (
              <div key={l.label}>
                <p><b>{l.label}</b></p>
                {l.names.length ? <ul class="plain">{l.names.map((n) => <li key={n}>{n}</li>)}</ul> : null}
              </div>
            ))}
          </details>
          <p class="muted update-sum">{panel.view.checksum}</p>
          <p>{panel.view.kept}</p>
          <div class="row">
            <button type="button" class="btn pri" data-install disabled={busy} onClick={install}>{panel.reinstall ? L.LABELS.installAgain : L.LABELS.install}</button>
            <button type="button" class="btn quiet" data-cancel disabled={busy} onClick={() => setPanel(null)}>{L.LABELS.cancel}</button>
          </div>
        </div>
      ) : null}
      <div class="pub-msg" role="status" aria-live="polite">{msg ? <p class={msg.kind}>{msg.text}</p> : null}</div>
    </section>
  );
}
