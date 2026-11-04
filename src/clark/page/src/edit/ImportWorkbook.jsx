// Import workbook (item 444), the prototype's two steps (system/prototype/io.js importExcel): say what is read and choose a file, then Check
// the import: the counts, every difference in words with a tick, and Import. Nothing is saved until Import; the server (POST
// /api/excel-import) reads the workbook, compares it with this project by ID and applies the ticked changes as ONE step, which Undo
// this import takes back. The workbook is sent once to be checked and not again. `api`, `read` and `tpl` (Get the template: GET /api/export?template=1) are seams for the tests.
import { useRef, useState } from "preact/hooks";
import { Dialog } from "./Dialog.jsx";
import { Icon } from "../components/Icon.jsx";
import { templateRequest, saveBlob } from "./publishApi.js";
import { sheetsOfWorkbook, checkWorkbook, applyWorkbook, undoWorkbook } from "./dataApi.js";
import * as L from "../logic/dataCard.js";

const T = L.IMPORT;
const MAX_FILE = 25 * 1024 * 1024;                       // clark's own limit (excel.MAX_FILE_BYTES); the server says it again
const SHOWN = 300;                                       // the changes listed with a tick; any more follow what the server takes for "all"

const REAL = { sheets: sheetsOfWorkbook, check: checkWorkbook, apply: applyWorkbook, undo: undoWorkbook };
const readBytes = async (file) => new Uint8Array(await file.arrayBuffer());

export function ImportWorkbook({ project, projectName, onClose, onDone, opener, api = REAL, read = readBytes, tpl = templateRequest }) {
  const [step, setStep] = useState({ at: "pick" });           // pick | checking | plan | applying | done
  const [problem, setProblem] = useState("");
  const [saved, setSaved] = useState("");                    // the template, once the browser has been asked to save it
  const [ticks, setTicks] = useState({});
  const [sheets, setSheets] = useState({});                  // the sheets the workbook has, ticked or not (item 655)
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
    // Which of the five sheets the workbook has is asked first; only those are offered, ticked as the person last left them (item 655).
    const found = await api.sheets(project, file.name, data);
    if (!found.ok) { setStep({ at: "pick" }); setProblem(found.words); return; }
    const names = Array.isArray(found.body.sheets) ? found.body.sheets : [];
    if (!names.length) { await runCheck(file.name, data, undefined); return; }       // none of the five: the check says so in its own words
    setSheets(L.startSheets(names, L.remembered()));
    setStep({ at: "sheets", file: file.name, data, names });
  }

  async function runCheck(name, data, ticked) {
    setStep({ at: "checking", file: name });
    const r = await api.check(project, name, data, ticked);
    if (!r.ok) { setStep({ at: "pick" }); setProblem(r.words); return; }
    setTicks(L.startTicks(r.body.items));
    setStep({ at: "plan", plan: r.body });
  }

  async function goOn() {
    const chosenSheets = L.ticked(sheets, step.names);
    if (!chosenSheets.length) return;
    L.remember(sheets, step.names);                        // remembered when the check is asked for, not when a box is ticked
    setProblem("");
    await runCheck(step.file, step.data, chosenSheets);
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
  if (step.at === "sheets") {
    const on = L.ticked(sheets, step.names);
    return (
      <Dialog key="sheets" id="import-box" opener={opener} title={T.pickTitle} onClose={onClose} first="#import-check"
        foot={<>{cancel}<button type="button" class="btn pri" id="import-check" disabled={!on.length} onClick={goOn}>{T.check}</button></>}>
        <p class="muted">{step.file} into {projectName}</p>
        <div class="imp-sheets" id="import-sheets-pick" role="group" aria-labelledby="import-sheets-head">
          <div class="st-bar"><b id="import-sheets-head">{T.sheetsHead}</b><span><button type="button" class="link" id="import-sheets-all" onClick={() => setSheets(L.startSheets(step.names, {}))}>{T.selectAll}</button> · <button type="button" class="link" id="import-sheets-clear" onClick={() => setSheets({})}>{T.clear}</button></span></div>
          <div class="imp-sheet-list">{step.names.map((n) => <label key={n}><input type="checkbox" name="import-sheet" value={n} checked={!!sheets[n]} onChange={(e) => setSheets({ ...sheets, [n]: e.currentTarget.checked })} /> {n}</label>)}</div>
          {on.length ? null : <p class="muted" role="status" id="import-no-sheets">{T.noSheets}</p>}
        </div>
        <p class="error" role="alert" id="import-problem">{problem}</p>
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
  const refused = p.refused || [];
  if (refused.length) {                                  // one row that breaks a rule refuses the whole file (the prototype's, io.js)
    const k = refused.length;
    return (
      <Dialog key="refused" id="import-box" opener={opener} title={T.checkTitle} onClose={onClose} first="#import-close"
        foot={<button type="button" class="btn pri" id="import-close" data-close onClick={onClose}>{T.close}</button>}>
        <p class="muted">{p.file} into {projectName}</p>
        <div class="imp-refused" id="import-refused" role="status">
          <b>{L.refusedHead(k)}</b>
          <ul>{refused.map((x, n) => <li key={n}>{x.name}: {x.why}</li>)}</ul>
          <p class="imp-after">{L.refusedFoot(k)}</p>
        </div>
      </Dialog>
    );
  }
  const empty = p.already_imported || !items.length;
  const setAll = (on) => { const t = {}; for (const i of items) t[i.n] = on && !!i.default && !i.problem; setTicks(t); };
  const isOn = (i) => !!(Object.prototype.hasOwnProperty.call(ticks, i.n) ? ticks[i.n] : i.default) && !i.problem;
  return (
    <Dialog key="plan" id="import-box" opener={opener} title={T.checkTitle} onClose={onClose} wide first={empty ? "#import-close" : "#import-go"}
      foot={<>{cancel}{empty ? <button type="button" class="btn pri" id="import-close" onClick={onClose}>{T.close}</button>
        : <button type="button" class="btn pri" id="import-go" disabled={!count || step.at === "applying"} onClick={doImport}>{p.unrecorded ? T.anyway : `Import ${count} ${count === 1 ? "change" : "changes"}`}</button>}</>}>
      <p class="muted">{p.file} into {projectName}</p>
      <div class="stat" id="import-summary">{L.countsRow(p).map(([n, w]) => <span key={w}><b>{n}</b> {w}</span>)}</div>
      <p id="import-sheets">{L.sheetLine(p)}</p>
      {p.already_imported ? <p id="import-already">{T.already}</p> : !items.length ? <p id="import-none">{T.none}</p> : null}
      {p.unrecorded && items.length ? <p class="imp-warn" id="import-unrecorded">{T.unrecorded}</p> : null}
      {p.problems.map((t, i) => <p class="imp-note" key={`p${i}`}>Not imported: {t}</p>)}
      {p.notes.map((t, i) => <p class="muted imp-note" key={`n${i}`}>{t}</p>)}
      {empty ? null : (
        <>
          <div class="st-bar"><span class="muted">{T.changesToCheck}</span><span><button type="button" class="link" id="import-accept-all" onClick={() => setAll(true)}>{T.acceptAll}</button> · <button type="button" class="link" id="import-reject-all" onClick={() => setAll(false)}>{T.rejectAll}</button></span></div>
          <ul class="imp-list" aria-label="Changes in this workbook">
            {shown.map((i) => (
              <li key={i.n} data-change={i.n}>
                <div class="imp-main"><span class="tag">{L.KIND_WORD[i.kind] || i.kind}</span> <span>{i.text}</span></div>
                {i.detail ? <div class="muted imp-detail">{i.detail}</div> : null}
                {i.kind === "removed" ? <div class="muted imp-detail">{T.acceptNote}</div> : null}
                {i.clash ? <div class="muted imp-detail">It changed in clark after the workbook was made.</div> : null}
                <div class="st-act" role="radiogroup" aria-label={i.text}>
                  <label><input type="radio" name={`st${i.n}`} value="1" checked={isOn(i)} onChange={() => setTicks({ ...ticks, [i.n]: true })} />{T.accept}</label>
                  <label><input type="radio" name={`st${i.n}`} value="0" checked={!isOn(i)} onChange={() => setTicks({ ...ticks, [i.n]: false })} />{T.reject}</label>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
      {items.length > SHOWN ? <p class="muted">and {items.length - SHOWN} more, taken as Accept all is for the rest: new and changed rows with no problem.</p> : null}
      <p class="error" role="alert" id="import-problem">{problem}</p>
    </Dialog>
  );
}
