// The Dashboard (#65): the report's sections (At a glance and the use case summary among them, #45), in the order clark keeps them (data.report_sections, by sort_order then id).
// View removes, never hides: it draws only the sections that show (a hidden one is dropped) and renders no edit component at all,
// so there is no input, text area, select, editable text, grip, menu or Add in the page. Edit (a page clark serves, with
// `tools` from edit/) draws every section, a hidden one dimmed, with those parts. A published file passes no tools and is never Edit.
import { useEffect, useLayoutEffect, useRef } from "preact/hooks";
import { armHint } from "../stores/motion.js";
import { data, mode, fromFile, dropAt, rebuilt } from "../stores/report.js";
import { Section } from "./Section.jsx";
import { Minimap } from "./Minimap.jsx";
import { scrollTargets, entries, countOf } from "../logic/minimap.js";
import { todayIso } from "../workItems.js";
import { coverLine } from "../logic/cover.js";
import { Cover } from "./Cover.jsx";
import { slots as slotsOf } from "../logic/placement.js";
import { emptyBody } from "../logic/emptyBody.js";
export { emptyBody };
import { templateFor, templateEmpty } from "../templates/index.js";
import { rowsFor } from "./ItemRows.jsx";
import { KINDS } from "../logic/sectionRows.js";
import { milestoneRows } from "../logic/milestones.js";
import { visibleDocs } from "../logic/documents.js";

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

// Row 679 and row 756: View and Edit draw different heights (Edit adds rows, fields and left-out sections), so the switch keeps the section the
// person is reading where it was: the first one with a real strip of itself (MIN_SEEN) below the top bar. The one nearest the bar by its
// bottom edge was wrong whenever only a thin tail of it showed above the next section: that tail was held, and the section being read
// moved by whatever the tail gained in Edit. When no section shows that much, the one that shows most. Read while the old DOM is still
// up (the render before the commit), put back before the paint.
const MIN_SEEN = 64;
function nearestTop() {
  const bar = document.querySelector(".top");
  const line = bar ? bar.getBoundingClientRect().bottom : 0;
  let best = null;
  let most = 0;
  let below = null;
  for (const el of document.querySelectorAll(".secs > .sec:not(.is-hidden)")) {
    const r = el.getBoundingClientRect();
    const seen = Math.min(r.bottom, window.innerHeight) - Math.max(r.top, line);
    if (seen >= MIN_SEEN) return { id: el.dataset.id, top: r.top };
    if (seen > most) { most = seen; best = { id: el.dataset.id, top: r.top }; }
    if (!below && r.top >= line) below = { id: el.dataset.id, top: r.top };
  }
  // Row 699: a dimmed (hidden) section can fill the screen, and View drops it. Then hold the first section that stays, even below the fold.
  return best || below;
}

export function Dashboard({ tools }) {
  const d = data.value;
  const editing = !!(tools && tools.Gutter) && mode.value === "edit" && !fromFile.value;
  const was = useRef({ editing, at: null });
  if (was.current.editing !== editing) was.current = { editing, at: nearestTop() };
  useLayoutEffect(() => {
    const at = was.current.at;
    was.current.at = null;
    const el = at && document.querySelector(`.secs > .sec[data-id="${CSS.escape(at.id)}"]`);
    if (el) window.scrollBy(0, el.getBoundingClientRect().top - at.top);
  }, [editing]);
  const all = (d.report_sections || []).filter((s) => s.type !== "needs");      // item 1158: a Needs from you section already on a dashboard stops showing (it stays stored); nothing else is changed
  // does not draw yet (only text bodies are drawn, #74). Rows are read from every section first (#95), so a section whose partner
  // is left out takes the full row and never pairs with the next one. The page clark serves is unchanged.
  // The file draws a text section with a body, the At a glance section when it carries tiles and the use case summary when it
  // carries use cases (item 45), Risks and issues, Open actions and Decisions only when they have a row to show (A-D5: an empty one is left out of the file, heading and all; View says it has nothing to show); the other types are left out until they are drawn.
  // A section template (#96) is drawn in the file and in the served View alike only while it has something to show (its isEmpty,
  // FR-11: View is what the client sees), so an empty template or a stub is in neither.
  const fileDraws = (s) => (templateFor(s.type) ? !templateEmpty(s, d) : s.type === "text" ? !emptyBody(s.body) : s.type === "glance" ? !!(d.glance && d.glance.tiles && d.glance.tiles.length) : s.type === "usecases" ? !!(d.use_cases && d.use_cases.length) : s.type === "docs" ? visibleDocs(d, true).length > 0 : s.type === "tracker" ? true : s.type === "milestones" ? milestoneRows(d.milestones, todayIso(), true).length > 0 : !!KINDS[s.type] && rowsFor(s.type).length > 0);
  const shown = (s) => !s.hidden && !(fromFile.value && !fileDraws(s)) && !(templateFor(s.type) && templateEmpty(s, d)) && !(s.type === "docs" && !visibleDocs(d, fromFile.value).length);       // #74: no document to show, no section
  const list = editing ? all : all.filter(shown);
  const places = slots(all, editing ? undefined : shown);
  const emptyWhy = editing ? "This report has no sections yet. Add the first one below." : all.length ? (fromFile.value ? "This report has no sections." : "Every section of this report is hidden. Switch to Edit to show them.") : fromFile.value ? "This report has no sections." : "This report has no sections yet. Switch to Edit to add one.";
  const anchors = {};
  for (const e of entries(list)) anchors[e.id] = e.anchor;      // one anchor per section, shared with the minimap
  const counts = {};
  for (const s of list) { const c = countOf(s, d, todayIso(), fromFile.value); if (c) counts[s.id] = c; }
  const first = editing && list.length ? list[0].id : null;
  useEffect(() => { if (first) armHint(first); }, [first]);      // the first time in Edit, the handle of the first section pulses once and says what it does
  const jump = (id) => { if (anchors[id]) jumpTo(anchors[id]); };
  const Bar = tools && tools.ReportBar && !fromFile.value ? tools.ReportBar : null;      // a page clark serves only (A-D2)
  return (
    <>
    {Bar ? <Bar /> : null}
    <section class={`frame report${rebuilt.value ? " asat-frame" : ""}`} id="report" data-mode={editing ? "edit" : "view"} inert={rebuilt.value ? true : undefined}>{/* item 349: as at a day, nothing in it can be focused or clicked */}
      {fromFile.value ? null : <Cover title={d.project.name} lines={coverLine(d.project, rebuilt.value ? "" : todayIso())} Switch={tools && tools.ProjectSwitch ? tools.ProjectSwitch : null} />}      {/* issue 1146: a published file shows these words in its one top bar */}
      {list.length === 0 ? <p class="muted" id="no-sections">{emptyWhy}</p> : null}
      <div class={`secs${editing && dropAt.value && dropAt.value.line === "end" ? " drop-end" : ""}`}>
        {list.map((s, i) => <Section key={s.id} section={s} index={i} count={list.length} slot={places[i]} anchor={anchors[s.id]} tools={editing ? tools : null} clean={!fromFile.value && tools ? tools.clean : null} />)}
      </div>
      {editing && list.length === 0 ? <tools.Add /> : null}
      <Minimap sections={list} onJump={jump} stickyHeight={topBarHeight()} counts={counts} />
    </section>
    </>
  );
}
