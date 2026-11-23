// Settings › Version and updates: labelled rows as the prototype draws them (Installed; Update with "Review X.Y.Z" or "Up to date." and
// a hint; Install from a file with Choose zip… and a hint; Last update with Undo update), the Review panel (Install is a second
// click), and Undo update (arm, then confirm). Edit parts only (a published file has no Settings). The server decides and
// checks everything; this draws its answers in plain words (logic/update.js). `api`, `reload`, `sleep` and `copy` are seams for
// the tests; the page passes none of them.
import { useEffect, useRef, useState } from "preact/hooks";
import * as A from "./updateApi.js";
import * as L from "../logic/update.js";
import { classicTheme } from "../components/Contents.jsx";
import { nowMs } from "../workItems.js";   // the one place that reads the clock
import { FormattedAnswer } from "./AskFormat.jsx";   // row 1278: release notes are markdown; drawn by the safe renderer ask clark uses (text nodes only), Copy still gives the original

const REAL = { status: A.updateStatus, review: A.reviewUpdate, install: A.installUpdate, arm: A.armUndo, undo: A.undoUpdate, who: A.whoAnswers,
  check: A.checkUpdate, download: A.downloadUpdate, cancel: A.cancelUpdate };
const realCopy = (t) => navigator.clipboard.writeText(t);

Update.chip = L.TITLE;                                              // the Settings chip says the card's heading (components/Views.jsx)
export function Update({ api = REAL, reload = () => window.location.reload(), sleep = (ms) => new Promise((r) => setTimeout(r, ms)), copy = realCopy, pollMs = 700 }) {
  const [state, setState] = useState({ phase: "loading", st: null, message: "" });
  const [panel, setPanel] = useState(null);           // null, or {id, view, reinstall}
  const opener = useRef("[data-review]");
  const [again, setAgain] = useState(null);           // the source to review again with Install again: "downloads" or "file"
  const [armed, setArmed] = useState(null);           // null, or {id, choice, line}
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const heading = useRef(null);
  const disarm = useRef(null);
  const going = useRef(false);      // set at once by the first Undo click or confirm, cleared when its request settles: busy is a closure value and a second click in the same task still reads false

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

  // The newest-version block (logic/update.js fetchView): while the server looks or downloads, the page asks again every pollMs.
  async function refresh() {
    const r = await api.status();
    if (r.status === 200 && r.body && r.body.ok === true) setState({ phase: "ready", st: L.statusView(r.body), message: "" });
    else setState({ phase: "failed", st: null, message: L.answerWords(r.status, r.body) });
  }
  const fkind = state.st ? state.st.fetch.kind : "none";
  useEffect(() => {
    if (!["looking", "downloading", "checking"].includes(fkind)) return undefined;
    const t = setTimeout(refresh, pollMs);
    return () => clearTimeout(t);
  }, [fkind, state.st]);

  async function fetchCall(call, back) {
    setBusy(true);
    setMsg(null);
    const r = await call();
    if (!(r.status === 200 && r.body && r.body.ok === true)) setMsg({ kind: "error", text: L.answerWords(r.status, r.body) });
    await refresh();
    setBusy(false);
    refocus(back);
  }
  const checkNow = () => fetchCall(api.check, "[data-check]");
  const download = () => fetchCall(api.download, "[data-fetch-cancel]");
  const cancelFetch = (back) => fetchCall(api.cancel, back);
  async function installFetched(id) {
    setBusy(true);
    await restarted(await api.install(id), "[data-fetch-install]");
  }
  useEffect(() => { if (panel && heading.current) heading.current.focus(); }, [panel]);

  const toUndo = () => requestAnimationFrame(() => { const b = document.querySelector("#update [data-undo]"); if (b && (!document.activeElement || document.activeElement === document.body)) b.focus(); });      // the question closed: the focus goes back to Undo update, unless the person has already moved on
  const dropAsk = () => { clearTimeout(disarm.current); setArmed(null); toUndo(); };      // Esc on the question
  useEffect(() => { if (armed) { const b = document.querySelector("#update [data-undo-confirm]"); if (b) b.focus(); } }, [armed]);      // the question opens: the focus moves to its button

  // The focus goes back to a button on the next frame, once Preact has drawn the buttons enabled again after setBusy(false).
  // (Review, Choose and Install are disabled while busy and lose the focus; Undo only says aria-disabled, but takes the same path.)
  const refocus = (sel) => requestAnimationFrame(() => { const b = document.querySelector("#update " + sel); if (b) b.focus(); });
  const closePanel = () => { setPanel(null); refocus(opener.current); };      // Cancel or Esc: the focus goes back to the button that opened the panel

  async function review(from, reinstall) {
    opener.current = from === "file" ? "[data-choose]" : "[data-review]";
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

  async function restarted(r, back) {
    if (r.status === 200 && r.body && r.body.ok === true && r.body.restart === true) {
      setMsg({ kind: "info", text: typeof r.body.message === "string" ? r.body.message.slice(0, 300) : "" });
      const how = await L.waitForRestart(api.who, sleep);
      if (how === "reload") { reload(); return; }
      setBusy(false);
      setMsg({ kind: "error", text: L.SLOW });
      refocus(back);
      return;
    }
    setBusy(false);
    setMsg({ kind: "error", text: L.answerWords(r.status, r.body) });
    refocus(back);
  }

  async function install() {
    setBusy(true);
    const id = panel.id;
    setPanel(null);
    await restarted(await api.install(id), opener.current);
  }

  async function arm() {
    if (going.current) return;
    going.current = true;
    setBusy(true);
    setMsg(null);
    let r;
    try { r = await api.arm(); } finally { going.current = false; }
    setBusy(false);
    if (r.status === 200 && r.body && r.body.ok === true) {
      setArmed({ id: r.body.arm_id, choice: r.body.choice === "full" ? "full" : "app_only", line: String(r.body.line || "").slice(0, 400) });
      clearTimeout(disarm.current);
      disarm.current = setTimeout(() => { setArmed(null); setMsg({ kind: "info", text: L.DISARMED }); toUndo(); }, 5000);
      return;
    }
    setMsg({ kind: "error", text: L.answerWords(r.status, r.body) });
  }

  async function confirmUndo() {
    if (going.current) return;
    going.current = true;
    clearTimeout(disarm.current);
    const a = armed;
    setArmed(null);
    setBusy(true);
    try { await restarted(await api.undo(a.id, a.choice === "app_only"), "[data-undo]"); } finally { going.current = false; }
  }

  async function copyNotes() {
    try { await copy(panel.view.notes); setMsg({ kind: "info", text: L.COPIED }); } catch (e) { setMsg({ kind: "error", text: L.NOT_COPIED }); }
  }

  const st = state.st;
  // The newest version on the releases page, drawn by its kind (logic/update.js fetchView): the words are L.FETCH and L.FETCH_LABELS.
  function fetchBlock(f) {
    const F = L.FETCH, B = L.FETCH_LABELS;
    const btn = (cls, attr, label, fn) => <button type="button" class={"btn " + cls} {...{ [attr]: true }} disabled={busy} onClick={fn}>{label}</button>;
    if (f.kind === "looking") return <p id="update-line">{F.looking}</p>;
    if (f.kind === "latest") return <><p id="update-line">{F.latest(f.version, f.when, L.dayText(new Date(nowMs())))}</p></>;
    if (f.kind === "offline") return <><p id="update-line" class="upd-state">{f.message}</p><div class="row">{btn("", "data-check", B.tryAgain, checkNow)}</div></>;
    if (f.kind === "avail") {
      return (
        <div class="upd-up" id="update-avail">
          <p id="update-line"><b>{F.ready(f.version)}</b></p>
          {L.releasedText(f) ? <p class="muted" id="update-released">{L.releasedText(f)}</p> : null}
          {f.notes ? <details class="update-files"><summary>{F.notesLabel}</summary>{classicTheme() ? <div class="update-notes" id="update-notes"><FormattedAnswer text={f.notes} /></div> : <pre class="update-notes" id="update-notes">{f.notes}</pre>}</details> : null}
          {f.note ? <p class="muted">{f.note}</p> : null}
          <p class="muted" id="update-kept">{L.KEPT}</p>
          <div class="row">{btn("pri", "data-download", B.download, download)}</div>
        </div>
      );
    }
    if (f.kind === "downloading") {
      return (
        <div class="upd-up" id="update-downloading">
          <p id="update-line"><b>{F.downloading(f.version)}</b></p>
          <div class="row"><div class="upd-pg" role="progressbar" aria-label={F.downloading(f.version)} aria-valuenow={f.pct} aria-valuemin="0" aria-valuemax="100"><i style={{ width: f.pct + "%" }} /></div>
            <span class="muted" id="update-pct">{F.progress(f.pct)}</span> {btn("", "data-fetch-cancel", B.cancel, () => cancelFetch("[data-download]"))}</div>
          <p class="muted upd-hint" id="update-hint">{F.downloadingHint}</p>
        </div>
      );
    }
    if (f.kind === "checking") return <div class="upd-up" id="update-checking"><p id="update-line"><b>{F.downloading(f.version)}</b></p><p class="muted upd-hint" id="update-hint">{F.checkingHint}</p></div>;
    if (f.kind === "ready") {
      return (
        <div class="upd-up" id="update-ready">
          <p id="update-line"><b>{F.downloaded(f.version)}</b></p>
          <p class="muted upd-hint" id="update-hint">{F.willChange(f.add, f.replace, f.remove)}</p>
          <div class="row">{btn("pri", "data-fetch-install", B.install, () => installFetched(f.id))} {btn("", "data-fetch-cancel", B.notNow, () => cancelFetch("[data-check]"))}</div>
        </div>
      );
    }
    return (
      <div class="upd-up" id="update-failed">
        <p id="update-line" class="error" role="alert">{f.message || F.didNotFinish}</p>
        <div class="row">{btn("pri", "data-download", B.downloadAgain, download)}</div>
      </div>
    );
  }
  return (
    <section class="frame setting" id="update">
      <h2 id="update-h" tabIndex={-1}>{L.TITLE}</h2>
      <p class="muted">{L.INTRO}</p>
      {state.phase === "loading" ? <p class="muted">{L.LOADING}</p> : null}
      {state.phase === "failed" ? <p class="error" role="alert">{state.message} <button type="button" class="btn sm" data-update-again onClick={load}>{L.LABELS.tryAgain}</button></p> : null}
      {st ? (
        <div class="upd-rows">
          <p class="upd-l" id="update-installed-l">{L.ROWS.installed}</p>
          <div class="upd-c" role="group" aria-labelledby="update-installed-l"><p id="update-installed"><b>{st.installed}</b></p></div>
          <p class="upd-l" id="update-row-l">{st.fetch.kind === "failed" && st.fetch.message === L.FAILED_TEXT ? L.FAILED_TITLE : L.ROWS.update}</p>
          <div class="upd-c" role="group" aria-labelledby="update-row-l" id="update-row">
            {st.blocked ? <p id="update-blocked">{st.blocked}</p> : (
              <>
                {st.fetch.kind !== "none" ? fetchBlock(st.fetch) : null}
                {st.fetch.kind !== "none" || st.review ? null : <p id="update-line">{st.line}</p>}
                {st.fetch.kind !== "none" || (st.review && !st.version) ? null
                  : <p class="muted upd-hint" id="update-hint">{st.review ? L.HINTS.ready(st.version) : L.HINTS.upToDate}</p>}
              </>
            )}
          </div>
          {st.blocked || !["looking", "avail", "latest"].includes(st.fetch.kind) ? null : (
            <>
              <p class="upd-l" id="update-checked-l">{L.ROWS.checked}</p>
              <div class="upd-c" role="group" aria-labelledby="update-checked-l" id="update-checked">
                <p>{L.checkedText(st.fetch.when, L.dayText(new Date(nowMs())))}</p>
                <div class="row">{<button type="button" class="btn" data-check disabled={busy} onClick={checkNow}>{L.FETCH_LABELS.checkNow}</button>}</div>
              </div>
            </>
          )}
          {st.blocked ? null : (
            <>
              <p class="upd-l" id="update-file-l">{L.ROWS.file}</p>
              <div class="upd-c" role="group" aria-labelledby="update-file-l" id="update-file">
                <div class="row">
                  {st.review ? <button type="button" class="btn" data-review aria-label={st.review} aria-describedby="update-file-hint" disabled={busy} onClick={() => review("downloads", false)}>{L.REVIEW_LABEL}</button> : null}
                  <button type="button" class="btn" data-choose aria-describedby="update-file-hint" disabled={busy} onClick={() => review("file", false)}>{L.LABELS.choose}</button>
                  {again ? <button type="button" class="btn" data-install-again disabled={busy} onClick={() => review(again, true)}>{L.LABELS.installAgain}</button> : null}
                </div>
                <p class="muted upd-hint" id="update-file-hint">{L.FILE_TEXT}</p>
              </div>
            </>
          )}
          {st.last ? (
            <>
              <p class="upd-l" id="update-last-l">{st.lastTo ? L.updatedTo(st.lastTo) : L.ROWS.last}</p>
              <div class="upd-c" role="group" aria-labelledby="update-last-l" id="update-last">
                {st.lastTo && st.lastFrom ? <><p>{L.installedText(st.lastFrom)}</p><p class="muted">{st.last}</p></> : <p>{st.last}</p>}
                {armed ? (
                  <div onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); dropAsk(); } }}>
                    <p id="update-armed">{armed.line}</p>
                    <div class="row"><button type="button" class="btn pri" data-undo-confirm aria-describedby="update-armed" aria-disabled={busy ? "true" : undefined} onClick={() => { if (!busy) confirmUndo(); }}>
                      {armed.choice === "full" ? L.LABELS.undoConfirm : L.LABELS.appOnly}</button></div>
                  </div>
                ) : <div class="row"><button type="button" class="btn" data-undo aria-label={L.LABELS.undo} aria-disabled={busy ? "true" : undefined} onClick={() => { if (!busy) arm(); }}>{L.LABELS.undoShown}</button></div>}
              </div>
            </>
          ) : null}
        </div>
      ) : null}
      {panel ? (
        <div class="backup-panel" id="update-panel" role="region" aria-labelledby="update-heading" onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); closePanel(); } }}>
          <p id="update-heading" tabIndex={-1} ref={heading}><b>{panel.view.heading}</b></p>
          {classicTheme() ? <div class="update-notes" id="update-notes"><FormattedAnswer text={panel.view.notes} /></div> : <pre class="update-notes" id="update-notes">{panel.view.notes}</pre>}
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
            <button type="button" class="btn quiet" data-cancel disabled={busy} onClick={closePanel}>{L.LABELS.cancel}</button>
          </div>
        </div>
      ) : null}
      <div class="pub-msg" role="status" aria-live="polite">{msg ? <p class={msg.kind}>{msg.text}</p> : null}</div>
    </section>
  );
}
