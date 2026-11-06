// The Gantt page's host (#926): everything the page needs from outside, behind one small interface, so the page itself never knows where the
// plan lives or what the wire looks like. A later step replaces the in-memory host below with ganttStoreHost.js (the real store).
//
//   host.read()                  -> { project: { name, client_name, week_ending }, settings: {...DEFAULT_SETTINGS}, lines: [stored lines], toast: null | { text, undo } }
//   host.subscribe(fn)           -> a function that stops listening; fn runs after every change
//   host.applyLines(ops, words)  -> Promise; ops are logic/ganttPage.js diff(): { op: 'new' | 'update' | 'delete', id, values | changes }
//   host.saveSettings(changes, words) -> Promise; changes are project fields (gantt_title, gantt_hidden_columns, gantt_default_rows ...)
//   host.undoLast()              -> Promise; puts back the last change
//   host.ownUndoKey              -> true when the page must listen for Cmd or Ctrl+Z itself (the store host leaves it to the app's own key)
// `words` is what the toast says. A host with a toast of its own shows it through read().toast; the store host uses the app's toast.
import { DEFAULT_SETTINGS, applyOps, sortLines } from "./ganttPage.js";

export function createMemoryHost({ project = { name: "Demo project", client_name: "", week_ending: "" }, settings = {}, lines = [], today } = {}) {
  let state = { project, settings: { ...DEFAULT_SETTINGS, ...settings }, lines: sortLines(lines), toast: null };
  const steps = [];
  const listeners = new Set();
  const tell = () => listeners.forEach((fn) => fn());
  const put = (next, words) => {
    steps.push({ lines: state.lines, settings: state.settings });
    state = { ...state, ...next, toast: words ? { text: words, undo: true } : null };
    tell();
    return Promise.resolve({ ok: true });
  };
  const host = {
    calls: [],
    today,
    ownUndoKey: true,
    read: () => state,
    subscribe: (fn) => { listeners.add(fn); return () => listeners.delete(fn); },
    applyLines(ops, words) { host.calls.push(["lines", ops, words]); return put({ lines: applyOps(state.lines, ops) }, words); },
    saveSettings(changes, words) { host.calls.push(["settings", changes, words]); return put({ settings: { ...state.settings, ...changes } }, words); },
    undoLast() {
      const back = steps.pop();
      if (!back) return Promise.resolve({ ok: false });
      host.calls.push(["undo"]);
      state = { ...state, ...back, toast: null };
      tell();
      return Promise.resolve({ ok: true });
    },
    dismiss() { state = { ...state, toast: null }; tell(); },
  };
  return host;
}
