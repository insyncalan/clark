// What the ask panel says (#47a). Every sentence is here, so one test can read them all. Apart from the title, none starts with the product's name; each
// says what happened and what to do next.
export const PANEL_TITLE = "ask clark";
export const OFF_LINE = "Asking is off. Turn it on in Settings.";                     // shown only when the server has answered that the switch is off
export const OFF_LINK = "Open Settings";
export const SIGNED_OUT_LINE = "Claude is not signed in on this computer, so there is nothing to ask yet. Sign in to Claude on this computer, then open this panel again.";
export const SETTINGS_LINK = "Open Settings";
// #54: every line that says where a question goes follows the provider in use, because it has to be true. The words themselves are written for Claude.
export const named = (text, who) => (who === "ChatGPT" ? text.replace(/Claude, which Anthropic runs/g, "ChatGPT, which OpenAI runs").replace(/Claude/g, "ChatGPT") : text);
export const DISCONNECTED_LINE = "Nothing is connected in Settings. Connect Claude or ChatGPT there to use this.";   // the server's status words, ai_connect.OFF_WORDS
// #1062: where a question goes and who pays moved from the panel to the Asking card in Settings.
export const ASK_NOTICE_LINE = "Your question and the passages it needs go to Claude, which Anthropic runs, and are billed to the Claude account signed in on this computer.";
export const CHECKING_LINE = "Checking whether you can ask…";
export const READY_LINE = "Ready. Ask about this project.";
export const MODEL_LINE = (name) => `Answering with ${name}.`;
export const PLACEHOLDER = "Ask a question about this project";
export const SEND = "Ask";
export const STOP = "Stop";
export const CLOSE = "Close";
export const NEW_CHAT = "New chat";
export const STOPPING_LINE = "Stopping. Your question and the earlier answers stay here.";
export const NO_ANSWER_LINE = "No answer came back. Wait a moment and ask again.";
export const NOT_REACHED_LINE = "The question did not reach clark. Check that its window is still open, then ask again.";
export const EMPTY_LINE = "Type a question first, then press Ask.";
export const YOU = "You";
export const REPLY = "Answer";
export const SOURCES = "Sources";
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
// The office quips shown while an answer is worked on (item 1094: the creaite list of 150, copied as it is). One shows at a time and
// changes every 5 to 10 seconds, from a shuffled deck so none comes round again until all have been shown (askPanelState.js).
export const QUIPS = [
  "Percolating coffee…",
  "Getting my steps in…",
  "Waiting for the conference call to start…",
  "You're on mute…",
  "Circling back…",
  "Touching base…",
  "Taking this offline…",
  "Aligning stakeholders…",
  "Socialising the deck…",
  "Putting it in the parking lot…",
  "Boiling a small ocean…",
  "Moving the needle…",
  "Picking the low-hanging fruit…",
  "Running it up the flagpole…",
  "Booking a meeting about the meeting…",
  "Waiting for the projector to connect…",
  "Hunting for a free meeting room…",
  "Reply-all-ing, carefully…",
  "Turning amber back to green…",
  "Herding stakeholders…",
  "Adding an action to the action log…",
  "Queueing for the kettle…",
  "Looking for the HDMI dongle…",
  "Can everyone see my screen?…",
  "Rescheduling the reschedule…",
  "Doing a deep dive…",
  "Taking it to the steering committee…",
  "Double-clicking on that…",
  "Going round the room…",
  "Adding it to the backlog…",
  "Chasing sign-off…",
  "Checking the RACI…",
  "Re-baselining the plan…",
  "Syncing on the sync…",
  "Grabbing five minutes…",
  "Reading the pre-read…",
  "Finding a whiteboard pen that works…",
  "Raising a ticket with IT…",
  "Wordsmithing the slide…",
  "Ideating…",
  "Leveraging the synergies…",
  "Updating the RAG status…",
  "Waiting for the lift…",
  "Joining from my phone…",
  "Finding the meeting link…",
  "Sorry, you go…",
  "Just finishing another call…",
  "Pinging the stakeholders…",
  "Bringing the deck to life…",
  "Locking in the agenda…",
  "Finding the action log…",
  "Unmuting…",
  "Sharing the wrong screen…",
  "Sharing the right screen…",
  "Waiting for the room to empty…",
  "Collecting the printouts…",
  "Refilling the stapler…",
  "Looking for a working pen…",
  "Fixing the wobbly chair…",
  "Warming up the projector…",
  "Asking who has the clicker…",
  "Moving the stand-up to Tuesday…",
  "Waiting for quorum…",
  "Taking the minutes…",
  "Agreeing the next steps…",
  "Parking that for now…",
  "Coming back to that…",
  "Noting the dependency…",
  "Updating your project record…",
  "Colour-coding the spreadsheet…",
  "Merging two spreadsheets…",
  "Finding the latest version…",
  "Renaming it final_final…",
  "Checking the shared drive…",
  "Clearing the inbox…",
  "Flagging it for later…",
  "Drafting a polite nudge…",
  "Softening the wording…",
  "Adding a gentle reminder…",
  "Writing the out-of-office…",
  "Booking the next check-in…",
  "Finding a slot that suits everyone…",
  "Declining a clashing invite…",
  "Accepting tentatively…",
  "Waiting for the calendar to load…",
  "Moving my lunch…",
  "Reheating my coffee…",
  "Finding the good mugs…",
  "Wiping the whiteboard…",
  "Taking a photo of the whiteboard…",
  "Drawing a box and an arrow…",
  "Adding another arrow…",
  "Labelling the swimlanes…",
  "Sorting the sticky notes…",
  "Grouping the sticky notes…",
  "Voting with dots…",
  "Timeboxing it…",
  "Setting a five-minute timer…",
  "Running slightly over…",
  "Going round once more…",
  "Asking any other business…",
  "Thanking everyone for their time…",
  "Sending the follow-up…",
  "Attaching the slides…",
  "Forgetting the attachment…",
  "Tidying the agenda…",
  "Numbering the actions…",
  "Assigning an owner…",
  "Agreeing a due date…",
  "Nudging the due date…",
  "Checking the dependencies…",
  "Raising a risk…",
  "Scoring the risk…",
  "Mitigating the risk…",
  "Closing the issue…",
  "Logging a decision…",
  "Recording who agreed…",
  "Printing double-sided…",
  "Unjamming the printer…",
  "Finding the meeting room key…",
  "Adjusting the air conditioning…",
  "Opening a window…",
  "Charging my laptop…",
  "Finding a free socket…",
  "Restarting for updates…",
  "Reconnecting to the Wi-Fi…",
  "Dialling in…",
  "Spelling my name for the call…",
  "Waiting in the lobby…",
  "Admitting everyone from the lobby…",
  "Turning my camera on…",
  "Blurring my background…",
  "Checking I'm not on mute…",
  "Saying hello to the room…",
  "Asking for a quick show of hands…",
  "Reading the room…",
  "Summarising the discussion…",
  "Playing it back…",
  "Checking for questions…",
  "Writing it in plain English…",
  "Cutting it to one page…",
  "Making the font smaller…",
  "Aligning the boxes…",
  "Fixing the bullet points…",
  "Choosing a better chart…",
  "Labelling the axes…",
  "Checking the numbers add up…",
  "Double-checking the dates…",
  "Converting the time zones…",
  "Proofreading…",
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
  headline: "Headline", standing: "Where it stands",      // a use case (issue 729): the words its editor uses
};
export const KIND_NAMES = { actions: "Action", decisions: "Decision", milestones: "Milestone", raid: "Risk or issue" };
