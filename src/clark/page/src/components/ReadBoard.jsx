// The Work items board for a published report (row 1533), read only. It draws what the editor's board draws (edit/Board.jsx): columns for Group by,
// one level of swimlanes, cards that open the file's peek, a full screen view, and column widths and collapse that are the viewer's own (stores/work.js
// keeps them in memory in a published file). It has no drag, no Move to menu, no card menu, no selection, no eye and no add, and it imports nothing
// that writes (stores/changes.js, api.js): the rules for which column a card is in are logic/board.js's, the same ones the editor uses.
import { useEffect, useRef } from "preact/hooks";
import { item, openPeek } from "../stores/report.js";
import { work, setWork, full, announce, contextFor } from "../stores/work.js";
import { build, boardGroup, isCollapsed, toggleCollapsed, orderedColumns, stepColumn, widthOf, setColumnWidth, clampWidth,
  COL_MIN, COL_MAX, COL_DEFAULT, COL_STEP } from "../logic/board.js";
import { useSettle } from "../stores/motion.js";
import { Icon } from "./Icon.jsx";
import { cursor, stopOf, cardKeys } from "../listKeys.js";

const TONED = ["status", "due", "priority"];
const TYPE_LETTER = { action: "A", risk: "R", issue: "I", assumption: "S", dependency: "P", decision: "D" };
export const LANE_WORDS = { workstream: "Workstream", type: "Type" };

function ColCount({ n }) {
  const ref = useRef(null);
  useSettle(ref, n);
  return <span class="cn num" ref={ref}>{n}</span>;
}

function Card({ card, stop, pos, size, selected }) {
  const label = `${card.id} ${card.title}, ${card.state.text}${card.due.words ? ", " + card.due.words.toLowerCase() : ""}`;
  const open = () => openPeek(card.id, "item");
  return (
    <article aria-posinset={pos} aria-setsize={size} class={`bcard k-${card.typeClass.slice(2)}${selected ? " sel" : ""}${card.open ? "" : " done"}`} data-id={card.id} data-kind={card.typeClass.slice(2)}>
      <div class="bc-main" role="button" tabIndex={stop ? 0 : -1} data-cursor={card.id} aria-label={label}
        onClick={open} onFocus={() => { cursor.value = card.id; }}
        onKeyDown={(e) => {
          if (e.target !== e.currentTarget) return;
          if (e.key === "Enter" && !e.shiftKey && !e.metaKey && !e.ctrlKey && !e.altKey) { e.preventDefault(); open(); return; }
          cardKeys(e);
        }}>
        <div class="bc-top"><span class={`type tl ${card.typeClass}`} role="img" aria-label={card.type} title={card.type}>{TYPE_LETTER[card.typeClass.slice(2)] || card.type.charAt(0)}</span><span class="bc-id num">{card.id}</span></div>
        <div class="bc-title">{card.title}</div>
        <div class="bc-foot">
          {card.initials ? <span class="av" title={card.owner} aria-hidden="true">{card.initials}</span> : null}
          {card.due.words ? <span class={`due-l${card.due.tone ? " " + card.due.tone : ""}`}>{card.due.words}</span> : null}
          <span class={`pill ${card.state.class}`}>{card.state.text}</span>
        </div>
      </div>
    </article>
  );
}

export function ReadBoard({ rows, today, type }) {
  const st = work.value, g = boardGroup(st.group);
  const b = build(rows, { group: g, lane: st.lane, ctx: contextFor(today, type) });
  const fsBtn = useRef(null);
  const isFull = full.value;
  // Full screen is a class on the body; Esc leaves it unless the peek or a menu is open (they take their own Esc first).
  useEffect(() => {
    document.body.classList.toggle("board-full", isFull);
    if (!isFull) return undefined;
    const esc = (e) => {
      if (e.key !== "Escape" || e.defaultPrevented) return;
      if (document.querySelector("[data-peek], .ddmenu:not(.leaving), .fbox:not(.leaving)")) return;
      leave(true);
    };
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, [isFull]);
  useEffect(() => { document.body.classList.add("board-view"); return () => { document.body.classList.remove("board-view", "board-full"); full.value = false; }; }, []);
  function leave(refocus) {
    full.value = false; announce.value = "Full screen off.";
    if (refocus) setTimeout(() => { if (fsBtn.current) fsBtn.current.focus(); }, 0);
  }
  const toggleFull = () => { if (isFull) leave(false); else { full.value = true; announce.value = "Full screen on."; } };
  const colsOf = (ln) => orderedColumns(work.value, g, ln.columns);
  const setWidth = (c, w) => setWork(setColumnWidth(work.value, g, c.key, w));
  const sayWidth = (c, w) => { announce.value = w === COL_DEFAULT ? "Column width reset." : `${c.label} column ${w} pixels wide.`; };
  const sepDown = (e, c) => {
    if (e.button !== 0) return;
    e.preventDefault(); e.stopPropagation();
    const col = e.currentTarget.closest(".col"), x0 = e.clientX, w0 = col.getBoundingClientRect().width;
    document.body.classList.add("col-resizing");
    const move = (ev) => setWidth(c, w0 + ev.clientX - x0);
    const off = () => { document.body.classList.remove("col-resizing"); document.removeEventListener("pointermove", move, true); document.removeEventListener("pointerup", off, true); document.removeEventListener("pointercancel", off, true); };
    document.addEventListener("pointermove", move, true); document.addEventListener("pointerup", off, true); document.addEventListener("pointercancel", off, true);
  };
  const sepKey = (e, c) => {
    const now = widthOf(work.value, g, c.key) || COL_DEFAULT;
    let w = null;
    if (e.key === "ArrowRight") w = now + COL_STEP; else if (e.key === "ArrowLeft") w = now - COL_STEP;
    else if (e.key === "Home") w = COL_MIN; else if (e.key === "End") w = COL_MAX; else if (e.key === "Enter") w = COL_DEFAULT;
    if (w === null) return;
    e.preventDefault(); w = clampWidth(w); setWidth(c, w); sayWidth(c, w);
  };
  // Alt+Left and Alt+Right move a column in the viewer's own layout (never saved to the file).
  const headKey = (e, c, ln) => {
    if (!e.altKey || e.ctrlKey || e.metaKey || (e.key !== "ArrowLeft" && e.key !== "ArrowRight")) return;
    e.preventDefault();
    const dir = e.key === "ArrowLeft" ? -1 : 1, r = stepColumn(work.value, g, ln.columns, c.key, dir);
    if (!r.moved) { announce.value = `${c.label} is already the ${dir < 0 ? "first" : "last"} column.`; return; }
    setWork(r.state); announce.value = `${c.label} moved to place ${r.index} of ${r.count}.`;
    setTimeout(() => { const el = document.querySelector(`.lane[data-lane="${CSS.escape(ln.key == null ? "" : ln.key)}"] .col[data-col="${CSS.escape(c.key)}"] .col-b`); if (el) el.focus(); }, 0);
  };
  const toned = TONED.includes(g), peeked = item.value;
  const drawn = [];
  b.lanes.forEach((ln) => ln.columns.forEach((c) => { if (!isCollapsed(st, g, c.key)) c.cards.forEach((cd) => drawn.push(cd.id)); }));
  const stopId = stopOf(drawn);
  return (
    <div class="board" id="work-board" data-full={isFull ? "1" : "0"} data-editing="0" data-readonly="1">
      <div class="lanebar" role="group" aria-label="Board view">
        <button type="button" class="bib fs" id="board-full" ref={fsBtn} aria-pressed={isFull ? "true" : "false"} aria-label={isFull ? "Leave full screen" : "View full screen"}
          data-tip={isFull ? "Leave full screen (Esc)" : "View full screen"} onClick={toggleFull}>
          <Icon name={isFull ? "arrows-in" : "arrows-out"} />
        </button>
      </div>
      <div class="boardbox" role="region" aria-label="Work items board">
        {b.lanes.map((ln) => (
          <div class={`lane${b.lane ? " has" : ""}`} key={ln.key == null ? "all" : ln.key} data-lane={ln.key == null ? "" : ln.key}>
            {b.lane ? <div class="lane-h" role="heading" aria-level="3"><span class="lh-in"><span class="ll">{ln.label}</span><span class="lc num">{ln.count}</span></span></div> : null}
            <div class="cols">
              {colsOf(ln).map((c) => {
                const shut = isCollapsed(st, g, c.key), wd = widthOf(st, g, c.key);
                const tone = toned && c.tone ? ` tone-${c.tone}` : "";
                return (
                  <section class={`col${shut ? " shut" : ""}${tone}`} key={c.key}
                    style={wd && !shut ? { flexBasis: wd + "px", width: wd + "px" } : undefined}
                    data-cell="1" data-col={c.key} data-lane={ln.key == null ? "" : ln.key} data-count={c.count} aria-label={`${c.label}, ${c.count}`}>
                    <h4 class="col-h">
                      <button type="button" class="col-b" aria-expanded={shut ? "false" : "true"} aria-label={`${c.label}, ${c.count}${shut ? ", collapsed" : ""}`} data-toggle={c.key}
                        aria-keyshortcuts="Alt+ArrowLeft Alt+ArrowRight" onKeyDown={(e) => headKey(e, c, ln)} onClick={() => setWork(toggleCollapsed(work.value, g, c.key))}>
                        <span class="dot" aria-hidden="true"></span><span class="cl">{c.label}</span><ColCount n={c.count} />
                      </button>
                      {shut ? null : <span class="col-rz" role="separator" tabIndex={0} aria-orientation="vertical" data-resize={c.key}
                        aria-label={`Resize the ${c.label} column`} aria-valuemin={COL_MIN} aria-valuemax={COL_MAX} aria-valuenow={wd || COL_DEFAULT}
                        aria-keyshortcuts="ArrowLeft ArrowRight Home End Enter" title="Drag to resize; double-click for the usual width"
                        onPointerDown={(e) => sepDown(e, c)} onKeyDown={(e) => sepKey(e, c)} onDblClick={() => { setWidth(c, COL_DEFAULT); sayWidth(c, COL_DEFAULT); }} />}
                    </h4>
                    {shut ? null : (
                      <div class="col-body">
                        {c.cards.length === 0 ? <p class="muted none">Nothing here</p>
                          : c.cards.map((cd) => <div key={cd.id} class="bwrap"><Card card={cd} stop={cd.id === stopId} pos={drawn.indexOf(cd.id) + 1} size={drawn.length} selected={peeked === cd.id} /></div>)}
                      </div>
                    )}
                  </section>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
