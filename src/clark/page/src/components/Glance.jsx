// The At a glance section (#45): Project health (a pill and the reason, two tile widths) and the tiles after it, in the order, with
// the outline and the hidden flags that glance_tiles holds. View leaves a hidden tile out; Edit draws it dimmed with its controls
// (`tools.glance`, edit/GlanceEdit.jsx). A published file draws the figures the file carries (data.glance, worked out at publish
// time from the rows the file keeps) and nothing else: no button, no control.
import { data, rows, openWork, fromFile } from "../stores/report.js";
import { todayIso } from "../workItems.js";
import { allTiles, fileTiles } from "../glanceTiles.js";

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
  const G = editing ? tools.glance : null;
  return (
    <div class={`fig health-fig rag-${t.rag}`} data-fig="health">
      <span class="k"><i class="ragdot" aria-hidden="true"></i>Project health{t.word ? <span class="tw">{t.word}</span> : null}</span>   {/* the word sits in the label row at the right; here it is read, as it says what it is */}
      <div class="hrow">
        {G ? <G.HealthPill health={data.value.project.health} reason={t.reason} /> : <span class={`pill hpill ${t.pill || "n"}`}>{t.value}</span>}
        {G ? <G.Reason health={data.value.project.health} reason={t.reason} /> : t.reason ? <span class="hreason">{t.reason}</span> : null}
      </div>
    </div>
  );
}

export function Glance({ tools }) {
  const d = data.value, editing = !!(tools && tools.glance) && !fromFile.value;
  const list = fromFile.value ? fileTiles(d.glance, d.project) : allTiles(rows.value, todayIso(), d.project, d.glance_tiles).filter((t) => editing || !t.hidden);
  const Wrap = editing ? tools.glance.Cell : Cell;
  const order = list.map((t) => t.key);
  return (
    <div class="glance" data-glance>
      {list.map((t, i) => (
        <Wrap key={t.key} tile={t} order={order} index={i}>
          {t.key === "health" ? <Health t={{ ...t, pill: d.project.health ? ({ "On track": "g", "At risk": "a", "Off track": "r" })[d.project.health] : "n" }} tools={tools} editing={editing} /> : <Figure t={t} file={fromFile.value} />}
        </Wrap>
      ))}
    </div>
  );
}
