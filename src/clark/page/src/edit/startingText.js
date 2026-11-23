// Row 1251: the starting text of the section templates, keyed by template id (logic/templates.js ids). One list, the owner's words, written
// exactly as ruled (17-11, row 1251; the typographic apostrophes are part of the words). CAPTION is the
// prompt in a caption field that is empty; EMPTY is one prompt for each empty part, in the order the parts are drawn.
// These words are instruction text for the person writing the report. They live in edit/ ONLY and are reached through the edit tools
// (`tools.startText`): never in View, the published file, Word, Excel or an email. tests/test_starting_text_1251.py checks that.
export const STARTING_TEXT = {
  "text": { empty: ["Write here."] },
  "text-image": { caption: "Say what the picture shows.", empty: ["Write here.", "Add a picture."] },
  "gallery": { caption: "Say what the picture shows.", empty: ["Add a picture."] },
  "quote": { empty: ["Write what they said.", "Say who said it."] },
  "callout": { empty: ["Write the one thing the reader must see."] },
  "contacts": { empty: ["Add a person."] },
  "one-doc": { empty: ["Add the file."] },
  "figures-4": { caption: "Say what the numbers cover.", empty: ["Pick what each number shows."] },
  "figures-3": { empty: ["Pick what each number shows."] },
  "table": { empty: ["Add the first row."] },
  "raid-3": { empty: ["Choose the items to show."] },
  "raid-4": { empty: ["Choose the items to show."] },
  "work-items": { caption: "Say what the list shows.", empty: ["Set a filter to choose the rows."] },
  "docs-links": { empty: ["Add a file or a link."] },
  "checklist": { empty: ["Link the work items to tick off."] },
  "link-preview": { empty: ["Paste the link.", "Write what the reader will find there."] },
  "key-dates": { empty: ["No milestones to show yet."] },
  "gantt": { empty: ["No Gantt lines in the client view yet."] },
  "gantt-table": { empty: ["No Gantt lines in the client view yet."] },
  "plan-summary": { empty: ["Write here.", "Add a step."] },      // Plan summary keeps its description; "Write here." sits under an empty paragraph, "Add a step." under an empty list item
  "current-state": { empty: ["Say where the project stands."] },      // Header and Text: its starting title is "Header" (ruled 16-11, plan issue 1262)
};

// Ruled (17-11): a part left at its starting text is hidden on publish by the existing empty-part rule. The prompts are Edit-only hints and
// never a saved body, so nothing is left at them and nothing extra is built (this switch stays false and nothing reads it): a prompt is never in View or the published file.
export const HIDE_STARTING_TEXT_ON_PUBLISH = false;

// Row 1251: the starting text is a Classic look. Cards keeps its own words and draws no prompt (the Cards look is frozen).
export const classicLook = () => typeof document !== "undefined" && !!document.getElementById("theme");
/** The words of startText in Classic; `old` (what the part showed before row 1251) in Cards. */
export const startOr = (old, id, part = "empty", n = 0) => (classicLook() ? startText(id, part, n) : old);

/** The prompt for part `part` ("empty" or "caption") of template `id`; `n` picks one of several empty prompts. "" when there is none. */
export function startText(id, part = "empty", n = 0) {
  const t = STARTING_TEXT[id];
  if (!t) return "";
  const v = t[part];
  return Array.isArray(v) ? (v[n] || "") : (typeof v === "string" ? v : "");
}

/** The template id of a plain text section, by its title: "Header" is Header and Text; every other text section is Text. */
export function textTemplateId(section) {
  return section && section.title === "Header" ? "current-state" : section && section.title === "Plan summary" ? "plan-summary" : "text";
}
