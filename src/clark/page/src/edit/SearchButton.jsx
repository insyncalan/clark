// The search button in the top bar (the prototype's #palBtn): an icon that opens the command palette, as Ctrl or Cmd + K does.
// Edit-served pages only: the top bar gets it from `tools` (edit/index.js), so a published file has none.
import { paletteOpen } from "./palette.js";
import { openPalette } from "./Palette.jsx";
import { narrowHeader } from "./narrowHeader.js";

export function SearchButton() {
  if (narrowHeader.value) return null;      // item 1177: at 900 px and narrower search is the first entry of the profile menu
  return (
    <button type="button" class="tb-act" id="pal-btn" aria-haspopup="dialog" aria-expanded={paletteOpen.value ? "true" : "false"} aria-label="Go to or do" title="Go to or do (Ctrl or Cmd + K)" onClick={() => openPalette()}>
      <svg class="tb-ico" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><circle cx="9" cy="9" r="5.5" /><path d="M13 13l4 4" /></svg>
    </button>
  );
}
