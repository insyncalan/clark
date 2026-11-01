// What the peek's Activity tab reads from clark (#42): GET /api/activity. Edit only: the published page has no file that names it.
import { token } from "../stores/report.js";

// {ok: true, view} or {ok: false} ({ok: false, missing: true} when the item is not in the open data, for example an archived one): never a throw.
export async function readActivity(code, id) {
  try {
    const q = `project=${encodeURIComponent(code)}&item=${encodeURIComponent(id)}`;
    const r = await fetch(`/api/activity?${q}`, { headers: { "X-Clark-Token": token() }, cache: "no-store" });
    const body = await r.json().catch(() => null);
    const v = body && body.activity;
    if (r.status === 404) return { ok: false, missing: true };
    if (!r.ok || !body || body.ok !== true || !v || !Array.isArray(v.rows)) return { ok: false };
    return { ok: true, view: v };
  } catch (e) {
    return { ok: false };
  }
}
