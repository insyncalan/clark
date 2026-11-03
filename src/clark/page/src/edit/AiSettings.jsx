// Settings: AI (#72, #446, #54). The card has a tile for Claude (subscription or API key) and a tile for OpenAI (API key; ChatGPT sign-in
// later), each with Connect or Disconnect; the model ask clark is to use, from the connected providers only, the recommended one marked
// (a weaker one asks first); and the one status line for the Edit parts' Settings, in the server's own words (GET /api/ai/status). The
// tiles and the models are the server's (GET /api/ai-connect); a server without them leaves the status line alone.
// THE KEY: it is typed in a password box, sent once to the server (which tests it, then keeps it in the Mac's keychain), and the box is
// emptied the moment it is sent. It is held in no state, no store, no storage and no message, and the server never sends it back: all
// this page ever learns is connected, true or false.
import { useEffect, useRef, useState } from "preact/hooks";
import { token } from "../stores/report.js";
import { realAiClient } from "./aiClient.js";
import { aiConnectRead, aiConnectSend, aiDisconnectSend, aiModelSend, words } from "./publishApi.js";

export const AI_CHECKING_LINE = "Checking whether AI suggestions are on…";
export const AI_LATER_LINE = "AI suggestions come in a later version.";      // the status route answered 404: no AI service in this version
export const AI_UNAVAILABLE_LINE = "AI suggestions are off, because clark could not check just now. Reload the page to try again.";
const client = realAiClient({ token });

const PROVS = [
  ["claude", "Claude", [["subscription", "Claude subscription"], ["key", "API key"]], "Through your Claude subscription (the Claude command) or an API key."],
  ["openai", "OpenAI", [["key", "API key"]], "Through an API key. ChatGPT sign-in comes in a later version."],
];
const HOW_WORDS = { subscription: "Claude subscription", key: "API key" };
const NOT_READ = "The AI choices could not be read just now. Reload the page to try again.";
// PENDING THE OWNER'S RULING (#54 wording): the connect button says "Connect" (PR 343) where creaite's says "Test and connect".
const GO_WORD = "Connect";

function ConnectBox({ prov, note, onClose, onDone }) {
  const [id, name, hows] = prov;
  const el = useRef(null), key = useRef(null);
  const [how, setHow] = useState(hows[0][0]);
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
    setSaid(how === "key" ? `Testing the key with ${name}…` : "");
    const r = await aiConnectSend(id, how, typed);
    setBusy(false);
    const b = r.body;
    if (r.status === 200 && b && b.ok === true && b[id] && b[id].connected === true) { onDone(b); return; }
    setSaid(r.status === 200 && b && typeof b.message === "string" && b.message ? b.message : words(r, `connect ${name}`));
  }
  return (
    <dialog id="ai-connect-dialog" class="dlg" data-provider={id} aria-labelledby="ai-connect-title" ref={el} onCancel={(e) => { e.preventDefault(); wipe(); onClose(); }}>
      <form class="dlg-form" onSubmit={submit} autocomplete="off">
        <h2 id="ai-connect-title">Connect {name}</h2>
        <p class="muted dlg-sub" data-ai-note>{note}</p>
        {hows.length > 1 ? (
          <div class="ai-how-pick">
            <span id="ai-how-l">How</span>
            <span class="seg" role="group" aria-labelledby="ai-how-l">
              {hows.map(([v, t]) => <button type="button" key={v} data-how={v} aria-pressed={how === v ? "true" : "false"} onClick={() => { setHow(v); setSaid(""); wipe(); }}>{t}</button>)}
            </span>
          </div>
        ) : null}
        {how === "key" ? (
          <label class="pub-field" for="ai-key">Key
            <input id="ai-key" ref={key} type="password" autocomplete="off" autocapitalize="off" spellcheck={false} placeholder="Paste your key" />
          </label>
        ) : null}
        <p class="error ai-msg" id="ai-connect-msg" role="alert">{said}</p>
        <div class="dlg-f">
          <button type="button" class="btn quiet" data-ai-cancel onClick={() => { wipe(); onClose(); }}>Cancel</button>
          <button type="submit" class="btn pri" data-ai-go disabled={busy}>{GO_WORD}</button>
        </div>
      </form>
    </dialog>
  );
}

// A weaker model asks first (FR-65): the server's words, then Keep the recommended model or Use it anyway.
function WeakerBox({ text, onKeep, onAccept }) {
  const el = useRef(null);
  useEffect(() => {
    const dlg = el.current;
    if (dlg && !dlg.open) dlg.showModal();
    return () => { if (dlg && dlg.open) dlg.close(); };
  }, []);
  return (
    <dialog id="ai-weaker-dialog" class="dlg" aria-labelledby="ai-weaker-title" aria-describedby="ai-weaker-text" ref={el} onCancel={(e) => { e.preventDefault(); onKeep(); }}>
      <div class="dlg-form">
        <h2 id="ai-weaker-title">Use a weaker model?</h2>
        <p class="muted dlg-sub" id="ai-weaker-text">{text}</p>
        <div class="dlg-f">
          <button type="button" class="btn quiet" data-ai-keep onClick={onKeep}>Keep the recommended model</button>
          <button type="button" class="btn pri" data-ai-anyway onClick={onAccept}>Use it anyway</button>
        </div>
      </div>
    </dialog>
  );
}

const readable = (b) => b && b.ok === true && typeof b.connected === "boolean" && Array.isArray(b.models) && b.claude && b.openai;

export function AiSettings() {
  const [shown, setShown] = useState({ state: "loading", line: AI_CHECKING_LINE });
  const [conn, setConn] = useState(null);                  // null: not read; "later": the server has no AI card; "unavailable"; or the server's answer
  const [open, setOpen] = useState(null);                  // the provider row whose connect box is open
  const [weaker, setWeaker] = useState(null);              // {model, text} while the weaker-model box is open
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
      setConn(r.status === 404 ? "later" : r.status === 200 && readable(r.body) ? r.body : "unavailable");
    });
    return () => { live = false; };
  }, []);

  const on = conn && typeof conn === "object";
  const label = (id) => { const m = on && conn.models.find((x) => x.id === id); return m ? m.label : ""; };

  async function disconnect(id, name) {
    setBusy(true);
    setMsg(null);
    const r = await aiDisconnectSend(id);
    setBusy(false);
    const b = r.body;
    if (r.status === 200 && readable(b) && b[id].connected === false) { setConn(b); setMsg({ kind: "note", text: b.message || "Disconnected." }); return; }
    setMsg({ kind: "error", text: r.status === 409 && b && typeof b.message === "string" ? b.message : words(r, `disconnect ${name}`) });
  }
  async function choose(id, accept) {
    setBusy(true);
    setMsg(null);
    const r = await aiModelSend(id, accept);
    setBusy(false);
    const b = r.body;
    if (r.status === 200 && readable(b) && typeof b.model === "string") { setConn(b); setMsg({ kind: "note", text: `Asking will use ${label(b.model) || "that model"}.` }); return; }
    if (r.status === 409 && b && b.code === "weaker" && typeof b.message === "string") { setWeaker({ model: id, text: b.message }); return; }
    setMsg({ kind: "error", text: r.status === 409 && b && typeof b.message === "string" ? b.message : words(r, "save that choice") });
  }
  const done = (b) => { const id = open && open[0]; setConn(b); setOpen(null); setMsg({ kind: "note", text: b.message || "Connected." }); setTimeout(() => { const d = document.querySelector(`[data-ai-tile=${id}] [data-ai-disconnect]`); if (d) d.focus(); }, 0); };
  const close = () => { setOpen(null); setTimeout(() => { if (opener.current && opener.current.isConnected) opener.current.focus(); }, 0); };
  const keep = () => { setWeaker(null); setConn({ ...conn }); };           // the drop-down goes back to the model in use

  return (
    <section class="frame setting" id="ai-settings">
      <h2>AI</h2>
      {on ? (
        <>
        <p class="muted">Sign in to Claude or OpenAI for ask clark and the AI menu: the passages they send go to the provider you choose. Keys stay in this computer's keychain, never in clark's files.</p>
        <div class="ai-provs">
          {PROVS.map((p) => {
            const [id, name, , line] = p, c = conn[id];
            return (
              <div class={`ai-prov${c.connected ? " on" : ""}`} data-ai-tile={id} key={id}>
                <h3>{name} <span class={`tag${c.connected ? " cl" : ""}`}>{c.connected ? "Connected" : "Not connected"}</span></h3>
                <p class="muted">{line}</p>
                {c.connected ? (
                  <>
                  <p class="ai-how">{HOW_WORDS[c.how] || name} · {conn.models.filter((m) => m.provider === id).map((m) => m.label).join(", ") || "no models"}</p>
                  <button type="button" class="btn sm" data-ai-disconnect disabled={busy} onClick={() => disconnect(id, name)}>Disconnect</button>
                  </>
                ) : <button type="button" class="btn pri sm" data-ai-connect={id} disabled={busy} onClick={(e) => { opener.current = e.currentTarget; setMsg(null); setOpen(p); }}>Connect…</button>}
              </div>
            );
          })}
        </div>
        <div class="fld ai-model">
          <label for="ai-model">Model for ask clark</label>
          <select id="ai-model" disabled={busy || !conn.models.length} value={conn.model} onChange={(e) => choose(e.currentTarget.value, false)}>
            {conn.models.length ? conn.models.map((m) => <option key={m.id} value={m.id}>{m.label}{m.recommended ? " (recommended)" : ""}</option>) : <option>Connect Claude or OpenAI first</option>}
          </select>
        </div>
        <div class="pub-msg" role={msg && msg.kind === "error" ? "alert" : "status"} aria-live="polite">{msg && msg.text ? <p class={msg.kind}>{msg.text}</p> : null}</div>
        {open ? <ConnectBox prov={open} note={conn.note} onClose={close} onDone={done} /> : null}
        {weaker ? <WeakerBox text={weaker.text} onKeep={keep} onAccept={() => { const m = weaker.model; setWeaker(null); choose(m, true); }} /> : null}
        </>
      ) : (
        <p class="muted">{conn === "unavailable" ? NOT_READ : "Suggestions for the text you select in the report. Nothing changes until you accept one."}</p>
      )}
      <p id="ai-state" data-state={shown.state}>{shown.line}</p>
    </section>
  );
}
