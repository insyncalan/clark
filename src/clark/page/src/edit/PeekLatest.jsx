// The peek's Latest update with its Draft button and its 'Last updated' stamp, and the warning bar above the title (Edit only: a
// published file and View show the fields and nothing else). Every change is one request with one Undo (changeCell), and the data is
// read again after it so the stamp is the one clark wrote. Draft writes the text from the item's own fields (peekLatest.js draftFor),
// with no AI. An action has a latest update; a risk, issue or decision has the stamp only.
import { useEffect, useRef, useState } from "preact/hooks";
import { data } from "../stores/report.js";
import { changeCell, say, refresh } from "../stores/changes.js";
import { showDate, todayIso } from "../workItems.js";
import { changeFor, tableOf } from "./itemEdit.js";
import { warnFor, draftFor, latestProblem, cleanLatest, stampText } from "./peekLatest.js";
import { Icon } from "../components/Icon.jsx";

const raw = (row) => ((data.value && data.value[tableOf(row)]) || []).find((r) => r.id === row.id) || null;
const toClose = () => { const el = document.activeElement; if (!el || el === document.body || !el.isConnected) { const c = document.querySelector("#peek [data-pk-close]"); if (c) c.focus(); } };

// A date moved from the bar: one change, one Undo, the toast says where it went.
function move(row, date) {
  const c = changeFor(row, "due", date, todayIso());
  if (!c || c.error) { say("problem", c ? c.error : "That is already the date."); return; }
  changeCell(tableOf(row), row.id, c.changes, { text: `${row.id} moved to ${showDate(date)}.`, back: c.back, place: "peek" }).then(() => refresh()).then(toClose);
}

export function PeekWarn({ row }) {
  const w = warnFor(row, todayIso());
  if (!w) return null;
  return (
    <div class="pk-warnbar" data-pk-warn={w.kind}>
      <p class="pk-warn"><Icon name="flash" cls="s" />{w.text}</p>
      <div class="pk-fix">{w.moves.map((m) => <button key={m.date} type="button" data-pk-move={m.date} onClick={() => move(row, m.date)}>{m.label}</button>)}</div>
    </div>
  );
}

export function PeekLatest({ row }) {
  const rec = raw(row), action = row.kind === "action";
  const [open, setOpen] = useState(false), [text, setText] = useState(""), [problem, setProblem] = useState("");
  const settled = useRef(false), saving = useRef(false), shown = useRef(null), box = useRef(null);
  useEffect(() => { if (open && box.current) { box.current.focus(); const n = box.current.value.length; box.current.setSelectionRange(n, n); } }, [open]);
  const now = rec && rec.latest_update ? String(rec.latest_update) : "";
  const stamp = rec ? stampText(rec.updated_at) : "";
  const start = () => { settled.current = false; setText(now); setProblem(""); setOpen(true); };
  const stop = () => { settled.current = true; setOpen(false); setProblem(""); setTimeout(() => { if (shown.current) shown.current.focus(); }, 0); };
  const save = (value) => {
    const next = cleanLatest(value);
    if (next === cleanLatest(now)) return stop();
    const p = latestProblem(next);
    if (p) { setProblem(p); return undefined; }
    if (saving.current) return undefined;
    // The box closes only when clark has saved it: a refusal (or no answer) leaves it open with what was typed, and says why in it.
    saving.current = true;
    return changeCell("actions", row.id, { latest_update: next || null },
      { text: next ? `Latest update of ${row.id} saved.` : `Latest update of ${row.id} cleared.`, back: `Latest update of ${row.id} is back as it was.`,
        place: "peek", refused: (message) => { setProblem(message); if (box.current) box.current.focus(); } })
      .then((reply) => { saving.current = false; if (reply) { stop(); return refresh(); } return undefined; });
  };
  const draft = () => {
    const a = raw(row), ms = a && a.milestone && ((data.value && data.value.milestones) || []).find((m) => m.id === a.milestone);
    const words = draftFor({ due: row.due_date, status: row.status, owner: row.owner, milestone: ms ? { name: ms.name, agreed: ms.baseline_date } : null }, todayIso());
    if (words === cleanLatest(now)) { say("note", "The latest update already says that."); return; }
    if (open) stop();                                                  // Draft replaces the box's text: leave the box without saving what was typed
    changeCell("actions", row.id, { latest_update: words }, { text: "Latest update drafted from the item's own fields.", back: `Latest update of ${row.id} is back as it was.`, place: "draft" }).then(() => refresh());
  };
  const key = (e) => {
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); stop(); }
    else if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); save(e.currentTarget.value); }
  };
  return (
    <div class="pk-latest" data-pk-latest>
      {action ? <>
        <div class="pk-lab"><span id="pk-latest-lab">Latest update</span> <button type="button" class="pk-draft" data-pk-draft onClick={draft}><Icon name="sparkle" cls="s" />Draft</button></div>
        {open
          ? <>
            <textarea class="pk-latest-in" data-pk-latest-in aria-label="Latest update" rows={3} value={text} placeholder="Add the latest update…" ref={box}
              onInput={(e) => { setText(e.currentTarget.value); if (problem) setProblem(""); }} onKeyDown={key} onBlur={(e) => { const to = e.relatedTarget; if (!settled.current && !(to && to.hasAttribute && to.hasAttribute("data-pk-draft"))) save(e.currentTarget.value); }} />
            {problem ? <p class="pk-latest-err" role="alert" data-pk-latest-err>{problem}</p> : <p class="pk-latest-hint">Enter saves, Shift+Enter adds a line, Esc leaves it as it was.</p>}
          </>
          : <button type="button" class="pk-latest-text" data-pk-latest-text ref={shown} onClick={start} id="pk-latest-txt" aria-labelledby="pk-latest-lab pk-latest-txt" title="Edit the latest update">{now || <span class="muted">Add the latest update…</span>}</button>}
      </> : null}
      {stamp ? <div class="pk-last" data-pk-last><Icon name="clock" cls="s" /> Last updated {stamp}</div> : null}
    </div>
  );
}
