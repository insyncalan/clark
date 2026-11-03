// The browser tests' way into the page (#63, #42): window.clarkPage. Only the test build (main-test.jsx) imports this file, so
// neither the served page nor a published file carries it. `tools` is what Edit adds; Help (#82) is among them.
import { workSelection } from "./stores/selection.js";
import { data, show, openPeek, closePeek, setProject, setFilters, peek, project, f } from "./stores/report.js";
import { markChanged, changed, useClock } from "./stores/changed.js";
import { closeAfter, CLOSE_MS } from "./edit/publishState.js";

// The finished Publish dialog closes by itself after CLOSE_MS (#437). In the test build it stays open until a test asks, so the many
// tests that read the finished dialog never race its timer; a test that wants the close sets a time with publishCloseMs(ms).
export function install(tools) {
  closeAfter.ms = null;
  const help = tools && tools.help ? { help: Object.freeze({ open: tools.help.open, close: tools.help.close, isOpen: tools.help.isOpen }) } : {};
  window.clarkPage = Object.freeze({ show, openPeek, closePeek, setProject, setFilters, filters: () => f.value, peek: () => peek.value, project: () => project.value, selected: () => workSelection.ids.value.slice(),
    markChanged, changed: () => changed.value.slice(), useClock,
    publishCloseMs: (ms) => { if (ms !== undefined) closeAfter.ms = ms; return { now: closeAfter.ms, page: CLOSE_MS }; },
    showHealth: (health, reason) => { data.value = { ...data.value, project: { ...data.value.project, health, health_reason: reason } }; }, ...help });
}
