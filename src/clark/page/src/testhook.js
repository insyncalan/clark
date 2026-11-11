// The browser tests' way into the page (#63, #42): window.clarkPage. Only the test build (main-test.jsx) imports this file, so
// neither the served page nor a published file carries it. `tools` is what Edit adds; Help (#82) is among them.
import { workSelection } from "./stores/selection.js";
import { data, show, openPeek, closePeek, setProject, setFilters, peek, project, f } from "./stores/report.js";
import { markChanged, changed, useClock } from "./stores/changed.js";
import { welcomeHeld } from "./stores/profile.js";
import { openImport } from "./edit/wordState.js";
import { closeAfter, CLOSE_MS } from "./edit/publishState.js";
import { openContext, toggleContext, closeContext, contextOpen, useContextText } from "./help/helpStore.js";

// The finished Publish dialog closes by itself after CLOSE_MS (#437). In the test build it stays open until a test asks, so the many
// tests that read the finished dialog never race its timer; a test that wants the close sets a time with publishCloseMs(ms).
export function install(tools) {
  // #174: the first-run welcome would greet every test that starts on a fresh store; it is held back here unless the test set
  // window.__clarkWelcome before the page loaded (test_welcome.py). The served page has no such hold.
  welcomeHeld.value = !window.__clarkWelcome;
  closeAfter.ms = null;
  // The Help peek (#645): the tests' stand-in for contextText (useText) lives here, in the test build, never in the served page.
  const peekHelp = Object.freeze({ open: openContext, toggle: toggleContext, close: closeContext, isOpen: () => contextOpen.value, useText: useContextText });
  const help = tools && tools.help ? { help: Object.freeze({ open: tools.help.open, close: tools.help.close, isOpen: tools.help.isOpen, peek: peekHelp }) } : {};
  window.clarkPage = Object.freeze({ show, openPeek, closePeek, setProject, setFilters, filters: () => f.value, peek: () => peek.value, project: () => project.value, selected: () => workSelection.ids.value.slice(),
    markChanged, changed: () => changed.value.slice(), useClock,
    openWordImport: () => openImport(),      // row 1063: the profile menu no longer has Import from Word; the box and route stay
    publishCloseMs: (ms) => { if (ms !== undefined) closeAfter.ms = ms; return { now: closeAfter.ms, page: CLOSE_MS }; },
    changeData: (fn) => { data.value = fn(data.value); },      // #970: a test adds or removes a work item as the data being read again does
    showHealth: (health, reason) => { data.value = { ...data.value, project: { ...data.value.project, health, health_reason: reason } }; }, ...help });
}
