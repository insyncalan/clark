// What a published file remembers for the client (#69): the type, Open / Closed / All, the filters and Group by, in the client's own
// browser under the file's own key (clientView.js: clark.work.<code>), never sent anywhere and never the editor's key. The search
// words are not kept. An address that already holds filters (a link) wins over what was kept. It runs only in a published file.
import { effect, signal } from "@preact/signals";
import { fromFile, status, data, project, rows, asAt, f, filterState, setFilterState } from "./report.js";
import { work, setWork } from "./work.js";
import { load, save, recall, remember } from "../clientView.js";

export function keepChoices() {
  const restored = signal(false);
  effect(() => {
    if (!fromFile.value || status.value !== "ready" || !data.value || restored.peek()) return;
    const st = recall(load(project.peek()), rows.peek(), asAt.peek());
    if (st) {
      if (!f.peek()) setFilterState({ mode: st.mode, type: st.type, filters: st.filters, not: st.not });
      setWork({ group: st.group });
    }
    restored.value = true;
  });
  effect(() => {
    if (!restored.value) return;
    save(project.peek(), remember(filterState.value, work.value.group));
  });
}
