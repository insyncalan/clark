// The calls behind Settings › Data and the project forms (item 444): POST /api/excel-import and /api/project. Edit's page only (a
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
// #655: which sheets the workbook has (and their row counts); the server keeps the workbook, named by `file` in the reply.
export const listSheets = (project, name, data) => post("/api/excel-import", { op: "sheets", project, name, data });
// ...then the check of only the ticked sheets (`tables`: "actions", "raid", "decisions", "milestones", "use_cases") of that kept workbook.
export const checkSheets = (project, file, tables) => post("/api/excel-import", { op: "check", project, file, sheets: tables });
export const applyWorkbook = (project, plan, accept, confirm) => post("/api/excel-import", { op: "apply", project, plan, accept, confirm: !!confirm });
export const undoWorkbook = (project, applyId) => post("/api/excel-import", { op: "undo", project, apply_id: applyId });
