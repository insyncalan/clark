// Checklist (#96), store type "checklist": its view part. Draws the lines in their order with a ticked or empty box and the words
// "Done" or "To do" (never colour alone), from the section's own content and the report's data only (no server call), so the published
// file and the served View read alike. Text nodes only, never dangerouslySetInnerHTML. isEmpty: true leaves the section out of the
// served View and the published file.
import { fromFile } from "../stores/report.js";
import { linesOf, countWords } from "./checklist.js";

export const READY = true;

export const isEmpty = (section, data) => linesOf(section, data, { fromFile: fromFile.value }).length === 0;

export function View({ section, data }) {
  const lines = linesOf(section, data, { fromFile: fromFile.value });
  if (!lines.length) return null;
  return (
    <div class="tpl-check" data-tpl="checklist">
      <p class="tpl-check-count">{countWords(lines)}</p>
      <ul class="tpl-check-list">
        {lines.map((l) => (
          <li key={l.key} class={`tpl-check-row${l.done ? " is-done" : ""}`}>
            <span class="tpl-check-box" aria-hidden="true">{l.done ? "✓" : ""}</span>
            <span class="tpl-check-text">{l.text}</span>
            <span class="tpl-check-state">{l.done ? "Done" : "To do"}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
