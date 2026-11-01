// Settings: "Not reviewed after (days)" (#160). One whole number for the project, 14 until changed. The box is checked on the page
// with the same words the server uses; a refused number leaves the old one in force. The server saves it as a project update, so
// History records who, how and when, and Undo can put the old number back. Edit parts only.
import { useState } from "preact/hooks";
import { data, project } from "../stores/report.js";
import { reviewDays } from "../stores/review.js";
import { parseReviewDays } from "../reviewSetting.js";
import { reviewDaysRequest, words } from "./publishApi.js";

export function ReviewDays() {
  const now = reviewDays.value;
  const [text, setText] = useState(null);                 // null: show the saved number
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);                  // {kind: "error" | "note", text}
  const shown = text === null ? String(now) : text;

  async function save(e) {
    e.preventDefault();
    const r = parseReviewDays(shown);
    if (!r.ok) { setMsg({ kind: "error", text: r.message }); return; }
    if (r.days === now) { setText(null); setMsg({ kind: "note", text: "That is the number already in use." }); return; }
    setBusy(true);
    setMsg(null);
    const a = await reviewDaysRequest(project.value, r.days);
    setBusy(false);
    const b = a.body;
    if (a.status === 200 && b && b.ok === true) {
      const d = data.value;
      data.value = { ...d, project: { ...d.project, review_days: r.days } };
      setText(null);
      setMsg({ kind: "note", text: `Saved. Items not reviewed in more than ${r.days} ${r.days === 1 ? "day" : "days"} are flagged.` });
      return;
    }
    setMsg({ kind: "error", text: words(a, "save the review period") });
  }

  return (
    <section class="frame setting" id="review-days">
      <h2>Not reviewed after (days)</h2>
      <p class="muted">An open item is flagged when nobody has changed it for more than this many days. It sets the Freshness filter in Work items and the optional Not reviewed tile on the Dashboard.</p>
      <form class="row" onSubmit={save}>
        <label for="review-days-box" class="muted">Days</label>
        <input id="review-days-box" class="days-box" type="text" inputmode="numeric" autocomplete="off" value={shown}
          aria-describedby="review-days-msg" aria-invalid={msg && msg.kind === "error" ? "true" : "false"}
          onInput={(e) => { setText(e.currentTarget.value); setMsg(null); }} disabled={busy} />
        <button type="submit" class="btn" data-save-days disabled={busy}>Save</button>
      </form>
      <div class="pub-msg" id="review-days-msg" role={msg && msg.kind === "error" ? "alert" : "status"} aria-live="polite">{msg && msg.text ? <p class={msg.kind}>{msg.text}</p> : null}</div>
    </section>
  );
}
