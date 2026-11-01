// The Help button in the top bar: a "?" beside the profile circle (the prototype's #helpBtn). It opens Help on the tab used last, as
// the "?" key and the profile menu's Help do. Edit-served pages only: the top bar gets it from `tools` (edit/index.js), so a published
// file has none.
import { openHelp } from "./helpStore.js";

export function HelpButton() {
  return <button type="button" class="hp-top" id="help-btn" aria-label="Help" title="Help (?)" onClick={() => openHelp()}><span aria-hidden="true">?</span></button>;
}
