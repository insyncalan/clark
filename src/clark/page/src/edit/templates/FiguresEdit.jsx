// The Key figures templates' Edit part (#96): each place is empty, a typed figure (label, number, a note, an as-of date) or a live one
// (Overdue actions, High risks and issues, Decisions needed: the same figures as the At a glance tiles). A field is saved when it
// is left (or its choice made): one change() each, so one step and one Undo. A figure with a label and no number (or the other way
// round) is saved and waits: the line under it says it stays out of the published page. The preview above is what View shows.
import { change } from "../../stores/changes.js";
import { data } from "../../stores/report.js";
import { todayIso } from "../../workItems.js";
import { FigureRow } from "../../templates/FiguresView.jsx";
import { PLACES, METRICS, LIMITS, slotsOf, bodyOf, figuresOf } from "../../templates/figures.js";

const BLANK = { mode: "typed", label: "", value: "", detail: "", asof: "" };

function save(section, slots) {
  return change({ op: "update", id: section.id, changes: { body: bodyOf(slots) }, place: "cell" }, "Figures saved.");
}

export function figuresEdit(type) {
  const places = PLACES[type];
  return function Edit({ section }) {
    const slots = slotsOf(section, places);
    while (slots.length < places) slots.push({ ...BLANK });
    const shown = figuresOf(section, data.value, todayIso(), places);
    const put = (i, one) => save(section, slots.map((s, j) => (j === i ? one : s)));
    const mode = (i, e) => {
      const m = e.currentTarget.value;
      put(i, m === "live" ? { mode: "live", metric: METRICS[0][0] } : { ...BLANK });
    };
    const field = (i, name) => (e) => {
      const v = e.currentTarget.value.trim();
      if (v !== (slots[i][name] || "")) put(i, { ...slots[i], [name]: v });
    };
    const key = section.body || "";
    return (
      <div class="tpl-edit" data-edit-only="" data-template={type}>
        {shown.length ? <FigureRow list={shown} type={type} /> : <p class="quiet">Nothing to show yet. Fill in a figure below, or choose a live one.</p>}
        <div class={`tpl-slots n${places}`}>
          {slots.map((s, i) => (
            <fieldset class="tpl-slot" key={`${i}-${key}`} data-slot={i}>
              <legend>{`Figure ${i + 1}`}</legend>
              <label>Source
                <select aria-label={`Figure ${i + 1} source`} value={s.mode === "live" ? "live" : "typed"} onChange={(e) => mode(i, e)}>
                  <option value="typed">Typed</option>
                  <option value="live">Live from the project</option>
                </select>
              </label>
              {s.mode === "live" ? (
                <label>Figure
                  <select aria-label={`Figure ${i + 1} live figure`} value={s.metric} onChange={(e) => put(i, { mode: "live", metric: e.currentTarget.value })}>
                    {METRICS.map(([k, name]) => <option value={k} key={k}>{name}</option>)}
                  </select>
                </label>
              ) : (
                <>
                  <label>Label<input type="text" maxLength={LIMITS.label} defaultValue={s.label} aria-label={`Figure ${i + 1} label`} onChange={field(i, "label")} /></label>
                  <label>Number<input type="text" maxLength={LIMITS.value} defaultValue={s.value} aria-label={`Figure ${i + 1} number`} onChange={field(i, "value")} /></label>
                  <label>Note<input type="text" maxLength={LIMITS.detail} defaultValue={s.detail} aria-label={`Figure ${i + 1} note`} onChange={field(i, "detail")} /></label>
                  <label>As of<input type="date" defaultValue={s.asof} aria-label={`Figure ${i + 1} as of`} onChange={field(i, "asof")} /></label>
                  {(s.label || s.value) && !(s.label && s.value) ? <p class="quiet">Add a {s.label ? "number" : "label"} to show this figure. It stays out of the published page until then.</p> : null}
                </>
              )}
            </fieldset>
          ))}
        </div>
      </div>
    );
  };
}
