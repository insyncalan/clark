// The browser tests' way into the page (#63, #42): window.clarkPage. Only the test build (main-test.jsx) imports this file, so
// neither the served page nor a published file carries it. `tools` is what Edit adds; Help (#82) is among them.
import { workSelection } from "./stores/selection.js";
import { data, show, openPeek, closePeek, setProject, setFilters, peek, project, f } from "./stores/report.js";
import { markChanged, changed, useClock } from "./stores/changed.js";

export function install(tools) {
  const help = tools && tools.help ? { help: Object.freeze({ open: tools.help.open, close: tools.help.close, isOpen: tools.help.isOpen }) } : {};
  window.clarkPage = Object.freeze({ show, openPeek, closePeek, setProject, setFilters, filters: () => f.value, peek: () => peek.value, project: () => project.value, selected: () => workSelection.ids.value.slice(),
    markChanged, changed: () => changed.value.slice(), useClock,
    showHealth: (health, reason) => { data.value = { ...data.value, project: { ...data.value.project, health, health_reason: reason } }; }, ...help });
}
