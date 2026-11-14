// #80: a Work items table cell (owner, due, priority, status) that changes in place, in Edit only. The cell's own content is a
// button; a click, Enter or Space opens that field's picker (Alt+Down too; a plain Down moves to the next row, WorkItems.jsx). A pick is one change through clark (one step,
// with Undo in the toast); Esc or a click away leaves it as it was. The button stops its click there, so a click on a cell
// never opens the peek; a click anywhere else on the row still does. In the peek (#448) the same cell takes `place="peek"`: its
// own picker key, so the table's picker and the peek's are never both open, and a pick is about the open item alone (never the bulk plan). One picker is open at a time. The Status cell shows the
// item's live look (itemEdit.statusPill, the same pill as View, #448); its picker and its toast say the status words. Item 210: a risk's or issue's Priority opens a
// picker for its impact and likelihood (RatingPick), the two its priority is worked out from. An assumption's or dependency's
// Priority is not a picker: its tooltip says it is set from impact and likelihood (a decision has none, and shows a dash).
import { openCell } from "../../stores/openCell.js";
import { useRef } from "preact/hooks";
import { data } from "../../stores/report.js";
import { changeCell, changeNewPerson, changeRating, say } from "../../stores/changes.js";
import { workSelection } from "../../stores/selection.js";
import { itemRows } from "../../stores/work.js";
import { cellPlan } from "../bulkLogic.js";
import { ask, runBulk } from "../Bulk.jsx";
import { todayIso } from "../../workItems.js";
import { canPick, changeFor, newPersonChange, pickField, isMatrixPick, fieldName, people, statusPill, tableOf, whyFixed } from "../itemEdit.js";
import { OwnerPick } from "./OwnerPick.jsx";
import { DuePick } from "./DuePick.jsx";
import { PriorityPick } from "./PriorityPick.jsx";
import { StatusPick } from "./StatusPick.jsx";

export const PICKERS = { owner: OwnerPick, due: DuePick, priority: PriorityPick, status: StatusPick };
export { openCell };                                     // "<id>:<field>" of the open picker, or "" (stores/openCell.js)

const key = (row, field) => `${row.id}:${field}`;

// After a change has been drawn the row may have moved (the list is sorted by due date): focus goes back to its cell if it was lost.
// If the row itself is gone (a filter no longer holds it), focus goes to the same cell of the next row, else the previous, else the table.
function near(k) {
  const own = document.querySelector(`[data-cell="${CSS.escape(k)}"]`), tr = own && own.closest ? own.closest("tr[data-id]") : null, field = k.slice(k.lastIndexOf(":") + 1), out = [];
  for (let n = tr && tr.nextElementSibling; n; n = n.nextElementSibling) if (n.dataset && n.dataset.id) out.push(`${n.dataset.id}:${field}`);
  for (let n = tr && tr.previousElementSibling; n; n = n.previousElementSibling) if (n.dataset && n.dataset.id) out.push(`${n.dataset.id}:${field}`);
  return { out, table: tr && tr.closest("table") };
}
function refocus(k, around) {
  setTimeout(() => {
    const now = document.activeElement;
    if (now && now !== document.body && now.isConnected) return;
    let el = document.querySelector(`[data-cell="${CSS.escape(k)}"]`);
    for (let i = 0; !el && around && i < around.out.length; i++) el = document.querySelector(`[data-cell="${CSS.escape(around.out[i])}"]`);
    if (!el && around && around.table && around.table.isConnected) { if (around.table.tabIndex < 0) around.table.tabIndex = -1; el = around.table; }
    if (el) el.focus();
  }, 0);
}

export function Cell({ row, field, said, keep, tip, children, place }) {
  const button = useRef(null);
  if (!canPick(row, field)) {
    const why = whyFixed(row, field);                       // a RAID item's priority: say why a click does nothing
    return why ? <span class="cell-fixed" data-fixed={`${row.id}:${field}`} title={why}>{children}</span> : children;
  }
  const k = place ? `${place}:${key(row, field)}` : key(row, field), open = openCell.value === k, Picker = PICKERS[field];
  if (field === "status" && !keep) { const p = statusPill(row, todayIso()); children = <span class={`pill ${p.class}`}>{p.text}</span>; }   // the live look; `keep`: the report rows (ItemRowsEdit) keep the pill they were given (Overdue, Red, ...)
  const close = (back) => { if (openCell.value === k) openCell.value = ""; if (back && button.current) button.current.focus(); };
  const pick = (value) => {
    // #196: on a row that is one of two or more selected, the pick changes that field of every selected row, and says so first.
    // D-12 and item 1182: a Rating pick (`rating:Red`, or a matrix cell `High/Medium`) is about this one risk or issue, never the bulk status change, so it skips the plan.
    const chosen = workSelection.ids.value, plan = !place && chosen.length >= 2 && pickField(field, value) !== "rating" && !isMatrixPick(field, value) ? cellPlan(row.id, field, itemRows.value.filter((r) => chosen.includes(r.id))) : null;
    if (plan && plan.why) { if (field === "owner") return plan.why; close(true); say("note", plan.why); return ""; }
    if (plan) {
      if (field === "owner" && !String(value == null ? "" : value).trim()) return "An owner can't be blank. Type a name, or TBC if no one is known yet.";
      close(true);
      ask(plan.question, () => runBulk(plan.table, plan.ids, plan.id, value, { place: "cell", from: row.id, asked: true }), { ids: plan.ids, from: row.id });   // the question has the count: asked once
      return "";
    }
    const today = todayIso();
    const c = changeFor(row, pickField(field, value), value, today);
    if (c && c.error) return c.error;
    close(true);
    const around = near(k);
    if (c) (c.one ? changeRating : changeCell)(tableOf(row), row.id, c.changes, { text: c.words, back: c.back, always: row.kind === "decision" && field === "status" && value === "Made", place: place || "cell" }).then(() => refocus(k, around));
    return "";
  };
  // Row 986: a name that is not on the list, added and assigned in one step. Resolves to {ok: true} (the picker has closed) or the words to
  // say beside what was typed ({message}, and `person`, the one already on the list, when the server says so). A selection of two or more
  // takes no new person here: the picker does not offer it.
  const add = async (person) => {
    const c = newPersonChange(row, person, todayIso());
    if (c && c.error) return { ok: false, message: c.error, code: "", person: null };
    if (!c) { close(true); return { ok: true }; }
    const r = await changeNewPerson(tableOf(row), row.id, c, place);
    if (r.ok) { close(true); refocus(k); }
    return r;
  };
  const toggle = () => { openCell.value = open ? "" : k; };
  const down = (e) => {
    if (e.key === "Escape" && open) { e.preventDefault(); e.stopPropagation(); close(true); }
    else if (e.key === "ArrowDown" && e.altKey && !open) { e.preventDefault(); openCell.value = k; }
  };
  return (
    <>
      <button type="button" class="cell-pick" ref={button} tabIndex={place ? 0 : -1} data-edit-only data-cell={k} data-tip={tip || undefined} aria-haspopup={field === "status" || field === "priority" ? "menu" : "dialog"}
        aria-expanded={open ? "true" : "false"} aria-label={`${fieldName(row, field)} of ${row.id}: ${said}. Change`}
        onClick={(e) => { e.stopPropagation(); toggle(); }} onKeyDown={down}><span class="cell-val">{children}</span></button>
      {open ? <Picker row={row} anchor={button} today={todayIso()} names={field === "owner" ? people(data.value) : undefined} onPick={pick} onAdd={field === "owner" && (place || workSelection.ids.value.length < 2) ? add : undefined} onClose={close} /> : null}
    </>
  );
}
