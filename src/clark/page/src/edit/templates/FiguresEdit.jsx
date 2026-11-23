// The Key figures templates' Edit part (#96): each place is empty, a typed figure (label, number, a note, an as-of date) or a live one
// (Overdue actions, High risks and issues, Decisions needed: the same figures as the At a glance tiles). A field is saved when it
// is left (or its choice made): one change() each, so one step and one Undo. A figure with a label and no number (or the other way
// round) is saved and waits: the line under it says it stays out of the published page. The preview above is what View shows.
import { StartPrompt } from "../StartPrompt.jsx";
import { change } from "../../stores/changes.js";
import { data } from "../../stores/report.js";
import { todayIso } from "../../workItems.js";
import { FigureRow } from "../../templates/FiguresView.jsx";
import { parseDay } from "../../templates/keydates.js";
import { dateWords } from "../../templates/safe.js";
import { COUNTS, PLACES, METRICS, LIMITS, metricsOffered, slotsOf, bodyOf, figuresOf, countOf, storedCount } from "../../templates/figures.js";

const BLANK = { mode: "typed", label: "", value: "", detail: "", asof: "" };

function save(section, slots, count) {
  return change({ op: "update", id: section.id, changes: { body: bodyOf(slots, count) }, place: "cell" }, "Figures saved.");
}

export function figuresEdit(type) {
  return function Edit({ section }) {
    const places = countOf({ ...section, type });      // row 1263: the Numbers card shows 3 or 4 (the count control); the older Key figures, three keeps its three
    const kept = storedCount({ ...section, type });       // written only once the person changes it
    const slots = slotsOf(section, PLACES[type]);       // every stored number, so the 4th is kept while the count is 3 (row 1263); only the first `places` are drawn
    while (slots.length < places) slots.push({ ...BLANK });
    const offered = metricsOffered(data.value);      // item 1337: a live figure is offered only while its section is there
    const shown = figuresOf(section, data.value, todayIso(), places);
    const put = (i, one) => save(section, slots.map((s, j) => (j === i ? one : s)), kept);
    const recount = (n) => save(section, slots, n);       // the count changes, no number is dropped
    const mode = (i, m) => {
      put(i, m === "live" && offered.length ? { mode: "live", metric: offered[0][0] } : { ...BLANK });
    };
    const field = (i, name) => (e) => {
      const v = e.currentTarget.value.trim();
      if (v !== (slots[i][name] || "")) put(i, { ...slots[i], [name]: v });
    };
    const day = (i) => (e) => {       // the date is typed as DD-MM-YYYY, as Key dates takes it: clark's own way, never the browser's calendar
      const el = e.currentTarget, raw = el.value.trim(), iso = raw ? parseDay(raw) : "";
      if (raw && !iso) { el.value = dateWords(slots[i].asof); return; }       // not a day: the old one comes back
      if (iso !== (slots[i].asof || "")) put(i, { ...slots[i], asof: iso });
    };
    return (
      <div class="tpl-edit" data-edit-only="" data-template={type}>
        {shown.length ? <FigureRow list={shown} type={type} count={places} /> : <><StartPrompt id={type === "figures4" ? "numbers" : "figures-3"} /><p class="quiet">Nothing to show yet. Fill in a figure below, or choose a live one.</p></>}
        {type === "figures4" ? (
          <div class="cb-grp" role="radiogroup" aria-label="How many numbers" data-count="">
            {COUNTS.map((n) => (
              <button type="button" role="radio" class="cb-btn" key={n} aria-checked={places === n ? "true" : "false"} onClick={() => places !== n && recount(n)}>{n}</button>
            ))}
          </div>
        ) : null}
        <div class={`tpl-slots n${places}`}>
          {slots.slice(0, places).map((s, i) => (
            <fieldset class="tpl-slot" key={i} data-slot={i}>
              <legend>{`Number ${i + 1}`}</legend>
              <div class="cb-grp" role="radiogroup" aria-label={`Number ${i + 1} source`} data-source="">
                <button type="button" role="radio" class="cb-btn" aria-checked={s.mode === "live" ? "false" : "true"} onClick={() => s.mode === "live" && mode(i, "typed")}>Typed</button>
                <button type="button" role="radio" class="cb-btn" disabled={!(offered.length || s.mode === "live")} aria-checked={s.mode === "live" ? "true" : "false"} onClick={() => s.mode !== "live" && mode(i, "live")}>Live</button>
              </div>
              {s.mode === "live" ? (
                <label>Figure
                  <select aria-label={`Number ${i + 1} live figure`} value={s.metric} onChange={(e) => put(i, { mode: "live", metric: e.currentTarget.value })}>
                    {METRICS.filter(([k]) => s.metric === k || offered.some(([o]) => o === k)).map(([k, name]) => <option value={k} key={k}>{name}</option>)}
                  </select>
                </label>
              ) : (
                <>
                  <label>Label<input type="text" key={`l${i}-${s.label}`} maxLength={LIMITS.label} defaultValue={s.label} aria-label={`Number ${i + 1} label`} onChange={field(i, "label")} /></label>
                  <label>Number<input type="text" key={`v${i}-${s.value}`} maxLength={LIMITS.value} defaultValue={s.value} aria-label={`Number ${i + 1} number`} onChange={field(i, "value")} /></label>
                  <label>Note<input type="text" key={`d${i}-${s.detail}`} maxLength={LIMITS.detail} defaultValue={s.detail} aria-label={`Number ${i + 1} note`} onChange={field(i, "detail")} /></label>
                  <label>As of<input type="text" key={`a${i}-${s.asof}`} inputMode="numeric" placeholder="DD-MM-YYYY" defaultValue={dateWords(s.asof)} aria-label={`Number ${i + 1} as of, DD-MM-YYYY`} onBlur={day(i)} /></label>
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
