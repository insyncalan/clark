// Undo several, on the peek's Activity tab: the bar ("N selected", Undo N, Clear), the preview that says what would go back and what
// stays (a dry run), the second confirm above 25, and the one polite line a screen reader hears. The tab (PeekActivity.jsx) draws the
// ticks and owns the state; the rules are in activityUndo.js and the selection in stores/selection.js.
import { MOST, countWords, undoWords, tooMany, sureWords, willLine, leftLine } from "./activityUndo.js";

export function UndoBar({ sel, phase, onUndo, onGo, onSure, onBack, undoBtn, head }) {
  const n = sel.size.value;
  if (n === 0 && !phase) return null;
  const over = n > MOST;
  return (
    <div class="pa-undo" data-pa-undo>
      {n > 0 ? (
        <div class="selbar" role="region" aria-label="Selection" data-pa-bar>
          <span class="sb-n num" data-pa-count>{n} selected</span>
          <button type="button" class="btn pa-do" data-pa-undo-n ref={undoBtn} disabled={over || (phase && phase.kind === "working")} onClick={onUndo}>{undoWords(n)}</button>
          <button type="button" class="link" data-pa-clear onClick={() => sel.clear()}>Clear</button>
        </div>
      ) : null}
      {over ? <p class="muted pa-msg" data-pa-over>{tooMany(n)}</p> : null}
      {phase && phase.kind === "reading" ? <p class="muted pa-msg" data-pa-reading>Checking what can be undone…</p> : null}
      {phase && phase.kind === "problem" ? <p class="pa-msg pa-bad" role="alert" data-pa-problem>{phase.message}</p> : null}
      {phase && (phase.kind === "preview" || phase.kind === "sure") ? <Preview phase={phase} n={n} onGo={onGo} onSure={onSure} onBack={onBack} head={head} /> : null}
    </div>
  );
}

function Preview({ phase, n, onGo, onSure, onBack, head }) {
  const { undo, skipped } = phase.reply;
  const nothing = undo.length === 0;
  const asking = phase.kind === "sure";
  return (
    <section class="pa-preview" aria-label="What Undo will do" data-pa-preview>
      <h3 class="pa-h" tabIndex={-1} ref={head} data-pa-head>{nothing ? "Nothing here can be undone" : `${countWords(undo.length)} will be undone`}</h3>
      {undo.length ? <ul class="pa-lines" data-pa-will>{undo.map((e, i) => <li key={i}>{willLine(e)}</li>)}</ul> : null}
      {skipped.length ? (
        <>
          <h3 class="pa-h">{`${countWords(skipped.length)} will be left as ${skipped.length === 1 ? "it is" : "they are"}`}</h3>
          <ul class="pa-lines" data-pa-left>{skipped.map((e, i) => <li key={i}>{leftLine(e)}</li>)}</ul>
        </>
      ) : null}
      {asking ? <p class="pa-sure" data-pa-sure>{sureWords(n)}</p> : null}
      <div class="pa-acts">
        {!nothing && !asking ? <button type="button" class="btn pa-do" data-pa-go onClick={onGo}>{`Undo ${undo.length}`}</button> : null}
        {asking ? <button type="button" class="btn pa-do" data-pa-yes onClick={onSure}>{`Yes, undo all ${n}`}</button> : null}
        <button type="button" class="link" data-pa-back onClick={onBack}>{asking ? "No, go back" : "Cancel"}</button>
      </div>
    </section>
  );
}
