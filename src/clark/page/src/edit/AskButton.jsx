// The ask button in the top bar (the prototype's #askBtn): opens the ask panel, as "/" does. It shows only while asking is on
// (askState.js: the switch the server keeps, read once here; it reads as off until the server answers, so nothing shows on a guess).
// Edit-served pages only: the top bar gets it from `tools` (edit/index.js).
import { useEffect } from "preact/hooks";
import { askOn, loadAsk } from "./askState.js";
import { closePanel, openPanel, panelOpen } from "./askPanelState.js";

export function AskButton() {
  useEffect(() => { loadAsk(); }, []);
  if (!askOn.value) return null;
  return (
    <button type="button" class="tb-act tb-ask" id="ask-btn" aria-expanded={panelOpen.value ? "true" : "false"} aria-label="ask clark" title="Open ask clark (/ or Ctrl or Cmd + J)" onClick={() => (panelOpen.value ? closePanel() : openPanel())}>
      <svg class="tb-ico" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3h7A2.5 2.5 0 0 1 16 5.5v5a2.5 2.5 0 0 1-2.5 2.5H9l-3.5 3v-3A2.5 2.5 0 0 1 4 10.5z" /></svg>
      <span class="tb-ask-w">ask clark</span> <kbd class="tb-key">/</kbd>
    </button>
  );
}
