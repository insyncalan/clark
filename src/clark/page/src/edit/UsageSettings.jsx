// Usage in tokens (row 1294, A8): what asking used this month, read only, from this computer's own count (GET /api/ask-usage). Tokens only.
// The words are the approved ones; the month's heading comes from the server, so its dates are the real ones.
import { useEffect, useState } from "preact/hooks";
import { project } from "../stores/report.js";
import { askOn } from "./askState.js";
import { askUsageRead } from "./publishApi.js";

const ASKING_ON = "Asking is on";
const ASKING_OFF = "Asking is off";
const ALL_ROW = "All projects";
const ALL_NOTE = "Tokens used";
const READ_ONLY = "Read only. Nothing here leaves this computer.";
const THIS_MONTH = "Usage this month";
const NO_QUESTIONS = "No questions: asking is off.";
const NOT_READ = "Usage could not be read just now.";

export const questionsWords = (n) => (n === 1 ? `${n} question` : `${n} questions`);
export const tokensWords = (n) => (n === 1 ? `${n} token` : `${n} tokens`);
// every answer counted; none counted; or some not
export const countLine = (q, t, u) => (!u ? `${questionsWords(q)} · ${tokensWords(t)}`
  : u >= q ? `${questionsWords(q)} · tokens not reported` : `${questionsWords(q)} · ${tokensWords(t)}, some not reported`);

function useUsage() {
  const [usage, setUsage] = useState(null);          // null: not read yet; "unavailable"; or the answer
  useEffect(() => {
    let live = true;
    askUsageRead().then((r) => {
      if (!live) return;
      const b = r.body;
      setUsage(r.status === 200 && b && b.ok === true && Array.isArray(b.projects) && b.all ? b : "unavailable");
    });
    return () => { live = false; };
  }, []);
  return usage;
}

export function UsageAll() {
  const usage = useUsage();
  const ok = usage && usage !== "unavailable";
  return (
    <section class="frame setting" id="ask-usage-all">
      <h2>{ok ? usage.title : "Usage"}</h2>
      {usage === "unavailable" ? <p class="muted" id="ask-usage-note">{NOT_READ}</p> : null}
      {ok ? (
        <ul class="ask-usage" id="ask-usage-list">
          {usage.projects.map((p) => (
            <li key={p.code} data-ask-usage-project={p.code}>
              <b>{p.code}</b> <span class="muted">{usage.asking ? ASKING_ON : ASKING_OFF}</span> <span>{countLine(p.questions, p.tokens, p.unreported)}</span>
            </li>
          ))}
          <li id="ask-usage-total"><b>{ALL_ROW}</b> <span class="muted">{ALL_NOTE}</span> <span>{countLine(usage.all.questions, usage.all.tokens, usage.all.unreported)}</span></li>
        </ul>
      ) : null}
      {ok ? <p class="muted" id="ask-usage-readonly">{READ_ONLY}</p> : null}
    </section>
  );
}

export function UsageProject() {
  const usage = useUsage();
  const code = project.value;
  const on = askOn.value;
  const ok = usage && usage !== "unavailable";
  const mine = ok ? usage.projects.find((p) => p.code === code) : null;
  const q = mine ? mine.questions : 0;
  return (
    <section class="frame setting" id="ask-usage-project">
      <h2>{THIS_MONTH}</h2>
      {usage === "unavailable" ? <p class="muted" id="ask-usage-note">{NOT_READ}</p> : null}
      {ok ? <p id="ask-usage-count">{q > 0 ? questionsWords(q) : on ? questionsWords(0) : NO_QUESTIONS}</p> : null}
    </section>
  );
}
