// What to import (#655): the step between choosing a workbook and Check the import. The sheets the file has among the five clark
// imports, each with its row count, all ticked to start. Only a ticked sheet is read: the server enforces it (excel_import.read_workbook
// `sheets`), this box only says which. Continue is off with no tick.
import { Dialog } from "./Dialog.jsx";
import * as L from "../logic/dataCard.js";

const T = L.IMPORT;

export function SheetChoice({ sheets, ticked, setTicked, opener, onClose, onContinue }) {
  const on = sheets.filter((s) => ticked[s.table]);
  const set = (all) => { const t = {}; for (const s of sheets) t[s.table] = all; setTicked(t); };
  return (
    <Dialog key="sheets" id="import-box" opener={opener} title={T.sheetsTitle} onClose={onClose} first="#import-continue"
      foot={<><button type="button" class="btn quiet" data-close onClick={onClose}>{T.cancel}</button><button type="button" class="btn pri" id="import-continue" disabled={!on.length} onClick={onContinue}>{T.continue}</button></>}>
      <p>{T.sheetsBody}</p>
      <div class="st-bar"><span /><span><button type="button" class="link" id="import-select-all" onClick={() => set(true)}>{T.selectAll}</button> · <button type="button" class="link" id="import-clear" onClick={() => set(false)}>{T.clear}</button></span></div>
      <div role="group" aria-labelledby="import-box-t">
      <ul class="imp-list" id="import-sheet-list">
        {sheets.map((s) => (
          <li key={s.table}><label><input type="checkbox" data-sheet={s.table} checked={!!ticked[s.table]} onChange={(e) => setTicked({ ...ticked, [s.table]: e.currentTarget.checked })} /> {L.sheetWord(s)}</label></li>
        ))}
      </ul>
      </div>
      <p class="muted" role="status" aria-live="polite" id="import-tick-one">{on.length ? "" : T.tickOne}</p>
    </Dialog>
  );
}
