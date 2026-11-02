// Settings: Logs and diagnostics (#110). Normal or Debug, a line on what is never logged, Open folder and Copy diagnostics, and the
// errors of the last 7 days, each in plain words (the server says them; the technical line stays in the report). The report is made by the server and copied as it is; the page never builds or edits it.
import { useState, useEffect } from "preact/hooks";
import { readDiagnostics, saveLevel, openLogFolder, said, LOAD_FAILED, SAVE_FAILED, OPEN_FAILED } from "./diagnosticsApi.js";

const COPY_FAILED = "The text could not be copied. Reload the page and try again.";
const COPIED = "Copied. Paste it into a message to the person who is helping you.";

// Copies `text` to the clipboard; true when it worked. The older way is the fallback for a browser that blocks the new one.
async function copy(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (e) {
    try {
      const box = document.createElement("textarea");
      box.value = text;
      box.setAttribute("readonly", "");
      box.style.position = "fixed";
      box.style.opacity = "0";
      document.body.appendChild(box);
      box.select();
      const ok = document.execCommand("copy");
      box.remove();
      return !!ok;
    } catch (e2) {
      return false;
    }
  }
}

export function Diagnostics() {
  const [info, setInfo] = useState(null);                // {level, notice, errors} once read
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);                  // {kind: "error" | "note", text}

  async function load() {
    const r = await readDiagnostics();
    const b = r.body;
    if (r.status === 200 && b && b.ok === true) { setInfo({ level: b.level, notice: b.notice || "", errors: Array.isArray(b.errors) ? b.errors : [], report: b.report }); return b; }
    setMsg({ kind: "error", text: LOAD_FAILED });
    return null;
  }
  useEffect(() => { load(); }, []);

  async function choose(level) {
    if (busy || (info && info.level === level)) return;
    setBusy(true);
    setMsg(null);
    const r = await saveLevel(level);
    if (r.status === 200 && r.body && r.body.ok === true) await load();
    else setMsg({ kind: "error", text: said(r, SAVE_FAILED) });
    setBusy(false);
  }

  async function openFolder() {
    setBusy(true);
    setMsg(null);
    const r = await openLogFolder();
    if (!(r.status === 200 && r.body && r.body.ok === true)) setMsg({ kind: "error", text: said(r, OPEN_FAILED) });
    setBusy(false);
  }

  async function copyReport() {
    setBusy(true);
    setMsg(null);
    const fresh = await load();                           // the newest errors and lines, not the ones from when the page opened
    if (fresh && typeof fresh.report === "string") setMsg((await copy(fresh.report)) ? { kind: "note", text: COPIED } : { kind: "error", text: COPY_FAILED });
    setBusy(false);
  }

  const level = info && info.level;
  return (
    <section class="frame setting" id="diagnostics">
      <h2>Logs and diagnostics</h2>
      <p class="muted">The log is a short record of what clark does, to help find faults. It never records report text, names, email addresses, notes or anything else you wrote: only counts, times and which part of clark was used. Nothing is sent anywhere.</p>
      <div class="row" role="group" aria-label="Logging detail">
        <button type="button" class={"btn" + (level === "normal" ? " pri" : "")} data-level="normal" aria-pressed={level === "normal"} onClick={() => choose("normal")} disabled={busy || !info}>Normal</button>
        <button type="button" class={"btn" + (level === "debug" ? " pri" : "")} data-level="debug" aria-pressed={level === "debug"} onClick={() => choose("debug")} disabled={busy || !info}>Debug</button>
      </div>
      <p class="muted small">Normal records what happened. Debug adds more detail. Warnings and errors are always recorded.</p>
      {info && info.notice ? <p class="note" id="debug-notice">{info.notice}</p> : null}
      <div class="row">
        <button type="button" class="btn" data-open-log onClick={openFolder} disabled={busy}>Open folder</button>
        <button type="button" class="btn" data-copy-diagnostics onClick={copyReport} disabled={busy}>Copy diagnostics</button>
      </div>
      <div class="pub-msg" role={msg && msg.kind === "error" ? "alert" : "status"} aria-live="polite">{msg && msg.text ? <p class={msg.kind}>{msg.text}</p> : null}</div>
      {info ? <h3>Errors in the last 7 days</h3> : null}
      {info && info.errors.length ? (
        <ul class="plain" id="log-errors">{info.errors.map((e, i) => <li key={i}>Last on {e.last}. Happened {e.count === 1 ? "once" : e.count + " times"}. {e.what} {e.next}</li>)}</ul>
      ) : info ? <p class="muted" id="log-errors">None.</p> : null}
    </section>
  );
}
