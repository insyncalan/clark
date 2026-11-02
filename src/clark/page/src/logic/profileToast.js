// What the toast says after a profile save (#440, row 5), by the prototype's words (system/prototype/views.js): "Name saved" or "Email saved".
// `before` is what clark held, `after` what it kept. Nothing changed says nothing (null); both changed say both.
export function savedWords(before, after) {
  const n = before.name !== after.name, e = before.email !== after.email;
  if (n && e) return "Name and email saved";
  if (n) return "Name saved";
  if (e) return "Email saved";
  return null;
}
