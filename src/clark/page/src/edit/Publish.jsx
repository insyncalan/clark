// Publish: its dialog (#43) (the last-published line is the report bar's chip, ReportBar.jsx). The command itself is in the profile menu (#77), which calls `open`. The dialog
// is a native <dialog> opened as a modal, so Tab stays inside it and Esc cancels; it is in the page only while it is open, so
// View has no form field in it. Local is ticked and disabled. To client is unticked every time, and disabled until the project
// has a client folder (Settings). The words are the spec's (docs/handoff/design-43-to-client.md).
import { useEffect, useRef } from "preact/hooks";
import { data, project } from "../stores/report.js";
import { Icon } from "../components/Icon.jsx";
import { showDate } from "../workItems.js";
import { dialogLine } from "./publishLine.js";
import { dialog, latest, next, NO_FOLDER_LEAD, NO_FOLDER_LINK, toPublishingCard, folderName, placeholderItems, placeholderWarning, open, close, tick, tickPdf, tickWord, wordPick, wordConfirm, pick, rename, confirmOverwrite, ready, cancel, go, refreshLatest } from "./publishState.js";
import { WordClash } from "./WordClash.jsx";
import { WordLayer } from "./Word.jsx";

export const lastLine = (l) => (l ? `Published ${showDate(l.at)} ${l.to_client ? "to the client" : "locally"}` : "");

// The success line with "Published (Publication N)" picked out as #pub-done (#353); the words and their order are the server's own.
function doneWords(m) {
  const head = m.kind === "success" && m.number ? `Published (Publication ${m.number})` : null;
  return head && m.text.startsWith(head) ? <><span id="pub-done">{head}</span>{m.text.slice(head.length)}</> : m.text;
}

function Dialog() {
  const s = dialog.value, el = useRef(null);
  const d = data.value, p = d && d.project;
  useEffect(() => {
    const dlg = el.current;
    if (dlg && !dlg.open) dlg.showModal();
    return () => {      // the menu item that opened it is gone: focus goes back to the profile circle
      if (dlg && dlg.open) dlg.close();
      const me = document.getElementById("profile-btn");
      if (me) me.focus();
    };
  }, []);
  // Where focus goes: the To client tick when it can be ticked, else the button; the question's chosen answer when it is asked.
  useEffect(() => {
    const dlg = el.current;
    if (!dlg) return;
    const target = s.phase === "wordclash" ? dlg.querySelector("input[name=word-clash]:checked") : s.phase === "clash" ? dlg.querySelector(s.choice === "rename" ? "#pub-name" : "input[name=clash]:checked") : s.phase === "done" ? dlg.querySelector("[data-go]")
      : dlg.querySelector("#pub-client:not([disabled])") || dlg.querySelector("[data-go]");
    if (target) target.focus();
  }, [s.phase, s.phase === "clash" ? s.choice : ""]);
  const working = s.phase === "working", clash = s.clash;
  const placeholders = placeholderItems(d);
  return (
    <dialog id="publish-dialog" class="dlg" aria-labelledby="pub-title" ref={el} onCancel={(e) => { e.preventDefault(); cancel(); }}>
      <form class="dlg-form" onSubmit={(e) => { e.preventDefault(); go(); }}>
        <h2 id="pub-title">{s.phase === "clash" ? clash.title : s.phase === "wordclash" ? "The Word file name is taken" : "Publish the report"}</h2>
        {s.phase === "clash" || s.phase === "wordclash" ? null : (
          <p class="muted dlg-sub" id="pub-sub">{dialogLine(p ? p.name : project.value, p && p.week_ending, next.value, latest.value, showDate)}</p>
        )}
        {s.phase === "wordclash" ? (
          <>
            <p class="muted" id="pub-said">The web page is published.</p>
            <WordClash clash={s.wclash} choice={s.wchoice} confirmed={s.wconfirmed} onPick={wordPick} onConfirm={wordConfirm} />
          </>
        ) : s.phase === "clash" ? (
          <fieldset class="pub-clash">
            <legend class="sr-only">What should clark do?</legend>
            <label class="pubopt"><input type="radio" name="clash" value="number" checked={s.choice === "number"} onChange={() => pick("number")} />
              <span><b>Add a number</b>{clash.numbered ? <small>saves as “{clash.numbered}”</small> : null}</span></label>
            <label class="pubopt"><input type="radio" name="clash" value="rename" checked={s.choice === "rename"} onChange={() => pick("rename")} />
              <span><b>Rename it</b></span></label>
            {s.choice === "rename" ? (
              <label class="pub-field">New file name
                <input type="text" id="pub-name" value={s.newName} onInput={(e) => rename(e.currentTarget.value)} autocomplete="off" spellcheck={false} />
              </label>
            ) : null}
            {clash.canOverwrite ? (
              <label class="pubopt"><input type="radio" name="clash" value="overwrite" checked={s.choice === "overwrite"} onChange={() => pick("overwrite")} />
                <span><b>Overwrite the existing file</b></span></label>
            ) : null}
            {s.choice === "overwrite" ? (
              <div class="pub-note">
                <p>{clash.note}</p>
                <label class="pubopt"><input type="checkbox" id="pub-confirm" checked={s.confirmed} onChange={(e) => confirmOverwrite(e.currentTarget.checked)} />
                  <span>Yes, replace the file in the client folder</span></label>
              </div>
            ) : null}
          </fieldset>
        ) : (
          <div class="pubopts">
            <label class="pubopt"><input type="checkbox" id="pub-local" checked disabled />
              <span><b>Local</b><small>Always. You choose the folder and name in the save window.</small></span></label>
            <label class={`pubopt${s.saved ? "" : " off"}`}><input type="checkbox" id="pub-client" checked={s.ticked} disabled={!s.saved || working} onChange={(e) => tick(e.currentTarget.checked)} />
              <span><b>To client</b><small>{s.saved ? `Copied to the client folder: ${folderName(s.saved)}` : <>{NO_FOLDER_LEAD}<button type="button" class="link" id="pub-to-set" disabled={working} onClick={toPublishingCard}>{NO_FOLDER_LINK}</button>.</>}</small></span></label>
            {/* #796: Word before PDF, the prototype's order (system/prototype/io.js:348-349) */}
            <label class="pubopt"><input type="checkbox" id="pub-word" checked={s.word} disabled={working} onChange={(e) => tickWord(e.currentTarget.checked)} />
              <span><b>Also a Word document</b><small>A Word copy of the report, saved in the folder last used for this project.</small></span></label>
            {/* the prototype's words (system/prototype/io.js:349); the note under the tick (WORDING: owner to rule) */}
            <label class="pubopt"><input type="checkbox" id="pub-pdf" checked={s.pdf} disabled={working} onChange={(e) => tickPdf(e.currentTarget.checked)} />
              <span><b>Also a PDF</b><small>The page as it prints: the tabs one after another, no controls, with the publication number in the foot</small>
                {s.pdf ? <small id="pub-pdf-note">Your browser’s print box opens; choose Save as PDF. In the print box, untick Headers and footers, so the PDF carries no web address.</small> : null}</span></label>
          </div>
        )}
        {/* item 437 rows 29 and 56: the second sentence is the prototype's (io.js, #pubWarn) */}
        {s.phase !== "clash" && s.phase !== "wordclash" && s.ticked ? <p class="muted dlg-warn" id="pub-warn">{s.word ? "The client will see this page and the Word report. Only what is shown in View mode is included." : "The client will see this page. Only what is shown in View mode is included."}</p> : null}
        {/* item 449: a warning, not a block: client-visible work items whose title is still the one Add gave them */}
        {s.phase !== "clash" && s.phase !== "wordclash" && placeholders.length ? <p class="dlg-warn" id="pub-placeholder" data-count={String(placeholders.length)}>{placeholderWarning(placeholders)}</p> : null}
        <div class="pub-msg" id="pub-msg" role={s.message && s.message.kind === "error" ? "alert" : "status"} aria-live="polite">
          {working ? <p class="working">{s.step === "word" ? "Saving the Word report…" : "Publishing…"}</p>
            : s.message ? <p class={s.message.kind}><span>{doneWords(s.message)}</span></p> : null}
        </div>
        <div class="dlg-f">
          {s.phase === "done" ? null : <button type="button" class="btn quiet" data-cancel onClick={cancel} disabled={working}>Cancel</button>}
          {/* #353 (the owner's ruling, the prototype's): the spinner and then the tick are on the button itself; once done the button is green and closes the box. */}
          <button type="submit" id="pub-go" class={`btn pri${s.phase === "done" ? " ok" : ""}`} data-go aria-busy={working ? "true" : undefined} title={s.phase === "done" ? "Close" : undefined} disabled={working || !ready(s)}>
            {working ? <><span class="spin" id="pub-spin" data-spin aria-hidden="true" />Publishing…</>
              : s.phase === "done" ? <><span class="pub-tick" data-tick aria-hidden="true"><Icon name="check" /></span>{s.message && s.message.number ? `Published (Publication ${s.message.number})` : "Published"}</>
              : s.phase === "clash" ? "OK" : s.phase === "wordclash" ? "Continue" : s.ticked ? "Publish and send to the client" : "Publish locally"}
          </button>
        </div>
      </form>
    </dialog>
  );
}

export { open as openPublish };
export function Publish() {
  useEffect(() => { refreshLatest(); }, [project.value]);
  if (!data.value) return null;
  return (
    <>
      <span class="pubbar"></span>
      {dialog.value ? <Dialog /> : null}
      <WordLayer />
    </>
  );
}
