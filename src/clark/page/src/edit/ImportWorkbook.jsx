// Import workbook (#444), the prototype's two steps (system/prototype/io.js importExcel): say what is read and choose a file, then Check
// the import: the counts, every difference in words with Accept / Reject (Accept all · Reject all above the list), and Import. Nothing is saved until Import; the server (POST
// /api/excel-import) reads the workbook, compares it with this project by ID and applies the accepted changes (sent by row number, as before) as ONE step, which Undo
// this import takes back. The workbook is sent once to be checked and not again. `api`, `read` and `tpl` (Get the template: GET /api/export?template=1) are seams for the tests.
import { useRef, useState } from "preact/hooks";
import { Dialog } from "./Dialog.jsx";
import { Icon } from "../components/Icon.jsx";
import { templateRequest, saveBlob } from "./publishApi.js";
import { checkWorkbook, applyWorkbook, undoWorkbook } from "./dataApi.js";
import * as L from "../logic/dataCard.js";

const T = L.IMPORT;
const MAX_FILE = 25 * 1024 * 1024;                       // clark's own limit (excel.MAX_FILE_BYTES); the server says it again
const SHOWN = 300;                                       // the changes listed with Accept / Reject; any more follow what the server takes for "all"

const REAL = { check: checkWorkbook, apply: applyWorkbook, undo: undoWorkbook };
const readBytes = async (file) => new Uint8Array(await file.arrayBuffer());

export function ImportWorkbook({ project, projectName, onClose, onDone, opener, api = REAL, read = readBytes, tpl = templateRequest }) {
  const [step, setStep] = useState({ at: "pick" });           // pick | checking | plan | applying | done
  const [problem, setProblem] = useState("");
  const [saved, setSaved] = useState("");                    // the template, once the browser has been asked to save it
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

  // Get the template: an export's workbook with no rows (the server makes it; the page asks about no project). The browser saves it.
  async function getTemplate() {
    setProblem(""); setSaved("");
    const r = await tpl();
    if (r.status !== 200 || !r.blob) { setProblem(r.status === 0 ? T.notAnswering : r.status === 403 ? T.stale : T.templateFailed); return; }
    setSaved(`${T.templateSaved}, “${saveBlob(r.blob, r.name || "import template.xlsx")}”.`);
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
        foot={<><button type="button" class="btn quiet gb tpl-get" id="import-template" onClick={getTemplate}><Icon name="dl" />{T.template}</button>{cancel}<button type="button" class="btn pri gb" id="import-choose" disabled={step.at === "checking"} onClick={() => input.current && input.current.click()}><Icon name="ul" />{T.choose}</button></>}>
        <p>{T.pickBody}</p>
        <p class="muted">{L.COLUMNS_INTRO}</p>
        <p class="imp-cols" id="import-columns">{L.IMPORT_COLUMNS.map(([sheet, cols]) => <span key={sheet}><b>{sheet}</b> {cols.join(", ")}<br /></span>)}</p>
        {step.at === "checking" ? <p class="muted" role="status" id="import-reading">{T.checking}</p> : null}
        {saved ? <p class="muted" role="status" id="import-template-saved">{saved}</p> : null}
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
        <div class="imp-bar" id="import-bar"><span class="muted">Changes to check</span>
          <span><button type="button" class="link" id="import-accept-all" onClick={() => setTicks(L.startTicks(items))}>Accept all</button> · <button type="button" class="link" id="import-reject-all" onClick={() => setTicks(L.rejectAll(items))}>Reject all</button></span></div>
      )}
      {empty ? null : (
        <ul class="imp-list" aria-label="Changes in this workbook">
          {shown.map((i) => {
            const on = L.isAccepted(i, ticks), name = `import-choice-${i.n}`;
            return (
              <li key={i.n} class={i.problem ? "bad" : ""} data-change={i.n} data-kind={i.kind}>
                <div class="imp-main">
                  <span class={i.kind === "removed" ? "tag" : "tag cl"}>{L.KIND_WORD[i.kind] || i.kind}</span> <span>{i.text}</span>
                  {i.kind === "removed" ? <div class="muted imp-detail imp-archive-note">{T.archiveNote}</div> : null}
                  {i.detail ? <div class="muted imp-detail">{i.detail}</div> : null}
                  {i.clash ? <div class="muted imp-detail">It changed in clark after the workbook was made.</div> : null}
                  {i.problem ? <div class="imp-detail error">Would be refused: {i.problem}</div> : null}
                </div>
                <div class="imp-act" role="radiogroup" aria-label={i.text}>
                  <label><input type="radio" name={name} value="1" checked={on} disabled={!!i.problem} onChange={() => setTicks({ ...ticks, [i.n]: true })} />Accept</label>
                  <label><input type="radio" name={name} value="0" checked={!on} disabled={!!i.problem} onChange={() => setTicks({ ...ticks, [i.n]: false })} />Reject</label>
                </div>
              </li>
            );
          })}
          {p.unchanged ? (
            <li class="imp-same" id="import-unchanged"><div class="imp-main"><span class="tag">{L.NO_CHANGE}</span> <span>{p.unchanged} {p.unchanged === 1 ? "row" : "rows"} in the workbook</span><div class="muted imp-detail">nothing differs</div></div></li>
          ) : null}
        </ul>
      )}
      {items.length > SHOWN ? <p class="muted">and {items.length - SHOWN} more, taken as Accept all takes them: new and changed rows with no problem.</p> : null}
      <p class="error" role="alert" id="import-problem">{problem}</p>
    </Dialog>
  );
}
