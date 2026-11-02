// Settings: AI (#72, #446). The card has a tile for Claude (Connect or Disconnect), a tile for OpenAI marked Later, the model ask clark is
// to use, and the one status line for the Edit parts' Settings, in the server's own words (GET /api/ai/status). The tiles and the model
// are the server's (GET /api/ai-connect); a server without them leaves the status line alone.
// THE KEY: it is typed in a password box, sent once to the server (which keeps it in the Mac's keychain), and the box is emptied the
// moment it is sent. It is held in no state, no store, no storage and no message, and the server never sends it back: all this page
// ever learns is connected, true or false.
import { useEffect, useRef, useState } from "preact/hooks";
import { token } from "../stores/report.js";
import { realAiClient } from "./aiClient.js";
import { aiConnectRead, aiConnectSend, aiDisconnectSend, aiModelSend, words } from "./publishApi.js";

export const AI_CHECKING_LINE = "Checking whether AI suggestions are on…";
export const AI_LATER_LINE = "AI suggestions come in a later version.";      // the status route answered 404: no AI service in this version
export const AI_UNAVAILABLE_LINE = "AI suggestions are off, because clark could not check just now. Reload the page to try again.";
const client = realAiClient({ token });

const HOWS = [["subscription", "Claude subscription"], ["key", "API key"]];
const HOW_WORDS = { subscription: "Claude subscription", key: "API key" };
const NOT_READ = "The AI choices could not be read just now. Reload the page to try again.";

// What the connect box says: the server's own words for a refusal, else the page's.
const cannot = (r) => words(r, "connect Claude");

function ConnectBox({ onClose, onDone }) {
  const el = useRef(null), key = useRef(null);
  const [how, setHow] = useState("subscription");
  const [said, setSaid] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const dlg = el.current;
    if (dlg && !dlg.open) dlg.showModal();
    return () => { if (key.current) key.current.value = ""; if (dlg && dlg.open) dlg.close(); };
  }, []);
  const wipe = () => { if (key.current) key.current.value = ""; };
  async function submit(e) {
    e.preventDefault();
    if (busy) return;
    const typed = how === "key" ? (key.current ? key.current.value.trim() : "") : undefined;
    wipe();                                                       // gone from the box before the request even starts
    if (how === "key" && !typed) { setSaid("Paste your key first."); return; }
    setBusy(true);
    setSaid("");
    const r = await aiConnectSend(how, typed);
    setBusy(false);
    const b = r.body;
    if (r.status === 200 && b && b.ok === true && b.connected === true) { onDone(b); return; }
    setSaid(r.status === 200 && b && typeof b.message === "string" && b.message ? b.message : cannot(r));
  }
  return (
    <dialog id="ai-connect-dialog" class="dlg" aria-labelledby="ai-connect-title" ref={el} onCancel={(e) => { e.preventDefault(); wipe(); onClose(); }}>
      <form class="dlg-form" onSubmit={submit} autocomplete="off">
        <h2 id="ai-connect-title">Connect Claude</h2>
        <p class="muted dlg-sub">The passages ask clark and the AI menu send go to Claude: they leave this computer and are billed to that account. The key is kept in this Mac's keychain, never in clark's files or backups, and is never shown again.</p>
        <div class="ai-how-pick">
          <span id="ai-how-l">How</span>
          <span class="seg" role="group" aria-labelledby="ai-how-l">
            {HOWS.map(([v, t]) => <button type="button" key={v} data-how={v} aria-pressed={how === v ? "true" : "false"} onClick={() => { setHow(v); setSaid(""); wipe(); }}>{t}</button>)}
          </span>
        </div>
        {how === "key" ? (
          <label class="pub-field" for="ai-key">Key
            <input id="ai-key" ref={key} type="password" autocomplete="off" autocapitalize="off" spellcheck={false} placeholder="Paste your key" />
          </label>
        ) : null}
        <p class="error ai-msg" id="ai-connect-msg" role="alert">{said}</p>
        <div class="dlg-f">
          <button type="button" class="btn quiet" data-ai-cancel onClick={() => { wipe(); onClose(); }}>Cancel</button>
          <button type="submit" class="btn pri" data-ai-go disabled={busy}>Connect</button>
        </div>
      </form>
    </dialog>
  );
}

export function AiSettings() {
  const [shown, setShown] = useState({ state: "loading", line: AI_CHECKING_LINE });
  const [conn, setConn] = useState(null);                  // null: not read; "later": the server has no AI card; "unavailable"; or the server's answer
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);                    // {kind: "error" | "note", text}
  const opener = useRef(null);
  useEffect(() => {
    let live = true;
    client.refresh().then(() => {
      if (!live) return;
      if (client.missing()) return setShown({ state: "later", line: AI_LATER_LINE });
      const line = client.line();
      setShown(line ? { state: client.status(), line } : { state: "unavailable", line: AI_UNAVAILABLE_LINE });
    });
    aiConnectRead().then((r) => {
      if (!live) return;
      const b = r.body;
      setConn(r.status === 404 ? "later" : r.status === 200 && b && b.ok === true && typeof b.connected === "boolean" && Array.isArray(b.models) ? b : "unavailable");
    });
    return () => { live = false; };
  }, []);

  const on = conn && typeof conn === "object";
  const label = (id) => { const m = on && conn.models.find((x) => x.id === id); return m ? m.label : ""; };

  async function disconnect() {
    setBusy(true);
    setMsg(null);
    const r = await aiDisconnectSend();
    setBusy(false);
    const b = r.body;
    if (r.status === 200 && b && b.ok === true && b.connected === false) { setConn(b); setMsg({ kind: "note", text: b.message || "Disconnected." }); return; }
    setMsg({ kind: "error", text: r.status === 409 && b && typeof b.message === "string" ? b.message : words(r, "disconnect Claude") });
  }
  async function choose(id) {
    setBusy(true);
    setMsg(null);
    const r = await aiModelSend(id);
    setBusy(false);
    const b = r.body;
    if (r.status === 200 && b && b.ok === true && typeof b.model === "string") { setConn(b); setMsg({ kind: "note", text: `Asking will use ${label(b.model) || "that model"}.` }); return; }
    setMsg({ kind: "error", text: r.status === 409 && b && typeof b.message === "string" ? b.message : words(r, "save that choice") });
  }
  const done = (b) => { setConn(b); setOpen(false); setMsg({ kind: "note", text: b.message || "Claude connected." }); setTimeout(() => { const d = document.querySelector("[data-ai-disconnect]"); if (d) d.focus(); }, 0); };
  const close = () => { setOpen(false); setTimeout(() => { if (opener.current && opener.current.isConnected) opener.current.focus(); }, 0); };

  return (
    <section class="frame setting" id="ai-settings">
      <h2>AI</h2>
      {on ? (
        <>
        <p class="muted">Sign in to Claude for ask clark and the AI menu: the passages they send go to Claude. OpenAI comes in a later version. Keys stay in this computer's keychain, never in clark's files.</p>
        <div class="ai-provs">
          <div class={`ai-prov${conn.connected ? " on" : ""}`} data-ai-tile="claude">
            <h3>Claude <span class={`tag${conn.connected ? " cl" : ""}`}>{conn.connected ? "Connected" : "Not connected"}</span></h3>
            <p class="muted">Through your Claude subscription (the Claude command) or an API key.</p>
            {conn.connected ? (
              <>
              <p class="ai-how">{HOW_WORDS[conn.how] || "Claude"} · {conn.models.map((m) => m.label).join(", ")}</p>
              <button type="button" class="btn sm" data-ai-disconnect disabled={busy} onClick={disconnect}>Disconnect</button>
              </>
            ) : <button type="button" class="btn pri sm" data-ai-connect ref={opener} disabled={busy} onClick={() => { setMsg(null); setOpen(true); }}>Connect…</button>}
          </div>
          <div class="ai-prov later" data-ai-tile="openai" aria-disabled="true">
            <h3>OpenAI <span class="tag">Later</span></h3>
            <p class="muted">Coming in a later version, with an API key or your ChatGPT sign-in.</p>
          </div>
        </div>
        <div class="fld ai-model">
          <label for="ai-model">Model for ask clark</label>
          <select id="ai-model" disabled={busy || !conn.models.length} value={conn.model} onChange={(e) => choose(e.currentTarget.value)}>
            {conn.models.length ? conn.models.map((m) => <option key={m.id} value={m.id}>{m.label}{m.recommended ? " (recommended)" : ""}</option>) : <option>Connect Claude first</option>}
          </select>
        </div>
        <div class="pub-msg" role={msg && msg.kind === "error" ? "alert" : "status"} aria-live="polite">{msg && msg.text ? <p class={msg.kind}>{msg.text}</p> : null}</div>
        {open ? <ConnectBox onClose={close} onDone={done} /> : null}
        </>
      ) : (
        <p class="muted">{conn === "unavailable" ? NOT_READ : "Suggestions for the text you select in the report. Nothing changes until you accept one."}</p>
      )}
      <p id="ai-state" data-state={shown.state}>{shown.line}</p>
    </section>
  );
}
