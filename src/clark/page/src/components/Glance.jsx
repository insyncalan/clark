// The At a glance section (#45): Project health (a pill and the reason, two tile widths) and the tiles after it, in the order, with
// the outline and the hidden flags that glance_tiles holds. View leaves a hidden tile out; Edit draws it dimmed with its controls
// (`tools.glance`, edit/GlanceEdit.jsx). A published file draws the figures the file carries (data.glance, worked out at publish
// time from the rows the file keeps); its tiles that count work items open the file's Work items filtered (row 1112), read only. No control.
import { data, rows, openWork, fromFile, tabs } from "../stores/report.js";
import { todayIso } from "../workItems.js";
import { allTiles, fileTiles } from "../glanceTiles.js";
import { useRef } from "preact/hooks";
import { useSettle } from "../stores/motion.js";
import { HTML_START } from "../logic/richWords.js";

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
  return !t.filter || (file && !tabs.value.includes("work"))      // row 1112: a published file's tile opens its Work items too, when the file has that tab
    ? <div class={`fig rag-${t.rag}`} data-fig={t.key} role="group" aria-label={aria}>{inner}</div>
    : <button type="button" class={`fig go rag-${t.rag}`} data-fig={t.key} onClick={() => openWork(t.filter)} aria-label={`${aria}. Opens Work items showing these`}>{inner}</button>;
}

// The reason as View and a published file draw it (item 1005). An old plain reason is a text node. The editor's HTML is drawn only after a
// cleaner has seen it: a published file's was cleaned at publish (publish.reason_html), and View's goes through `clean` (the page's own
// cleaner; the published page has none and no use for one). Never the stored string as it is.
export function ReasonText({ reason, file, clean }) {
  if (!reason) return null;
  if (!HTML_START.test(reason)) return <span class="hreason">{reason}</span>;
  const html = file ? reason : (clean ? clean(reason) : "");
  return html ? <div class="hreason prose" dangerouslySetInnerHTML={{ __html: html }} /> : null;
}

function Health({ t, tools, editing, clean }) {
  const G = editing ? tools.glance : null, hrow = useRef(null);
  useSettle(hrow, `${t.pill}|${t.value}|${t.reason || ""}`);
  return (
    <div class={`fig health-fig rag-${t.rag}`} data-fig="health">
      <span class="k"><i class="ragdot" aria-hidden="true"></i>Project health{t.word ? <span class="tw">{t.word}</span> : null}</span>   {/* the word sits in the label row at the right; here it is read, as it says what it is */}
      <div class="hrow" ref={hrow}>
        {G ? <G.HealthPill health={data.value.project.health} reason={t.reason} /> : <span class={`pill hpill ${t.pill || "n"}`}>{t.value}</span>}
        {G ? <G.Reason health={data.value.project.health} reason={t.reason} /> : <ReasonText reason={t.reason} file={fromFile.value} clean={clean} />}
      </div>
    </div>
  );
}

export function Glance({ tools, clean }) {
  const d = data.value, editing = !!(tools && tools.glance) && !fromFile.value;
  const list = fromFile.value ? fileTiles(d.glance, d.project) : allTiles(rows.value, todayIso(), d.project, d.glance_tiles).filter((t) => editing || !t.hidden);
  const Wrap = editing ? tools.glance.Cell : Cell;
  const order = list.map((t) => t.key);
  return (
    <>
    <div class="glance" data-glance>
      {list.map((t, i) => (
        <Wrap key={t.key} tile={t} order={order} index={i}>
          {t.key === "health" ? <Health t={{ ...t, pill: d.project.health ? ({ "On track": "g", "At risk": "a", "Off track": "r" })[d.project.health] : "n" }} tools={tools} editing={editing} clean={clean} /> : <Figure t={t} file={fromFile.value} />}
        </Wrap>
      ))}
    </div>
    {editing ? <tools.glance.Hint /> : null}
    </>
  );
}
