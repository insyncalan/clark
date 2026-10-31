// What the ask panel says (#47a). Every sentence is here, so one test can read them all. None starts with the product's name; each
// says what happened and what to do next.
export const PANEL_TITLE = "Ask about this project";
export const OFF_LINE = "Asking is off. Turn it on in Settings.";                     // shown while the switch is off or not yet known
export const OFF_LINK = "Open Settings";
export const SIGNED_OUT_LINE = "Claude is not signed in on this computer, so there is nothing to ask yet. Sign in to Claude on this computer, then open this panel again.";
export const SETTINGS_LINK = "Open Settings";
// #47a: the connect box says where the words go and who pays for them.
export const SENT_LINE = "Your question and the passages it needs go to Claude, which Anthropic runs, and are billed to the Claude account signed in on this computer.";
export const CHECKING_LINE = "Checking whether you can ask…";
export const READY_LINE = "Ready. Ask about this project.";
export const MODEL_LINE = (name) => `Answering with ${name}.`;
export const PLACEHOLDER = "Ask a question about this project";
export const SEND = "Ask";
export const STOP = "Stop";
export const CLOSE = "Close";
export const STOPPING_LINE = "Stopping. Your question and the earlier answers stay here.";
export const NO_ANSWER_LINE = "No answer came back. Wait a moment and ask again.";
export const NOT_REACHED_LINE = "The question did not reach clark. Check that its window is still open, then ask again.";
export const EMPTY_LINE = "Type a question first, then press Ask.";
export const YOU = "You";
export const REPLY = "Answer";
export const GRIP = "Drag to change the width of this panel";
// The suggestions above the box: one row that scrolls sideways (#214).
export const PILLS_LABEL = "Questions you can ask";
export const SUGGESTIONS = [
  "Check this report",
  "What is overdue?",
  "Which risks are red?",
  "What is the next milestone?",
  "Summarise this week",
  "Which use cases need attention?",
];
export const WORKING = "Working";
export const LOG_LABEL = "The chat so far";
// The office quips shown while an answer is worked on (#214, the prototype's own list, cut to the plain ones: no names, no days, no
// buzzwords). One shows at a time and changes every 5 to 10 seconds, never the same twice running (askPanelState.js).
export const QUIPS = [
  "Percolating coffee…",
  "Getting my steps in…",
  "Waiting for the conference call to start…",
  "You're on mute…",
  "Circling back…",
  "Touching base…",
  "Taking this offline…",
  "Putting it in the parking lot…",
  "Moving the needle…",
  "Running it up the flagpole…",
  "Booking a meeting about the meeting…",
  "Waiting for the projector to connect…",
  "Hunting for a free meeting room…",
  "Reply-all-ing, carefully…",
  "Turning amber back to green…",
  "Queueing for the kettle…",
  "Looking for the HDMI dongle…",
  "Rescheduling the reschedule…",
  "Going round the room…",
  "Adding it to the backlog…",
  "Chasing sign-off…",
  "Grabbing five minutes…",
  "Reading the pre-read…",
  "Finding a whiteboard pen that works…",
  "Wordsmithing the slide…",
  "Finding the meeting link…",
  "Just finishing another call…",
  "Refilling the stapler…",
  "Fixing the wobbly chair…",
  "Warming up the projector…",
  "Asking who has the clicker…",
  "Waiting for quorum…",
  "Taking the minutes…",
  "Agreeing the next steps…",
  "Parking that for now…",
  "Coming back to that…",
  "Noting the dependency…",
  "Colour-coding the spreadsheet…",
  "Finding the latest version…",
  "Checking the shared drive…",
  "Drafting a polite nudge…",
  "Softening the wording…",
  "Writing the out-of-office…",
  "Finding a slot that suits everyone…",
  "Accepting tentatively…",
  "Reheating my coffee…",
  "Finding the good mugs…",
  "Wiping the whiteboard…",
  "Drawing a box and an arrow…",
  "Adding another arrow…",
  "Sorting the sticky notes…",
  "Timeboxing it…",
  "Running slightly over…",
  "Attaching the slides…",
  "Forgetting the attachment…",
  "Unjamming the printer…",
  "Opening a window…",
  "Finding a free socket…",
  "Reconnecting to the Wi-Fi…",
  "Waiting in the lobby…",
  "Blurring my background…",
  "Reading the room…",
  "Summarising the discussion…",
  "Cutting it to one page…",
  "Checking the numbers add up…",
];

// A change an answer suggests (#47e). The before and after come from the saved data, never from the answer's words.
export const CHANGE_HEAD = "Suggested change";
export const NEW_HEAD = "Suggested new item";
export const FIELD = "Field";
export const NOW = "Now";
export const AFTER = "After Apply";
export const NOT_SET = "Not set";
export const APPLY = "Apply";
export const APPLYING_LINE = "Saving the change…";
export const FROM_FILE = "From your file";
export const CONFIRM_LINE = "This change comes from one of your files. Read the passage, tick the box, then press Apply.";
export const CONFIRM_NO_PASSAGE_LINE = "This answer read your files, so check the change against them. Tick the box, then press Apply.";
export const CONFIRM_BOX = "I have checked this change and want to save it";
export const DONE_LINE = "Done.";
export const UNDO = "Undo";
export const UNDONE_LINE = "Undone. The old values are back.";
export const UNDO_FAILED_LINE = "That could not be undone. Open the item and change it back yourself.";
export const REFUSED_LINE = "That change can't be made by asking. Nothing was changed. Make it yourself on the board.";
export const NOT_SAVED_LINE = "The change was not saved. Nothing was changed. Ask again, or make it yourself on the board.";
export const CHANGES_GONE_LINE = "The suggested changes could not be shown. Nothing was changed. Ask again.";
export const FIELD_NAMES = {
  description: "Title", decision: "Decision", name: "Name", owner: "Owner", made_by: "Made by", priority: "Priority",
  due_date: "Due", status: "Status", workstream: "Workstream", milestone: "Milestone", impact: "Impact", likelihood: "Likelihood",
  date: "Date", needed_by: "Needed by", baseline_date: "Agreed date", forecast_date: "Forecast", actual_date: "Achieved",
  closed: "Closed on", raised: "Raised", type: "Type",
};
export const KIND_NAMES = { actions: "Action", decisions: "Decision", milestones: "Milestone", raid: "Risk or issue" };
