// Import workbook (#444), the prototype's two steps (system/prototype/io.js importExcel): say what is read and choose a file, then Check
// the import: the counts, every difference in words with a tick, and Import. Nothing is saved until Import; the server (POST
// /api/excel-import) reads the workbook, compares it with this project by ID and applies the ticked changes as ONE step, which Undo
// this import takes back. The workbook is sent once to be checked and not again. `api` and `read` are seams for the tests.
import { useRef, useState } from "preact/hooks";
import { Dialog } from "./Dialog.jsx";
import { Icon } from "../components/Icon.jsx";
import { checkWorkbook, applyWorkbook, undoWorkbook } from "./dataApi.js";
import * as L from "../logic/dataCard.js";

const T = L.IMPORT;
const MAX_FILE = 25 * 1024 * 1024;                       // clark's own limit (excel.MAX_FILE_BYTES); the server says it again
const SHOWN = 300;                                       // the changes listed with a tick; any more follow what the server takes for "all"

const REAL = { check: checkWorkbook, apply: applyWorkbook, undo: undoWorkbook };
const readBytes = async (file) => new Uint8Array(await file.arrayBuffer());

export function ImportWorkbook({ project, projectName, onClose, onDone, opener, api = REAL, read = readBytes }) {
  const [step, setStep] = useState({ at: "pick" });           // pick | checking | plan | applying | done
  const [problem, setProblem] = useState("");
  const [ticks, setTicks] = useState({});
  const input = useRef(null);

  async function chosen(e) {
    const file = e.currentTarget.files && e.currentTarget.files[0];
    e.currentTarget.value = "";
    if (!file) return;
    setProblem("");
    if (file.size > MAX_FILE) { setProblem(T.tooBig); return; }
    setStep({ at: "checking", file: file.name });
    let data;
    try { data = L.toBase64(await read(file)); } catch (err) { setStep({ at: "pick" }); setProblem(T.readFailed); return; }
    const r = await api.check(project, file.name, data);
    if (!r.ok) { setStep({ at: "pick" }); setProblem(r.words); return; }
    setTicks(L.startTicks(r.body.items));
    setStep({ at: "plan", plan: r.body });
  }

  async function doImport() {
    const p = step.plan;
    const accept = L.acceptedNumbers(p.items, ticks);
    if (!accept.length) return;
    setProblem("");
    setStep({ at: "applying", plan: p });
    const r = await api.apply(project, p.plan, accept, p.unrecorded);
    if (!r.ok) { setStep({ at: "plan", plan: p }); setProblem(r.words); return; }
    onDone(r.body);
    setStep({ at: "done", message: r.body.message, applyId: r.body.apply_id });
  }

  async function undo() {
    const id = step.applyId;
    setProblem("");
    const r = await api.undo(project, id);
    if (!r.ok) { setProblem(r.words); return; }
    onDone(r.body);
    setStep({ at: "undone", message: T.undone });
  }

  const cancel = <button type="button" class="btn quiet" data-close onClick={onClose}>{T.cancel}</button>;
  const fileInput = <input ref={input} type="file" id="import-file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" hidden onChange={chosen} />;

  if (step.at === "pick" || step.at === "checking") {
    return (
      <Dialog key="pick" id="import-box" opener={opener} title={T.pickTitle} onClose={onClose} first="#import-choose"
        foot={<>{cancel}<button type="button" class="btn pri gb" id="import-choose" disabled={step.at === "checking"} onClick={() => input.current && input.current.click()}><Icon name="ul" />{T.choose}</button></>}>
        <p>{T.pickBody}</p>
        {step.at === "checking" ? <p class="muted" role="status" id="import-reading">{T.checking}</p> : null}
        <p class="error" role="alert" id="import-problem">{problem}</p>
        {fileInput}
      </Dialog>
    );
  }
  if (step.at === "done" || step.at === "undone") {
    return (
      <Dialog key="done" id="import-box" opener={opener} title={T.checkTitle} onClose={onClose} first="#import-close"
        foot={<>{step.at === "done" && step.applyId ? <button type="button" class="btn quiet" id="import-undo" onClick={undo}>{T.undo}</button> : null}<button type="button" class="btn pri" id="import-close" onClick={onClose}>{T.close}</button></>}>
        <p role="status" id="import-result">{step.message}</p>
        <p class="error" role="alert" id="import-problem">{problem}</p>
      </Dialog>
    );
  }
  const p = step.plan, items = p.items, shown = items.slice(0, SHOWN), count = L.acceptedNumbers(items, ticks).length;
  const empty = p.already_imported || !items.length;
  return (
    <Dialog key="plan" id="import-box" opener={opener} title={T.checkTitle} onClose={onClose} wide first={empty ? "#import-close" : "#import-go"}
      foot={<>{cancel}{empty ? <button type="button" class="btn pri" id="import-close" onClick={onClose}>{T.close}</button>
        : <button type="button" class="btn pri" id="import-go" disabled={!count || step.at === "applying"} onClick={doImport}>{p.unrecorded ? T.anyway : `Import ${count} ${count === 1 ? "change" : "changes"}`}</button>}</>}>
      <p class="muted">{p.file} into {projectName}</p>
      <p id="import-summary"><b>{L.summaryLine(p)}</b></p>
      {p.already_imported ? <p id="import-already">{T.already}</p> : !items.length ? <p id="import-none">{T.none}</p> : null}
      {p.unrecorded && items.length ? <p class="imp-warn" id="import-unrecorded">{T.unrecorded}</p> : null}
      {p.problems.map((t, i) => <p class="imp-note" key={`p${i}`}>Not imported: {t}</p>)}
      {p.notes.map((t, i) => <p class="muted imp-note" key={`n${i}`}>{t}</p>)}
      {empty ? null : (
        <ul class="imp-list" aria-label="Changes in this workbook">
          {shown.map((i) => (
            <li key={i.n} class={i.problem ? "bad" : ""} data-change={i.n}>
              <label>
                <input type="checkbox" checked={!!(Object.prototype.hasOwnProperty.call(ticks, i.n) ? ticks[i.n] : i.default) && !i.problem} disabled={!!i.problem}
                  onChange={(e) => setTicks({ ...ticks, [i.n]: e.currentTarget.checked })} />
                <span class="tag">{L.KIND_WORD[i.kind] || i.kind}</span> <span>{i.text}</span>
              </label>
              {i.detail ? <div class="muted imp-detail">{i.detail}</div> : null}
              {i.clash ? <div class="muted imp-detail">It changed in clark after the workbook was made.</div> : null}
              {i.problem ? <div class="imp-detail error">Would be refused: {i.problem}</div> : null}
            </li>
          ))}
        </ul>
      )}
      {items.length > SHOWN ? <p class="muted">and {items.length - SHOWN} more, taken as the ticks above are for the rest: new and changed rows with no problem.</p> : null}
      <p class="error" role="alert" id="import-problem">{problem}</p>
    </Dialog>
  );
}
