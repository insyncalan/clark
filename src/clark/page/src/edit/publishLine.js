// The Publish dialog's own words (#437, the prototype's io.js): the line under the title, and the finished button. Nothing here names a
// folder or a file. `next` is the number this publication will have; `last` is {at: YYYY-MM-DD, to_client} or null.
import { plainDate } from "../logic/picker.js";

export const doneWords = (n) => (Number.isInteger(n) && n >= 1 ? `Published (Publication ${n})` : "Published");

export function dialogLine(name, weekEnding, next, last) {
  const bits = [name];
  if (weekEnding) bits.push(`week ending ${plainDate(weekEnding)}`);
  if (Number.isInteger(next) && next >= 1) bits.push(`this will be Publication ${next}`);
  if (last && last.at) bits.push(`last published ${plainDate(last.at)}${last.to_client ? ", to the client" : ", locally"}`);
  return bits.join(" · ");
}
