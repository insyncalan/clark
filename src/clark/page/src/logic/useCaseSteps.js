// The next steps of a use case, as the summary and the published Use cases tab say them (the prototype's views.js and usecases.js).
// Plain JS and no page store, so the page and the tests share it.
//   A next step is any open work item linked to the use case: an action, a risk, an issue, a decision still pending.
//   A client sees the item's client wording (client_message) and nothing else: a step with no client wording is left out, never
//   drawn with the item's own title. The person who works on the report sees the wording when there is some and the title when there is not;
//   In Edit the page draws the step's own title and owner as text to change in place (edit/StepEdit.jsx), not this wording.
import { ownerOf } from "../workItems.js";

/** What a step says to the client: the item's client wording, trimmed, or "" when it has none. `rows` are the data's actions, risks and decisions. */
export function wordingOf(r) {
  return String((r && r.client_message) || "").replace(/\s+/g, " ").trim();
}

/** {id: client wording} for every work item of the data that has some. */
export function wordingById(d) {
  const out = {};
  for (const r of [...((d && d.actions) || []), ...((d && d.raid) || []), ...((d && d.decisions) || [])]) {
    const w = wordingOf(r);
    if (w) out[r.id] = w;
  }
  return out;
}

/** The steps to draw from a use case's open work items (list rows): each row with `said`, the words to show. A client's drop the ones with no wording. */
export function stepsFrom(open, wording, { client = false } = {}) {
  const out = [];
  for (const r of open) {
    const w = wording[r.id] || "";
    if (client && !w) continue;
    out.push({ ...r, said: w || r.title });
  }
  return out;
}

/** The letters in an owner's circle: the first letter of up to two words, as the prototype draws them; "?" for no owner (or TBC). */
export function avatarOf(name) {
  return ownerOf(name).initials || "?";
}
