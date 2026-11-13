// The demo data banner and its box (#731). Edit only: a published file has no edit parts, so it can never show the banner (and
// shell.css hides it in print). One line over every view while the made-up demo projects are on show: "This is demo data." and
// Remove demo data, which asks first. Removing reads the project list again and lands on the empty screen when none remain.
import { useEffect, useState } from "preact/hooks";
import { signal } from "@preact/signals";
import { loadProjects, projects, project, openProjectAt, leaveProject } from "../stores/report.js";
import { say, toast, undone } from "../stores/changes.js";
import { Dialog } from "./Dialog.jsx";
import { openBox, closeBox } from "./boxes.js";
import { readDemo, sendDemoRemove } from "./demoApi.js";
import { DEMO } from "../logic/demoWords.js";
import * as D from "../logic/dataCard.js";

// The banner (the box's opener) is gone once the demo is removed: focus goes to the first of these that is drawn: the empty screen's button, the first
// project of the Choose-a-project list (the person has projects of their own left), the project switch (one of them is open), the profile circle.
// When no project went, to the profile circle.
const AFTER_REMOVAL = ["#np-empty", ".choose button", "#project-name", "#profile-btn"];

export const demoOn = signal(false);

export function DemoBanner() {
  useEffect(() => { readDemo().then((on) => { demoOn.value = on; }); }, [project.value, toast.value, undone.value]);        // read again when another project opens and after each saved change or Undo: an edit makes a demo project the person's
  if (!demoOn.value) return null;
  return (
    <div class="demo-banner" id="demo-banner" role="status" data-edit-only>
      <span>{DEMO.banner}</span>
      <button type="button" class="btn sm" id="demo-remove" onClick={(e) => openBox("demo", { opener: e.currentTarget })}>{DEMO.remove}</button>
    </div>
  );
}

export function DemoConfirm({ opener, onClose }) {
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const [note, setNote] = useState("");
  async function go() {
    if (busy) return;
    setBusy(true);
    const r = await sendDemoRemove();
    if (!r.ok) { setBusy(false); setProblem(r.message); return; }
    demoOn.value = false;
    if (r.removed === 0) { setNote(DEMO.none); return; }       // an edit had made every demo project the person's: nothing went, the banner goes, and the box says so (Cancel closes it)
    await loadProjects();                                             // the screen underneath is settled before the box closes, so the fallback finds what is really there
    if (!projects.value.some((p) => p.code === project.value)) leaveProject();     // the open project went: the empty screen, or the list of the projects left
    closeBox();
  }
  return (
    <Dialog id="demo-confirm" opener={opener} title={DEMO.confirmTitle} onClose={onClose} first="#demo-cancel" fallback={note ? "#profile-btn" : AFTER_REMOVAL}
      foot={<><button type="button" class="btn quiet" id="demo-cancel" onClick={onClose}>{DEMO.cancel}</button><button type="button" class="btn pri" id="demo-go" disabled={busy || !!note} onClick={go}>{DEMO.remove}</button></>}>
      <p>{DEMO.confirmBody}</p>
      <p role="status" id="demo-none">{note}</p>
      <p class="error" role="alert" id="demo-problem">{problem}</p>
    </Dialog>
  );
}

// The one button on the empty screen once the demo is gone: the project form Settings uses; the new project opens on Work items.
export function NewProjectButton() {
  async function saved(body) {
    closeBox();
    await loadProjects();
    openProjectAt(body.code, "work");
    say("done", D.PROJECT.created(body.name));
  }
  return <button type="button" class="btn pri" id="np-empty" onClick={(e) => openBox("project", { row: null, opener: e.currentTarget, onSaved: saved })}>{DEMO.newProject}</button>;
}
