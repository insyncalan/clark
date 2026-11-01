// Which AI place each editor on the page uses (#72, slice 6). One table, kept as data, so nothing else decides the place: the editor's
// AI hook asks placeFor(key) and uses what it gets. A key that is not here gives null, and the page draws no AI for that editor.
// The places are the five in aiMenu.js; what each one offers is set there (and by the server's menu), not here. Plain JS, no DOM.
import { placeKnown } from "./aiMenu.js";

// editor key -> place
export const PLACE_OF = {
  // The rich editors: all three take the full list (Format notes, Make into) of the current place.
  "section.body": "current",         // every text section of the report
  "current.state": "current",        // Current state (the report's headline)
  "usecase.standing": "current",     // a use case's "Where it stands"
  // The notes editor: a Notes-kind section (when it lands) and any meeting-notes field. It adds Pull out the tasks.
  "notes.section": "notes",
  // Short plain fields in the peek: an item's text, a risk's wording. Section titles stay out (no entry).
  "peek.item_text": "plain",
  "peek.risk_wording": "plain",
  // Words meant to reach a client: the milestone's client wording. Its client check applies (the place decides it).
  "milestone.client_wording": "client_message",
  // The Draft email preview.
  "email.draft": "email",
};

// The rich field name the page's RichField is given (its `field` prop) -> the editor's key above. A new rich field needs a line here
// and in PLACE_OF; tests/test_ai_places.py fails on a RichField with no line.
export const RICH_FIELDS = {
  body: "section.body",
  headline: "current.state",
  standing: "usecase.standing",
};

// The editors that are not a RichField (a plain editable box), by the file that mounts them -> key.
export const OTHER_EDITORS = {
  "components/DraftEmail.jsx": "email.draft",
};

// The place for an editor key, or null when there is none (the editor gets no AI). Only own entries count, never a built-in name.
export function placeFor(key) {
  if (typeof key !== "string" || !Object.prototype.hasOwnProperty.call(PLACE_OF, key)) return null;
  const place = PLACE_OF[key];
  return placeKnown(place) ? place : null;
}

// The key for a RichField's `field` prop, or null.
export function keyForField(field) {
  return typeof field === "string" && Object.prototype.hasOwnProperty.call(RICH_FIELDS, field) ? RICH_FIELDS[field] : null;
}

// What the menu shows for an editor (the aiMenu menu of its place), or null when the editor has no place.
export { menu } from "./aiMenu.js";
