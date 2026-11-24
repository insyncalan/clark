// The Add page box (row 1252, Classic only): the Add page button in Settings, Reports asks for it with the window event `clark:add-page` (AddPages.jsx).
// Step 1 "Choose a starter" lists the five starters with their template names; step 2 "Name it" is the page's name (at most 40 letters); a preview beside the
// list (below it at 900) shows the chosen starter's parts with their approved prompt lines. The Gantt starter switches the project's prebuilt Gantt page on; any
// other starter stores one added page with the starter's sections, internal and in the menu after the others. Both are one change with one Undo.
import { useState } from "preact/hooks";
import { change } from "../stores/changes.js";
import { Dialog } from "./Dialog.jsx";
import { STARTERS, TEMPLATES, startSections } from "../logic/templates.js";
import { FIELDS, DEFAULT_NAME, NAME_MAX, nameOf, editorOn, tabName } from "../gantt/ganttTab.js";

export const NAME_LIMIT = 40;
const NAMES = { "work-items": "Work items" };      // the issue and the mock-up call the Work items part by the section's own name
const tname = (id) => NAMES[id] || (TEMPLATES.find((t) => t.id === id) || {}).name || id;

export function AddPageBox({ project, opener, onClose }) {
  const [at, setAt] = useState(0);
  const [typed, setTyped] = useState(null);
  const [busy, setBusy] = useState(false);
  const starter = STARTERS[at], gantt = starter.id === "gantt", ganttOn = editorOn(project);
  const name = (typed === null ? starter.name : typed).replace(/\s+/g, " ").trim();
  const ok = !!name && (!gantt || nameOf(name) !== null);
  const choose = (i) => { if (STARTERS[i].id === "gantt" && ganttOn) return; setAt(i); };
  const submit = async (e) => {
    e.preventDefault();
    if (!ok || busy) return;
    setBusy(true);
    const words = `Added “${name}” to the menu.`;
    const r = gantt
      ? await change({ kind: "projects", op: "update", changes: { [FIELDS.editor]: 1, ...(name !== tabName(project) ? { [FIELDS.name]: name } : {}) }, place: "menu" }, words)
      : await change({ kind: "added_pages", op: "new", values: { name, starter: starter.id, client: 0, hidden: 0, sections: JSON.stringify(startSections(starter.id)) } }, words);
    setBusy(false);
    if (r) onClose();
  };
  return (
    <Dialog id="add-page-box" title="Add page" wide first="#add-page-name" opener={opener} onClose={onClose} onSubmit={submit}
      foot={<><button type="button" class="btn" onClick={onClose}>Cancel</button><button type="submit" class="btn pri" disabled={!ok || busy}>Add page</button></>}>
      <div class="ap-cols">
        <div class="ap-pick">
          <h3 id="ap-step-1">Choose a starter</h3>
          <div role="radiogroup" aria-labelledby="ap-step-1">
            {STARTERS.map((s, i) => {
              const off = s.id === "gantt" && ganttOn;
              return (
                <button type="button" role="radio" key={s.id} class="ap-choice" aria-checked={i === at ? "true" : "false"} aria-disabled={off ? "true" : undefined} onClick={() => choose(i)}>
                  <b>{s.name}</b>
                  {s.description ? <small>{s.description}</small> : null}
                  <span class="ap-chips">{s.parts.map((p) => <i key={p.template} data-template={p.template}>{tname(p.template)}</i>)}</span>
                </button>
              );
            })}
          </div>
          <h3 id="ap-step-2">Name it</h3>
          <input id="add-page-name" type="text" class="dlg-field" aria-labelledby="ap-step-2" maxLength={gantt ? NAME_MAX : NAME_LIMIT} value={typed === null ? starter.name : typed}
            onInput={(e) => setTyped(e.currentTarget.value)} />
        </div>
        <div class="ap-preview">
          <h3>{starter.name}</h3>
          <div class="ap-mini">
            {starter.parts.map((p, i) => <div class="ap-part" key={i} data-template={p.template}><b>{tname(p.template)}</b>{p.prompt ? <span>{p.prompt}</span> : null}</div>)}
          </div>
        </div>
      </div>
    </Dialog>
  );
}
