// Settings › Quit (item 836): one button that stops clark, so no Terminal is needed to end it. The server answers first and then stops;
// this card only says what happened, in plain words (the server's own when it refused). Edit parts only: a published file has none.
import { useRef, useState } from "preact/hooks";
import { token } from "../stores/report.js";

const STOPPING = "Stopping clark. You can close this window.";
const ASK = "Quit clark now? To start it again, double-click clark.command in the clark folder. With Docker, start it the same way you did before.";
const AGAIN = "To start clark again, double-click clark.command in the clark folder. With Docker, start it the same way you did before.";
const FAILED = "Quitting did not work. Try again.";

// {status, body}: never a throw; a status of 0 is "no answer".
async function quit() {
  try {
    const r = await fetch("/api/quit", { method: "POST", headers: { "X-Clark-Token": token(), "Content-Type": "application/json" }, body: "{}", cache: "no-store" });
    return { status: r.status, body: await r.json().catch(() => null) };
  } catch (e) {
    return { status: 0, body: null };
  }
}

const said = (b) => (b && typeof b.code === "string" && /^[a-z_]+$/.test(b.code) && typeof b.message === "string" && b.message ? b.message : FAILED);

Quit.chip = "Quit";                                         // the Settings chip says the card's heading (components/Views.jsx); an Edit-only name stays out of the published page
export function Quit() {
  const [phase, setPhase] = useState("idle");              // idle | ask | busy | done
  const [msg, setMsg] = useState("");
  const sent = useRef(false);                              // presses before the page redraws all see the same phase; this alone says a request is already out
  function ask() { if (phase === "idle") { setMsg(""); setPhase("ask"); } }
  function cancel() { if (phase === "ask") setPhase("idle"); }
  async function go() {
    if (phase !== "ask" || sent.current) return;
    sent.current = true;
    setPhase("busy");
    setMsg("");
    const r = await quit();
    if (r.status === 200 && r.body && r.body.ok === true) { setPhase("done"); setMsg(STOPPING + " " + AGAIN); return; }
    sent.current = false;
    setMsg(said(r.body));
    setPhase("idle");
  }
  return (
    <section class="frame setting" id="quit">
      <h2 id="quit-h" tabIndex={-1}>Quit</h2>
      <p class="muted">Quit clark when you have finished. Nothing is left running.</p>
      <div class="row">
        {phase === "ask" ? (
          <div>
            <p role="alert">{ASK}</p>
            <button type="button" class="btn" id="quit-yes" onClick={go}>Quit clark</button>
            <button type="button" class="btn" id="quit-no" onClick={cancel}>Cancel</button>
          </div>
        ) : <button type="button" class="btn" onClick={ask} disabled={phase !== "idle"}>Quit clark</button>}
      </div>
      <div class="pub-msg" role="status" aria-live="polite">{msg ? <p class={phase === "done" ? "note" : "error"}>{msg}</p> : null}</div>
    </section>
  );
}
