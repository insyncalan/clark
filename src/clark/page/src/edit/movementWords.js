// The words of the Milestones Movement block (#136), owner only: the page's copy of the constants in src/clark/movement_view.py and
// of the plain refusals in clark/milestone_rows.py and clark/changes.py. A test (tests/test_movement_page.py) holds every one of them
// to its Python original, so a change in one place without the other fails. Dates are shown DD-MM-YYYY. Nothing here starts with
// the product's name.
export const HEADING = "Movement";
export const TAG_INTERNAL = "Internal only: never published";
export const HELP_LINE = "Movement is for you and the team: it is never published.";
export const LOADING = "Loading Movement.";
export const READ_FAILS = "Movement couldn't be loaded. Check that clark is still running, then try again.";
export const TRY_AGAIN = "Try again";
export const WHAT_CHANGED = "What changed";
export const DECIDE = "Decide what to do";
export const DECIDE_HELP = "Each choice changes the record at once, with Undo.";
export const NOTHING_CHANGED = "Nothing has changed since it was first agreed.";
export const NO_DATE_YET = "No date yet";
export const HOLD_LABEL = "Hold: keep the forecast, agreed date unchanged";
export const MOVE_LABEL = "Move the agreed date";
export const KEEP_LABEL = "Keep the date";
export const CONFIRM = "Move the agreed date of %s from %s to %s? The original date (%s) is kept and a decision is recorded. You can undo this.";
export const TOAST_HOLD = "Hold recorded in the note. Undo.";
export const TOAST_MOVED = "%s: the agreed date is now %s. Undo.";
export const UNDONE = "Undone";
export const RECOVER_LABEL = "Add a recovery action";
export const ESCALATE_LABEL = "Escalate to steering";
export const RECOVER_TITLE = "Recover %s";
export const ESCALATE_TITLE = "Steering decision on %s";
export const TOAST_ACTION = "%s added and linked to %s. Undo.";
export const TOAST_DECISION = "%s added for %s. Undo.";
// The explanation line a new recovery action or steering decision starts with (BEHIND_LINE, NOT_BEHIND_LINE).
export const BEHIND_LINE = "%s is %s behind its agreed date.";
export const NOT_BEHIND_LINE = "%s is not behind its agreed date.";
export const NO_WORKSTREAM = "There is no open workstream to put the action in. Open or add a workstream first, then try again.";
export const NOTE_HEADING = "Internal note";
export const NOTE_PLACEHOLDER = "What is going on, what you are waiting for";
export const NOTE_HELP = "Saves when you leave the box. Never published.";
export const TOAST_NOTE = "Note saved. Undo.";
export const NOTE_FAILED = "The note couldn't be saved, and nothing was changed. Reload the page and try again.";
export const ADD_MILESTONE = "Add milestone";
export const NEW_MILESTONE = "New milestone";
export const TOAST_MILESTONE = "Milestone added. Undo.";
export const NOT_SLIPPED = "This milestone hasn't slipped, so its agreed date can't be moved yet.";
export const CHOICE_FAILED = "That choice couldn't be recorded, and nothing was changed. Reload the page and try again.";
export const LABELS = { original: "Original", agreed: "Agreed", forecast: "Forecast", progress: "Progress", owner: "Owner" };
export const FIELDS = { to: "New agreed date (DD-MM-YYYY)", who: "Who agreed it", reason: "Reason", source: "Source" };
export const WHO_MISSING = "Say who agreed the new date.";
export const REASON_MISSING = "Give the reason the agreed date is moving.";
export const SOURCE_MISSING = "Give the source: where it was agreed, for example the meeting or the email.";
export const DATE_UNREADABLE = "The new agreed date isn't a date I can read. Write it as DD-MM-YYYY.";
export const SAME_DATE = "The new agreed date is the same as the current one (%s).";
export const EARLIER_DATE = "The new agreed date must be later than the current one (%s).";
export const PAST_DATE = "The new agreed date can't be before today (%s).";
export const ARCHIVED = "That milestone is archived. Restore it first.";
export const NOT_HERE = "That milestone isn't in this project.";

// Fill each %s in order.
export function fill(text, ...parts) {
  let i = 0;
  return text.replace(/%s/g, () => String(parts[i++]));
}

// The refusals the server may give for a milestone change are fixed sentences (changes.py). These are the ones the page shows as
// they are; a reply made of anything else gets CHOICE_FAILED, so the server's own text is never shown.
const SENTENCES = [
  /Only a planned milestone can be rebaselined; this one is (done|cancelled)\./,
  /This milestone has no agreed date yet, so there is nothing to rebaseline\. Set its agreed date instead\./,
  /This milestone hasn't slipped, so give the new agreed date\./,
  /This milestone hasn't slipped, so its agreed date can't be moved yet\./,
  /The new agreed date isn't a date I can read\. Write it as DD-MM-YYYY(, for example \d\d-\d\d-\d{4})?\./,
  /The new agreed date is the same as the current one \(\d\d-\d\d-\d{4}\)\./,
  /The new agreed date must be later than the current one \(\d\d-\d\d-\d{4}\)\./,
  /The new agreed date can't be before today \(\d\d-\d\d-\d{4}\)\./,
  /Say who agreed the new date\./,
  /Give the reason the agreed date is moving\./,
  /Give the source: where it was agreed, for example the meeting or the email\./,
  /That milestone is archived\. Restore it first\./,
  /That milestone isn't in this project\./,
  /An agreed date can't be cleared once it is set\. Move it to a new date instead\./,
  /Say the new agreed date, later than the current one\./,
];

// The server's refusal when it is made only of the sentences above, else "".
export function knownRefusal(message) {
  if (typeof message !== "string" || !message) return "";
  let rest = message;
  for (const s of SENTENCES) rest = rest.replace(new RegExp(s.source, "g"), "");
  return rest.trim() === "" ? message : "";
}
