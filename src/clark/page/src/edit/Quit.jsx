// Settings › Quit (#836): one button that stops clark, so no Terminal is needed to end it. The server answers first and then stops;
// this card only says what happened, in plain words (the server's own when it refused). Edit parts only: a published file has none.
import { useState } from "preact/hooks";
import { token } from "../stores/report.js";

const STOPPING = "clark is stopping. You can close this window.";
const FAILED = "clark could not quit. Try again.";

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
  const [phase, setPhase] = useState("idle");              // idle | busy | done
  const [msg, setMsg] = useState("");
  async function go() {
    if (phase !== "idle") return;
    setPhase("busy");
    setMsg("");
    const r = await quit();
    if (r.status === 200 && r.body && r.body.ok === true) { setPhase("done"); setMsg(STOPPING); return; }
    setMsg(said(r.body));
    setPhase("idle");
  }
  return (
    <section class="frame setting" id="quit">
      <h2 id="quit-h" tabIndex={-1}>Quit</h2>
      <p class="muted">Quit clark when you have finished. Nothing is left running.</p>
      <div class="row">
        <button type="button" class="btn" onClick={go} disabled={phase !== "idle"}>Quit clark</button>
      </div>
      <div class="pub-msg" role="status" aria-live="polite">{msg ? <p class={phase === "done" ? "note" : "error"}>{msg}</p> : null}</div>
    </section>
  );
}
