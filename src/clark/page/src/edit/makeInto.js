// Make into: one new work item from a passage, in one step with Undo, through the change the report already makes (stores/changes.js).
// No AI call. Resolves to the reply, or null when it failed (the toast says why).
import { change } from "../stores/changes.js";
import { makeIntoRequest, makeIntoDone } from "../logic/makeInto.js";

export function makeInto(id, text) {
  const req = makeIntoRequest(id, text);
  return req ? change(req, makeIntoDone(id)) : Promise.resolve(null);
}
