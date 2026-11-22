// Settings: AI (#54, #446). A tile each for Claude and ChatGPT with Connect or Disconnect, and the model asking
// uses. clark holds no key or password: Disconnect only stops clark using the person's own sign-in.  Below them, AI suggestions (#72): one status line for the Edit parts' Settings, in the server's own words (GET /api/ai/status): on,
// off, not signed in, or busy. There is one switch for Claude on this computer, the one under Asking; this line only says what it
// means for suggestions. Until the server has answered, or when it cannot, the line says so and AI reads as off.
import { useEffect, useLayoutEffect, useRef, useState } from "preact/hooks";
import { token } from "../stores/report.js";
import { realAiClient } from "./aiClient.js";
import { askProvider } from "./askState.js";
import { classicTheme } from "../components/Contents.jsx";
import { aiCancelSend, aiConnectRead, aiConnectSend, aiDisconnectSend, aiModelSend, aiProgressRead, aiTestSend, aiVerifySend, words } from "./publishApi.js";

export const AI_CHECKING_LINE = "Checking whether AI suggestions are on…";
export const AI_LATER_LINE = "AI suggestions come in a later version.";      // the status route answered 404: no AI service in this version
export const AI_UNAVAILABLE_LINE = "AI suggestions are off, because clark could not check just now. Reload the page to try again.";
const client = realAiClient({ token });

export const CONNECTING_LINE = "Connecting…";
export const CONNECTED_LINE = "Connected. Asking can use its models.";
export const TEST_LABEL = "Test the connection";
export const TESTING_LINE = "Testing…";
// Row 1492, Classic only: the approved words of Check again.
export const CHECK_AGAIN_LABEL = "Check again";
export const CANCEL_LABEL = "Cancel";
export const UNCHECKED_LINE = "Signed in, not checked yet";
export const STEP_LINES = [["command", "Checking the command…"], ["signin", "Checking you are signed in…"], ["ask", "Asking for one word…"]];
export const noNetwork = (name) => `${name} could not be reached. Check your internet connection, then press Check again.`;
const TILES = [
  ["claude", "Claude", "Through your Claude subscription, on this computer."],
  ["chatgpt", "ChatGPT", "Through your ChatGPT subscription, using the Codex command on this computer. What you ask goes to OpenAI."],
];

function ConnectCard() {
  const [conn, setConn] = useState(null);                // null: not read yet; "later": no route; "unavailable"; or the server's view
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);                  // {kind: "error" | "note", text}
  const [pending, setPending] = useState("");            // the tile whose switch was just pressed: "Connecting…" shows while the server checks the sign-in
  const [test, setTest] = useState(null);                // null: not run; "running"; or {kind: "error" | "note", lines: [string]}
  const [weaker, setWeaker] = useState(null);            // {model, text}: a smaller model asks first
  const classic = classicTheme();
  const [verifying, setVerifying] = useState("");        // Classic: the tile whose check is running
  const [step, setStep] = useState("command");           // Classic: the step that check is on
  const [fails, setFails] = useState({});                // Classic: tile -> the one fixed sentence of its last failed check
  const back = useRef("");                                // selector of the control to refocus once the card has redrawn
  const busyNow = useRef(false);
  const readable = (b) => b && b.ok === true && b.claude && b.chatgpt && Array.isArray(b.models);
  useEffect(() => { if (conn && conn.active) askProvider.value = conn.active; }, [conn && conn.active]);
  useEffect(() => {
    let live = true;
    aiConnectRead().then((r) => { if (live) setConn(r.status === 404 ? "later" : r.status === 200 && readable(r.body) ? r.body : "unavailable"); });
    return () => { live = false; };
  }, []);
  useEffect(() => {                                       // Classic: back from signing in in Terminal, the tile reads again (the page read once before)
    if (!classic) return undefined;
    const again = () => { if (!busyNow.current) aiConnectRead().then((r) => { if (!busyNow.current && r.status === 200 && readable(r.body)) setConn(r.body); }); };
    window.addEventListener("focus", again);
    return () => window.removeEventListener("focus", again);
  }, [classic]);
  useLayoutEffect(() => {
    if (!back.current) return;
    const el = document.querySelector(back.current);
    back.current = "";
    if (el) el.focus({ preventScroll: true });
  }, [conn, verifying]);
  if (conn === null || conn === "later") return null;
  if (conn === "unavailable") return <p id="ai-connect-state" class="muted">Could not check the AI connection just now. Reload the page to try again.</p>;

  async function send(request, what, again, tile) {
    if (busyNow.current) return null;                  // aria-disabled keeps focus on the control, so the click is ignored here
    busyNow.current = true;
    setPending(tile || "");
    setTest(null);
    back.current = again || "";
    setBusy(true);
    setMsg(null);
    const r = await request();
    busyNow.current = false;
    setBusy(false);
    setPending("");
    const b = r.body;
    if (r.status === 200 && readable(b)) { setConn(b); setWeaker(null); setMsg({ kind: "note", text: b.message }); return null; }
    if (r.status === 409 && b && b.code === "weaker" && typeof b.message === "string") return b.message;
    setConn({ ...conn });                                // the drop-down goes back to the model in use
    setMsg({ kind: "error", text: r.status >= 400 && r.status < 500 && b && typeof b.message === "string" ? b.message : words(r, what) });
    return null;
  }
  async function choose(model) {
    const text = await send(() => aiModelSend(model), "save that choice", "#ai-model");
    if (text) { setConn({ ...conn }); setWeaker({ model, text }); }
  }
  if (classic && conn.docker) return null;              // Docker has no Terminal and no asking: none of these words, steps or buttons are shown there
  async function verify(id, name) {
    if (busyNow.current) return;
    busyNow.current = true;
    setBusy(true);
    setMsg(null);
    setTest(null);
    setWeaker(null);
    setStep("command");
    setVerifying(id);
    back.current = `[data-ai-cancel=${id}]`;
    const poll = setInterval(() => aiProgressRead().then((p) => { const at = p.body && p.body.steps && p.body.steps[id]; if (at) setStep(at); }), 500);
    const r = await aiVerifySend(id);
    clearInterval(poll);
    busyNow.current = false;
    setBusy(false);
    setVerifying("");
    const b = r.body;
    if (r.status === 200 && readable(b)) {
      setFails({ ...fails, [id]: "" });
      back.current = `[data-ai-disconnect=${id}]`;
      setConn(b);
      setMsg({ kind: "note", text: b.message });
      return;
    }
    const text = r.status === 0 ? noNetwork(name) : r.status >= 400 && r.status < 500 && b && typeof b.message === "string" ? b.message : words(r, "check the connection");
    setFails({ ...fails, [id]: text });
    back.current = `[data-ai-check=${id}]`;
    setConn({ ...conn });
  }
  const anyOn = conn.claude.connected || conn.chatgpt.connected;
  async function runTest() {
    if (busyNow.current || !anyOn) return;
    busyNow.current = true;
    setBusy(true);
    setMsg(null);
    setTest("running");
    const r = await aiTestSend();
    busyNow.current = false;
    setBusy(false);
    const b = r.body;
    if (r.status === 200 && b && b.ok === true && Array.isArray(b.results)) {
      setTest({ kind: "note", lines: b.results.map((x) => (x.answered ? `${x.label} answered in ${x.seconds} seconds.` : `${x.label}: ${x.message}`)) });
    } else setTest({ kind: "error", lines: [r.status >= 400 && r.status < 500 && b && typeof b.message === "string" ? b.message : words(r, "test the connection")] });
  }
  return (
    <>
    <p class="muted" data-ai-intro>{conn.intro}</p>
    <div class="ai-provs">
      {TILES.map(([id, name, line]) => {
        const c = conn[id];
        if (classic) {
          const ok = c.connected && c.checked === true, why = fails[id] || c.why, running = verifying === id;
          const toggle = c.connected
            ? <button type="button" class="btn sm" data-ai-disconnect={id} aria-pressed="true" aria-disabled={busy ? "true" : undefined} onClick={() => send(() => aiDisconnectSend(id), `turn off ${name}`, `[data-ai-connect=${id}]`, "")}>Turn off {name}</button>
            : <button type="button" class="btn pri sm" data-ai-connect={id} aria-pressed="false" aria-disabled={busy ? "true" : undefined} onClick={() => verify(id, name)}>Turn on {name}</button>;
          return (
            <div class={`ai-prov${ok ? " on" : ""}`} data-ai-tile={id} key={id}>
              <h3>{name} <span class={`tag${ok ? " cl" : ""}`}>{ok ? "Connected" : "Not connected"}</span></h3>
              <p class="muted">{line}</p>
              {running ? STEP_LINES.slice(0, Math.max(1, STEP_LINES.findIndex((x) => x[0] === step) + 1)).map(([k, words_]) => <p class="muted" data-ai-step={k} role="status" key={k}>{words_}</p>)
                : ok ? <p class="muted" data-ai-status>{c.checked_line}</p> : c.connected ? <p class="muted" data-ai-status>{UNCHECKED_LINE}</p> : null}
              {!running && why ? <p data-ai-why>{why}</p> : null}
              {running
                ? <button type="button" class="btn sm" data-ai-cancel={id} onClick={() => aiCancelSend(id)}>{CANCEL_LABEL}</button>
                : <>{toggle}{!ok && (c.connected || c.why || fails[id]) ? <>{" "}<button type="button" class="btn sm" data-ai-check={id} aria-disabled={busy ? "true" : undefined} onClick={() => verify(id, name)}>{CHECK_AGAIN_LABEL}</button></> : null}</>}
            </div>
          );
        }
        return (
          <div class={`ai-prov${c.connected ? " on" : ""}`} data-ai-tile={id} key={id}>
            <h3>{name} <span class={`tag${c.connected ? " cl" : ""}`}>{c.connected ? "Connected" : "Not connected"}</span></h3>
            <p class="muted">{line}</p>
            {pending === id ? <p data-ai-status role="status">{CONNECTING_LINE}</p> : c.connected ? <p class="muted" data-ai-status>{CONNECTED_LINE}</p> : null}
            {c.why ? <p data-ai-why>{c.why}</p> : null}
            {c.connected
              ? <button type="button" class="btn sm" data-ai-disconnect={id} aria-pressed="true" aria-disabled={busy ? "true" : undefined} onClick={() => send(() => aiDisconnectSend(id), `turn off ${name}`, `[data-ai-connect=${id}]`, "")}>Turn off {name}</button>
              : <button type="button" class="btn pri sm" data-ai-connect={id} aria-pressed="false" aria-disabled={busy ? "true" : undefined} onClick={() => send(() => aiConnectSend(id), `turn on ${name}`, `[data-ai-disconnect=${id}]`, id)}>Turn on {name}</button>}
          </div>
        );
      })}
    </div>
    <div class="row">
      <button type="button" class="btn sm" data-ai-test aria-disabled={busy || !anyOn ? "true" : undefined} onClick={runTest}>{TEST_LABEL}</button>
    </div>
    <div class="ai-msg" data-ai-test-out role={test && test !== "running" && test.kind === "error" ? "alert" : "status"} aria-live="polite">
      {test === "running" ? <p>{TESTING_LINE}</p> : test ? test.lines.map((l, i) => <p key={i} class={test.kind === "error" ? "bad" : undefined}>{l}</p>) : null}
    </div>
    <div class="ai-model">
      <label for="ai-model">Model for ask clark</label>{" "}
      <select id="ai-model" disabled={!conn.models.length} aria-disabled={busy ? "true" : undefined} value={conn.model} onChange={(e) => { if (busy) setConn({ ...conn }); else choose(e.currentTarget.value); }}>
        {conn.models.length ? conn.models.map((m) => <option key={m.id} value={m.id}>{m.label}{m.recommended ? " (recommended)" : ""}</option>) : <option value="">Connect Claude or ChatGPT first</option>}
      </select>
    </div>
    <p class="muted" data-ai-size>{conn.size}</p>
    {weaker ? (
      <div class="ai-msg" role="alert" data-ai-weaker>
        <p>{weaker.text}</p>
        <button type="button" class="btn sm" data-ai-accept aria-disabled={busy ? "true" : undefined} onClick={() => send(() => aiModelSend(weaker.model, true), "save that choice", "#ai-model")}>Use it anyway</button>{" "}
        <button type="button" class="btn sm" data-ai-keep onClick={() => setWeaker(null)}>Keep the model I have</button>
      </div>
    ) : null}
    <p class={`ai-msg${msg && msg.kind === "error" ? " bad" : ""}`} role={msg && msg.kind === "error" ? "alert" : "status"} data-ai-msg>{msg ? msg.text : ""}</p>
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
