// Row 1234: the words of the Configure button and panel (Edit only). The APPROVED_ ones are the ruled wording (16-11 00:58, Dubai).
// Every string that is NOT approved is in an UNRULED_ constant below, so the list of what still needs a ruling is this file's UNRULED_ lines.
export const CONFIGURE = "Configure";
export const TITLE = "Configure use cases";
export const NUMBER_LABEL = "Number shown";
export const SHOWN_LABEL = "Use cases shown";
export const ALL_WORD = "All";
export const OF = (n) => `of ${n}`;
export const SCROLL_LABEL = "Viewers can scroll the list";
export const SAME_NOTE = "Edit uses the same number but scrolls whenever a number is set, so you can reach every use case; viewers get the scrolling only when it is On.";
export const SCROLL_HELP = (n) => `On: the list is ${n} rows tall and scrolls up and down to the rest. Off: viewers see only the first ${n}.`;
export const TRACKER_LABEL = "Status tracker";
export const TRACKER_WORDS = { top: "Top", bottom: "Bottom", off: "Off" };
export const TRACKER_HELP = "The count by status and the bar. Top or bottom of the list, or off.";
export const DONE = "Done";

// Not ruled yet (no ruling): nothing here may be treated as final wording.
// (none: the close button reads DONE, item 9 of the words file)

// Row 1230: the Milestones section's Configure uses this same box; these are its own ruled words (ruled 16-11).
export const MS_TITLE = "Configure milestones";
export const MS_NUMBER_LABEL = "Milestones shown in the list";
export const MS_SHOWN_LABEL = "Milestones shown";
export const MS_SAME_NOTE = "Edit uses the same number but scrolls whenever a number is set, so you can reach every milestone; viewers get the scrolling only when it is On.";
export const MS_TRACKER_HELP = "The counts by state; they double as the key. Top or bottom of the list, or off.";
