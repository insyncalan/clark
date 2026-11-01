// Checklist (#96), store type "checklist": its Edit part. Fill in place: type a line and tick it, or link a work item (its words and
// whether it is done then follow the work item); change a typed line where it is; remove one. Each save is one change() (one step,
// one Undo, place "cell"). Given { section, tools }.
import { useState } from "preact/hooks";
import { data } from "../../stores/report.js";
import { say } from "../../stores/changes.js";
import { useList } from "./useList.js";
import { rowsOf } from "../../workItems.js";
import { itemsOf, bodyOf, MAX_ITEMS, TEXT_MAX, problem } from "../../templates/checklist.js";

const EMPTY_WORDS = "No lines yet. Type the first line below, or link a work item. It stays out of the published page until it has a line.";
const cut = (s, n) => { const c = Array.from(String(s)); return c.length > n ? `${c.slice(0, n - 1).join("").trimEnd()}…` : c.join(""); };

export function Edit({ section }) {
  const [tick, setTick] = useState(0);                      // a refused change redraws the row, so a box shows what was saved
  const items = itemsOf(section);
  const d = data.value || {};
  const work = rowsOf(d);
  const byId = new Map(work.map((r) => [r.id, r]));
  const list = useList(section, items);
  const save = (make, words) => list.put(make, bodyOf, words).then((r) => { if (!r) setTick(tick + 1); return r; });
  const full = () => { if (items.length >= MAX_ITEMS) { say("problem", problem.full); return true; } return false; };
  const linked = new Set(items.filter((i) => typeof i.item === "string").map((i) => i.item));
  const offer = work.filter((r) => !linked.has(r.id) && !["Cancelled", "Withdrawn"].includes(r.status));

  const retext = (n, el) => {
    const old = list.latest()[n], text = el.value.trim();
    if (!old) return;
    if (text === old.text) return;
    if (!text || Array.from(text).length > TEXT_MAX) { say("problem", problem.text); el.value = old.text; return; }
    save((cur) => cur.map((x, i) => (i === n ? { text, done: x.done } : x)), "Line changed.");
  };
  const toggle = (n, on) => save((cur) => cur.map((x, i) => (i === n ? { text: x.text, done: on ? 1 : 0 } : x)), on ? "Line ticked." : "Line unticked.");
  const remove = (n) => save((cur) => cur.filter((_, i) => i !== n), "Line removed.");
  const link = (e) => {
    const id = e.currentTarget.value;
    e.currentTarget.value = "";
    if (!id || full()) return;
    save((cur) => [...cur, { item: id }], "Work item linked.");
  };
  const addTyped = (e) => {
    e.preventDefault();
    const form = e.currentTarget, text = form.elements.text.value.trim();
    if (full()) return;
    if (!text || Array.from(text).length > TEXT_MAX) { say("problem", problem.text); form.elements.text.focus(); return; }
    save((cur) => [...cur, { text, done: 0 }], "Line added.").then((r) => { if (r) form.reset(); });
  };

  return (
    <div class="tple" data-tpl="checklist">
      {items.length === 0 ? <p class="quiet tple-empty">{EMPTY_WORDS}</p> : (
        <ul class="tple-list" data-tick={tick}>
          {items.map((i, n) => (typeof i.item === "string" ? (
            <li key={`w${i.item}`} class="tple-row">
              <span class="tple-main">
                <span class="tple-name">{byId.has(i.item) ? cut(byId.get(i.item).title || i.item, 120) : "A work item that is no longer in the report"}</span>
                <span class="tple-sub">{i.item}{byId.has(i.item) ? (["Closed", "Made"].includes(byId.get(i.item).status) ? ", done" : ", to do") : ""}, follows the work item</span>
              </span>
              <button type="button" class="btn tple-x" aria-label={`Remove the line for ${i.item}`} onClick={() => remove(n)}>Remove</button>
            </li>
          ) : (
            <li key={`t${n}`} class="tple-row">
              <input class="tple-tick" type="checkbox" checked={i.done === 1} aria-label={`Done: ${i.text}`} onChange={(e) => toggle(n, e.currentTarget.checked)} />
              <input key={`x${n}-${i.text}`} class="tple-in" type="text" defaultValue={i.text} aria-label="Checklist line" onBlur={(e) => retext(n, e.currentTarget)} onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.blur(); }} />
              <button type="button" class="btn tple-x" aria-label={`Remove ${i.text}`} onClick={() => remove(n)}>Remove</button>
            </li>
          )))}
        </ul>
      )}
      <div class="tple-add">
        <form class="tple-typed" onSubmit={addTyped}>
          <label><span class="tple-cap">New line</span><input class="tple-in" name="text" type="text" placeholder="Send the plan to the board" /></label>
          <button type="submit" class="btn">Add line</button>
        </form>
        <label class="tple-pick"><span class="tple-cap">Link a work item</span>
          <select class="tple-in" onChange={link} disabled={!offer.length} aria-label="Link a work item">
            <option value="">{offer.length ? "Choose a work item…" : "No work items left to link"}</option>
            {offer.map((r) => <option key={r.id} value={r.id}>{`${r.id}: ${cut(r.title || "", 70)}`}</option>)}
          </select>
        </label>
      </div>
    </div>
  );
}
