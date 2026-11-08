// What must happen before this page goes (#944): a different project is a page load, and Back or a closed tab ends the page. Kept apart
// from report.js, whose open path holds no timer (test_peek OpenTime); nothing here is on that path.
export const busy = [];                  // functions that give a promise for what is still being saved (changes.js: its queue)
export const beforeReload = [];          // functions run just before the page is loaded again (changes.js: keep the message, once)
export const leaving = { on: false };    // true while the page is going away: api.js then sends a save so that it outlives the page

// Wait (at most `limit` ms) for what the field just left has started, and for every save in the queue, including ones queued meanwhile.
export async function saved(limit = 8000) {
  const end = performance.now() + limit, left = () => Math.max(0, end - performance.now());
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  await wait(0);                                           // what the field's blur starts is started by now
  for (let i = 0; i < 20; i++) {
    const mine = busy.map((f) => f());
    await Promise.race([Promise.all(mine), wait(left())]);
    await wait(0);
    if (!left() || busy.map((f) => f()).every((p, k) => p === mine[k])) return;      // nothing new was queued meanwhile
  }
}
