// What the toast says after a save in Settings › Personal › About you (#429), and what its Undo says. Plain sentences ending in a full stop, like
// every other toast (itemEdit.js: "Owner of A-1 is back to X."). The prototype's "Name saved" / "Email saved" (system/prototype/views.js:1465) with the
// full stop. The toast never repeats the value (the box shows it); the old value appears only in the Undo line.
export const FIELDS = [["name", "Name"], ["email", "Email"]];

/** The boxes whose saved value is not what it was: [{field, label, cleared}] in box order, `cleared` when the new value is blank. A value that
 *  differs only by spaces at its ends is not a change (clark keeps the trimmed text). Nothing changed: an empty list, and so no toast. */
export function changedFields(before, after) {
  const same = (a, b) => String(a || "").trim() === String(b || "").trim();
  return FIELDS.filter(([f]) => !same(before[f], after[f])).map(([field, label]) => ({ field, label, cleared: !String(after[field] || "").trim() }));
}

const joined = (list) => list.map((c, i) => (i ? c.label.toLowerCase() : c.label)).join(" and ");

/** "Name saved." / "Email cleared." / "Name and email saved." and, when one was cleared and the other saved, one sentence for each in box order. */
export function savedWords(changes) {
  if (!changes.length) return "";
  if (changes.every((c) => c.cleared === changes[0].cleared)) return `${joined(changes)} ${changes[0].cleared ? "cleared" : "saved"}.`;
  return changes.map((c) => `${c.label} ${c.cleared ? "cleared" : "saved"}.`).join(" ");
}

/** What the toast says after Undo: "Name is back to Sam Lee." / "Email is blank again." / "Name and email are back as they were." */
export function backWords(changes, before) {
  if (changes.length !== 1) return "Name and email are back as they were.";
  const { field, label } = changes[0];
  const was = String(before[field] || "").trim();
  return was ? `${label} is back to ${was}.` : `${label} is blank again.`;
}
