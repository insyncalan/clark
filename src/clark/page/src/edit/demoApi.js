// The demo data banner's two calls (#731): GET /api/demo (is demo data on show) and POST /api/demo/clear. Never a throw.
import { token } from "../stores/report.js";
import { DEMO } from "../logic/demoWords.js";

export async function readDemo() {
  try {
    const r = await fetch("/api/demo", { headers: { "X-Clark-Token": token() }, cache: "no-store" });
    const body = await r.json().catch(() => null);
    return !!(r.ok && body && body.ok === true && body.demo === true);
  } catch (e) {
    return false;
  }
}

// {ok: true} or {ok: false, message}
export async function sendDemoRemove() {
  try {
    const r = await fetch("/api/demo/clear", { method: "POST", headers: { "X-Clark-Token": token(), "Content-Type": "application/json" }, body: "{}", cache: "no-store" });
    const body = await r.json().catch(() => null);
    if (r.ok && body && body.ok === true) return { ok: true };
    const said = body && typeof body.message === "string" && body.message.length <= 400 && r.status === 400 ? body.message : "";
    return { ok: false, message: said || DEMO.failed };
  } catch (e) {
    return { ok: false, message: DEMO.failed };
  }
}
