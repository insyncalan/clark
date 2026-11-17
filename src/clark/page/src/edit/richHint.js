// items 1188, 1193: the hint an empty text section shows in Edit. The default text sections (Current state, Summary, This week, Next week) each have
// a guiding line of their own: default_sections.SECTION_HINTS, written in by the build. It lives in the edit part of the page, never in the part a
// published file carries, because it is instruction text a client must not read. It is a hint only: it is never a body, and nothing saves it.
import { startText, textTemplateId } from "./startingText.js";
const SECTION_HINTS = __CLARK_SECTION_HINTS__;

/** The RichField's `empty` text for a text section (undefined keeps the field's own "Click to write."). */
export function richHint(section) {
  return section && section.type === "text" && Object.prototype.hasOwnProperty.call(SECTION_HINTS, section.title) ? SECTION_HINTS[section.title]
    : section && section.type === "text" ? startText(textTemplateId(section), "empty") : undefined;      // row 1251: the Text and Header and Text starting words
}
