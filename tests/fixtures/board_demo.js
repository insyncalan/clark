// Test-only (tests/test_board.py): the board's pure logic on a bare page, never part of clark's bundle.
import * as board from "@src/logic/board.js";
import * as dragCore from "@src/logic/dragCore.js";
window.T = { board, dragCore };

// Every move the logic can be asked for, over every row, grouping and column (and a lane): [{id, group, key, lane, result}], a
// date being finished with the suggested one. The tests replay each accepted request against a real store.
T.sweep = (data, project, today, me) => {
  const rows = board.rowsFor(data), ctx = board.ctxFor(data, { project, today, me });
  const out = [];
  const finish = (r) => (r.ok && r.needsDate ? board.dateMove(r, r.needsDate.suggested, today) : r);
  for (const row of rows) {
    for (const g of board.GROUPS.map((x) => x.id).filter((x) => x !== "nothing")) {
      const cols = board.columnsFor(g, rows, ctx);
      const from = { group: g, key: board.cellOf(g, row, ctx), lane: null };
      for (const c of cols) out.push({ id: row.id, group: g, key: c.key, lane: null, result: finish(board.moveFor(row, from, { group: g, key: c.key, lane: null }, ctx)) });
      for (const lg of board.LANE_GROUPS.filter((x) => x !== g)) {
        const lanes = board.columnsFor(lg, rows, ctx), lk = board.cellOf(lg, row, ctx);
        const fromL = { group: g, key: from.key, lane: { group: lg, key: lk } };
        for (const ln of lanes) {
          for (const c of [cols.find((x) => x.key === from.key), cols[0], cols[cols.length - 1]].filter(Boolean)) {
            const to = { group: g, key: c.key, lane: { group: lg, key: ln.key } };
            out.push({ id: row.id, group: g, key: c.key, lane: to.lane, result: finish(board.moveFor(row, fromL, to, ctx)) });
          }
        }
      }
    }
  }
  return out;
};
