// The Dashboard (#65): the report's sections (At a glance and the use case summary among them, #45), in the order clark keeps them (data.report_sections, by sort_order then id).
// View removes, never hides: it draws only the sections that show (a hidden one is dropped) and renders no edit component at all,
// so there is no input, text area, select, editable text, grip, menu or Add in the page. Edit (a page clark serves, with
// `tools` from edit/) draws every section, a hidden one dimmed, with those parts. A published file passes no tools and is never Edit.
import { data, mode, fromFile, dropAt } from "../stores/report.js";
import { Section } from "./Section.jsx";
import { Minimap } from "./Minimap.jsx";
import { scrollTargets, entries, countOf } from "../logic/minimap.js";
import { todayIso } from "../workItems.js";
import { slots as slotsOf } from "../logic/placement.js";
import { emptyBody } from "../logic/emptyBody.js";
export { emptyBody };

// A section set beside the next one shares its row with it (half width each); every other section takes the full row. The rows
// are read from ALL the sections, then the hidden ones are left out, so a pair with one half hidden shows the other full width and
// the sections either side never pair (#95).
export function slots(all, keep) {
  const at = slotsOf(all, keep);
  return all.filter((s) => at[s.id]).map((s) => at[s.id]);
}

// Scroll so a section's top sits just under the sticky top bar (the minimap's click). Never a #link: the address is left alone.
function topBarHeight() {
  const bar = document.querySelector(".top");
  return bar ? Math.round(bar.getBoundingClientRect().height) : 0;
}
function jumpTo(anchor) {
  const el = document.getElementById(anchor);
  if (!el) return;
  const top = el.getBoundingClientRect().top + window.scrollY;
  const at = scrollTargets([{ id: anchor, top }], topBarHeight(), 12)[anchor];
  window.scrollTo(0, at);
  el.focus({ preventScroll: true });
}

export function Dashboard({ tools }) {
  const d = data.value;
  const editing = !!(tools && tools.Gutter) && mode.value === "edit" && !fromFile.value;
  const all = d.report_sections || [];
  // does not draw yet (only text bodies are drawn, #74). Rows are read from every section first (#95), so a section whose partner
  // is left out takes the full row and never pairs with the next one. The page clark serves is unchanged.
  // The file draws a text section with a body, the At a glance section when it carries tiles and the use case summary when it
  // carries use cases (#45); the other types are left out until they are drawn.
  const fileDraws = (s) => (s.type === "text" ? !emptyBody(s.body) : s.type === "glance" ? !!(d.glance && d.glance.tiles && d.glance.tiles.length) : s.type === "usecases" ? !!(d.use_cases && d.use_cases.length) : false);
  const shown = (s) => !s.hidden && !(fromFile.value && !fileDraws(s));
  const list = editing ? all : all.filter(shown);
  const places = slots(all, editing ? undefined : shown);
  const emptyWhy = editing ? "This report has no sections yet. Add the first one below." : all.length ? (fromFile.value ? "This report has no sections." : "Every section of this report is hidden. Switch to Edit to show them.") : fromFile.value ? "This report has no sections." : "This report has no sections yet. Switch to Edit to add one.";
  const anchors = {};
  for (const e of entries(list)) anchors[e.id] = e.anchor;      // one anchor per section, shared with the minimap
  const counts = {};
  for (const s of list) { const c = countOf(s, d, todayIso(), fromFile.value); if (c) counts[s.id] = c; }
  const jump = (id) => { if (anchors[id]) jumpTo(anchors[id]); };
  return (
    <section class="frame report" id="report" data-mode={editing ? "edit" : "view"}>
      <p class="crumbs">{d.project.client_name || "Report"}</p>
      <h1>{d.project.name}</h1>
      {list.length === 0 ? <p class="muted" id="no-sections">{emptyWhy}</p> : null}
      <div class={`secs${editing && dropAt.value && dropAt.value.line === "end" ? " drop-end" : ""}`}>
        {list.map((s, i) => <Section key={s.id} section={s} index={i} count={list.length} slot={places[i]} anchor={anchors[s.id]} tools={editing ? tools : null} clean={!fromFile.value && tools ? tools.clean : null} />)}
      </div>
      {editing && list.length === 0 ? <tools.Add /> : null}
      <Minimap sections={list} onJump={jump} stickyHeight={topBarHeight()} counts={counts} />
    </section>
  );
}
