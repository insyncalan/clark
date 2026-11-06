// The ask panel's connection check (row 858). The server's check runs the Claude Code helper and can take up to 15 s, so it is
// asked once and kept for this page session: a second open within CHECK_KEEP_MS does not ask again, and a second open while the
// first check is still out shares its answer. Only a good "ready" answer is kept (a signed-out or failed one is asked again, so
// signing in elsewhere is noticed on the next open). Five minutes: long enough that a working session asks once, short enough
// that a helper signed out meanwhile is noticed; a question is checked again by the server anyway. Settings calls forgetCheck()
// whenever it changes the connection, the model or the asking switch, so the next open asks afresh.
import { token } from "../stores/report.js";

export const CHECK_KEEP_MS = 5 * 60 * 1000;
let kept = null;         // { body, at }
let out = null;          // the check in flight: a promise of { status, body }
let gen = 0;             // bumped by forgetCheck(): an answer to an older check is not kept

export function forgetCheck() { kept = null; gen++; }

/** The good "ready" body kept from an earlier open, or null. */
export function keptCheck(now = performance.now()) { return kept && now - kept.at < CHECK_KEEP_MS ? kept.body : null; }

/** Ask the status route (once at a time) and resolve to its body, or null when the check failed. */
export function runCheck() {
  if (out) return out;
  const mine = gen;
  out = (async () => {
    let b = null;
    try {
      const x = await fetch("/api/ask/status", { headers: { "X-Clark-Token": token() }, cache: "no-store" });
      const body = await x.json().catch(() => null);
      b = x.status === 200 ? body : null;
    } catch (e) { b = null; }
    if (b && b.ok === true && b.ask_enabled === true && b.connected === true && mine === gen) kept = { body: b, at: performance.now() };
    return b;
  })().finally(() => { out = null; });
  return out;
}
