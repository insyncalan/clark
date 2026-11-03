// The Publish dialog's line under its title (#437 row 26, the prototype's io.js): the project, the week, the number this publication will
// have and when the last one went, and where. Nothing here names a folder or a file. `next` is a whole number from 1, or 0 until the server
// has said; `last` is {at: YYYY-MM-DD, to_client} or null. Other places that say when the last one went keep their own words (lastLine).
export function dialogLine(name, weekEnding, next, last, shown) {
  const bits = [name];
  if (weekEnding) bits.push(`week ending ${shown(weekEnding)}`);
  if (Number.isInteger(next) && next >= 1) bits.push(`this will be Publication ${next}`);
  if (last && last.at) bits.push(`last published ${shown(last.at)}${last.to_client ? ", to the client" : ", locally"}`);
  return bits.join(" · ");
}
