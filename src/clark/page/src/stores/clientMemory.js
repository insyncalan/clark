// What a published file remembers for the client (#69): the type, Open / Closed / All, the filters and Group by, in the client's own
// browser under the file's own key (clientView.js: clark.work.<code>), never sent anywhere and never the editor's key. The search
// words are not kept. An address that already holds filters (a link) wins over what was kept. It runs only in a published file.
// A click on a tab writes an address with no filters (stores/report.js show()): that empty state is the address's, not the person's, so
// it is never saved. Coming into Work items with no filters in the address brings the kept choices back; a save is made only on the
// Work items page, where the person changes the filters (Clear all there still saves the empty state).
import { effect, signal } from "@preact/signals";
import { fromFile, status, data, project, rows, asAt, f, view, filterState, setFilterState } from "./report.js";
import { work, setWork } from "./work.js";
import { load, save, recall, remember } from "../clientView.js";

export function keepChoices() {
  const restored = signal(false);
  effect(() => {
    if (!fromFile.value || status.value !== "ready" || !data.value || restored.peek()) return;
    const st = recall(load(project.peek()), rows.peek(), asAt.peek());
    if (st) {
      if (!f.peek() && view.peek() === "work") setFilterState({ mode: st.mode, type: st.type, filters: st.filters, not: st.not });
      setWork({ group: st.group });
    }
    restored.value = true;
  });
  let lastView = "";
  effect(() => {
    if (!restored.value) return;
    const here = view.value, st = filterState.value, group = work.value.group;
    const entering = here === "work" && lastView !== "work";
    lastView = here;
    if (here !== "work") return;                          // the other pages carry no filters of the person's: nothing to save there
    if (entering && !f.peek()) {                          // arrived by a tab: the address is empty, the kept choices are not
      const kept = recall(load(project.peek()), rows.peek(), asAt.peek());
      if (kept) setFilterState({ mode: kept.mode, type: kept.type, filters: kept.filters, not: kept.not });   // this run saves them again
      return;
    }
    save(project.peek(), remember(st, group));
  });
}
