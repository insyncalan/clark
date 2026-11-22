// Row 1251: the Edit-only prompt for an empty part of a template. Draws one quiet line with the words of startingText.js; nothing when the
// template has no prompt for that part. Never part of View, the published file or an export: it is under edit/ and reached as tools.StartPrompt.
import { startText, classicLook } from "./startingText.js";

export function StartPrompt({ id, part = "empty", n = 0, children = null }) {
  const words = classicLook() ? startText(id, part, n) : "";
  return words ? <p class="quiet tpl-prompt" data-tpl-prompt={`${id}-${part}-${n}`}>{words}{children}</p> : null;
}
