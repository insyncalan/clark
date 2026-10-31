// What the Movement block reads from clark (#136): GET /api/movement. Edit only: the published page has no file that names it.
// The change it makes goes through api.js, the one file that names the routes that change things.
import { token } from "../stores/report.js";

const headers = () => ({ "X-Clark-Token": token() });

// {ok: true, view} or {ok: false}: never a throw.
export async function readMovement(code) {
  try {
    const r = await fetch(`/api/movement?project=${encodeURIComponent(code)}`, { headers: headers(), cache: "no-store" });
    const body = await r.json().catch(() => null);
    const v = body && body.movement;
    if (!r.ok || !body || body.ok !== true || !v || !Array.isArray(v.rows)) return { ok: false };
    return { ok: true, view: v };
  } catch (e) {
    return { ok: false };
  }
}
