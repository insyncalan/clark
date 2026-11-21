// Settings: asking (#47). The on/off switch and the folders asking may read, for the open project. Edit parts only: a published
// file has no Settings. The switch is askState.js, kept by the server for this computer; the folders are saved by the server too (the
// page asks the server to open the folder window and shows what the server answers, in its words).
import { useEffect, useRef, useState } from "preact/hooks";
import { signal } from "@preact/signals";
import { project } from "../stores/report.js";
import { askOn, askStatus, askSaved, askDocker, askProvider, loadAsk, setAsk, ASK_OFF_LINE, ASK_CHECKING_LINE, ASK_UNAVAILABLE_LINE } from "./askState.js";
import { named, ASK_NOTICE_LINE } from "./askWords.js";
import { ChatsAll, ChatsProject } from "./ChatsSettings.jsx";
import { ConnectorsAll, ConnectorsProject } from "./ConnectorSettings.jsx";
import { AiSettings } from "./AiSettings.jsx";
import { UsageAll, UsageProject } from "./UsageSettings.jsx";
import { AllInstructions, OwnInstructions } from "./AskInstructions.jsx";
import { SlashList } from "./SlashCommandsList.jsx";
import { announceSwitch, leaveSwitch } from "./switchToast.js";
import { classicTheme } from "../components/Contents.jsx";
import { announce, LINKS } from "./indexNote.js";
import { aiConnectRead, askFoldersRead, askFoldersChange, askFoldersChoose, askFoldersAllRead, askFoldersAllChange, askFoldersAllChoose, words } from "./publishApi.js";

const ASK_ON_TOAST = "ask clark is on";
const ASK_OFF_TOAST = "ask clark is off";
const ALL = "all", PROJECT = "project";
const ALL_LINE = "What is the same in every project. A project's own tab shows what belongs to that project.";
const USED_FROM_ALL = "Connections and the model are yours, not this project's. They are the same in every project.";
export const askTab = signal(PROJECT);
export function showAskTab(t) { askTab.value = t === ALL ? ALL : PROJECT; }
const MAX_FOLDERS = 20;
// Changes and safety (row 1294, area 5): four statements about the code, not switches. Each is pinned by tests/test_ask_safety_1294.py.
export const SAFETY = [
  ["Every change needs your approval", "A change can be taken back with Undo, except a decision marked Made, which a new decision replaces."],
  ["A change taken from one of your own files or passages needs an extra tick", "You confirm \u201cI have checked this change and want to save it\u201d first."],
  ["ask clark is never on a published report", "A published file has no ask clark button or panel, and it asks nothing."],
  ["Passwords and keys are never sent", "A question or a file that looks like one is stopped, and you are told."],
];
const SAFETY_NOTE = "These are not switches.";
const ALL_FOLDERS_COUNT = "Counts towards each project's 20.";
const ALL_FOLDERS_NONE = "No folders are set for all projects.";
const NOT_READY = "Choosing folders isn't ready on this computer yet. Asking uses only this project's data until it is.";

// The status line under each folder (Row 1366): the server says what it has read ("Indexing… 42%" then "Indexed ..."). It is asked again
// every 2 seconds while a folder is being read, and for a few more turns after a change, because the read starts just after the folder is saved.
function useIndexLines(read, deps) {
  const [index, setIndex] = useState({});
  const [projects, setProjects] = useState({});
  const [tick, setTick] = useState(0);
  const grace = useRef(0);
  useEffect(() => {
    let live = true, t = null;
    read().then((r) => {
      if (!live) return;
      const ix = r.status === 200 && r.body && r.body.index && typeof r.body.index === "object" ? r.body.index : {};
      setIndex(ix);
      setProjects(r.status === 200 && r.body && r.body.projects && typeof r.body.projects === "object" ? r.body.projects : {});
      const reading = Object.keys(ix).some((k) => ix[k] && ix[k].state === "reading");
      if (reading || grace.current > 0) {
        if (!reading) grace.current -= 1;
        t = setTimeout(() => setTick((n) => n + 1), 2000);
      }
    });
    return () => { live = false; if (t) clearTimeout(t); };
  }, [tick, ...deps]);
  return { index, projects, again: () => { grace.current = 3; setTick((n) => n + 1); } };
}
// The state the server's line stands for, for the screen-reader line (indexNote.js): "Indexing… N%" is reading, "100% indexed..." is done.
function phaseOf(line) {
  const t = line && typeof line.line === "string" ? line.line : "";
  const m = /^Indexing\u2026 (\d+)%$/.exec(t);
  if (m) return { phase: "reading", read: Number(m[1]), total: 100 };
  return t.startsWith("100% indexed") ? { phase: "done", read: 1, total: 1 } : null;
}
// The files left out of a folder (Row 1366 row 6, Classic only): the "(why)" link on the line opens a plain list, name then reason; collapsed by default; the server cuts it at 200 and says how many more.
function leftOf(line) {
  const left = line && line.left && Array.isArray(line.left.files) ? line.left : null;
  return left && left.files.length ? left : null;
}
function LeftOut({ line, id, open }) {
  const left = leftOf(line);
  if (!left || !open) return null;
  return (
    <div class="ask-left-out">
      <ul class="ask-left-list" id={id}>
        {left.files.map((f, i) => <li key={i}><span class="ask-left-name">{f[0]}</span> <span class="ask-left-why">{f[1]}</span></li>)}
        {left.more > 0 ? <li class="ask-left-more">{`and ${left.more} more`}</li> : null}
      </ul>
    </div>
  );
}
// The line is quiet text; the polite live region beside it speaks only at 0, 25, 50, 75 and 100 percent (Row 1371), not at every percent.
// A failed or cleared folder's line ends in the words of its link ("Try again", "Index again"): they are drawn as a button that reads the folder again (row 1371).
const AGAIN = { failed: LINKS.retry, cleared: LINKS.reindex };
function FolderLine({ line, id, onAgain, projects }) {
  const [open, setOpen] = useState(false);
  const prev = useRef(null);
  const said = useRef("");
  const next = phaseOf(line);
  const spoken = announce(prev.current, next);
  if (spoken) said.current = spoken;
  prev.current = next;
  if (!classicTheme()) return null;                  // its rules are the Classic theme's: Cards keeps the card as it was
  const why = leftOf(line) ? <> <button type="button" class="ask-left-btn" aria-expanded={open ? "true" : "false"} aria-controls={id} onClick={() => setOpen(!open)}>{LINKS.why}</button></> : null;
  const word = line ? AGAIN[line.state] : null;
  let text = line ? line.line : "";
  if (line && line.state === "done" && projects && typeof projects.line === "string") text = projects.line;
  const again = word && text.endsWith(word) ? <> <button type="button" class="ask-left-btn" data-ask-index-again onClick={onAgain}>{word}</button></> : null;
  if (again) text = text.slice(0, text.length - word.length).trimEnd();
  return <><div class="ask-folder-line">{text}{again}{why}</div><div class="ask-folder-live" role="status" aria-live="polite">{said.current}</div><LeftOut line={line} id={id} open={open} /></>;
}

// The asking switch's behaviour, shared by this card and the Essentials card (row 1115): `flip` turns asking on or off and says so in the toast
// with its Undo; the switch is disabled while the request runs, so focus is put back once it is not (row 849). The caller owns busy and the message line.
export function useAskFlip(on, busy, setBusy, setMsg) {
  const switchRef = useRef(null);
  const refocus = useRef(false);
  useEffect(() => {
    if (!busy && refocus.current) { refocus.current = false; if (switchRef.current) switchRef.current.focus(); }
  }, [busy]);
  async function flip() {
    const now = !on;
    setBusy(true);
    setMsg(null);
    refocus.current = true;
    const r = await setAsk(now);
    setBusy(false);
    if (!r.ok) setMsg({ kind: "error", text: r.message });
    else {
      if (r.message) setMsg({ kind: "note", text: r.message });
      announceSwitch(now ? ASK_ON_TOAST : ASK_OFF_TOAST, () => setAsk(!now), now ? ASK_OFF_TOAST : ASK_ON_TOAST);
    }
  }
  return { switchRef, flip };
}

function AskProject() {
  const on = askOn.value;
  const status = askStatus.value;
  const saved = askSaved.value;
  const code = project.value;
  const [folders, setFolders] = useState(null);          // null: not read yet; "unavailable"; or the list
  const [shared, setShared] = useState([]);               // the folders for all projects (row 1294), read in this project too
  const [busy, setBusy] = useState(false);
  const [typing, setTyping] = useState(false);       // the server said no window can open here: a box to type the location into
  const [typed, setTyped] = useState("");
  const [msg, setMsg] = useState(null);                  // {kind: "error" | "note", text}: the switch's
  const [fmsg, setFmsg] = useState(null);                // the same, for the folders

  const { switchRef, flip } = useAskFlip(on, busy, setBusy, setMsg);
  const { index, again } = useIndexLines(() => askFoldersRead(code), [code]);
  const reindex = async () => { await askFoldersChange(code, "reindex"); again(); };
  const [modelName, setModelName] = useState("");      // row 1351 part 2: the model asking uses, as the server names it; empty until read or when it cannot be read

  useEffect(() => {
    if (!classicTheme()) return undefined;           // Cards keeps the card as it was: no model name, no extra read
    let live = true;
    aiConnectRead().then((r) => {
      const b = r.body;
      if (!live || r.status !== 200 || !b || !Array.isArray(b.models)) return;
      const m = b.models.find((x) => x.id === b.model);
      setModelName(m ? m.label : "");
    });
    return () => { live = false; };
  }, []);

  useEffect(() => {
    let live = true;
    setFolders(null);
    askFoldersRead(code).then((r) => {
      if (!live) return;
      const b = r.body;
      setFolders(r.status === 200 && b && b.ok === true && Array.isArray(b.folders) ? b.folders : "unavailable");
      setShared(r.status === 200 && b && Array.isArray(b.shared) ? b.shared : []);
    });
    return () => { live = false; };
  }, [code]);

  // The server's own words when it gave some (it never starts with the product's name); otherwise the page's, with a next step.
  function failure(r) {
    const b = r.body;
    if (r.status === 0 || r.status === 403 || (b && typeof b.code === "string")) return words(r, "save that folder");
    return "That folder could not be saved just now. Wait a moment and try again; if it keeps happening, close clark and start it again.";
  }

  // Choose folder and Remove are disabled while the request runs, which drops the focus: put it back once the list is drawn again.
  // After a Remove it goes to the Remove button that took its place, or to Choose folder when none is left.
  function refocusFolders(at) {
    setTimeout(() => {
      const root = document.getElementById("ask-folders-card");
      if (!root) return;
      const rm = root.querySelectorAll("[data-ask-remove]");
      const el = at >= 0 && rm.length ? rm[Math.min(at, rm.length - 1)] : root.querySelector("[data-ask-choose]");
      if (el) el.focus();
    }, 0);
  }

  async function change(action, path) {
    const at = action === "remove" && Array.isArray(folders) ? folders.indexOf(path) : -1;
    setBusy(true);
    setFmsg(null);
    const r = action === "choose" ? await askFoldersChoose(code) : await askFoldersChange(code, action, path);
    setBusy(false);
    const b = r.body;
    if (action !== "add") refocusFolders(at);
    else setTimeout(() => { const i = document.getElementById("ask-folder-path"); if (i) i.focus(); }, 0);   // Add folder is disabled while the request runs: the focus goes to the box
    if (r.status === 200 && b && b.ok === true && Array.isArray(b.folders)) {
      setFolders(b.folders);
      again();
      if (b.message) setFmsg({ kind: "note", text: b.message });
      return true;
    }
    if (b && b.code === "no_window") setTyping(true);
    setFmsg({ kind: "error", text: failure(r) });
  }

  async function addTyped(e) {
    e.preventDefault();
    const path = typed.trim();
    if (!path) return;
    if (await change("add", path)) setTyped("");
  }

  const list = Array.isArray(folders) ? folders : [];
  return (
    <>
    <section class="frame setting" id="ask-settings">
      <h2 id="ask-settings-h" tabIndex={-1}>{`Asking in ${code}`}</h2>
      <p class="muted">{named("Claude is started on this computer for you.", askProvider.value)}</p>
      <p class="muted" id="ask-notice">{named(ASK_NOTICE_LINE, askProvider.value)}</p>
      <p id="ask-state">{status === "loading" ? ASK_CHECKING_LINE : status === "unavailable" ? ASK_UNAVAILABLE_LINE : on ? "Asking is on." : ASK_OFF_LINE}</p>
      {classicTheme() && askDocker.value ? <p class="muted" id="ask-docker" data-ask-docker>{askDocker.value}</p> : null}
      {status === "ready" && !saved ? <p class="muted" id="ask-unsaved">This computer's saved data can't keep this choice yet, so asking stays off. Restart clark to bring the saved data up to date.</p> : null}
      <div class="row">
        <button type="button" class="btn" ref={switchRef} data-ask-switch aria-pressed={on ? "true" : "false"} disabled={busy || status !== "ready"} onClick={flip}>{on ? "Turn off asking" : "Turn on asking"}</button>
      </div>
      <div class="pub-msg" role={msg && msg.kind === "error" ? "alert" : "status"} aria-live="polite">{msg && msg.text ? <p class={msg.kind}>{msg.text}</p> : null}</div>
    </section>
    <section class="frame setting" id="ask-used-all">
      <h2>Used from All projects</h2>
      {classicTheme() ? (
        <>
          <div class="row ask-model">
            <div class="ask-model-text">
              <span class="ask-model-label">Model</span>
              <small class="muted ask-model-same">Same for every project.</small>
            </div>
            {modelName ? <b class="ask-model-name" data-ask-model>{modelName}</b> : null}
            <button type="button" class="btn ask-model-change" data-ask-goall onClick={() => showAskTab(ALL)}>Change</button>
          </div>
          <p class="muted ask-model-note">{USED_FROM_ALL}</p>
        </>
      ) : (<>
        <p class="muted">{USED_FROM_ALL}</p>
        <div class="row"><button type="button" class="btn" data-ask-goall onClick={() => showAskTab(ALL)}>Change</button></div>
      </>)}
    </section>
    <ConnectorsProject code={code} />
    <section class="frame setting" id="ask-folders-card">
      <h2>{`Source folders for ${code}`}</h2>
      <p class="muted">{named("Asking may read the files in these folders, as well as this project's own data. It only reads: it never changes a file. Parts of the files in these folders can be sent to Claude, which Anthropic runs, when they help answer a question.", askProvider.value)}</p>
      {folders === "unavailable" ? <p class="muted" id="ask-folders-note">{NOT_READY}</p> : null}
      {folders !== "unavailable" && folders !== null && !list.length ? <p class="muted" id="ask-folders-none">No folders are set. Asking uses only this project's data.</p> : null}
      {shared.length && Array.isArray(folders) ? (
        <ul class="ask-folders" id="ask-folders-shared">
          {shared.map((p, i) => (
            <li key={p}><span class="folder-now">{p}</span> <span class="muted">All projects</span> <button type="button" class="btn sm quiet" data-ask-change-shared onClick={() => showAskTab(ALL)}>Change</button><FolderLine line={index[p]} id={"ask-left-s" + i} onAgain={reindex} /></li>
          ))}
        </ul>
      ) : null}
      {list.length ? (
        <ul class="ask-folders" id="ask-folders">
          {list.map((p, i) => (
            <li key={p}><span class="folder-now">{p}</span> <button type="button" class="btn sm quiet" data-ask-remove={p} disabled={busy} onClick={() => change("remove", p)}>Remove</button><FolderLine line={index[p]} id={"ask-left-o" + i} onAgain={reindex} /></li>
          ))}
        </ul>
      ) : null}
      {Array.isArray(folders) && shared.length + list.length ? <p class="muted" id="ask-folders-count">{shared.length + list.length} of {MAX_FOLDERS}</p> : null}
      {Array.isArray(folders) ? (
        <div class="row">
          <button type="button" class="btn" data-ask-choose disabled={busy} onClick={() => change("choose")}>Choose folder</button>
        </div>
      ) : null}
      {typing && Array.isArray(folders) ? (
        <form class="row" id="ask-folder-form" onSubmit={addTyped}>
          <label for="ask-folder-path">Folder location</label>
          <input id="ask-folder-path" class="grow" type="text" autocomplete="off" spellcheck={false} value={typed} onInput={(e) => setTyped(e.currentTarget.value)} />
          <button type="submit" class="btn" data-ask-add disabled={busy || !typed.trim()}>Add folder</button>
        </form>
      ) : null}
      <div class="pub-msg" role={fmsg && fmsg.kind === "error" ? "alert" : "status"} aria-live="polite">{fmsg && fmsg.text ? <p class={fmsg.kind}>{fmsg.text}</p> : null}</div>
    </section>
    <OwnInstructions goAll={() => showAskTab(ALL)} />
    {classicTheme() ? <UsageProject /> : null}
    {classicTheme() ? <SlashList scope="project" code={code} goAll={() => showAskTab(ALL)} /> : null}
    {classicTheme() ? <ChatsProject /> : null}
    </>
  );
}

// The page's two tabs (row 1294, A8, first slice): "All projects" holds what is the same everywhere (the connections and the model, for now) and the project's
// own tab holds what belongs to this project. One shows at a time. They are two buttons in a group (aria-current names the one shown), so Tab and Enter work and
// the cards stay direct children of the Settings page, where Search settings reads them.
function AllProjects() {
  return (
    <>
    <section class="frame setting" id="ask-all">
      <h2 id="ask-settings-h" tabIndex={-1}>Asking for all projects</h2>
      <p class="muted">{ALL_LINE}</p>
    </section>
    <AiSettings />
    <ConnectorsAll />
    <AllInstructions />
    {classicTheme() ? <SlashList scope="all" code="" /> : null}
    <AllFolders />
    {classicTheme() ? <ChatsAll /> : null}
    {classicTheme() ? <UsageAll /> : null}
    {classicTheme() ? <Safety /> : null}
    </>
  );
}

function Safety() {
  return (
    <section class="frame setting" id="ask-safety">
      <h2>Changes and safety</h2>
      <ul class="ask-safety">
        {SAFETY.map(([title, line]) => (
          <li key={title}><strong>{title}</strong> <span class="muted">Always.</span><br /><span class="muted">{line}</span></li>
        ))}
      </ul>
      <p class="muted">{SAFETY_NOTE}</p>
    </section>
  );
}

// The folders for all projects (row 1294): read in every project and counted towards its 20. The same list, Remove, Choose folder and typed location as a project's own.
// Remove touches no file; the toast's Undo adds the folder back (at the end of the list).
function AllFolders() {
  const [folders, setFolders] = useState(null);          // null: not read yet; "unavailable"; or the list
  const [busy, setBusy] = useState(false);
  const [typing, setTyping] = useState(false);
  const [typed, setTyped] = useState("");
  const [msg, setMsg] = useState(null);
  const code = project.value;
  const { index, projects, again } = useIndexLines(() => askFoldersAllRead(code), [code]);
  const reindex = async () => { await askFoldersChange(code, "reindex"); again(); };

  useEffect(() => {
    let live = true;
    askFoldersAllRead().then((r) => {
      if (!live) return;
      const b = r.body;
      setFolders(r.status === 200 && b && b.ok === true && Array.isArray(b.folders) ? b.folders : "unavailable");
    });
    return () => { live = false; };
  }, []);

  function refocus(at) {
    setTimeout(() => {
      const root = document.getElementById("ask-all-folders");
      if (!root) return;
      const rm = root.querySelectorAll("[data-ask-all-remove]");
      const el = at >= 0 && rm.length ? rm[Math.min(at, rm.length - 1)] : root.querySelector("[data-ask-all-choose]");
      if (el) el.focus();
    }, 0);
  }

  async function change(action, path) {
    const at = action === "remove" && Array.isArray(folders) ? folders.indexOf(path) : -1;
    setBusy(true);
    setMsg(null);
    const r = action === "choose" ? await askFoldersAllChoose() : await askFoldersAllChange(action, path);
    setBusy(false);
    const b = r.body;
    if (action !== "add") refocus(at);
    else setTimeout(() => { const i = document.getElementById("ask-all-folder-path"); if (i) i.focus(); }, 0);
    if (r.status === 200 && b && b.ok === true && Array.isArray(b.folders)) {
      setFolders(b.folders);
      again();
      if (b.message) setMsg({ kind: "note", text: b.message });
      return true;
    }
    if (b && b.code === "no_window") setTyping(true);
    setMsg({ kind: "error", text: r.status === 0 || r.status === 403 || (b && typeof b.code === "string") ? words(r, "save that folder") : "That folder could not be saved just now. Wait a moment and try again; if it keeps happening, close clark and start it again." });
  }

  async function addTyped(e) {
    e.preventDefault();
    const path = typed.trim();
    if (!path) return;
    if (await change("add", path)) setTyped("");
  }

  const list = Array.isArray(folders) ? folders : [];
  return (
    <section class="frame setting" id="ask-all-folders">
      <h2>Source folders for all projects</h2>
      <p class="muted">{ALL_FOLDERS_COUNT}</p>
      {folders === "unavailable" ? <p class="muted" id="ask-all-folders-note">{NOT_READY}</p> : null}
      {folders !== "unavailable" && folders !== null && !list.length ? <p class="muted" id="ask-all-folders-none">{ALL_FOLDERS_NONE}</p> : null}
      {list.length ? (
        <ul class="ask-folders" id="ask-all-folder-list">
          {list.map((p, i) => (
            <li key={p}><span class="folder-now">{p}</span> <button type="button" class="btn sm quiet" data-ask-all-remove={p} disabled={busy} onClick={() => change("remove", p)}>Remove</button><FolderLine line={index[p]} id={"ask-left-a" + i} onAgain={reindex} projects={projects[p]} /></li>
          ))}
        </ul>
      ) : null}
      {Array.isArray(folders) ? (
        <div class="row">
          <button type="button" class="btn" data-ask-all-choose disabled={busy} onClick={() => change("choose")}>Choose folder</button>
        </div>
      ) : null}
      {typing && Array.isArray(folders) ? (
        <form class="row" id="ask-all-folder-form" onSubmit={addTyped}>
          <label for="ask-all-folder-path">Folder location</label>
          <input id="ask-all-folder-path" class="grow" type="text" autocomplete="off" spellcheck={false} value={typed} onInput={(e) => setTyped(e.currentTarget.value)} />
          <button type="submit" class="btn" data-ask-all-add disabled={busy || !typed.trim()}>Add folder</button>
        </form>
      ) : null}
      <div class="pub-msg" role={msg && msg.kind === "error" ? "alert" : "status"} aria-live="polite">{msg && msg.text ? <p class={msg.kind}>{msg.text}</p> : null}</div>
    </section>
  );
}

export function AskSettings() {
  const code = project.value;
  const tab = askTab.value === ALL ? ALL : PROJECT;
  useEffect(() => { loadAsk(true); return leaveSwitch; }, []);      // asked again each time Settings opens, so the page never shows a stale choice; once for the page, not per tab, so a tab change cannot re-read the switch under a click
  return (
    <>
    <div class="ask-tabs" id="ask-tabs" role="group" aria-label="Asking settings for">
      <span class="muted ask-tabs-lab" aria-hidden="true">Settings for</span>
      {[ALL, PROJECT].map((id) => (
        <button type="button" class="ask-tab" key={id} data-ask-tab={id} aria-current={tab === id ? "true" : undefined} onClick={() => showAskTab(id)}>{id === ALL ? "All projects" : code}</button>
      ))}
    </div>
    {tab === ALL ? <AllProjects /> : <AskProject />}
    </>
  );
}
