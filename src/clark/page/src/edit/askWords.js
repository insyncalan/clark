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
// row 1292 feature 2: the first-run card in an empty chat, three plain lines. Written for Claude; named() swaps the provider in use.
// The sentences are a draft: the spec gives the ideas, the words wait for the project head (listed as B1 in the words file).
export const FIRST_RUN_LABEL = "About ask clark";
export const FIRST_RUN_READS = "It reads what is in this project. Mail, Teams, calendars and SharePoint are used only if you turn that connector on in Settings.";
export const FIRST_RUN_CHANGES = "It can suggest changes. Nothing is saved until you press Apply, and every change can be undone.";
export const FIRST_RUN_SENT = "Your question goes to Claude, which Anthropic runs.";
export const FIRST_RUN_LINK = "Open the Asking card in Settings";
// item 1352, Classic only (Cards keeps the three plain lines and the status words above): the card as the prototype draws it, a heading, three bullets and a tip.
// The connector sentence is rule 11 of the 1292 rules: the connectors are used only when they are turned on in Settings.
export const CARD_HEAD = "Ask about this project";
export const CARD_READS = "I read this project's work items, milestones and use cases. Mail, Teams, calendars and SharePoint are used only if you turn that connector on in Settings.";
export const CARD_READS_FOLDERS = "I read this project's work items, milestones and use cases and the folders you named. Mail, Teams, calendars and SharePoint are used only if you turn that connector on in Settings.";   // item 1352: shown in place of the line above only when the project has folders
export const CARD_CHANGES = "I can suggest changes. Nothing is saved until you press Apply, and every change can be undone.";
export const CARD_CHANGES_BOLD = "Nothing is saved until you press Apply";      // drawn in the heavier weight, as the prototype does
export const CARD_SENT = "Your question and what it needs go to Claude.";
export const CARD_LINK = "What will be sent? (Settings)";
// row 1366 AP27: the passages line and the pictures line, words approved in NEW-WORDS (items 6 and 10); row 1537 AP6: also inside longer words, or an item ID from this chat.
export const CARD_PASSAGES = "Passages from the folders you list go to Claude, which Anthropic runs, only when they contain words from your question, also inside longer words, or an item ID from this chat.";
export const CARD_PICTURES = "On a Mac, pictures (PNG and JPG) in your folders are read on this Mac and are never sent out; text found in them is treated like any other passage from your folders.";
export const CARD_TIP_BEFORE = "Tip: press the sparkle on a work item, a section or a use case to ask about just that. Type ";
export const CARD_TIP_KEY = "/";
export const CARD_TIP_AFTER = " in the box for slash commands.";
export const CLASSIC_STATUS_READY = "Ready. Reading this project's report data.";   // the prototype's status line; it does not name the model
export const CLASSIC_STANDING = "Standing instructions on";                          // the prototype's words, no full stop (the line is a button there)
export const CHECKING_LINE = "Checking whether you can ask…";
export const READY_LINE = "Ready. Ask about this project.";
export const MODEL_LINE = (name) => `Answering with ${name}.`;
export const STANDING_LINE = "Standing instructions on.";   // row 1292 step S13, the mock-up's words with the full stop every line of the panel ends in
export const PLACEHOLDER = "Ask a question about this project";
export const PLACEHOLDER_CLASSIC = "Ask a question or give an instruction... (type / for slash commands)";          // row 1350: Classic only; Cards keeps PLACEHOLDER
export const SEND = "Ask";
export const STOP = "Stop";
export const CLOSE = "Close";
export const NEW_CHAT = "New chat";
// Row 1095: History, the earlier chats of this project, kept on this computer.
export const HISTORY = "History";
export const HISTORY_TITLE = "Earlier chats";
export const HISTORY_NOTE = "Kept on this computer, for this project only.";
export const HISTORY_UNTITLED = (when) => `Chat from ${when}`;
export const HISTORY_EMPTY = "No earlier chats yet. A chat is kept here once it has an answer.";
export const HISTORY_OPEN = (title) => `Open the chat: ${title}`;
export const HISTORY_DELETE = (title) => `Remove the chat: ${title}`;
export const DELETE = "Remove";
export const STOPPING_LINE = "Stopping. Your question and the earlier answers stay here.";
export const NO_ANSWER_LINE = "No answer came back. Wait a moment and ask again.";
export const STOPPED_LINE = "Stopped. Nothing was changed.";      // row 1293 line 7: the server's own stopped line (ask.py STOPPED), said by the page when an answer still came after Stop
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
// Row 1093: the suggestions follow the page that is open, and then the subject of the last question asked. A page without a list of its
// own (Settings, a published file) keeps the list above.
export const PILLS_BY_SUBJECT = {
  dashboard: ["Is the project on track?", "What is overdue?", "Which risks are red?", "What is the next milestone?", "What needs a decision soon?", "What changed this week?"],
  work: ["What is overdue?", "Which work items are blocked?", "What is due this week?", "Who has the most open work items?", "Which work items have no owner?", "What changed in the work items this week?"],
  milestones: ["What is the next milestone?", "Which milestones are late?", "Which milestones are due this month?", "What is holding up the next milestone?", "Which milestones have no work items?", "How many milestones are done?"],
  usecases: ["Which use cases need attention?", "Which use cases are not started?", "Which use cases have open risks?", "Which use cases are done?", "What changed in the use cases this week?", "Which use cases have no owner?"],
  risks: ["Which risks are red?", "Which risks have no owner?", "Which issues are open?", "What changed in the risks this week?", "Which risks are new this week?", "Which risks are due soon?"],
  gantt: ["What is the next milestone?", "Which work items are running late?", "Which work items hold up the end date?", "Which work items start next week?", "Which milestones are at risk?", "What ends this month?"],
};
// Row 1332: with Help open the suggestions are about Help, not about the page behind it.
export const PILLS_HELP = ["How do I add a work item?", "How do I change the view?", "How do I publish a report?", "What does Preview do?", "How do I turn ask clark off?", "Where are my settings?"];
// Row 1332: what the project holds puts one of a subject's own questions first. Only a question already in that subject's list is named here, so the
// state reorders the set and never adds to it. States: overdue (late open items), red (high risks), noOwner (open items with no owner).
export const PILLS_STATE = {
  dashboard: { overdue: "What is overdue?", red: "Which risks are red?" },
  work: { overdue: "What is overdue?", noOwner: "Which work items have no owner?" },
  milestones: { overdue: "Which milestones are late?" },
  usecases: { red: "Which use cases have open risks?", noOwner: "Which use cases have no owner?" },
  risks: { red: "Which risks are red?", noOwner: "Which risks have no owner?" },
  gantt: { overdue: "Which work items are running late?", red: "Which milestones are at risk?" },
};
// Row 1332 rows 3 and 11: after an answer that names items, the suggestions open with what can be done about THOSE items (DRAFT contract: items=[{id,state}],
// state words overdue / red / no_owner). The two questions about one item or a few carry the ids in brackets only in the question sent, never in the shown words; the rest are plain questions.
export const PILLS_ITEM_DUE = "Change the due date";
export const PILLS_ITEM_URGENCY = "Raise the urgency";
export const PILLS_ITEM_REPORT = "Include in the weekly report";
export const PILLS_ITEM_OWNERS = "Who owns these?";
export const PILLS_ITEM_LATE = "Why are these late?";
export const PILLS_MAX = 6;
export const PILLS_PAGE = { dashboard: "dashboard", work: "work", milestones: "milestones", usecases: "usecases", gantt: "gantt" };
// Words in a question that name a subject. The first one found in the last question wins.
export const PILLS_WORDS = [["milestone", "milestones"], ["use case", "usecases"], ["risk", "risks"], ["issue", "risks"], ["work item", "work"], ["task", "work"]];
export const WORKING = "Working";
export const WORKING_CLASSIC = "Working. You can close this: it carries on.";   // item 1352: Classic status line while a question is out; true while the page stays loaded (closing the panel does not stop the question)
// Row 1220: messages typed while an answer is made wait above the box. These words need approval.
const waitingCount = (n) => (n === 1 ? "1 message is" : `${n} messages are`);
export const QUEUE_LABEL = "Messages waiting to be sent";
export const QUEUE_REMOVE = "Remove this message";
export const QUEUE_MORE = (n) => `and ${n} more`;
export const QUEUE_STOPPED = (n) => `Stopped. ${waitingCount(n)} waiting`;
export const QUEUE_FAILED = (n) => `${waitingCount(n)} waiting`;
export const QUEUE_SEND = "Send the waiting messages";
export const QUEUE_CLEAR = "Clear";
export const QUEUE_FULL = "5 messages are already waiting. Wait for one to be sent, or remove one.";
export const QUEUE_DROP = (n) => `${waitingCount(n)} waiting and would be dropped. Press again to go on.`;
export const QUEUE_SAY_ADDED = (n) => `Message queued. ${n} waiting`;
export const QUEUE_SAY_REMOVED = (n) => `Message removed. ${n} waiting`;
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
  "Finding a biscuit…",
  "Passing the slides round…",
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
  "Herding the cats…",
  "Adding an action to the action log…",
  "Queueing for the kettle…",
  "Looking for the HDMI dongle…",
  "Can everyone see my screen?…",
  "Rescheduling the reschedule…",
  "Doing a deep dive…",
  "Taking it to the committee…",
  "Double-clicking on that…",
  "Going round the room…",
  "Adding it to the backlog…",
  "Chasing a signature…",
  "Checking who is in the room…",
  "Redrawing the plan…",
  "Catching up before the catch-up…",
  "Grabbing five minutes…",
  "Reading the notes beforehand…",
  "Finding a whiteboard pen that works…",
  "Raising a ticket with IT…",
  "Wordsmithing the slide…",
  "Thinking out loud…",
  "Shaking the vending machine…",
  "Watering the office plant…",
  "Waiting for the lift…",
  "Joining from my phone…",
  "Finding the meeting link…",
  "Sorry, you go…",
  "Just finishing another call…",
  "Knocking on a few doors…",
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
  "Moving the stand-up to a later slot…",
  "Waiting for everyone to arrive…",
  "Taking the minutes…",
  "Agreeing the next steps…",
  "Parking that for now…",
  "Coming back to that…",
  "Noting what depends on what…",
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

// Row 1292 (S6, no streaming yet; Classic only): the working line says the one step the page really knows (the question is out to the provider) and how long
// it has been going, counted from the send. A longer step list waits for real progress from the server. Cards keeps the quips above.
export const STEP_ASKING = "Asking Claude";
export const workingFor = (secs) => `Working ${Math.max(0, Math.floor(secs))}s`;
export const workingLine = (who, secs) => `${named(STEP_ASKING, who)} · ${workingFor(secs)}`;

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
// row 1292 step S4 (the words follow the mock-up; NEEDS RULING until the one words table is ruled)
export const WHY = "Why";
export const NOT_NOW = "Not now";
export const NOT_NOW_LINE = "Not now. Nothing was changed.";
export const BRING_BACK = "Bring it back";
export const APPLY_ALL = (n) => `Apply all ${n}`;
export const UNDO_ALL = "Undo all";
export const ALL_DONE_LINE = (n) => (n === 1 ? "Done. 1 change saved." : `Done. ${n} changes saved.`);
export const ALL_UNDONE_LINE = "Undone. The old values are back.";
export const ALL_PARTLY_LINE = (done, n) => `${done} of ${n} changes were saved. The others were not. Check the board and ask again.`;
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

// Row 1292 (S12): the Draft beside the panel (mock-up image 09).
export const DRAFT_TITLE = "Draft";
// Shown when a draft was written in a run that read a connector (names of the parts read, joined with "and").
export const DRAFT_VIA = (names) => `Written using your ${names}. Read it before you apply it.`;
export const DRAFT_HINT = "Edit it freely. Nothing is in the report yet.";
export const DRAFT_CLOSE = "Close the draft";
export const DRAFT_TEXT_LABEL = "Draft text";
export const DRAFT_ADD = "Add to the report";
export const DRAFT_COPY = "Copy";
export const DRAFT_COPIED = "Draft copied.";
export const DRAFT_COPY_FAILED = "The draft could not be copied. Select the text and copy it yourself.";
export const DRAFT_MENU_LABEL = "Where the draft goes";
export const DRAFT_READY = "Draft ready";
export const DRAFT_READY_LINE = "Nothing is in the report yet.";
export const DRAFT_OPEN = "Open the draft";
export const DRAFT_EMPTY = "The draft is empty. Write something, or close it.";

// row 1292 step S10: the slash menu. NEEDS RULING: the one-line hint under each command is a draft, to be ruled with the other new words (decision 25).
export const SLASH_LABEL = "Commands";
export const SLASH_YOURS = "Yours";      // row 1295: the tag of a command the person wrote (the editor mock-up marks it "you"; Settings calls it Yours)
export const SLASH_NONE = "No command by that name";
export const SLASH_HINT = {
  check: "Check this report",
  summary: "Summarise this week",
  overdue: "What is overdue",
  risks: "Which risks are red",
  milestones: "The next milestone",
  usecases: "Which use cases need attention",
  history: "Earlier chats",
  new: "Start a new chat",
};

// Row 1292 (feature 9): the words under each answer (mock-up ask.js, Copy, Ask again and their notices).
export const ANSWER_COPY = "Copy";
export const ANSWER_AGAIN = "Ask again";
export const ANSWER_COPIED = "Copied";                                         // A NEW-WORDS 1953 and the ticket: "Copied" for 2 s, replacing the longer sentence
export const ANSWER_COPY_LABEL = "Copy this answer";                            // A NEW-WORDS 1953: the screen-reader name
export const ANSWER_AGAIN_LABEL = "Ask this question again";                    // A NEW-WORDS 1953: the screen-reader name
export const ANSWER_COPIED_MS = 2000;
export const ANSWER_COPY_FAILED = "Could not copy. Select the text and copy it yourself.";
// Row 1292 (reopened): Ask about this, and where an answer came from. Each line names its source: M = the approved ask clark prototype, T = the ticket body, A = the new-words log.
export const ABOUT_LABEL = (name) => `Ask clark about ${name}`;                // M views.js: aria-label "Ask clark about <id>"
export const ABOUT_TITLE = "Ask clark about this";                              // M views.js: title
export const ABOUT_CHIP = (label) => `About ${label}`;                          // M ask.js drawCtx, T feature 1 ("About PDF-A-018 Write the user test scripts")
export const ABOUT_REMOVE = (label) => `Stop asking about ${label}`;            // M ask.js drawCtx: aria-label
export const ABOUT_REMOVE_TITLE = "Remove";                                     // M ask.js drawCtx: title; A 11-13: "Remove" is the app's word for a bin
export const ABOUT_SECTION = (title) => `Section: ${title}`;                    // M ask.js ctxLabel
export const ABOUT_LINE = (label) => `About ${label}`;                          // M ask.js: the small line under the person's question
// What is sent ahead of the person's words so the answer is about the subject. Model-facing, never shown (the same rule as the request lines A approved 17-11).
export const ABOUT_LEAD = (kind, id, name) => `About ${kind} ${id}${name && name !== id ? ` (${name})` : ""}: `;
// The suggestions once a subject is chosen (M ask.js PILLS; T feature 1 names the item ones).
export const PILLS_ABOUT = {
  item: ["Is it late?", "Who owns it?", "What is it needed for?", "Draft an update", "Move it a week"],
  milestone: ["Is it on track?", "What is holding it up?"],
  "use case": ["Where does it stand?", "What work sits behind it?"],
  section: ["Summarise this section", "What is missing here?"],
};
export const CITE_LABEL = (n, id) => `Source ${n}: open ${id}`;                 // M ask.js cite(): aria-label
export const CITE_TITLE = (id) => `Open ${id}`;                                 // M ask.js cite(): title
export const USED = "Used:";                                                    // M ask.js botHtml; A 18-11: the heading is "Used"
const COUNT = (n, one, many) => `${n} ${n === 1 ? one : many}`;
/** T feature 3: "17 work items, 6 milestones and 8 use cases read · as at DD-MM-YYYY". A kind with none is left out; the day only when the server gave one. */
export function READ_LINE(read) {
  if (!read || typeof read !== "object") return "";
  if (Number.isInteger(read.left_out) && read.left_out > 0 && Number.isInteger(read.items) && read.items >= 0) return `${read.items} ${read.items === 1 ? "item" : "items"} read, ${read.left_out} left out.`;      // row 1294: a project cut to fit the limit says how many were read and how many were left out (the ruled line)
  const parts = [[read.work_items, "work item", "work items"], [read.milestones, "milestone", "milestones"], [read.use_cases, "use case", "use cases"]]
    .filter(([n]) => Number.isInteger(n) && n > 0).map(([n, one, many]) => COUNT(n, one, many));
  if (!parts.length) return "";
  const said = parts.length > 1 ? parts.slice(0, -1).join(", ") + " and " + parts[parts.length - 1] : parts[0];
  return `${said} read${typeof read.as_at === "string" && read.as_at ? " · as at " + read.as_at : ""}`;
}
// row 1350: the two hints Classic words differently; Cards keeps SLASH_HINT. A Classic hint is SLASH_HINT_CLASSIC[name] when there is one.
export const SLASH_HINT_CLASSIC = {
  summary: "Summarise this week into a draft",
  overdue: "What is overdue?",
};
// Row 1365: the warning for a source folder whose names hold a people or contract word. A WARNING the person accepts or declines; no choice is Declined.
// APPROVED WORDING (row 1365 ticket rule 13:39, approved 13:41; ruling WO-M17452 14:03); this is its one place. {provider} is Claude, or ChatGPT when
// Claude is off and ChatGPT is on (askProvider). For ChatGPT the words "which Anthropic runs" are dropped (the ruling), and no other words are added.
export const PEOPLE_CONTRACT_HOLDS = "This folder holds ";
export const PEOPLE_CONTRACT_AND = " and ";
// Row 1365 AP5 (words approved, row 1365, 26-11 02:39): the number of readable files in a matched folder, after its name: "(1 readable file)", "(0 readable files)", "(12 readable files)".
export const PEOPLE_CONTRACT_COUNT = (n) => ` (${n} readable ${n === 1 ? "file" : "files"})`;
export const PEOPLE_CONTRACT_MAY_GO = (who) => `. Passages from it may go to ${who === "ChatGPT" ? "ChatGPT" : "Claude, which Anthropic runs"}, and they can contain personal information.`;
export const PEOPLE_CONTRACT_QUESTION = (who) => `Send passages from this folder to ${who === "ChatGPT" ? "ChatGPT" : "Claude"}?`;
export const PEOPLE_CONTRACT_ACCEPT = "Accept";
export const PEOPLE_CONTRACT_DECLINE = "Decline";
export const PEOPLE_CONTRACT_DECLINED = "Left out of ask clark.";
export const PEOPLE_CONTRACT_ACCEPTED = (who) => `Passages may go to ${who === "ChatGPT" ? "ChatGPT" : "Claude"}.`;
// Kept from the first version of the notice (no new words): the button that leaves the flagged subfolders out, so the rest of the folder is read.
export const PEOPLE_CONTRACT_LEAVE = "Leave these subfolders out";
