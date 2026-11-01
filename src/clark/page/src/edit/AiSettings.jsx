// Settings: AI suggestions (#72). One status line for the Edit parts' Settings, in the server's own words (GET /api/ai/status): on,
// off, not signed in, or busy. There is one switch for Claude on this computer, the one under Asking; this line only says what it
// means for suggestions. Until the server has answered, or when it cannot, the line says so and AI reads as off.
import { useEffect, useState } from "preact/hooks";
import { token } from "../stores/report.js";
import { realAiClient } from "./aiClient.js";

export const AI_CHECKING_LINE = "Checking whether AI suggestions are on…";
export const AI_UNAVAILABLE_LINE = "AI suggestions are off, because clark could not check just now. Reload the page to try again.";
const client = realAiClient({ token });

export function AiSettings() {
  const [shown, setShown] = useState({ state: "loading", line: AI_CHECKING_LINE });
  useEffect(() => {
    let live = true;
    client.refresh().then(() => {
      if (!live) return;
      const line = client.line();
      setShown(line ? { state: client.status(), line } : { state: "unavailable", line: AI_UNAVAILABLE_LINE });
    });
    return () => { live = false; };
  }, []);
  return (
    <section class="frame setting" id="ai-settings">
      <h2>AI</h2>
      <p class="muted">Suggestions for the text you select in the report. Nothing changes until you accept one.</p>
      <p id="ai-state" data-state={shown.state}>{shown.line}</p>
    </section>
  );
}
