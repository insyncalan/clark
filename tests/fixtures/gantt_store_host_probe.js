// Test-only (tests/test_gantt_page.py): the store host's request builder, run under node, to read what is sent for a new line.
import { lineRequests } from "@src/gantt/logic/ganttStoreHost.js";
import { diff } from "@src/gantt/logic/ganttPage.js";

const line = (id, n) => ({ id, name: `Line ${id}`, type: "task", parent: "", start: "2026-11-02", end: "2026-11-06", pct: 0, health: "", depends: [], owner: "", workstream: "",
  priority: "", baseline_start: "", baseline_end: "", effort: null, budget: null, deliverable: "", show: 0, note: "", sort_order: n });
const before = [line("GNT-001", 1), line("GNT-002", 2), line("GNT-003", 3)];
const after = [before[0], before[1], line("GNT-004", 3), { ...before[2], sort_order: 4 }];
const out = lineRequests("PRJ", before, diff(before, after)).map((make) => make(new Map()).req);
console.log(JSON.stringify(out));
