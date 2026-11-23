// "Ask about this" (row 1292): a sparkle at the right of a work item row, a report section's header and a use case row, in Edit only and in
// Classic only (Cards is left as it is). The callers draw it only while editing, so View and a published file never get one. It opens the ask
// panel with a chip naming the subject; the chip has its own Remove, and the panel works without it.
import { askOn } from "./askState.js";
import { askAbout } from "./askPanelState.js";
import { ABOUT_LABEL, ABOUT_TITLE, ABOUT_SECTION } from "./askWords.js";
import { Icon } from "../components/Icon.jsx";
import { classicTheme } from "../components/Contents.jsx";

/** `kind` is "item" | "section" | "use case"; `id` is the row's ID; `name` is what the chip says (the ID and the title, or "Section: " and the title). */
export function AskAbout({ kind, id, name }) {
  if (!askOn.value || !classicTheme()) return null;               // shown only while asking is on, as the ask button is
  const said = kind === "section" ? ABOUT_SECTION(name) : name;          // what the chip says
  const label = ABOUT_LABEL(said);
  return (
    <button type="button" class="ask-about" data-edit-only data-ask-about={id} aria-label={label} title={ABOUT_TITLE}
      onClick={(e) => { e.stopPropagation(); askAbout({ kind, id, name: said }); }}><Icon name="sparkle" /></button>
  );
}
