// The Help button in the top bar: a "?" beside the profile circle (the prototype's #helpBtn). It does what the "?" key does: opens the
// peek for the screen you are on (helpStore.js), or the full Help on the tab used last when that screen has no peek text. Edit-served
// pages only: the top bar gets it from `tools` (edit/index.js), so a published file has none.
import { openHelp, toggleContext, contextOpen } from "./helpStore.js";

export function HelpButton() {
  return <button type="button" class="hp-top" id="help-btn" aria-label="Help" title="Help (?)" aria-expanded={contextOpen.value ? "true" : "false"} onClick={() => { if (!toggleContext()) openHelp(); }}><span aria-hidden="true">?</span></button>;
}
