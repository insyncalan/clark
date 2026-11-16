/* row 1234-A: the next steps text; the digit is a pill badge when something is open. The text content stays the one string stepsWord(n). */
import { stepsParts } from "../logic/useCasesList.js";

export function StepsBadge({ n }) {
  const [d, rest] = stepsParts(n);
  return d ? <><b class="ucn-b">{d}</b>{rest}</> : rest;
}
