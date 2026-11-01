// The Word screens (#48), Edit parts only: the Export to Word box and the Import from Word box, both native <dialog>s opened as
// modals (Tab stays inside, Esc cancels; focus goes back to the profile circle when one closes). Each is in the page only while it is
// open. The state and the rules are in wordState.js; the server's own plain words are shown as they are. What is busy says so in
// words (and its buttons are off), never by colour alone.
import { useEffect, useRef } from "preact/hooks";
import { data, project, mode } from "../stores/report.js";
import { NO_FOLDER, folderName } from "./publishState.js";
import { WordClash } from "./WordClash.jsx";
import { WORD_FILE_MB } from "./wordApi.js";
import { exportBox, goExport, cancelExport, tickClient, pickClash, confirmReplace, exportReady,
  importBox, goRead, goAdd, cancelImport, chooseFile, tickItem, tickAllItems } from "./wordState.js";

const shownDate = (iso) => (/^\d{4}-\d\d-\d\d$/.test(iso) ? iso.slice(8) + "-" + iso.slice(5, 7) + "-" + iso.slice(0, 4) : iso);
// Why an empty list is empty, said once: everything in the file was added before, or there was nothing to find (a list with problems
// says what each one is, so it only says nothing new was found).
const nothingNew = (plan) => plan.already > 0 ? `Everything in ${plan.file} has been added before, so there is nothing new to add.`
  : plan.problems.length ? `Nothing new was found in ${plan.file}.`
  : `Nothing new was found in ${plan.file}. Put actions, risks, issues or decisions under a heading with that name, then choose the file again.`;
export const count = (n, one, many) => `${n} ${n === 1 ? one : many || one + "s"}`;

// A modal dialog that is shown when it mounts, and gives focus back to the profile circle when it goes.
function useModal(el) {
  useEffect(() => {
    const dlg = el.current;
    if (dlg && !dlg.open) dlg.showModal();
    return () => {
      if (dlg && dlg.open) dlg.close();
      const me = document.getElementById("profile-btn");
      if (me) me.focus();
    };
  }, []);
}

function Export() {
  const s = exportBox.value, el = useRef(null);
  const p = data.value && data.value.project;
  useModal(el);
  // Focus: the To client tick when it can be ticked, else the button; the chosen answer when the name is taken.
  useEffect(() => {
    const dlg = el.current;
    if (!dlg) return;
    const target = s.phase === "clash" ? dlg.querySelector("input[name=word-clash]:checked") : s.phase === "done" ? dlg.querySelector("[data-go]")
      : dlg.querySelector("#word-client:not([disabled])") || dlg.querySelector("[data-go]");
    if (target) target.focus();
  }, [s.phase]);
  const working = s.phase === "working";
  return (
    <dialog id="word-export-dialog" class="dlg" aria-modal="true" aria-labelledby="word-x-title" aria-busy={working ? "true" : "false"} ref={el} onCancel={(e) => { e.preventDefault(); cancelExport(); }}>
      <form class="dlg-form" onSubmit={(e) => { e.preventDefault(); goExport(); }}>
        <h2 id="word-x-title">{s.phase === "clash" ? "The Word file name is taken" : "Export to Word"}</h2>
        {s.phase === "clash" ? null : (
          <p class="muted dlg-sub">{p ? p.name : project.value}{p && p.week_ending ? ` · week ending ${shownDate(p.week_ending)}` : ""}</p>
        )}
        {s.phase === "clash" ? (
          <WordClash clash={s.clash} choice={s.choice} confirmed={s.confirmed} onPick={pickClash} onConfirm={confirmReplace} />
        ) : (
          <div class="pubopts">
            <p class="muted word-where">The report is saved as a Word file in the folder last used for this project. If there is none yet, a window asks you to choose one.</p>
            <label class={`pubopt${s.saved ? "" : " off"}`}><input type="checkbox" id="word-client" checked={s.ticked} disabled={!s.saved || working} onChange={(e) => tickClient(e.currentTarget.checked)} />
              <span><b>To client</b><small>{s.saved ? `Also copied to the client folder: ${folderName(s.saved)}` : NO_FOLDER}</small></span></label>
          </div>
        )}
        {s.phase !== "clash" && s.ticked ? <p class="muted dlg-warn" id="word-warn">The client will see this report.</p> : null}
        <div class="pub-msg word-msg" id="word-export-msg" role={s.message && s.message.kind === "error" ? "alert" : "status"} aria-live="polite">
          {working ? "Saving the Word report… If a window asks where to save it, choose a folder there." : s.message ? <p class={s.message.kind}>{s.message.text}</p> : null}
        </div>
        <div class="dlg-f">
          {s.phase === "done" ? null : <button type="button" class="btn quiet" data-cancel onClick={cancelExport} disabled={working}>Cancel</button>}
          <button type="submit" class="btn pri" data-go disabled={working || !exportReady(s)}>
            {s.phase === "done" ? "Close" : s.phase === "clash" ? "Continue" : s.ticked ? "Save and send to the client" : "Save the Word report"}
          </button>
        </div>
      </form>
    </dialog>
  );
}

function Import() {
  const s = importBox.value, el = useRef(null);
  useModal(el);
  const busy = s.phase === "reading" || s.phase === "adding";
  useEffect(() => {
    const dlg = el.current;
    if (!dlg) return;
    const target = s.phase === "choose" ? dlg.querySelector("#word-file") : s.phase === "plan" ? dlg.querySelector("[data-add]:not([disabled])") || dlg.querySelector("[data-cancel]") : null;
    if (target) target.focus();
  }, [s.phase]);
  const plan = s.plan, n = s.ticks.length;
  return (
    <dialog id="word-import-dialog" class="dlg wi" aria-modal="true" aria-labelledby="word-i-title" aria-busy={busy ? "true" : "false"} ref={el} onCancel={(e) => { e.preventDefault(); cancelImport(); }}>
      <form class="dlg-form" onSubmit={(e) => { e.preventDefault(); if (s.phase === "choose") goRead(); else if (s.phase === "plan") goAdd(); }}>
        <h2 id="word-i-title">Import from Word</h2>
        {s.phase === "plan" || s.phase === "adding" ? (
          <>
            <p class="muted dlg-sub" id="word-count">{plan.items.length === 0 ? nothingNew(plan) : `${count(plan.items.length, "new item")} found in ${plan.file}. Nothing is added until you choose.`}</p>
            {plan.items.length ? (
              <>
                <div class="wi-all">
                  <button type="button" class="link" data-all="on" onClick={() => tickAllItems(true)} disabled={busy}>Tick all</button>
                  <button type="button" class="link" data-all="off" onClick={() => tickAllItems(false)} disabled={busy}>Untick all</button>
                </div>
                <fieldset class="wi-items" disabled={busy}>
                  <legend class="sr-only">Items to add</legend>
                  {plan.items.map((i) => (
                    <label class="pubopt wi-item" key={i.n}><input type="checkbox" data-n={i.n} checked={s.ticks.includes(i.n)} onChange={(e) => tickItem(i.n, e.currentTarget.checked)} />
                      <span><b>{i.n}.</b>{i.text}</span></label>
                  ))}
                </fieldset>
              </>
            ) : null}
            {plan.problems.length || plan.notes.length ? (
              <ul class="wi-notes" id="word-notes">
                {plan.problems.map((t, k) => <li key={"p" + k}>{t}</li>)}
                {plan.notes.map((t, k) => <li key={"n" + k}>{t}</li>)}
              </ul>
            ) : null}
          </>
        ) : (
          <>
            <p class="muted dlg-sub">Choose a Word file of up to {WORD_FILE_MB} MB. You will see what it holds first. Nothing is added until you choose.</p>
            <label class="pub-field">Word file
              <input type="file" id="word-file" accept=".docx" disabled={busy} onChange={(e) => chooseFile(e.currentTarget.files && e.currentTarget.files[0])} />
            </label>
          </>
        )}
        <div class="pub-msg word-msg" id="word-import-msg" role={s.message && s.message.kind === "error" ? "alert" : "status"} aria-live="polite">
          {s.phase === "reading" ? "Reading the file…" : s.phase === "adding" ? `Adding ${count(n, "item")}…` : s.message ? <p class={s.message.kind}>{s.message.text}</p> : null}
        </div>
        <div class="dlg-f">
          <button type="button" class="btn quiet" data-cancel onClick={cancelImport} disabled={busy}>{s.phase === "plan" && plan.items.length === 0 ? "Close" : "Cancel"}</button>
          {s.phase === "plan" || s.phase === "adding" ? (
            plan.items.length ? <button type="submit" class="btn pri" data-add disabled={busy || n === 0}>{n === 0 ? "Add items" : `Add ${count(n, "item")}`}</button> : null
          ) : (
            <button type="submit" class="btn pri" data-read disabled={busy || !s.file}>Read the file</button>
          )}
        </div>
      </form>
    </dialog>
  );
}

// Mounted once, beside the Publish box (Publish.jsx), so the page's own files need no new place for it. The import box is Edit's: View has none.
export function WordLayer() {
  return (
    <>
      {exportBox.value ? <Export /> : null}
      {mode.value === "edit" && importBox.value ? <Import /> : null}
    </>
  );
}
