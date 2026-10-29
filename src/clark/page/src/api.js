// The page's only way to change anything: POST /api/change and POST /api/undo (#65). No other file names these two routes, so a
// build that leaves this file out (the published page, view.jsx) has no way to change a thing and no mention of them.
// Every reply is turned into plain words here: the page never shows the server's own text, only what plainChange (report.js)
// picks for the status, or for a message it knows.
import { token, plainChange } from "./stores/report.js";

const KIND = "report_sections";

// {ok: true, reply} or {ok: false, message}: never a throw, whatever the network or the server did.
async function post(path, body) {
  try {
    const r = await fetch(path, {
      method: "POST",
      headers: { "X-Clark-Token": token(), "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    const reply = await r.json().catch(() => null);
    if (!r.ok || !reply || reply.ok !== true || !Array.isArray(reply.sections)) return { ok: false, message: plainChange(r.ok ? 500 : r.status, reply) };
    return { ok: true, reply };
  } catch (e) {
    return { ok: false, message: plainChange(0) };
  }
}

// `req` is the change's own parts: op, id, values, changes, before, after, place (see clark/changes.py).
export const sendChange = (project, req) => post("/api/change", { project, kind: KIND, ...req });
export const sendUndo = (project, applyId) => post("/api/undo", { project, apply_id: applyId });
