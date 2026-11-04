// The At a glance section (#45): Project health (a pill and the reason, two tile widths) and the tiles after it, in the order, with
// the outline and the hidden flags that glance_tiles holds. View leaves a hidden tile out; Edit draws it dimmed with its controls
// (`tools.glance`, edit/GlanceEdit.jsx). A published file draws the figures the file carries (data.glance, worked out at publish
// time from the rows the file keeps) and nothing else: no button, no control.
import { data, rows, openWork, fromFile, project } from "../stores/report.js";
import { todayIso } from "../workItems.js";
import { hasReviewDates } from "../filters.js";
import { allTiles, fileTiles, staleTile, staleShown, setStaleShown, STALE } from "../glanceTiles.js";
import { useRef, useState } from "preact/hooks";
import { useSettle } from "../stores/motion.js";

function Cell({ tile, children }) {
  return <div class={`tcell${tile.key === "health" ? " health" : ""}`} data-tile={tile.key}>{children}</div>;
}

function Figure({ t, file }) {
  const inner = (
    <>
      <span class="k"><i class="ragdot" aria-hidden="true"></i>{t.label}</span>
      <span class="vrow">
        <span class="v num">{t.value}</span>
        {t.word ? <span class="tw" aria-hidden="true">{t.word}</span> : null}   {/* beside the figure; the word is in the tile's own label below, so it is not read twice */}
      </span>
      <span class="dd">{t.detail}</span>
    </>
  );
  const aria = `${t.label}: ${t.value}${t.detail ? ", " + t.detail : ""}${t.word ? ". " + t.word : ""}`;
  return file || !t.filter
    ? <div class={`fig rag-${t.rag}`} data-fig={t.key} role="group" aria-label={aria}>{inner}</div>
    : <button type="button" class={`fig go rag-${t.rag}`} data-fig={t.key} onClick={() => openWork(t.filter)} aria-label={`${aria}. Opens Work items showing these`}>{inner}</button>;
}

function Health({ t, tools, editing }) {
  const G = editing ? tools.glance : null, hrow = useRef(null);
  useSettle(hrow, `${t.pill}|${t.value}|${t.reason || ""}`);
  return (
    <div class={`fig health-fig rag-${t.rag}`} data-fig="health">
      <span class="k"><i class="ragdot" aria-hidden="true"></i>Project health{t.word ? <span class="tw">{t.word}</span> : null}</span>   {/* the word sits in the label row at the right; here it is read, as it says what it is */}
      <div class="hrow" ref={hrow}>
        {G ? <G.HealthPill health={data.value.project.health} reason={t.reason} /> : <span class={`pill hpill ${t.pill || "n"}`}>{t.value}</span>}
        {G ? <G.Reason health={data.value.project.health} reason={t.reason} /> : t.reason ? <span class="hreason">{t.reason}</span> : null}
      </div>
    </div>
  );
}

// Not reviewed (item 160): the optional tile after the stored ones. Off by default; the eye in Edit turns it on for this project, in this
// browser. It is offered only where the Freshness filter is (some row carries a date to count from), and never in a published file.
function staleFor(editing, code, shown) {
  if (fromFile.value || !hasReviewDates(rows.value)) return null;
  if (!editing && !shown) return null;
  return { ...staleTile(rows.value, todayIso()), hidden: !shown };
}

export function Glance({ tools }) {
  const d = data.value, editing = !!(tools && tools.glance) && !fromFile.value;
  const code = project.value, [, redraw] = useState(0), shown = staleShown(code);
  const list = fromFile.value ? fileTiles(d.glance, d.project) : allTiles(rows.value, todayIso(), d.project, d.glance_tiles).filter((t) => editing || !t.hidden);
  const Wrap = editing ? tools.glance.Cell : Cell;
  const order = list.map((t) => t.key);       // the stored tiles only: the Not reviewed tile is always last and is not moved
  const stale = staleFor(editing, code, shown);
  const StaleWrap = editing ? tools.glance.StaleCell : Cell;
  const eye = (on) => { setStaleShown(code, on); redraw((n) => n + 1); };
  return (
    <>
    <div class="glance" data-glance>
      {list.map((t, i) => (
        <Wrap key={t.key} tile={t} order={order} index={i}>
          {t.key === "health" ? <Health t={{ ...t, pill: d.project.health ? ({ "On track": "g", "At risk": "a", "Off track": "r" })[d.project.health] : "n" }} tools={tools} editing={editing} /> : <Figure t={t} file={fromFile.value} />}
        </Wrap>
      ))}
      {stale ? <StaleWrap key={STALE} tile={stale} onEye={eye}><Figure t={stale} file={false} /></StaleWrap> : null}
    </div>
    {editing ? <tools.glance.Hint /> : null}
    </>
  );
}
