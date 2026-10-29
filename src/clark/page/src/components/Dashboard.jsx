// The Dashboard (#65): the counts as they were (until the At a glance section is drawn, #45), then the report's sections, in the order clark keeps them (data.report_sections, by sort_order then id).
// View removes, never hides: it draws only the sections that show (a hidden one is dropped) and renders no edit component at all,
// so there is no input, text area, select, editable text, handle, options menu or Add in the page. Edit (a page clark serves, with
// `tools` from edit/) draws every section, a hidden one dimmed, with those parts. A published file passes no tools and is never Edit.
import { data, counts, mode, fromFile, dropAt, rows, openWork } from "../stores/report.js";
import { todayIso } from "../workItems.js";
import { tiles, HEALTH_WORDS } from "../glanceTiles.js";
import { Section } from "./Section.jsx";
import { slots as slotsOf } from "../logic/placement.js";

// A section set beside the next one shares its row with it (half width each); every other section takes the full row. The rows
// are read from ALL the sections, then the hidden ones are left out, so a pair with one half hidden shows the other full width and
// the sections either side never pair (#95).
export function slots(all, keep) {
  const at = slotsOf(all, keep);
  return all.filter((s) => at[s.id]).map((s) => at[s.id]);
}

// A text section's body with nothing to read (#74): no letters once tags and spaces are gone (a non-breaking space is a space) and
// no picture. `<p></p>`, `<br>`, `&nbsp;` or spaces alone are empty. The body is the HTML publish.clean_html already cleaned; it
// is parsed as an inert document (nothing in it runs or loads) only to read its text.
export function emptyBody(html) {
  if (typeof html !== "string" || !html.trim()) return true;
  const doc = new DOMParser().parseFromString(html, "text/html");
  return !doc.body.textContent.trim() && !doc.body.querySelector("img");
}

export function Dashboard({ tools }) {
  const d = data.value;
  const editing = !!(tools && tools.Handle) && mode.value === "edit" && !fromFile.value;
  const all = d.report_sections || [];
  // does not draw yet (only text bodies are drawn, #74). Rows are read from every section first (#95), so a section whose partner
  // is left out takes the full row and never pairs with the next one. The page clark serves is unchanged.
  const shown = (s) => !s.hidden && !(fromFile.value && (s.type !== "text" || emptyBody(s.body)));
  const list = editing ? all : all.filter(shown);
  const places = slots(all, editing ? undefined : shown);
  const emptyWhy = editing ? "This report has no sections yet. Add the first one below." : all.length ? (fromFile.value ? "This report has no sections." : "Every section of this report is hidden. Switch to Edit to show them.") : fromFile.value ? "This report has no sections." : "This report has no sections yet. Switch to Edit to add one.";
  return (
    <section class="frame report" id="report" data-mode={editing ? "edit" : "view"}>
      <p class="crumbs">{d.project.client_name || "Report"}</p>
      <h1>{d.project.name}</h1>
      {fromFile.value ? (
        <div class="glance">
          <div class="tile"><span class="n num">{counts.value.work}</span><span class="l">Work items</span></div>
          <div class="tile"><span class="n num">{counts.value.milestones}</span><span class="l">Milestones</span></div>
          <div class="tile"><span class="n">{d.project.health || "Not set"}</span><span class="l">Health</span></div>
        </div>
      ) : <Glance d={d} />}
      {list.length === 0 ? <p class="muted" id="no-sections">{emptyWhy}</p> : null}
      <div class={`secs${editing && dropAt.value && dropAt.value.line === "end" ? " drop-end" : ""}`}>
        {list.map((s, i) => <Section key={s.id} section={s} index={i} count={list.length} slot={places[i]} tools={editing ? tools : null} />)}
      </div>
      {editing && list.length === 0 ? <tools.Add after={null} /> : null}
    </section>
  );
}

// At a glance (#79): Project health takes the room the other tiles leave (they sit at the right); each other tile is a button that
// opens Work items filtered to exactly what it counts. A tile with nothing to count is still drawn, so the row never jumps.
function Glance({ d }) {
  const health = d.project.health, rag = HEALTH_WORDS[health] || "n";
  return (
    <div class="glance" data-glance>
      <div class="fig health-fig" data-fig="health">
        <span class="k">Project health</span>
        <div class="hrow"><span class={`pill ${rag}`}>{health || "Not set"}</span>{d.project.health_reason ? <span class="hreason">{d.project.health_reason}</span> : null}</div>
      </div>
      {tiles(rows.value, todayIso()).map((t) => (
        <button type="button" class={`fig go rag-${t.rag}`} key={t.key} data-fig={t.key} onClick={() => openWork(t.filter)}
          aria-label={`${t.label}: ${t.value}, ${t.detail}. Open the list`}>
          <span class="k"><i class="ragdot" aria-hidden="true"></i>{t.label}</span>
          <span class="v num">{t.value}</span>
          <span class="dd">{t.detail}</span>
        </button>
      ))}
    </div>
  );
}
