// The Key figures templates' Edit part (#96): each place is empty, a typed figure (label, number, a note, an as-of date) or a live one
// (Overdue actions, High risks and issues, Decisions needed: the same figures as the At a glance tiles). A field is saved when it
// is left (or its choice made): one change() each, so one step and one Undo. A figure with a label and no number (or the other way
// round) is saved and waits: the line under it says it stays out of the published page. The preview above is what View shows.
import { StartPrompt } from "../StartPrompt.jsx";
// Row 1263 (one Numbers card, approved mock-up): the count is 3 or 4, the body's own or (an older section, no migration) its type's. In the
// Classic theme the card has the count control "Numbers 3 | 4" and a Typed | Live switch per number; Cards keeps its Edit as it was.
import { change } from "../../stores/changes.js";
import { data } from "../../stores/report.js";
import { todayIso } from "../../workItems.js";
import { FigureRow } from "../../templates/FiguresView.jsx";
import { parseDay } from "../../templates/keydates.js";
import { dateWords } from "../../templates/safe.js";
import { classicTheme } from "../../components/Contents.jsx";
import { COUNTS, METRICS, LIMITS, metricsOffered, slotsOf, bodyOf, figuresOf, countOf, ownCount, liveFigures } from "../../templates/figures.js";

const BLANK = { mode: "typed", label: "", value: "", detail: "", asof: "" };

function save(section, slots, count, type) {
  return change({ op: "update", id: section.id, changes: { body: bodyOf(slots, count, type) }, place: "cell" }, "Figures saved.");
}

// The Typed | Live switch and the count control: two buttons, one pressed (Classic only).
function Seg({ cls, label, items, on, onPick }) {
  return (
    <span class={`num-seg ${cls}`} role="group" aria-label={label}>
      {items.map(([k, name, off]) => <button type="button" key={k} aria-pressed={on === k ? "true" : "false"} disabled={off} onClick={() => on !== k && onPick(k)}>{name}</button>)}
    </span>
  );
}

const lower = (t) => (t ? t.charAt(0).toLowerCase() + t.slice(1) : "");

export function figuresEdit(type) {
  return function Edit({ section }) {
    const classic = classicTheme();
    const count = countOf(section, type), places = count;
    const own = ownCount(section);                   // an older body names no count and is saved without one, as it was
    const slots = slotsOf(section, places);
    while (slots.length < places) slots.push({ ...BLANK });
    const offered = metricsOffered(data.value);      // item 1337: a live figure is offered only while its section is there
    const shown = figuresOf(section, data.value, todayIso(), places);
    const now = classic && slots.some((s) => s.mode === "live") ? liveFigures(data.value, todayIso()) : {};
    const put = (i, one) => save(section, slots.map((s, j) => (j === i ? one : s)), own, type);
    const setCount = (n) => save(section, slotsOf(section, n), n, type);
    const pick = (i, m) => put(i, m === "live" && offered.length ? { mode: "live", metric: offered[0][0] } : { ...BLANK });
    const mode = (i, e) => pick(i, e.currentTarget.value);
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
        {classic ? (
          <div class="num-bar">
            <span class="num-bar-l">Numbers</span>
            <Seg cls="num-count" label="How many numbers" items={COUNTS.map((n) => [n, String(n)])} on={count} onPick={setCount} />
          </div>
        ) : null}
        {shown.length ? <FigureRow list={shown} type={type} count={count} /> : <><StartPrompt id="figures-4" /><p class="quiet">Nothing to show yet. Fill in a figure below, or choose a live one.</p></>}
        <div class={`tpl-slots n${places}`}>
          {slots.map((s, i) => (
            <fieldset class="tpl-slot" key={i} data-slot={i}>
              <legend>{`${classic ? "Number" : "Figure"} ${i + 1}`}</legend>
              {classic ? (
                <Seg cls="num-source" label={`Figure ${i + 1} source`} on={s.mode === "live" ? "live" : "typed"} onPick={(m) => pick(i, m)}
                  items={[["typed", "Typed"], ["live", "Live", !offered.length && s.mode !== "live"]]} />
              ) : (
                <label>Source
                  <select aria-label={`Figure ${i + 1} source`} value={s.mode === "live" ? "live" : "typed"} onChange={(e) => mode(i, e)}>
                    <option value="typed">Typed</option>
                    {offered.length || s.mode === "live" ? <option value="live">Live from the project</option> : null}
                  </select>
                </label>
              )}
              {s.mode === "live" ? (
                <>
                <label>Figure
                  <select aria-label={`Figure ${i + 1} live figure`} value={s.metric} onChange={(e) => put(i, { mode: "live", metric: e.currentTarget.value })}>
                    {METRICS.filter(([k]) => s.metric === k || offered.some(([o]) => o === k)).map(([k, name]) => <option value={k} key={k}>{name}</option>)}
                  </select>
                </label>
                {classic ? (
                  <p class="quiet">Worked out from the project each time.{now[s.metric] ? <> Now: <b>{String(now[s.metric].value)}</b>, {lower(now[s.metric].detail)}.</> : null}</p>
                ) : null}
                </>
              ) : (
                <>
                  <label>Label<input type="text" key={`l${i}-${s.label}`} maxLength={LIMITS.label} defaultValue={s.label} aria-label={`Figure ${i + 1} label`} onChange={field(i, "label")} /></label>
                  <label>Number<input type="text" key={`v${i}-${s.value}`} maxLength={LIMITS.value} defaultValue={s.value} aria-label={`Figure ${i + 1} number`} onChange={field(i, "value")} /></label>
                  <label>Note<input type="text" key={`d${i}-${s.detail}`} maxLength={LIMITS.detail} defaultValue={s.detail} aria-label={`Figure ${i + 1} note`} onChange={field(i, "detail")} /></label>
                  <label>As of<input type="text" key={`a${i}-${s.asof}`} inputMode="numeric" placeholder="DD-MM-YYYY" defaultValue={dateWords(s.asof)} aria-label={`Figure ${i + 1} as of, DD-MM-YYYY`} onBlur={day(i)} /></label>
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
