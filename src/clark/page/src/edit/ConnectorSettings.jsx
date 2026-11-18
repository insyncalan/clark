// Settings: connectors (row 1306, slice C3; design A8). Only the connectors found on this computer are listed, the same list in every project. Each is Off until it is
// turned on for all projects; a project can then turn it off for itself. Read only: the page holds no key and keeps nothing about a connector in project data.
import { useEffect, useState } from "preact/hooks";
import { askConnectorsRead, askConnectorsChange, words } from "./publishApi.js";

export const CONNECTORS_LINE = "Mail, Teams, calendars and SharePoint are used only if you turn that connector on in Settings.";
const READ_ONLY = "A connector is only read from, never changed.";
const NONE = "No connectors were found on this computer.";
const NOT_READY = "Connectors can't be checked just now. None is used until they can be.";      // wording proposed to Jarvis 18-11 20:1x: the first approved sentence said they stay off, which is not true of a saved On
const ALL_NOTE = "Only connectors that are set up on this computer are listed, and the list is the same for every project. Off means clark never asks it anything. On lets ask clark read from it, read only, when your question needs it; each one it used is listed under the answer. A project can turn a connector off for itself in its own tab.";
const PROJECT_NOTE = "Only the connectors that are On for all projects appear here.";

function useConnectors(code) {
  const [list, setList] = useState(null);          // null: not read yet; "unavailable"; or the list
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  useEffect(() => {
    let live = true;
    setList(null);
    askConnectorsRead(code).then((r) => {
      if (!live) return;
      const b = r.body;
      setList(r.status === 200 && b && b.ok === true && Array.isArray(b.connectors) ? b.connectors : "unavailable");
    });
    return () => { live = false; };
  }, [code]);
  async function change(body) {
    setBusy(true);
    setMsg(null);
    const r = await askConnectorsChange(body);
    setBusy(false);
    const b = r.body;
    if (r.status === 200 && b && b.ok === true && Array.isArray(b.connectors)) setList(b.connectors);
    else setMsg(words(r, "save that connector choice"));
  }
  return { list, busy, msg, change };
}

function Msg({ msg }) {
  return <div class="pub-msg" role="alert" aria-live="polite">{msg ? <p class="error">{msg}</p> : null}</div>;
}

/** All projects tab: every connector found, each On or Off for clark. */
export function ConnectorsAll({ code }) {
  const { list, busy, msg, change } = useConnectors(code);
  const found = Array.isArray(list) ? list : [];
  return (
    <section class="frame setting" id="ask-connectors">
      <h2>Other connectors found on this computer</h2>
      <p class="muted" id="ask-connectors-line">{CONNECTORS_LINE}</p>
      <p class="muted" id="ask-connectors-readonly">{READ_ONLY}</p>
      {list === "unavailable" ? <p class="muted" id="ask-connectors-unavailable">{NOT_READY}</p> : null}
      {Array.isArray(list) && !found.length ? <p class="muted" id="ask-connectors-none">{NONE}</p> : null}
      {found.length ? (
        <ul class="ask-folders" id="ask-connectors-list">
          {found.map((c) => (
            <li key={c.id}><span class="folder-now">{c.label}</span> <button type="button" class="btn sm" data-connector={c.id} aria-pressed={c.on ? "true" : "false"} disabled={busy} onClick={() => change({ id: c.id, on: !c.on })}>{c.on ? "On for clark" : "Off for clark"}</button></li>
          ))}
        </ul>
      ) : null}
      <p class="muted" id="ask-connectors-note-all">{ALL_NOTE}</p>
      <Msg msg={msg} />
    </section>
  );
}

/** A project's tab: only the connectors that are On for all projects, each with a turn-off for this project alone. */
export function ConnectorsProject({ code }) {
  const { list, busy, msg, change } = useConnectors(code);
  const on = Array.isArray(list) ? list.filter((c) => c.on) : [];
  return (
    <section class="frame setting" id="ask-connectors-project">
      <h2>{`Connectors in ${code}`}</h2>
      {list === "unavailable" ? <p class="muted" id="ask-connectors-unavailable">{NOT_READY}</p> : null}
      {Array.isArray(list) && !on.length ? <p class="muted" id="ask-connectors-none">No connector is on for all projects.</p> : null}
      {on.length ? (
        <ul class="ask-folders" id="ask-connectors-list">
          {on.map((c) => (
            <li key={c.id}><span class="folder-now">{c.label}</span> <span class="muted">{`On for all projects. Turn it off here for ${code} only.`}</span> <button type="button" class="switch" role="switch" data-connector-here={c.id} aria-checked={c.off_here ? "false" : "true"} aria-label={`Use ${c.label} in ${code}`} disabled={busy} onClick={() => change({ project: code, id: c.id, off_here: !c.off_here })} /></li>
          ))}
        </ul>
      ) : null}
      <p class="muted" id="ask-connectors-note-project">{PROJECT_NOTE}</p>
      <Msg msg={msg} />
    </section>
  );
}
