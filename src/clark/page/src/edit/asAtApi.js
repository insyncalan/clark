// The page's only way to the Dashboard as at a day (item 349): GET /api/as-at. It reads; nothing on the server is changed by it.
import { token } from "../stores/report.js";

// {status, body}: never a throw, whatever the network or the server did. A status of 0 is "no answer".
export async function readAsAt(project, day) {
  try {
    const r = await fetch(`/api/as-at?project=${encodeURIComponent(project)}&date=${encodeURIComponent(day)}`, { headers: { "X-Clark-Token": token() }, cache: "no-store" });
    return { status: r.status, body: await r.json().catch(() => null) };
  } catch (e) {
    return { status: 0, body: null };
  }
}
