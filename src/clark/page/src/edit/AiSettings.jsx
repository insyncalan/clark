// Settings: AI (#54, #446). A tile for Claude with Connect or Disconnect, a tile for OpenAI that says it comes later, and the model asking
// uses. clark holds no key or password: Disconnect only stops clark using the person's own sign-in. Below them, AI suggestions (#72): one status line for the Edit parts' Settings, in the server's own words (GET /api/ai/status): on,
// off, not signed in, or busy. There is one switch for Claude on this computer, the one under Asking; this line only says what it
// means for suggestions. Until the server has answered, or when it cannot, the line says so and AI reads as off.
import { useEffect, useState } from "preact/hooks";
import { token } from "../stores/report.js";
import { realAiClient } from "./aiClient.js";
import { aiConnectRead, aiConnectSend, aiDisconnectSend, aiModelSend, words } from "./publishApi.js";

export const AI_CHECKING_LINE = "Checking whether AI suggestions are on…";
export const AI_LATER_LINE = "AI suggestions come in a later version.";      // the status route answered 404: no AI service in this version
export const AI_UNAVAILABLE_LINE = "AI suggestions are off, because clark could not check just now. Reload the page to try again.";
const client = realAiClient({ token });

function ConnectCard() {
  const [conn, setConn] = useState(null);                // null: not read yet; "later": no route; "unavailable"; or the server's view
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);                  // {kind: "error" | "note", text}
  const [weaker, setWeaker] = useState(null);            // {model, text}: a smaller model asks first
  const readable = (b) => b && b.ok === true && b.claude && Array.isArray(b.models);
  useEffect(() => {
    let live = true;
    aiConnectRead().then((r) => { if (live) setConn(r.status === 404 ? "later" : r.status === 200 && readable(r.body) ? r.body : "unavailable"); });
    return () => { live = false; };
  }, []);
  if (conn === null || conn === "later") return null;
  if (conn === "unavailable") return <p id="ai-connect-state" class="muted">Could not check the AI connection just now. Reload the page to try again.</p>;

  async function send(request, what) {
    setBusy(true);
    setMsg(null);
    const r = await request();
    setBusy(false);
    const b = r.body;
    if (r.status === 200 && readable(b)) { setConn(b); setWeaker(null); setMsg({ kind: "note", text: b.message }); return null; }
    if (r.status === 409 && b && b.code === "weaker" && typeof b.message === "string") return b.message;
    setConn({ ...conn });                                // the drop-down goes back to the model in use
    setMsg({ kind: "error", text: r.status >= 400 && r.status < 500 && b && typeof b.message === "string" ? b.message : words(r, what) });
    return null;
  }
  async function choose(model) {
    const text = await send(() => aiModelSend(model), "save that choice");
    if (text) { setConn({ ...conn }); setWeaker({ model, text }); }
  }
  const c = conn.claude;
  return (
    <>
    <p class="muted">Sign in to Claude for ask clark and the AI menu: the passages they send go to Claude. No password or key is kept.</p>
    <div class="ai-provs">
      <div class={`ai-prov${c.connected ? " on" : ""}`} data-ai-tile="claude">
        <h3>Claude <span class={`tag${c.connected ? " cl" : ""}`}>{c.connected ? "Connected" : "Not connected"}</span></h3>
        <p class="muted">Through your Claude subscription, using the Claude command on this computer.</p>
        {c.why ? <p data-ai-why>{c.why}</p> : null}
        {c.connected
          ? <button type="button" class="btn sm" data-ai-disconnect disabled={busy} onClick={() => send(() => aiDisconnectSend("claude"), "disconnect Claude")}>Disconnect</button>
          : <button type="button" class="btn pri sm" data-ai-connect disabled={busy} onClick={() => send(() => aiConnectSend("claude"), "connect Claude")}>Connect</button>}
      </div>
      <div class="ai-prov later" data-ai-tile="openai">
        <h3>OpenAI <span class="tag">Later</span></h3>
        <p class="muted">Coming soon, through your ChatGPT sign-in.</p>
      </div>
    </div>
    <div class="ai-model">
      <label for="ai-model">Model for ask clark</label>{" "}
      <select id="ai-model" disabled={busy || !conn.models.length} value={conn.model} onChange={(e) => choose(e.currentTarget.value)}>
        {conn.models.length ? conn.models.map((m) => <option key={m.id} value={m.id}>{m.label}{m.recommended ? " (recommended)" : ""}</option>) : <option value="">Connect Claude first</option>}
      </select>
    </div>
    {weaker ? (
      <div class="ai-msg" role="alert" data-ai-weaker>
        <p>{weaker.text}</p>
        <button type="button" class="btn sm" data-ai-accept disabled={busy} onClick={() => send(() => aiModelSend(weaker.model, true), "save that choice")}>Use it anyway</button>{" "}
        <button type="button" class="btn sm" data-ai-keep onClick={() => setWeaker(null)}>Keep the model I have</button>
      </div>
    ) : null}
    <p class={`ai-msg${msg && msg.kind === "error" ? " bad" : ""}`} role="status" data-ai-msg>{msg ? msg.text : ""}</p>
    </>
  );
}

export function AiSettings() {
  const [shown, setShown] = useState({ state: "loading", line: AI_CHECKING_LINE });
  useEffect(() => {
    let live = true;
    client.refresh().then(() => {
      if (!live) return;
      if (client.missing()) return setShown({ state: "later", line: AI_LATER_LINE });
      const line = client.line();
      setShown(line ? { state: client.status(), line } : { state: "unavailable", line: AI_UNAVAILABLE_LINE });
    });
    return () => { live = false; };
  }, []);
  return (
    <section class="frame setting" id="ai-settings">
      <h2>AI</h2>
      <ConnectCard />
      <p class="muted">Suggestions for the text you select in the report. Nothing changes until you accept one.</p>
      <p id="ai-state" data-state={shown.state}>{shown.line}</p>
    </section>
  );
}
