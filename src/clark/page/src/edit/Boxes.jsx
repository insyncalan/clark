// Draws the box Settings opened (boxes.js): the project form, Import workbook or the Reset the demo data confirm (#444). Edit only.
import { useState } from "preact/hooks";
import { box, closeBox } from "./boxes.js";
import { Dialog } from "./Dialog.jsx";
import { ProjectForm } from "./ProjectForm.jsx";
import { ImportWorkbook } from "./ImportWorkbook.jsx";
import { demoReset } from "./dataApi.js";
import * as L from "../logic/dataCard.js";

const KEY = "clark-demo-reset-done";

// The sentence the Data card shows once after a reset: kept in sessionStorage across the reload (never anywhere longer), in try/catch
// because storage can be unavailable. Nothing but the sentence is kept.
export function takeResetDone() {
  try { const v = sessionStorage.getItem(KEY); if (v) sessionStorage.removeItem(KEY); return v || ""; } catch (e) { return ""; }
}

function ResetBox({ opener, onClose, api = { reset: demoReset }, reload = () => window.location.reload() }) {
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  async function go() {
    setBusy(true);
    const r = await api.reset();
    if (!r.ok) { setBusy(false); setProblem(r.words); return; }
    try { sessionStorage.setItem(KEY, L.RESET.done); } catch (e) { /* the card then says nothing after the reload */ }
    reload();
  }
  return (
    <Dialog id="reset-box" title={L.RESET.title} onClose={() => { if (!busy) onClose(); }} first="#reset-cancel" opener={opener}
      foot={<><button type="button" class="btn quiet" id="reset-cancel" data-close disabled={busy} onClick={onClose}>{L.IMPORT.cancel}</button><button type="button" class="btn danger" id="reset-go" disabled={busy} onClick={go}>{L.RESET.go}</button></>}>
      <p>{L.RESET.body}</p>
      <p class="error" role="alert" id="reset-problem">{problem}</p>
    </Dialog>
  );
}

export function Boxes() {
  const b = box.value;
  if (!b) return null;
  if (b.kind === "project") return <ProjectForm key="project" {...b.props} onClose={closeBox} />;
  if (b.kind === "import") return <ImportWorkbook key="import" {...b.props} onClose={closeBox} />;
  if (b.kind === "reset") return <ResetBox key="reset" {...b.props} onClose={closeBox} />;
  return null;
}
