// item 1188: the hint an empty text section shows in Edit. Only the first default section, Current state, has one of its own: the line
// default_sections.CURRENT_STATE_PREFILL, written in by the build. It lives in the edit part of the page, never in the part a published
// file carries, because it is instruction text a client must not read. It is a hint only: it is never a body, and nothing saves it.
const CURRENT_STATE_HINT = __CLARK_CURRENT_STATE_HINT__;

/** The RichField's `empty` text for a text section (undefined keeps the field's own "Click to write."). */
export function richHint(section) {
  return section && section.type === "text" && section.title === "Current state" ? CURRENT_STATE_HINT : undefined;
}
