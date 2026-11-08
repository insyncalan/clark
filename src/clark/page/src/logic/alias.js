// item 613: the Alias clark suggests from a full name: the first name, then the initials, comma-separated ("Jane Doe" suggests "Jane,JD").
// Pure: nothing here draws, reads or saves. Settings › Profile › About you fills its Alias box from it (edit/Personal.jsx), shown with a
// space after the comma ("Jane, JD"), and keeps that Alias in clark's settings beside the name and the email.

// The words of a name: split on spaces, commas taken out (an Alias is comma-separated, so a comma inside a word would split it).
const words = (name) => String(name || "").replace(/,/g, " ").trim().split(/\s+/).filter(Boolean);

// The first letter of a word, as a capital ("van" gives "V", "Ó" stays "Ó"); a word with no letter gives nothing.
const initial = (word) => { const m = word.match(/\p{L}/u); return m ? m[0].toLocaleUpperCase() : ""; };

/** The suggested Alias for a full name. Two or more words: the first word, a comma, then the first letter of every word ("Jane Doe"
 *  gives "Jane,JD"). One word: that word alone. An empty name: "" (no suggestion). */
export function suggestAlias(name) {
  const w = words(name);
  if (!w.length) return "";
  if (w.length === 1) return w[0];
  return `${w[0]},${w.map(initial).join("")}`;
}

/** What to offer beside the Alias box: the suggestion, or "" when there is nothing to offer. A suggestion never overwrites an Alias the
 *  person typed: once the box holds anything, nothing is offered. */
export function aliasOffer(name, alias) {
  if (String(alias || "").trim()) return "";
  return suggestAlias(name);
}
