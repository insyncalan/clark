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
export const PILLS_PAGE = { dashboard: "dashboard", work: "work", milestones: "milestones", usecases: "usecases", gantt: "gantt" };
// Words in a question that name a subject. The first one found in the last question wins.
export const PILLS_WORDS = [["milestone", "milestones"], ["use case", "usecases"], ["risk", "risks"], ["issue", "risks"], ["work item", "work"], ["task", "work"]];
export const WORKING = "Working";
// Row 1220: messages typed while an answer is made wait above the box. These words need approval.
const waitingCount = (n) => (n === 1 ? "1 message is" : `${n} messages are`);
export const QUEUE_LABEL = "Messages waiting to be sent";
export const QUEUE_REMOVE = "Remove this message";
export const QUEUE_MORE = (n) => `and ${n} more`;
export const QUEUE_STOPPED = (n) => `Stopped. ${waitingCount(n)} waiting`;
export const QUEUE_FAILED = (n) => `${waitingCount(n)} waiting`;
export const QUEUE_SEND = "Send them";
export const QUEUE_CLEAR = "Clear";
export const QUEUE_FULL = "5 messages are already waiting. Wait for one to be sent, or remove one.";
export const QUEUE_DROP = (n) => `${waitingCount(n)} waiting and would be dropped. Press again to go on.`;
export const QUEUE_SAY_ADDED = (n) => `Message queued. ${n} waiting`;
export const QUEUE_SAY_REMOVED = (n) => `Message removed. ${n} waiting`;
// Row 1292 (S7): under an answer. These words need approval.
export const COPY = "Copy";
export const COPIED = "Copied";
export const COPY_FAILED = "Copy did not work. Select the text and copy it yourself.";
export const ASK_AGAIN = "Ask again";
export const COPY_LABEL = "Copy this answer";
export const ASK_AGAIN_LABEL = "Ask this question again";
export const LOG_LABEL = "The chat so far";
// Row 1292 (S6, no streaming yet): the working line says the one step the page really knows (the question is out to the provider) and how long
// it has been going, counted from the send. A longer step list waits for real progress from the server. These words need approval.
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
