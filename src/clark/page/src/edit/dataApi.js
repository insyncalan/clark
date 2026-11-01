// The calls behind Settings › Data and the project forms (#444): POST /api/excel-import, /api/project and /api/demo. Edit's page only (a
// published file has no Settings and asks nothing). Each answers { ok, status, body, words }: never a throw, and `words` is the plain
// sentence to show when it did not work (logic/dataCard.js replyWords). No other file names these routes.
import { token } from "../stores/report.js";
import { replyWords } from "../logic/dataCard.js";

async function post(path, payload) {
  try {
    const r = await fetch(path, { method: "POST", headers: { "X-Clark-Token": token(), "Content-Type": "application/json" }, body: JSON.stringify(payload), cache: "no-store" });
    const body = await r.json().catch(() => null);
    const ok = r.ok && !!body && body.ok === true;
    return { ok, status: r.status, body, words: ok ? "" : replyWords(r.status, body) };
  } catch (e) {
    return { ok: false, status: 0, body: null, words: replyWords(0, null) };
  }
}

export const saveProject = (req) => post("/api/project", req);
export const checkWorkbook = (project, name, data) => post("/api/excel-import", { op: "check", project, name, data });
export const applyWorkbook = (project, plan, accept, confirm) => post("/api/excel-import", { op: "apply", project, plan, accept, confirm: !!confirm });
export const undoWorkbook = (project, applyId) => post("/api/excel-import", { op: "undo", project, apply_id: applyId });
export const demoState = () => post("/api/demo", { op: "state" });
export const demoReset = () => post("/api/demo", { op: "reset" });
