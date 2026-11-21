// Settings: Files for asking (row 1294, design A8; words from the ruling of 20-11, logged in NEW-WORDS). One switch for all projects and, on a project's tab, the project's own
// turn-off. It is real: ask_service.py reads the same two flags again for every question that carries files, and the panel (AskPanel.jsx) shows the paperclip only while both allow.
// There is no Pictures switch: nothing reads a picture yet.
import { useEffect, useState } from "preact/hooks";
import { askFilesRead, askFilesChange, words } from "./publishApi.js";

const FILES_LINE = "Files: text, Markdown and CSV (5 files of 10 MB, for that question only). A project can turn these off for itself.";

function useFiles(code) {
  const [state, setState] = useState(null);          // null: not read yet; "unavailable"; or {on, off_here}
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [undo, setUndo] = useState(null);            // the step of the last change, for its Undo
  useEffect(() => {
    let live = true;
    setState(null);
    askFilesRead(code).then((r) => {
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
    const r = await askFilesChange(body);
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
    <div class="pub-msg" role="alert" aria-live="polite">
      {msg ? <p class="error">{msg}</p> : null}
      {undo ? <p class="muted"><button type="button" class="link" data-files-undo disabled={busy} onClick={() => change({ undo })}>Undo</button></p> : null}
    </div>
  );
}

/** All projects tab: the Files switch for every project. */
export function FilesAll() {
  const { state, busy, msg, undo, change } = useFiles(null);
  const ready = state && state !== "unavailable";
  return (
    <section class="frame setting" id="ask-files-all">
      <h2>Files</h2>
      {state === "unavailable" ? <p class="muted" id="ask-files-unavailable">Files cannot be checked just now. They are checked again when you ask, and none are sent if they are off.</p> : null}
      <p class="muted" id="ask-files-line">{FILES_LINE}</p>
      {ready ? <div class="row"><button type="button" class="switch" role="switch" data-files-switch aria-checked={state.on ? "true" : "false"} aria-label="Files" disabled={busy} onClick={() => change({ on: !state.on })} /></div> : null}
      <Msg msg={msg} undo={undo} busy={busy} change={change} />
    </section>
  );
}

/** A project's tab: the project's own turn-off, shown while Files are on for all projects. */
export function FilesProject({ code }) {
  const { state, busy, msg, undo, change } = useFiles(code);
  const ready = state && state !== "unavailable";
  return (
    <section class="frame setting" id="ask-files-project">
      <h2>{`Files in ${code}`}</h2>
      {state === "unavailable" ? <p class="muted" id="ask-files-unavailable">Files cannot be checked just now. They are checked again when you ask, and none are sent if they are off.</p> : null}
      {ready ? (
        <div class="row">
          <span class="folder-now">Files</span> <span class="muted" id="ask-files-here-line">{state.on ? `On for all projects. Turn it off here for ${code} only.` : "Off for all projects."}</span>
          {state.on ? <button type="button" class="switch" role="switch" data-files-here aria-checked={state.off_here ? "false" : "true"} aria-label={`Files in ${code}`} disabled={busy} onClick={() => change({ project: code, off_here: !state.off_here })} /> : null}
        </div>
      ) : null}
      <Msg msg={msg} undo={undo} busy={busy} change={change} />
    </section>
  );
}
