// Row 1046 (approved mock-up 1046-alerts): a Critical notice (upgrade required) also shows a banner under the top bar, until the person has read it
// (Mark as read here or in the bell; the action does the same). It speaks once, as an alert. The first unread critical notice is the one shown.
import { shown, readIds, readOne } from "./noticesState.js";
import { go } from "./Bell.jsx";
import { WORDS } from "../logic/notices.js";

export function CriticalBanner() {
  const n = shown.value.find((x) => x.severity === "critical" && !readIds.value.includes(x.id));
  if (!n) return null;
  return (
    <div class="crit-banner" id="crit-banner" role="alert" data-id={n.id}>
      <span class="crit-text"><b>{n.title}.</b>{n.body ? " " + n.body : ""}</span>
      {n.action ? <button type="button" class="crit-btn" id="crit-act" onClick={() => { go(n.action.to); readOne(n.id); }}>{n.action.label}</button> : null}
      <button type="button" class="crit-btn" id="crit-read" onClick={() => readOne(n.id)}>{WORDS.markRead}</button>
    </div>
  );
}
