// Settings › Safety (#111): the backups, newest first, with Preview and Restore. Edit parts only (a published file has no Settings).
// The server decides and checks everything; this draws its answers in plain words (logic/safety.js). `api` and `reload` are
// seams for the tests; the page passes neither.
import { useEffect, useState } from "preact/hooks";
import { listBackups, previewBackup, restoreBackup } from "./safetyApi.js";
import * as L from "../logic/safety.js";

const REAL = { list: listBackups, preview: previewBackup, restore: restoreBackup };

export function Safety({ api = REAL, reload = () => window.location.reload(), store }) {
  const [state, setState] = useState({ phase: "loading", list: null, message: "" });
  const [panel, setPanel] = useState(null);                  // null, or {name, preview, confirming}
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(() => { const d = L.takeDone(store); return d ? { kind: "success", text: d } : null; });

  async function load() {
    setState((s) => ({ ...s, phase: "loading" }));
    const r = await api.list();
    if (r.status === 200 && r.body && r.body.ok === true && Array.isArray(r.body.backups)) setState({ phase: "ready", list: r.body, message: "" });
    else setState({ phase: "failed", list: null, message: L.answerWords(r.status, r.body) });
  }
  useEffect(() => { load(); }, []);

  async function look(name, confirming) {
    setBusy(true);
    setMsg(null);
    const r = await api.preview(name);
    setBusy(false);
    if (r.status === 200 && r.body && r.body.ok === true) setPanel({ name, preview: r.body, confirming });
    else { setPanel(null); setMsg({ kind: "error", text: L.answerWords(r.status, r.body) }); }
  }

  async function putBack() {
    const p = panel.preview;
    setBusy(true);
    const r = await api.restore(panel.name, p.last_step);
    if (r.status === 200 && r.body && r.body.ok === true) {
      L.rememberDone(r.body.message, store);
      reload();
      return;
    }
    setBusy(false);
    setPanel(null);
    setMsg({ kind: "error", text: L.answerWords(r.status, r.body) });
  }

  const list = state.list;
  return (
    <section class="frame setting" id="safety">
      <h2>{L.TITLE}</h2>
      <p class="muted">{L.INTRO}</p>
      {state.phase === "loading" ? <p class="muted">{L.LOADING}</p> : null}
      {state.phase === "failed" ? <p class="error" role="alert">{state.message} <button type="button" class="btn sm" data-safety-again onClick={load}>{L.LABELS.tryAgain}</button></p> : null}
      {list ? (
        <>
          <p id="safety-status" class={list.newest_ok ? "" : "error"}>{list.status}</p>
          {list.warning ? <p class="error" id="safety-warning" role="alert">{list.warning}</p> : null}
          {list.backups.length ? (
            <ul class="plain backup-list" id="backup-list">
              {list.backups.map((b) => {
                const v = L.rowView(b);
                return (
                  <li key={v.name} data-backup={v.name}>
                    <span class="when num">{v.when}</span> <span class="kind">{v.kind}</span> <span class="muted size">{v.size}</span>
                    <span class="acts">
                      <button type="button" class="btn sm" data-preview disabled={busy} onClick={() => look(v.name, false)}>{L.LABELS.preview}</button>
                      <button type="button" class="btn sm" data-restore disabled={busy} onClick={() => look(v.name, true)}>{L.LABELS.restore}</button>
                    </span>
                  </li>
                );
              })}
            </ul>
          ) : <p class="muted">{L.NONE_SHOWN}</p>}
          <p class="keep"><b>{list.keep_label}:</b> <span class="num" id="safety-keep">{list.keep}</span></p>
          <p class="muted">{list.keep_help}</p>
        </>
      ) : null}
      {panel ? (
        <div class="backup-panel" id="backup-panel" role="region" aria-label="Backup preview">
          {L.previewLines(panel.preview).map((t) => <p key={t}>{t}</p>)}
          {panel.confirming && L.canRestore(panel.preview) ? (
            <>
              <p><b id="backup-confirm">{L.confirmLine(panel.preview)}</b></p>
              <div class="row">
                <button type="button" class="btn pri" data-put-back disabled={busy} onClick={putBack}>{L.LABELS.putBack}</button>
                <button type="button" class="btn quiet" data-cancel disabled={busy} onClick={() => setPanel(null)}>{L.LABELS.cancel}</button>
              </div>
            </>
          ) : (
            <div class="row">
              {L.canRestore(panel.preview) ? <button type="button" class="btn" data-restore-from-preview disabled={busy} onClick={() => setPanel({ ...panel, confirming: true })}>{L.LABELS.restore}</button> : null}
              <button type="button" class="btn quiet" data-cancel onClick={() => setPanel(null)}>{L.LABELS.close}</button>
            </div>
          )}
        </div>
      ) : null}
      <div class="pub-msg" role={msg && msg.kind === "error" ? "alert" : "status"} aria-live="polite">{msg ? <p class={msg.kind}>{msg.text}</p> : null}</div>
    </section>
  );
}
