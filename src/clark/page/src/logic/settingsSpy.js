// Which Settings card is being read (#440, row 15), by the prototype's rule: the last card whose top has reached `edge` (just under the
// sticky chip row); before any has, the first. `tops` are the cards' tops in page order. Plain logic, no page.
export function currentIndex(tops, edge) {
  let cur = 0;
  tops.forEach((t, i) => { if (t <= edge) cur = i; });
  return cur;
}
