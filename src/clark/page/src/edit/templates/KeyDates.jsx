// Key dates (#96), store type "keydates": its Edit part. Fill in place: take a milestone's date from the list, or type a label and a
// day (DD-MM-YYYY); change a typed date where it is; remove one. Each save is one change() (one step, one Undo, place "cell").
// Given { section, tools }.
import { useState } from "preact/hooks";
import { data } from "../../stores/report.js";
import { say } from "../../stores/changes.js";
import { useList } from "./useList.js";
import { todayIso } from "../../logic/milestones.js";
import { itemsOf, bodyOf, linesOf, showDay, parseDay, MAX_ITEMS, LABEL_MAX, problem } from "../../templates/keydates.js";
import { dateWords } from "../../templates/safe.js";

const EMPTY_WORDS = "No dates yet. Take a date from a milestone, or type a label and a day below. It stays out of the published page until it has a date.";

export function Edit({ section }) {
  const [tick, setTick] = useState(0);                      // a refused change redraws the row, so a field shows what was saved
  const items = itemsOf(section);
  const d = data.value || {};
  const shown = new Set(linesOf(section, d, { fromFile: false, today: todayIso() }).map((l) => l.key));
  const list = useList(section, items);
  const save = (make, words) => list.put(make, bodyOf, words).then((r) => { if (!r) setTick(tick + 1); return r; });
  const full = () => { if (items.length >= MAX_ITEMS) { say("problem", problem.full); return true; } return false; };
  const used = new Set(items.filter((i) => typeof i.milestone === "string").map((i) => i.milestone));
  const offer = (d.milestones || []).filter((m) => !m.archived && m.status !== "Cancelled" && !used.has(m.id));
  const nameOf = (id) => { const m = (d.milestones || []).find((x) => x.id === id); return m ? m.name : ""; };
  const dateOf = (id) => { const m = (d.milestones || []).find((x) => x.id === id); return m ? m.baseline_date || m.forecast_date || "" : ""; };

  const longLabel = (t) => !t || Array.from(t).length > LABEL_MAX;
  const edit = (n, field, el) => {
    const old = list.latest()[n], raw = el.value.trim();
    if (!old) return;
    if (field === "label") {
      if (raw === old.label) return;
      if (longLabel(raw)) { say("problem", problem.label); el.value = old.label; return; }
      save((cur) => cur.map((x, i) => (i === n ? { label: raw, date: old.date } : x)), "Date changed.");
      return;
    }
    const day = parseDay(raw);
    if (day === old.date) { el.value = dateWords(old.date); return; }
    if (!day) { say("problem", problem.day); el.value = dateWords(old.date); return; }
    save((cur) => cur.map((x, i) => (i === n ? { label: old.label, date: day } : x)), "Date changed.");
  };
  const remove = (n) => save((cur) => cur.filter((_, i) => i !== n), "Date removed.");
  const addMilestone = (e) => {
    const id = e.currentTarget.value;
    e.currentTarget.value = "";
    if (!id || full()) return;
    save((cur) => [...cur, { milestone: id }], "Milestone date added.");
  };
  const addTyped = (e) => {
    e.preventDefault();
    const form = e.currentTarget, label = form.elements.label.value.trim(), day = parseDay(form.elements.date.value);
    if (full()) return;
    if (longLabel(label)) { say("problem", problem.label); form.elements.label.focus(); return; }
    if (!day) { say("problem", problem.day); form.elements.date.focus(); return; }
    save((cur) => [...cur, { label, date: day }], "Date added.").then((r) => { if (r) form.reset(); });
  };

  return (
    <div class="tple" data-tpl="keydates">
      {items.length === 0 ? <p class="quiet tple-empty">{EMPTY_WORDS}</p> : (
        <ul class="tple-list" data-tick={tick}>
          {items.map((i, n) => (typeof i.milestone === "string" ? (
            <li key={`m${i.milestone}`} class="tple-row">
              <span class="tple-main">
                <span class="tple-name">{nameOf(i.milestone) || "A milestone that is no longer in the report"}</span>
                <span class="tple-sub">{shown.has(i.milestone) ? `${showDay(dateOf(i.milestone))}, from the milestone` : "Left out of the published page"}</span>
              </span>
              <button type="button" class="btn tple-x" aria-label={`Remove ${nameOf(i.milestone) || "this milestone"}`} onClick={() => remove(n)}>Remove</button>
            </li>
          ) : (
            <li key={`t${n}`} class="tple-row">
              <input key={`l${n}-${i.label}`} class="tple-in" type="text" defaultValue={i.label} maxLength={LABEL_MAX} aria-label="Date label" onBlur={(e) => edit(n, "label", e.currentTarget)} onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.blur(); }} />
              <input key={`d${n}-${i.date}`} class="tple-in tple-day" type="text" defaultValue={dateWords(i.date)} inputMode="numeric" aria-label="Date, DD-MM-YYYY" onBlur={(e) => edit(n, "date", e.currentTarget)} onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.blur(); }} />
              <button type="button" class="btn tple-x" aria-label={`Remove ${i.label}`} onClick={() => remove(n)}>Remove</button>
            </li>
          )))}
        </ul>
      )}
      <div class="tple-add">
        <label class="tple-pick"><span class="tple-cap">Take a date from a milestone</span>
          <select class="tple-in" onChange={addMilestone} disabled={!offer.length} aria-label="Take a date from a milestone">
            <option value="">{offer.length ? "Choose a milestone…" : "No milestones left to add"}</option>
            {offer.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </label>
        <form class="tple-typed" onSubmit={addTyped}>
          <label><span class="tple-cap">Label</span><input class="tple-in" name="label" type="text" maxLength={LABEL_MAX} placeholder="Go live" /></label>
          <label><span class="tple-cap">Day (DD-MM-YYYY)</span><input class="tple-in tple-day" name="date" type="text" inputMode="numeric" placeholder="15-01-2030" /></label>
          <button type="submit" class="btn">Add date</button>
        </form>
      </div>
    </div>
  );
}
