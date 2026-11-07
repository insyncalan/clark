// The first-run setup page (row 836, step 5): "Setting up clark", one line per check, Check again and the folder chooser. It draws the
// lines it is given and decides nothing; the server and the doctor do (logic/setup.js). `api.checks` (GET /api/setup/checks, a list of
// {id, status, words}), `api.chooseFolder` (POST /api/setup/folder) and `onReady` (called once every line is ready or advice) are
// seams: the page passes none until the server's setup mode exists, and the tests pass fakes. Not yet reached from the app's entry.
import { useEffect, useRef, useState } from "preact/hooks";
import * as L from "../logic/setup.js";

export function SetupPage({ api, onReady = () => {} }) {
  const [state, setState] = useState({ phase: "loading", lines: [] });   // loading | shown | refused
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const told = useRef(false);
  const live = useRef(true);

  async function load() {
    setState((s) => ({ ...s, phase: "loading" }));
    let lines = null;
    try { lines = L.linesFrom(await api.checks()); } catch (e) { lines = null; }
    if (!live.current) return;
    if (lines === null) { setState({ phase: "refused", lines: [] }); return; }
    setState({ phase: "shown", lines });
    if (L.allReady(lines) && !told.current) { told.current = true; onReady(); }
  }
  useEffect(() => { load(); return () => { live.current = false; }; }, []);

  async function again() { setMsg(null); await load(); }

  async function choose() {
    setBusy(true);
    setMsg(null);
    let r = null;
    try { r = await api.chooseFolder(); } catch (e) { r = null; }
    const a = L.folderAnswer(r);
    if (a.kind === "chosen") await load(); else setMsg({ kind: a.kind === "none" ? "info" : "error", text: a.text });
    setBusy(false);
  }

  const { phase, lines } = state;
  const ready = phase === "shown" && L.allReady(lines);
  return (
    <section class="frame setting" id="setup">
      <h1 id="setup-h">{L.TITLE}</h1>
      <div role="status" aria-live="polite">
        {phase === "loading" ? <p class="muted" id="setup-loading">{L.LOADING}</p> : null}
        {phase === "refused" ? <p class="error" id="setup-refused">{L.REFUSED}</p> : null}
        {ready ? <p id="setup-ready">{L.ALL_READY}</p> : null}
      </div>
      {phase === "shown" ? (
        <div class="upd-rows" id="setup-lines">
          {lines.map((l) => [
            <p class="upd-l" id={`setup-${l.id}-l`} key={`${l.id}-l`}>{l.label}</p>,
            <div class="upd-c" role="group" aria-labelledby={`setup-${l.id}-l`} data-status={l.status} key={l.id}>
              <p class={L.lineClass(l.status)} data-line={l.id}>{l.words}</p>
            </div>,
          ])}
        </div>
      ) : null}
      {msg ? <p class={msg.kind === "error" ? "error" : "muted"} id="setup-msg" role={msg.kind === "error" ? "alert" : "status"}>{msg.text}</p> : null}
      {phase !== "loading" ? (
        <div class="row">
          <button type="button" class="btn pri" data-again disabled={busy} onClick={again}>{L.CHECK_AGAIN}</button>
          {phase === "shown" ? <button type="button" class="btn" data-folder disabled={busy} onClick={choose}>{L.CHOOSE_FOLDER}</button> : null}
        </div>
      ) : null}
    </section>
  );
}
