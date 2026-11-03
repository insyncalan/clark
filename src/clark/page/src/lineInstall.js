// The filter line (#153) is the app's only. The two app entries (main.jsx and main-test.jsx) import this file, which hands the line to
// the shared parts (stores/lineSlot.js); view.jsx, the published file's entry, never does, so that bundle holds none of the line's code.
import { installLine } from "./stores/lineSlot.js";
import { LINE_CORE } from "./stores/line.js";
import { FilterLine } from "./components/FilterLine.jsx";

installLine({ ...LINE_CORE, FilterLine });
