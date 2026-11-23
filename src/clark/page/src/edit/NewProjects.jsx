// Settings: asking for new projects and a project's own asking (row 1294, design A8; ruling B of 20-11). The computer-wide switch stays the master; the All projects row is only
// the value a project gets when it is created, and the project's own button turns asking off for that project alone. Asking works only while both are on (ask_service.py).
// Nothing here is kept in the browser: it reads and changes GET and POST /api/ask-new-projects.
import { useEffect, useState } from "preact/hooks";
import { askNewRead, askNewChange, words } from "./publishApi.js";

function useNew(code) {
  const [state, setState] = useState(null);          // null: not read yet; "unavailable"; or {on, off_here}
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [undo, setUndo] = useState(null);            // the step of the last change, for its Undo
  useEffect(() => {
    let live = true;
    setState(null);
    askNewRead(code).then((r) => {
      if (!live) return;
      const b = r.body;
      setState(r.status === 200 && b && b.ok === true && typeof b.on === "boolean" ? { on: b.on, off_here: b.off_here === true } : "unavailable");
    });
    return () => { live = false; };
  }, [code]);
  async function change(body) {
    setBusy(true);
    setMsg(null);
    setUndo(null);
    const r = await askNewChange(body);
    setBusy(false);
    const b = r.body;
    if (r.status === 200 && b && b.ok === true && typeof b.on === "boolean") {
      setState({ on: b.on, off_here: b.off_here === true });
      if (b.apply_id && !body.undo) setUndo(b.apply_id);
    } else setMsg(words(r, "save that choice"));
  }
  return { state, busy, msg, undo, change };
}

function Msg({ msg, undo, busy, change }) {
  return (
    <div class="ask-new-msg" role="alert" aria-live="polite">
      {msg ? <p class="error">{msg}</p> : null}
      {undo ? <p class="muted"><button type="button" class="link" data-new-undo disabled={busy} onClick={() => change({ undo })}>Undo</button></p> : null}
    </div>
  );
}

/** All projects tab: the starting value for projects made from now on. It changes no project that exists. */
export function NewProjectsAll() {
  const { state, busy, msg, undo, change } = useNew(null);
  const ready = state && state !== "unavailable";
  return (
    <div class="ask-new" id="ask-new-all">
      <div class="row">
        <span class="folder-now">Asking for new projects</span> <span class="muted" id="ask-new-line">A project can still turn asking off in its own tab.</span>
        {ready ? <button type="button" class="switch" role="switch" data-new-switch aria-checked={state.on ? "true" : "false"} aria-label="Asking for new projects" disabled={busy} onClick={() => change({ on: !state.on })} /> : null}
      </div>
      <Msg msg={msg} undo={undo} busy={busy} change={change} />
    </div>
  );
}

/** A project's tab: this project's own asking, with the button that turns it off or on for this project only. */
export function AskHere({ code }) {
  const { state, busy, msg, undo, change } = useNew(code);
  const ready = state && state !== "unavailable";
  if (!ready) return null;      // unknown shows nothing here: the computer-wide switch above still says what it says, and the panel fails closed
  return (
    <div class="ask-new" id="ask-new-here">
      <div class="row">
        <span class="folder-now" id="ask-here-state">{`Asking is ${state.off_here ? "off" : "on"} for ${code}.`}</span> <span class="muted">The default for new projects is set under All projects.</span>
        <button type="button" class="btn" data-ask-here aria-pressed={state.off_here ? "false" : "true"} disabled={busy} onClick={() => change({ project: code, off_here: !state.off_here })}>{state.off_here ? "Turn on asking" : "Turn off asking"}</button>
      </div>
      <Msg msg={msg} undo={undo} busy={busy} change={change} />
    </div>
  );
}
