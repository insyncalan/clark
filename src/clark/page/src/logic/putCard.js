// A RAID card put at slot i of the body's cards: a new card goes in its slot, or on the end when the body has shrunk below the slot
// (writing past the end would leave a hole); no card takes the slot out.
export function putCard(cards, i, card) {
  const next = cards.slice();
  if (!card) next.splice(i, 1);
  else if (i >= next.length) next.push(card);
  else next[i] = card;
  return next;
}
