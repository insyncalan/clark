// The progress tracker's template settings (#930): its Size. One entry for edit/TemplateSettings.jsx's list; another template adds its
// own entry there in the same shape: { title, line, label, options: [[value, name, what]], current(section), save(section, value) }.
import { change } from "../stores/changes.js";
import { trackerOf, bodyOf, withSize, WORDS as VIEW_WORDS } from "../logic/tracker.js";
import { WORDS, SIZE_OPTIONS } from "../logic/trackerEdit.js";

export const trackerSettings = {
  title: VIEW_WORDS.title,
  line: WORDS.settingsLine,
  label: WORDS.sizeLabel,
  options: SIZE_OPTIONS,
  current: (section) => trackerOf(section, false).size,
  // One change, one Undo, the same route as every other change to the section's body.
  save(section, value) {
    const next = withSize(trackerOf(section, false), value);
    return next ? change({ op: "update", id: section.id, changes: { body: bodyOf(next) }, place: "cell" }, WORDS.saved) : Promise.resolve(false);
  },
};
