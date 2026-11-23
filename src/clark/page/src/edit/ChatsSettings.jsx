// Chats kept (row 1294, A8): how many earlier chats ask clark keeps for each project, and clearing the open project's chats. The chats are kept in
// this browser (askHistory.js, a per-project store), so the number is kept there too: the server holds no chats, so it has nothing to hold the number for.
import { project } from "../stores/report.js";
import { KEEP_OPTIONS, keepChoice, setKeep, chats, clearChats, histTick } from "./askHistory.js";

const KEPT_HEAD = "Chats";
const KEPT_LABEL = "Chats kept";
const KEPT_LINE = "The most recent chats kept for each project, with your data. Clearing them is done in a project's tab.";
const OLDER_GO = "Older chats go the next time a chat is saved.";      // true: askHistory.js keepChat drops the oldest at the next save (pinned in Drop)
const EARLIER = "Earlier chats";

export function ChatsAll() {
  return (
    <section class="frame setting" id="ask-chats-all">
      <h2>{KEPT_HEAD}</h2>
      <div class="row">
        <label for="ask-chats-keep"><b>{KEPT_LABEL}</b></label>
        <select id="ask-chats-keep" data-ask-keep value={String(keepChoice.value)} onChange={(e) => { setKeep(Number(e.currentTarget.value)); }}>
          {KEEP_OPTIONS.map((n) => <option key={n} value={String(n)}>{n}</option>)}
        </select>
      </div>
      <p class="muted" id="ask-chats-line">{KEPT_LINE}</p>
      <p class="muted" id="ask-chats-older">{OLDER_GO}</p>
    </section>
  );
}

export function ChatsProject() {
  const code = project.value;
  void histTick.value;                                // read again when the chats change
  const n = chats().length;
  return (
    <section class="frame setting" id="ask-chats-project">
      <h2>{`Chats in ${code}`}</h2>
      <p><b>{EARLIER}</b></p>
      <p class="muted" id="ask-chats-note">{`Kept with your data for ${code}.`}</p>
      <div class="row"><button type="button" class="btn" id="ask-chats-clear" data-ask-clear-chats disabled={n === 0} onClick={() => clearChats()}>{`Clear all chats (${n})`}</button></div>
    </section>
  );
}
