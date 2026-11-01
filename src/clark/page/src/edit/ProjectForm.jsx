// The project form (#444), the prototype's (system/prototype/views.js C.projectForm): New project (name, short code, client,
// workstreams) and Edit (the code stays, greyed). The code is suggested from the name until it is typed in. The server checks it all
// again and says in words if it will not do (a taken code, a bad name); the box stays open with that line. `api` is a seam for tests.
import { useState } from "preact/hooks";
import { Dialog } from "./Dialog.jsx";
import { saveProject } from "./dataApi.js";
import * as L from "../logic/dataCard.js";

const T = L.PROJECT;

export function ProjectForm({ row, opener, onClose, onSaved, api = { save: saveProject } }) {
  const edit = !!row;
  const [name, setName] = useState(row ? row.name : "");
  const [code, setCode] = useState(row ? row.code : "");
  const [typedCode, setTypedCode] = useState(edit);
  const [client, setClient] = useState(row ? row.clientName : "");
  const [ws, setWs] = useState(row ? row.wsNames.join(", ") : "Delivery");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");

  const onName = (v) => { setName(v); if (!typedCode) setCode(L.suggestCode(v)); };
  async function submit(e) {
    e.preventDefault();
    if (busy) return;
    const req = L.projectRequest(edit ? "edit" : "new", { code, name, client, workstreams: ws });
    if (!edit && !L.CODE_RE.test(req.code)) { setProblem("Use a short code of 3 to 7 letters or digits, starting with a letter."); return; }
    setBusy(true);
    setProblem("");
    const r = await api.save(req);
    setBusy(false);
    if (!r.ok) { setProblem(r.words); return; }
    onSaved(r.body, edit);
  }
  return (
    <Dialog id="project-form" opener={opener} title={edit ? T.editTitle(row.name) : T.newTitle} onClose={onClose} first="#pN" onSubmit={submit}
      foot={<><button type="button" class="btn quiet" data-close onClick={onClose}>{T.cancel}</button><button type="submit" class="btn pri" disabled={busy}>{edit ? T.save : T.create}</button></>}>
      {edit ? null : <p class="muted dlg-note">{T.newNote}</p>}
      <div class="dlg-form">
        <label for="pN">{T.name}</label>
        <input class="dlg-field" id="pN" required value={name} placeholder={T.namePlace} maxLength={120} onInput={(e) => onName(e.currentTarget.value)} />
        <label for="pC">{T.code}</label>
        <input class="dlg-field dlg-code" id="pC" required maxLength={7} pattern="[A-Za-z][A-Za-z0-9]{2,6}" value={code} disabled={edit} placeholder={T.codePlace}
          onInput={(e) => { setTypedCode(true); setCode(e.currentTarget.value); }} />
        <label for="pCl">{T.client}</label>
        <input class="dlg-field" id="pCl" value={client} placeholder={T.clientPlace} maxLength={120} onInput={(e) => setClient(e.currentTarget.value)} />
        <label for="pW">{T.workstreams}</label>
        <input class="dlg-field" id="pW" value={ws} placeholder={T.workstreamsPlace} onInput={(e) => setWs(e.currentTarget.value)} aria-describedby={edit ? "pW-note" : undefined} />
        {edit ? <p class="muted dlg-small" id="pW-note">{T.workstreamsNote}</p> : null}
      </div>
      <p class="error" role="alert" id="project-problem">{problem}</p>
    </Dialog>
  );
}
