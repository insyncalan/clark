// Test-only (tests/test_pair_widths_1214.py): the real placement logic on a bare page that carries the page's own shell.css, so the grid
// is the real grid. The sections are drawn with the slot classes placement gives; the rectangles are read from the browser; the columns
// value is read by the very expression the page's drag uses (the test copies it out of src/clark/page/src/edit/drag.js into columnsNow).
import * as placement from "@src/logic/placement.js";

const HEIGHT = 120;

function draw(list) {
  const host = document.getElementById("root");
  host.textContent = "";
  const grid = document.createElement("div");
  grid.className = "secs";
  const slot = placement.slots(list);
  for (const s of list) {
    const el = document.createElement("section");
    el.className = "sec slot-" + slot[s.id];
    el.dataset.id = s.id;
    el.style.height = HEIGHT + "px";
    el.textContent = s.title;
    grid.appendChild(el);
  }
  host.appendChild(grid);
}

function rects() {
  const out = {};
  for (const el of document.querySelectorAll(".secs > .sec[data-id]")) {
    const r = el.getBoundingClientRect();
    out[el.dataset.id] = { left: r.left, top: r.top, right: r.right, bottom: r.bottom, width: r.width };
  }
  return out;
}

const rowsOf = (list) => placement.rows(list).map((r) => r.map((s) => s.id));

// Draw `list`; the pointer is at fraction (fx, fy) of section `at`; `id` is dragged. Gives what the page would offer and, when it is
// dropped, the rows and the widths drawn after it.
function probe(list, id, at, fx, fy) {
  draw(list);
  const before = rects();
  const r = before[at];
  const point = { x: r.left + (r.right - r.left) * fx, y: r.top + (r.bottom - r.top) * fy };
  const columns = window.columnsNow();
  const target = placement.targetAt(list, id, before, point, { columns });
  const drop = target && placement.place(list, id, target);
  let after = null, rows = null;
  if (drop && drop.ok) {
    const next = placement.applied(list, drop.payload);
    draw(next);
    after = rects();
    rows = rowsOf(next);
  }
  return { columns, target, rows, before, after, ok: !!(drop && drop.ok) };
}

window.T = { placement, draw, rects, probe, innerWidth: () => window.innerWidth };
