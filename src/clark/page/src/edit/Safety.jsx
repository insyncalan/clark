// Settings › Safety (#111): the backups, newest first, with Preview and Restore. Edit parts only (a published file has no Settings).
// The server decides and checks everything; this draws its answers in plain words (logic/safety.js). `api` and `reload` are
// seams for the tests; the page passes neither.
import { useEffect, useRef, useState } from "preact/hooks";
import { listBackups, previewBackup, restoreBackup, setCopyFolder } from "./safetyApi.js";
import * as L from "../logic/safety.js";

const REAL = { list: listBackups, preview: previewBackup, restore: restoreBackup, setCopyFolder };

// Copy my backups to (#622): one optional folder, off until a path is saved. Saved by the Save button or Enter (never by leaving the box,
// because saving makes the folder when it isn't there). An empty box turns it off. The server decides; a refusal is shown under the box
// and the box keeps what was typed. The OneDrive folders it found are offered as one-press choices that fill the box.
// `row` (row 1115, Essentials): the box alone, for a setting row that brings the name and the help line; its ids then start with "ess-" so the page never holds one twice.
export function CopyFolder({ list, api, saved, row }) {
  const ix = row ? "ess-safety" : "safety";
  const [typed, setTyped] = useState(list.copy_folder || "");
  const [said, setSaid] = useState(null);                    // null, or {kind: "success" | "error", text}
  const [busy, setBusy] = useState(false);
  async function save() {
    if (busy) return;                                    // not `disabled` while it works: a disabled button drops the keyboard's focus to the page
    setBusy(true);
    setSaid(null);
    const r = await api.setCopyFolder(typed);
    setBusy(false);
    if (r.status === 200 && r.body && r.body.ok === true) {
      setTyped(r.body.folder);
      saved(r.body.folder);
      setSaid({ kind: "success", text: r.body.message });
    } else setSaid({ kind: "error", text: L.answerWords(r.status, r.body) });
  }
  return (
    <div class={row ? "copy-fld" : "fld copy-fld"} id={`${ix}-copy`}>
      {row ? null : <label for="safety-copy-box">{list.copy_label}</label>}
      <input id={`${ix}-copy-box`} type="text" value={typed} autocomplete="off" spellcheck={false} {...{ [row ? "data-ess-copy-folder" : "data-copy-folder"]: "" }} aria-describedby={`${row ? "" : ix + "-copy-line "}${ix}-copy-said`}
        aria-invalid={said && said.kind === "error" ? "true" : undefined}
        onInput={(e) => setTyped(e.currentTarget.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); if (!busy) save(); } }} />
      {row ? null : <small id="safety-copy-line">{list.copy_help}</small>}
      {(list.copy_suggestions || []).map((path) => (
        <button type="button" class="btn quiet sm" {...{ [row ? "data-ess-copy-suggestion" : "data-copy-suggestion"]: "" }} key={path} aria-disabled={busy ? "true" : undefined} onClick={() => { if (!busy) setTyped(path); }}>Use {path}</button>
      ))}
      <div class="row"><button type="button" class="btn sm" {...{ [row ? "data-ess-copy-save" : "data-copy-save"]: "" }} aria-disabled={busy ? "true" : undefined} onClick={save}>{L.LABELS.save}</button></div>
      <div id={`${ix}-copy-said`} role={said && said.kind === "error" ? "alert" : "status"} aria-live="polite">{said ? <p class={said.kind === "error" ? "fld-bad" : "success"}>{said.text}</p> : null}</div>
    </div>
  );
}

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

  // The answer is drawn below the list, so it is brought into view and given focus (a screen reader reads it, the keyboard stays there).
  const panelEl = useRef(null);
  const msgEl = useRef(null);
  const shown = (el) => { if (el) { el.focus({ preventScroll: true }); el.scrollIntoView({ block: "nearest" }); } };
  useEffect(() => { if (panel) shown(panelEl.current); }, [panel && panel.name, panel && panel.confirming]);
  useEffect(() => { if (msg && state.phase === "ready") shown(msgEl.current); }, [msg, state.phase]);

  // Closing the panel hands focus back to the row button that opened it, so the keyboard does not start again from the top.
  const opener = useRef(null);
  const asked = useRef(0);                                   // the newest preview asked for; closing the panel makes a late answer stale
  const closePanel = () => { asked.current += 1; setPanel(null); const el = opener.current; if (el && el.isConnected) el.focus(); };

  async function look(name, confirming, e) {
    if (e && e.currentTarget) opener.current = e.currentTarget;
    const mine = ++asked.current;
    setBusy(true);
    setMsg(null);
    const r = await api.preview(name);
    setBusy(false);
    if (mine !== asked.current) return;
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
      <h2 id="safety-h" tabIndex={-1}>{L.TITLE}</h2>
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
                      <button type="button" class="btn sm" data-preview disabled={busy} onClick={(e) => look(v.name, false, e)}>{L.LABELS.preview}</button>
                      <button type="button" class="btn sm" data-restore disabled={busy} onClick={(e) => look(v.name, true, e)}>{L.LABELS.restore}</button>
                    </span>
                  </li>
                );
              })}
            </ul>
          ) : <p class="muted">{L.NONE_SHOWN}</p>}
          <p class="keep"><b>{list.keep_label}:</b> <span class="num" id="safety-keep">{list.keep}</span></p>
          <p class="muted">{list.keep_help}</p>
          {list.copy_warning ? <p class="error" id="safety-copy-warning" role="alert">{list.copy_warning}</p> : null}
          <CopyFolder list={list} api={api} saved={(folder) => setState((s) => ({ ...s, list: { ...s.list, copy_folder: folder, copy_warning: null } }))} />
        </>
      ) : null}
      {panel ? (
        <div class="backup-panel" id="backup-panel" role="region" aria-label="Backup preview" tabIndex={-1} ref={panelEl}
             onKeyDown={(e) => { if (e.key === "Escape" && !busy) { e.stopPropagation(); closePanel(); } }}>
          {L.previewLines(panel.preview).map((t) => <p key={t}>{t}</p>)}
          {panel.confirming && L.canRestore(panel.preview) ? (
            <>
              <p><b id="backup-confirm">{L.confirmLine(panel.preview)}</b></p>
              <div class="row">
                <button type="button" class="btn pri" data-put-back disabled={busy} onClick={putBack}>{L.LABELS.putBack}</button>
                <button type="button" class="btn quiet" data-cancel disabled={busy} onClick={closePanel}>{L.LABELS.cancel}</button>
              </div>
            </>
          ) : (
            <div class="row">
              {L.canRestore(panel.preview) ? <button type="button" class="btn" data-restore-from-preview disabled={busy} onClick={() => setPanel({ ...panel, confirming: true })}>{L.LABELS.restore}</button> : null}
              <button type="button" class="btn quiet" data-cancel onClick={closePanel}>{L.LABELS.close}</button>
            </div>
          )}
        </div>
      ) : null}
      <div class="pub-msg" ref={msgEl} tabIndex={-1} role={msg && msg.kind === "error" ? "alert" : "status"} aria-live="polite">{msg ? <p class={msg.kind}>{msg.text}</p> : null}</div>
    </section>
  );
}
